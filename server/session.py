"""Orchestration des sessions (spec/05-session-server).

Sans FastAPI : ce module ne manipule que des dicts JSON et des octets
(duck-typing du WebSocket), pour que la logique soit testable sans réseau.
Le câblage WebSocket et HTTP vit dans `server/app.py`.
"""

from __future__ import annotations

import os
import secrets
import time
from collections import deque
from dataclasses import dataclass

from .protocol import parse_client_message

MAX_SESSIONS = 2  # SRV-D6 : 2 sessions en direct (crédit total de 150 $)
MAX_MINUTES = 10
MAX_COST_USD = 1.50
FPS = 1
REFUSAL_WINDOW_S = 60.0  # SRV-R2.4 : plus de 5 refus en 1 min…
MAX_REFUSALS = 5
BAN_S = 300.0  # …connexions refusées pendant 5 min


@dataclass
class Limits:
    max_sessions: int = MAX_SESSIONS
    max_minutes: int = MAX_MINUTES
    max_cost_usd: float = MAX_COST_USD
    fps: int = FPS
    daily_budget_usd: float = 10.0


def limits_from_env() -> Limits:
    """Limites, budget jour surchargeable (`FIXLOOP_DAILY_BUDGET`, SRV-R8.3)."""
    try:
        daily = float(os.environ.get("FIXLOOP_DAILY_BUDGET", 10.0))
    except ValueError:
        daily = 10.0
    return Limits(daily_budget_usd=daily)


class SessionRegistry:
    """Ouverture et contrôle d'accès (SRV-R2). Pur et synchrone."""

    def __init__(self, limits: Limits | None = None, access_code: str | None = None,
                 procedures: dict | None = None, day_total: object = None):
        self.limits = limits or Limits()
        self.access_code = access_code
        self.procedures = procedures if procedures is not None else {}
        self.day_total = day_total  # coût estimé du jour, câblé par le serveur (SRV-R8.3)
        self.sessions: dict[str, dict] = {}  # session_id -> bike_id, ip
        self._refusals: dict[str, list[float]] = {}  # ip -> instants des refus
        self._banned_until: dict[str, float] = {}  # ip -> fin du blocage

    @property
    def live_count(self) -> int:
        return len(self.sessions)

    def release(self, session_id: str | None) -> None:
        self.sessions.pop(session_id, None)

    def _refuse(self, ip: str, now: float) -> None:
        recent = [t for t in self._refusals.get(ip, []) if now - t < REFUSAL_WINDOW_S]
        recent.append(now)
        self._refusals[ip] = recent
        if len(recent) > MAX_REFUSALS:
            self._banned_until[ip] = now + BAN_S

    def hello(self, msg: object, ip: str, now: float | None = None
              ) -> tuple[str, dict]:
        """Traite un message d'ouverture ; rend (type, corps) à envoyer.

        `hello_ack` (SRV-R2.1) ou `error` puis fermeture (`access_denied`
        SRV-R2.2, `busy` SRV-R2.3, `bad_message`). Le bannissement (SRV-R2.4)
        rend `access_denied` sans prolonger le blocage.
        """
        now = time.monotonic() if now is None else now
        if now < self._banned_until.get(ip, 0.0):
            return "error", {"code": "access_denied",
                             "message": "Trop de tentatives. Réessaie dans 5 minutes."}
        parsed = parse_client_message(msg)
        if parsed is None or parsed.get("type") != "hello":
            self._refuse(ip, now)
            return "error", {"code": "bad_message", "message": "Message illisible, ignoré."}
        if self.access_code is not None and parsed.get("access_code") != self.access_code:
            self._refuse(ip, now)
            return "error", {"code": "access_denied", "message": "Code d'accès refusé."}
        if self.day_total is not None and self.day_total() > self.limits.daily_budget_usd:
            return "error", {"code": "budget",  # SRV-R8.3 : sans compter un refus
                             "message": "Le budget du jour est dépassé. Réessaie demain."}
        if self.live_count >= self.limits.max_sessions:
            self._refuse(ip, now)
            return "error", {"code": "busy",
                             "message": "Deux sessions sont en cours. Réessaie dans un moment."}
        session_id = secrets.token_hex(8)
        self.sessions[session_id] = {"bike_id": parsed["bike_id"], "ip": ip}
        return "hello_ack", {"session_id": session_id,
                             "limits": {"max_minutes": self.limits.max_minutes,
                                        "max_cost_usd": self.limits.max_cost_usd,
                                        "fps": self.limits.fps},
                             "procedures": sorted(self.procedures)}


# ------------------------------------------------------------------ boucle (SRV-T5)

STALE_S = 5.0  # SRV-R4.3 : un résultat SAM plus vieux que 5 s est écarté


def session_time(t_ms: int, t0_ms: int) -> float:
    """Horodatage client -> secondes depuis `start` (SRV-R4.5)."""
    return (t_ms - t0_ms) / 1000.0


def check_result(age_s: float, frame_index: int, last_applied: int) -> str:
    """Filtre d'un résultat SAM : `ok`, `stale` ou `out_of_order` (SRV-R4.3)."""
    if age_s > STALE_S:
        return "stale"
    if frame_index < last_applied:
        return "out_of_order"
    return "ok"


class WorkQueue:
    """File de la machine à états : une seule mesure en attente (SRV-R5.3).

    `done` et `command` ne sont jamais écartés et gardent l'ordre d'arrivée
    avec les mesures (SRV-R5.4).
    """

    def __init__(self) -> None:
        self.q: deque = deque()
        self.dropped_measures = 0

    def __len__(self) -> int:
        return len(self.q)

    def put_measure(self, m: object, keyframe: object) -> None:
        kept = [it for it in self.q if it[0] != "measure"]
        self.dropped_measures += len(self.q) - len(kept)
        self.q = deque(kept)
        self.q.append(("measure", m, keyframe))

    def put_control(self, kind: str, payload: object = None) -> None:
        self.q.append((kind, payload))

    def take(self) -> tuple | None:
        return self.q.popleft() if self.q else None


def step_thresholds(step: dict) -> tuple[float | None, float | None]:
    """Seuils (en place, tombée) lus dans les règles de l'étape (SRV-R6.2)."""
    on_max, off_min = None, None
    for rule in step.get("success", []) + step.get("anomaly", []):
        thr = rule.get("threshold")
        if not isinstance(thr, (int, float)):
            continue
        if rule.get("type") == "contact_ratio_max":
            on_max = thr if on_max is None else min(on_max, thr)
        elif rule.get("type") == "contact_ratio_min":
            off_min = thr if off_min is None else min(off_min, thr)
    return on_max, off_min


def label_for(contact: float | None, on_max: float | None,
              off_min: float | None) -> str:
    """Étiquette d'overlay d'après les seuils de l'étape (SRV-R6.2)."""
    if contact is None or contact != contact:
        return "non vu"
    if on_max is not None and contact <= on_max:
        return "en place"
    if off_min is not None and contact >= off_min:
        return "tombée"
    return "incertain"


class QueueOutput:
    """Sortie `Output` (01-core-loop) vers la file d'envoi (design 05, section 2).

    `loop` None = même fil, dépôt direct (tests) ; sinon `call_soon_threadsafe`
    depuis le fil de la machine à états (SRV-R5.2).
    """

    def __init__(self, loop: object, queue: object) -> None:
        self.loop, self.queue = loop, queue

    def _put(self, msg: dict) -> None:
        if self.loop is None:
            self.queue.put_nowait(msg)
        else:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, msg)

    def say(self, text: str) -> None:
        self._put({"type": "say", "text": text})

    def highlight(self, parts: list, color: str) -> None:
        self._put({"type": "highlight", "parts": list(parts), "color": color})

    def state(self, snapshot: dict) -> None:
        self._put({"type": "state", **snapshot})


def keyframe_image(img: object, box: tuple | None) -> object:
    """Gros plan autour du plateau pour Spark, image entière à défaut (AGT-R3.2)."""
    if box is None:
        return img
    from fixloop.agent import crop_around
    return crop_around(img, box, margin=0.6)


def overlay_for(frame_index: int, t_ms: int, w: int, h: int, parts: dict,
                contact: float | None, label: str, verdict: str, latency_ms: float,
                red_parts: object = frozenset()) -> dict:
    """Message `overlay` : contours SVG, couleur, dimensions (SRV-R6.2)."""
    return {"type": "overlay", "frame_index": frame_index, "t_ms": t_ms,
            "w": w, "h": h,
            "parts": {p: {"path": pr.svg_path or "",
                          "color": "red" if p in red_parts else "blue"}
                      for p, pr in parts.items()},
            "contact": contact, "label": label, "verdict": verdict,
            "latency_ms": latency_ms}


MAX_FPS = 10  # SRV-R3.2 : 10 img/s max, au-delà les images sont écartées
SLOW_S = 15.0  # SRV-R7.5 : dire le retard après 15 s sans résultat SAM
ABANDON_S = 60.0  # SRV-R7.6 : abandon après 60 s sans résultat
CLOSE_DELAY_S = 2.0  # SRV-R6.3 : `closed` puis fermeture après 2 s


class FpsGuard:
    """Fenêtre glissante : au plus `max_per_s` images par seconde (SRV-R3.2)."""

    def __init__(self, max_per_s: int = MAX_FPS) -> None:
        self.max_per_s: int = max_per_s
        self.times: list = []

    def allow(self, now: float) -> bool:
        self.times = [t for t in self.times if now - t < 1.0]
        if len(self.times) >= self.max_per_s:
            return False
        self.times.append(now)
        return True


def map_result_error(error: str | None) -> tuple[str, str] | None:
    """Erreur SAM fatale -> (code, message) puis fermeture (SRV-R7.1, R7.2).

    Rend None pour les erreurs douces : la session continue d'observer.
    """
    if error == "Clé API refusée":
        return ("api_key", "Ta clé API est refusée. Vérifie-la puis reconnecte-toi.")
    if error in ("Crédit épuisé", "Trop de requêtes"):
        return ("budget", "Le crédit est épuisé pour aujourd'hui.")
    return None


SLOW_PHRASE = "La connexion est lente, je continue d'essayer."  # SRV-R7.3, au plus 1/min
STOP_PHRASE = "Je dois m'arrêter : plus de crédit pour aujourd'hui."  # SRV-R7.2, dit avec budget


def watchdog_state(age_s: float, can_warn: bool) -> str:
    """État du chien de garde SAM : `ok`, `warn` ou `abandon` (SRV-R7.3 + tâche)."""
    if age_s > ABANDON_S:
        return "abandon"  # 60 s sans résultat : abandon (design 05, section 6)
    if age_s > SLOW_S and can_warn:
        return "warn"
    return "ok"


def summary_for(counters: dict) -> dict:
    """Résumé joint à `closed` (SRV-R6.3) : images écartées et résultats rejetés."""
    return {"dropped": counters.get("dropped", 0), "stale": counters.get("stale", 0),
            "out_of_order": counters.get("out_of_order", 0)}


def check_session_limits(cost_usd: float, elapsed_s: float, limits: Limits) -> str:
    """`ok`, `cost` ou `duration` : arrêt au-delà de 1,50 $ ou 10 min (SRV-R8.2)."""
    if cost_usd > limits.max_cost_usd:
        return "cost"
    if elapsed_s >= limits.max_minutes * 60:
        return "duration"
    return "ok"


SENSITIVE_KEYS = {"image", "jpeg", "audio", "key", "api_key"}  # SRV-R9.2 : jamais au journal


def _clean(value: object) -> object:
    """Retire octets et champs sensibles avant écriture du journal (SRV-R9.2)."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()
                if k not in SENSITIVE_KEYS and not isinstance(v, (bytes, bytearray))}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value if not isinstance(v, (bytes, bytearray))]
    return value


class SessionRecorder:
    """Journal `data/sessions/<id>.jsonl` et enregistrements replay (SRV-R9)."""

    def __init__(self, root: object = "data/sessions",
                 recordings_root: object = "data/recordings",
                 record: bool = False) -> None:
        from pathlib import Path
        self.root, self.recordings_root = Path(root), Path(recordings_root)
        self.record = record

    def finish(self, session_id: str, report: dict) -> object:
        """Écrit le journal : méta, compteurs, latences, coûts, puis événements."""
        import json
        from pathlib import Path
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{session_id}.jsonl"
        head = {"type": "session", "session_id": session_id,
                "bike_id": report.get("bike_id"), "success": report.get("success"),
                "ended": report.get("ended", "closed"),
                "counters": report.get("counters", {}),
                "latencies": report.get("latencies", []),
                "costs": report.get("costs", {})}
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(_clean(head), ensure_ascii=False) + "\n")
            for event in report.get("events", []):
                fh.write(json.dumps(_clean({"type": "event", **event}),
                                     ensure_ascii=False) + "\n")
        return path

    def _recording_dir(self, session_id: str) -> object | None:
        if not self.record:
            return None
        from pathlib import Path
        out = Path(self.recordings_root) / session_id
        out.mkdir(parents=True, exist_ok=True)
        return out

    def record_image(self, session_id: str, frame_index: int, jpeg: bytes) -> object | None:
        """Image reçue, pour le replay (`FIXLOOP_RECORD=1`, SRV-R9.3)."""
        out = self._recording_dir(session_id)
        if out is None:
            return None
        path = out / f"frame-{frame_index:05d}.jpg"
        path.write_bytes(jpeg)
        return path

    def record_raw(self, session_id: str, frame_index: int, raw: str) -> object | None:
        """Sortie SAM brute, pour le replay (`FIXLOOP_RECORD=1`, SRV-R9.3)."""
        out = self._recording_dir(session_id)
        if out is None:
            return None
        path = out / f"raw-{frame_index:05d}.txt"
        path.write_text(raw, encoding="utf-8")
        return path


class Models:
    """Modèles d'une session : perception, Spark, mémoire, coûts (design 05, section 2)."""

    def __init__(self, perception_factory: object, agent: object, memory: object,
                 costs: object) -> None:
        self.perception_factory = perception_factory  # procedure -> perception
        self.agent = agent
        self.memory = memory
        self.costs = costs


class SimPerception:
    """Perception factice : scène synthétique ou `raw_*.txt`, sans réseau (SRV-T10)."""

    def __init__(self, script: tuple = ("off", "on"), raw: dict | None = None,
                 h: int = 300, w: int = 400, costs: object = None) -> None:
        self.script = list(script)
        self.raw = raw  # {partie: texte brut recollé} rejoué image par image
        self.h, self.w, self.costs = h, w, costs
        self.i = 0

    @classmethod
    def from_raw(cls, raw_dir: object, h: int, w: int,
                 costs: object = None) -> "SimPerception":
        """Rejoue `raw_chain.txt` + `raw_chainring.txt` (replay, sans réseau)."""
        from pathlib import Path
        raw = {}
        for part in ("chain", "chainring"):
            raw[part] = (Path(raw_dir) / f"raw_{part}.txt").read_text(encoding="utf-8")
        return cls(raw=raw, h=h, w=w, costs=costs)

    def done_sync(self, fi: int, t: float) -> object:
        """Résultat pour l'image `fi` : synchrone, testable sans boucle."""
        import numpy as np

        from fixloop.perception import ImageResult, PartResult, mask_to_svg_path, masks_from_records, parse_raw
        from fixloop.sim import frame as sim_frame
        if self.raw is not None:
            parts = {}
            for part, largest in (("chain", False), ("chainring", True)):
                lines = self.raw[part].splitlines(keepends=True)
                one = "".join(line for line in lines if line.startswith(f"<{fi}f>"))
                found = masks_from_records(parse_raw(one).records, self.h, self.w,
                                           0.4, largest)
                pr = found.get(fi)
                if pr is not None and pr.mask is not None:
                    parts[part] = PartResult(pr.mask, pr.confidence, pr.box,
                                             mask_to_svg_path(pr.mask), pr.n_objects)
        else:
            fm = sim_frame(self.script[min(self.i, len(self.script) - 1)], fi, t)
            parts = {}
            for p, mask in fm.masks.items():
                ys, xs = np.nonzero(mask)
                parts[p] = PartResult(mask, 0.9, (int(xs.min()), int(ys.min()),
                                                 int(xs.max()) + 1, int(ys.max()) + 1),
                                      mask_to_svg_path(mask), 1)
        return ImageResult(fi, t, parts, {"total_s": 0.0, "attempts": {}}, None,
                           self.w, self.h)

    def try_submit(self, jpeg: bytes, fi: int, t: float):  # tâche asyncio ou None
        import asyncio
        self.i += 1
        return asyncio.get_running_loop().create_task(self._done(fi, t))

    async def _done(self, fi: int, t: float):
        return self.done_sync(fi, t)


def build_models(procedures: dict, costs: object, fake: bool = False) -> Models:
    """Assemble les modèles ; `fake` rejoue sans aucun réseau (SRV-T10)."""
    if fake:
        from tests.fakes import FakeAgent, FakeMemory
        return Models(lambda proc: SimPerception(costs=costs),
                      FakeAgent(), FakeMemory(), costs)
    from fixloop.agent import SparkAgent
    from fixloop.memory import WonderMemory
    from fixloop.perception import LivePerception
    return Models(lambda proc: LivePerception(proc, costs=costs),
                  SparkAgent(procedures, costs=costs), WonderMemory(), costs)


class _RecordingOutput(QueueOutput):
    """Retient les pièces surlignées en rouge pour l'overlay (SRV-R6.2)."""

    def __init__(self, loop: object, queue: object, red_parts: set) -> None:
        super().__init__(loop, queue)
        self.red_parts = red_parts

    def highlight(self, parts: list, color: str) -> None:
        if color == "red":
            self.red_parts.update(parts)
        else:
            self.red_parts.difference_update(parts)
        super().highlight(parts, color)


class LiveSession:
    """Une connexion WebSocket : réception, perception, machine à états, envoi.

    La machine à états tourne dans un fil, un appel à la fois (SRV-R5.2) ;
    `Session` (01-core-loop) avec `debounce_frames = 3` en direct (CORE-R9.2).
    """

    def __init__(self, ws: object, registry: SessionRegistry, ip: str,
                 procedures: dict, models: Models, limits: Limits,
                 clock: object = None, recorder: SessionRecorder | None = None) -> None:
        self.ws = ws
        self.registry, self.ip = registry, ip
        self.session_id: str | None = None
        self.bike_id: str | None = None
        self.procedures, self.models, self.limits = procedures, models, limits
        self.recorder = recorder  # journal + enregistrements (SRV-R9, None = sans journal)
        self.latencies: list = []  # latences SAM acceptées, en ms (SRV-R9.1)
        self.journal_written = False
        self.clock = clock if clock is not None else time.monotonic  # horloge par défaut ; un test peut la remplacer
        self.work = WorkQueue()
        self.counters = {"dropped": 0, "stale": 0, "out_of_order": 0, "bad_message": 0,
                         "too_big": 0}
        self.red_parts: set = set()
        self.sm: object = None
        self.perception: object = None
        self.frame_index = 0
        self.last_applied = -1
        self.t0_ms: int | None = None
        self.startup: list = []  # (jpeg, t_ms) pour le diagnostic (SRV-R4.1)
        self.pending_frames: dict = {}  # frame_index -> (t_ms, jpeg, reçu_monotonic)
        self.paused = False
        self.started = False  # message `start` reçu : les images comptent
        self.closing = False
        self.closed_sent = False
        self.fps_guard = FpsGuard()
        self.fatal: tuple[str, str] | None = None  # erreur SAM fatale à remonter
        self.last_slow_said: float | None = None  # SRV-R7.3 : au plus une fois par minute
        self.last_result_at: float | None = None
        self.started_at: float | None = None  # SRV-R8.2 : durée max 10 min
        self.consec_errors = 0  # 3 exceptions de suite -> arrêt (design 05, section 6)

    def note_worker_ok(self) -> None:
        self.consec_errors = 0

    def note_worker_error(self) -> bool:
        """Rend True à la 3e exception de suite : il faut arrêter (SRV-T7)."""
        self.consec_errors += 1
        return self.consec_errors >= 3
        self._work_event: object = None
        self._out_queue: object = None
        self.output: object = None

    # ---------------------------------------------------------- boucles asyncio
    async def run(self) -> None:
        import asyncio
        import json
        loop = asyncio.get_running_loop()
        if self.clock is None:
            self.clock = loop.time
        self._work_event = asyncio.Event()
        self._out_queue = asyncio.Queue()
        self.output = _RecordingOutput(loop, self._out_queue, self.red_parts)
        first = await self.ws.receive()  # SRV-R2.1 : ouverture par hello
        if "text" not in first:
            return
        kind, body = self.registry.hello(first["text"], self.ip, self.clock())
        if kind != "hello_ack":
            await self.ws.send_text(json.dumps({"type": "error", **body}))
            await self.ws.close()
            return
        self.session_id, self.bike_id = body["session_id"], self._bike_of(body)
        self.started_at = self.clock()
        await self.ws.send_text(json.dumps({"type": "hello_ack", **body}))
        receiver = asyncio.create_task(self._receive())
        sender = asyncio.create_task(self._send())
        worker = asyncio.create_task(self._sm_worker())
        watchdog = asyncio.create_task(self._watchdog())
        try:
            await receiver
        except Exception:
            pass  # déconnexion client : on nettoie (SRV-R7.4)
        finally:
            self._write_journal(False, ended="disconnect")  # SRV-R9.1, une seule fois
            for task in (sender, worker, watchdog):
                task.cancel()
            self.registry.release(self.session_id)

    def _bike_of(self, body: dict) -> str:
        return self.registry.sessions[body["session_id"]]["bike_id"]

    async def _send(self) -> None:
        import asyncio
        import json
        while True:
            msg = await self._out_queue.get()
            await self.ws.send_text(json.dumps(msg))

    async def _watchdog(self) -> None:
        """15 s sans résultat SAM : le dire (1/min) ; 60 s : abandonner (SRV-R7.3).

        Arrête aussi la session au-delà de 1,50 $ ou 10 min (SRV-R8.2).
        """
        import asyncio
        while True:
            await asyncio.sleep(1.0)
            if not self.started or self.paused or self.closed_sent or self.last_result_at is None:
                continue
            now = self.clock()
            can_warn = self.last_slow_said is None or now - self.last_slow_said >= 60.0
            state = watchdog_state(now - self.last_result_at, can_warn)
            if state == "warn":
                self.last_slow_said = now
                self.output.say(SLOW_PHRASE)
            elif state == "abandon":
                await self._abort("internal", "Aucun résultat, la session est abandonnée.")
                return
            outcome = check_session_limits(self._session_cost(), now - (self.started_at or now),
                                           self.limits)
            if outcome == "cost":
                self.output.say(STOP_PHRASE)
                await self._finish(False)
                return
            if outcome == "duration":
                await self._finish(False)
                return

    def _session_cost(self) -> float:
        """Coût estimé de la session, 0 sans journal (SRV-R8.1)."""
        try:
            if self.models.costs is None or self.session_id is None:
                return 0.0
            return float(self.models.costs.session_total(self.session_id))
        except Exception:
            return 0.0

    async def _receive(self) -> None:
        from .protocol import parse_binary, parse_client_message
        while not self.closing:
            message = await self.ws.receive()
            if "text" in message:
                self._on_text(parse_client_message(message["text"]))
            elif "bytes" in message:
                self._on_binary(parse_binary(message["bytes"]))
            else:
                return  # déconnexion (SRV-R7.4 : finally de run() nettoie)

    # ---------------------------------------------------------- entrées client
    def _send_now(self, msg: dict) -> None:
        self._out_queue.put_nowait(msg)  # fil de la boucle : dépôt direct

    def _on_text(self, parsed: dict | None) -> None:
        if parsed is None:
            self.counters["bad_message"] += 1  # SRV-R3.1 : ignoré, journalisé
            return
        kind = parsed["type"]
        if kind == "start":
            self.started = True
            self.startup = []
        elif kind == "user_done":
            self.work.put_control("done")
            self._work_event.set()
        elif kind == "command":
            self.work.put_control("command", parsed["cmd"])
            self._work_event.set()
        elif kind == "pause":
            self.paused = True
        elif kind == "resume":
            self.paused = False
        elif kind == "stop":
            self.work.put_control("stop")
            self._work_event.set()

    def _on_binary(self, decoded: dict | None) -> None:
        if decoded is None:
            return
        if decoded.get("too_big"):
            self.counters["too_big"] += 1  # SRV-R3.3 : image ignorée
            return
        if decoded["kind"] != "image":
            return  # audio : voix (SRV-T6, hors périmètre de SRV-T5)
        if self.paused or self.closing or not self.started:
            return
        self._on_image(decoded["payload"], decoded["t_ms"])

    def _record(self, func: str, *args: object) -> None:
        """Enregistrement replay : n'interrompt jamais la session (SRV-R9.3)."""
        try:
            if self.recorder is not None and self.session_id is not None:
                getattr(self.recorder, func)(self.session_id, *args)
        except Exception:
            pass

    def _on_image(self, jpeg: bytes, t_ms: int) -> None:
        fi = self.frame_index
        self.frame_index += 1
        if not self.fps_guard.allow(self.clock()):  # SRV-R3.2 : au-delà de 10 img/s
            self.counters["dropped"] += 1
            return
        self._record("record_image", fi, jpeg)
        if self.t0_ms is None:  # démarrage : on retient, le diagnostic décidera (SRV-R4.1)
            self.pending_frames[fi] = (t_ms, jpeg, self.clock())
            if len(self.startup) < 3:
                self.startup.append((jpeg, t_ms))
                if len(self.startup) == 3:
                    self.t0_ms = self.startup[0][1]
                    self.work.put_control("start", list(self.startup))
                    self._work_event.set()
            return
        task = self._submit(jpeg, fi, t_ms)
        if task is None:
            self.counters["dropped"] += 1  # SRV-R4.2 : 3 en cours, abandonnée

    def _submit(self, jpeg: bytes, fi: int, t_ms: int):  # tâche asyncio ou None
        if self.perception is None:
            self.pending_frames[fi] = (t_ms, jpeg, self.clock())
            return "held"  # appliquée quand la perception existera (diagnostic lent)
        self.pending_frames[fi] = (t_ms, jpeg, self.clock())
        task = self.perception.try_submit(jpeg, fi, t_ms)
        if task is None:
            del self.pending_frames[fi]
            return None
        task.add_done_callback(lambda t: self._on_result(t, fi))
        return task

    def _on_result(self, task: object, fi: int) -> None:
        import cv2
        import numpy as np
        from fixloop.geometry import measure
        try:
            result = task.result()
        except Exception:
            self.counters["stale"] += 1
            self.pending_frames.pop(fi, None)
            return
        self.last_result_at = self.clock()
        fatal = map_result_error(result.error)
        if fatal is not None:  # SRV-R7.2, R7.3 : erreur SAM fatale -> fermer
            self.pending_frames.pop(fi, None)
            self.fatal = fatal
            self._work_event.set()
            return
        t_ms, jpeg, recv_t = self.pending_frames.pop(fi, (0, b"", self.clock()))
        age = self.clock() - recv_t
        verdict = check_result(age, fi, self.last_applied)
        if verdict != "ok":  # SRV-R4.3
            self.counters["stale" if verdict == "stale" else "out_of_order"] += 1
            return
        self.last_applied = fi
        t = session_time(t_ms, self.t0_ms or t_ms)  # SRV-R4.5
        fm = result.to_frame_masks()
        fm.t = t
        proc = self.sm.procedure if self.sm is not None else None
        m = measure(fm, proc or next(iter(self.procedures.values())))
        img = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        box = result.parts.get("chainring", None)
        keyframe = keyframe_image(img, box.box if box is not None else None)
        contact = next(iter(m.contact.values()), None)
        contact = None if contact is None or contact != contact else round(contact, 3)
        on_max, off_min = ((step_thresholds(self.sm.step) if self.sm is not None else (None, None)))
        label = label_for(contact, on_max, off_min)
        latency_ms = round(age * 1000, 1)
        self.latencies.append(latency_ms)  # SRV-R9.1
        overlay = overlay_for(fi, t_ms, result.w, result.h, result.parts, contact,
                              label, self.sm.verdict if self.sm is not None else "0",
                              latency_ms, set(self.red_parts))
        self._send_now(overlay)
        import json
        self._record("record_raw", fi, json.dumps(overlay, ensure_ascii=False))
        self.work.put_measure((m, keyframe), None)
        self._work_event.set()

    # ---------------------------------------------------------- fil machine à états
    def _write_journal(self, success: bool, ended: str = "closed") -> None:
        """Journal de fin de session, une seule fois (SRV-R9.1, R7.4)."""
        if self.journal_written or self.recorder is None or self.session_id is None:
            return
        self.journal_written = True
        try:
            costs = {"session_usd": round(self._session_cost(), 6)}
            try:
                costs["day_usd"] = round(float(self.models.costs.day_total()), 6)
            except Exception:
                pass
            self.recorder.finish(self.session_id, {
                "bike_id": self.bike_id, "success": success, "ended": ended,
                "events": list(self.sm.log) if self.sm is not None else [],
                "counters": {**self.counters, **summary_for(self.counters)},
                "latencies": list(self.latencies), "costs": costs})
        except Exception:
            pass

    async def _finish(self, success: bool) -> None:
        """Journal, `closed` (avec résumé) puis fermeture après 2 s (SRV-R6.3)."""
        import asyncio
        if self.closed_sent:
            return
        self.closed_sent = True
        self.closing = True
        self._write_journal(success)
        self._send_now({"type": "closed", "success": success,
                        "summary": summary_for(self.counters)})
        await asyncio.sleep(CLOSE_DELAY_S)
        try:
            await self.ws.close()
        except Exception:
            pass

    async def _abort(self, code: str, message: str, say: str | None = None) -> None:
        """Erreur fatale : phrase éventuelle, `error`, puis fermeture (SRV-R7)."""
        import asyncio
        if self.closed_sent:
            return
        self.closed_sent = True
        self.closing = True
        self._write_journal(False, ended="error")
        if say is not None:
            self._send_now({"type": "say", "text": say})
        self._send_now({"type": "error", "code": code, "message": message})
        await asyncio.sleep(1.0)
        try:
            await self.ws.close()
        except Exception:
            pass

    async def _apply(self, func: object, *args: object) -> bool:
        """Un appel machine à états : True pour continuer, False pour arrêter (SRV-T7)."""
        import asyncio
        try:
            await asyncio.to_thread(func, *args)
        except Exception:
            if self.note_worker_error():  # 3 exceptions de suite -> arrêt
                await self._abort("internal", "La session est interrompue, reconnecte-toi.")
                return False
            return True
        self.note_worker_ok()
        return True

    async def _sm_worker(self) -> None:
        import asyncio
        from fixloop.state_machine import Session
        while True:
            await self._work_event.wait()
            self._work_event.clear()
            if self.fatal is not None:  # erreur SAM fatale (SRV-R7.1, R7.2)
                code, message = self.fatal
                self.fatal = None
                await self._abort(code, message,
                                  say=STOP_PHRASE if code == "budget" else None)
                return
            while (item := self.work.take()) is not None:
                kind = item[0]
                if kind == "start":
                    _, startup = item
                    proc0 = next(iter(self.procedures.values()))
                    self.perception = self.models.perception_factory(proc0)
                    self.sm = Session(self.procedures, self.models.agent, self.models.memory,
                                      self.output, self.bike_id, debounce_frames=3)
                    imgs = [self._decode(jpeg) for jpeg, _ in startup]
                    self._replay_held()
                    if not await self._apply(self.sm.start, imgs):
                        return
                elif kind == "measure":
                    _, (m, keyframe), _ = item
                    if self.sm is not None and not await self._apply(self.sm.on_measures, m,
                                                                     keyframe):
                        return
                elif kind == "done":
                    if self.sm is not None and not await self._apply(self.sm.on_user_done):
                        return
                elif kind == "command":
                    if self.sm is not None and not await self._apply(self.sm.on_command,
                                                                      item[1]):
                        return
                elif kind == "stop":
                    await self._finish(False)
                    return
                if self.sm is not None and self.sm.state == "CLOTURE":
                    await self._finish(True)  # SRV-R6.3
                    return

    def _decode(self, jpeg: bytes) -> object:
        import cv2
        import numpy as np
        return cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)

    def _replay_held(self) -> None:
        """Soumet les images arrivées avant la perception (diagnostic lent)."""
        for fi in sorted(self.pending_frames):
            t_ms, jpeg, _ = self.pending_frames[fi]
            self.pending_frames[fi] = (t_ms, jpeg, self.clock())
            task = self.perception.try_submit(jpeg, fi, t_ms)
            if task is None:
                self.counters["dropped"] += 1
                del self.pending_frames[fi]
            else:
                task.add_done_callback(lambda t, fi=fi: self._on_result(t, fi))
