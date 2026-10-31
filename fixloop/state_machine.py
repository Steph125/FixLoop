"""Machine à états de FixLoop (spec/01-core-loop/design.md, section 6).

Logique pure, sans appel réseau : les modèles Meta sont injectés via `Agent` et `Memory`,
la sortie vers le téléphone via `Output`. Les tests et la simulation passent des faux objets.
"""

from __future__ import annotations

import json
import math
from collections import deque
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .models import Measures, Verdict
from .verifier import holds, verify


def _sanitize(value: Any) -> Any:
    """Rend une valeur sûre pour JSON : pas de numpy, d'octets ni de NaN (CORE-R8.2, R8.3)."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} octets binaires>"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_sanitize(v) for v in sorted(value, key=repr)]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def export_jsonl(log: list[dict], path: str | Path) -> Path:
    """Exporte le journal en JSON Lines, une ligne par événement (CORE-R8.2)."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as fh:
        for entry in log:
            fh.write(json.dumps(_sanitize(entry), ensure_ascii=False) + "\n")
    return path


class State(str, Enum):
    DEMARRAGE = "DEMARRAGE"
    OBSERVATION = "OBSERVATION"
    ARBITRAGE = "ARBITRAGE"
    ANOMALIE = "ANOMALIE"
    ETAPE_VALIDEE = "ETAPE_VALIDEE"
    ESSAI_DYNAMIQUE = "ESSAI_DYNAMIQUE"
    CLOTURE = "CLOTURE"


class Agent(Protocol):  # Muse Spark
    def diagnose(self, images: list[Any], procedures: dict[str, dict], history: str
                 ) -> tuple[str, str | None]: ...  # (id de fiche, raison dite a l'utilisateur)
    def arbitrate(self, step: dict, keyframes: list[Any], window: list[Measures]) -> Verdict: ...
    def explain(self, step: dict, verdict: Verdict, keyframes: list[Any]) -> tuple[str, str | None]: ...


class Memory(Protocol):  # Muse Wonder
    def load(self, bike_id: str) -> str: ...
    def save(self, bike_id: str, report: dict) -> None: ...


class Output(Protocol):  # téléphone
    def say(self, text: str) -> None: ...
    def highlight(self, parts: list[str], color: str) -> None: ...
    def state(self, snapshot: dict) -> None: ...  # CORE-R11 : instantané à chaque changement


DEFAULT_ADVICE = "Je ne vois pas bien. Montre-moi le plateau de face, mains hors du champ."
FALLBACK_PROBLEM = "Il y a un problème, regarde la pièce en rouge."
PART_FRENCH = {"chain": "la chaîne", "chainring": "le plateau", "derailleur": "le dérailleur"}
FRAMING_COOLDOWN_S = 10.0


class Session:
    def __init__(self, procedures: dict[str, dict], agent: Agent, memory: Memory, out: Output,
                 bike_id: str, anomaly_cooldown_s: float = 8.0, keyframes_kept: int = 3,
                 arbitration_cooldown_s: float = 10.0, debounce_frames: int = 4,
                 framing_timeout_s: float = 6.0):
        self.procedures, self.agent, self.memory, self.out = procedures, agent, memory, out
        self.bike_id = bike_id
        self.debounce_frames = debounce_frames  # 3 en direct, 4 en replay (CORE-R9.1)
        self.framing_timeout_s = framing_timeout_s
        self.last_seen: dict[str, float] = {}
        self.next_framing_t = -1.0
        self.cooldown = anomaly_cooldown_s
        self.arbitration_cooldown = arbitration_cooldown_s
        self.next_arbitration_t = -1.0
        self.state = State.DEMARRAGE
        self.procedure: dict | None = None
        self.k = 0
        self.window: list[Measures] = []
        self.user_done = False
        self.verdict = "0"
        self.last_contact: dict[tuple[str, str], float] = {}
        self._last_emitted: tuple | None = None
        self.keyframes: deque = deque(maxlen=keyframes_kept)
        self.suppressed: dict[str, float] = {}       # message d'anomalie -> réactivé à t
        self.dynamic_t0: float | None = None
        self.fail_streak = 0
        self.model_calls = {"spark": 0, "wonder": 0}
        self.log: list[dict] = []
        self.t = 0.0

    # ------------------------------------------------------------------ entrées
    def _safe_load(self) -> str:
        """Historique, ou repli "aucun" si la memoire leve (CORE-R4.7)."""
        try:
            history = self.memory.load(self.bike_id)
        except Exception:
            self._event("memory_error", where="load")
            return "aucun"
        self.model_calls["wonder"] += 1
        return history

    def _safe_save(self, report: dict) -> None:
        """Ecrit le rapport ; journalise `memory_error` si la memoire leve (CORE-R4.7)."""
        try:
            self.memory.save(self.bike_id, report)
        except Exception:
            self._event("memory_error", where="save")
            return
        self.model_calls["wonder"] += 1

    def start(self, images: list[Any]) -> None:
        history = self._safe_load()
        try:
            result = self.agent.diagnose(images, self.procedures, history)
        except Exception:
            result = None
        self.model_calls["spark"] += 1
        if isinstance(result, (tuple, list)) and len(result) == 2:  # AGT-T6 : (id, raison)
            proc_id, raison = result
        else:  # compatibilite : ancien protocole rendant l'id seul
            proc_id, raison = result, None
        if proc_id not in self.procedures:  # inconnu ou agent muet : 1re fiche
            proc_id, raison = next(iter(self.procedures)), None
            self._event("diagnose", procedure=proc_id, fallback=True)
        else:
            self._event("diagnose", procedure=proc_id)
        self.procedure = self.procedures[proc_id]
        self.out.say(f"Je vois : {self.procedure.get('title', proc_id)}.")  # AGT-R1.4
        if isinstance(raison, str) and raison.strip():
            self.out.say(raison.strip())
        self._enter_step(0)
        self._maybe_emit_state()

    def on_user_done(self) -> None:
        if self.state in (State.OBSERVATION, State.ESSAI_DYNAMIQUE):
            self.user_done = True
            self._event("user_done")

    def on_measures(self, m: Measures, keyframe: Any = None) -> None:
        if self.state == State.CLOTURE:
            return
        if m.t < self.t:  # arrivée hors ordre : ignorée (le serveur livre dans le désordre)
            return
        self.t = m.t
        if keyframe is not None:
            self.keyframes.append(keyframe)
        for part, seen in m.detected.items():
            if seen:
                self.last_seen[part] = m.t
        self.last_contact = dict(m.contact)
        if self.state == State.OBSERVATION:
            self.window.append(m)
            if self._check_step() is not None:  # verdict discret : on peut signaler le cadrage
                self._check_framing()
        elif self.state == State.ESSAI_DYNAMIQUE:
            self.window.append(m)
            self._check_dynamic()
        self._maybe_emit_state()

    # ------------------------------------------------------------------ logique
    @property
    def step(self) -> dict:
        return self.procedure["steps"][self.k]

    def _enter_step(self, k: int) -> None:
        self.k, self.window, self.user_done = k, [], False
        self.verdict = "0"
        self.state = State.OBSERVATION
        self.out.say(self.step["instruction"])
        self.out.highlight(self.step.get("highlight", []), "blue")
        self._event("step", step=self.step["id"])

    def snapshot(self) -> dict:
        """Instantané observable : état, fiche, étape k/K, verdict, contacts, compteurs (CORE-R11.1)."""
        contact = {f"{a}/{b}": (None if val != val else round(val, 3))
                   for (a, b), val in self.last_contact.items()}
        if self.procedure is None:
            return {"state": self.state.value, "procedure": None, "step": None,
                    "verdict": self.verdict, "contact": contact, "user_done": self.user_done,
                    "model_calls": dict(self.model_calls), "t": round(self.t, 2)}
        return {"state": self.state.value,
                "procedure": {"id": self.procedure["id"], "title": self.procedure["title"]},
                "step": {"index": self.k + 1, "count": len(self.procedure["steps"]),
                         "id": self.step["id"], "instruction": self.step["instruction"]},
                "verdict": self.verdict, "contact": contact, "user_done": self.user_done,
                "model_calls": dict(self.model_calls), "t": round(self.t, 2)}

    def _maybe_emit_state(self) -> None:
        """Notifie l'instantané si l'état, l'étape ou le verdict a changé (CORE-R11.2)."""
        key = (self.state, self.k, self.verdict)
        if key != self._last_emitted:
            self._last_emitted = key
            self.out.state(self.snapshot())

    def _check_step(self) -> Verdict | None:
        """Rend le verdict s'il est discret (`0`), sinon None (quelque chose a été dit)."""
        v = verify(self.step, self.window, self.user_done, self.debounce_frames)
        self.verdict = v.value
        if v.value == "eps" and self._suppressed(v):
            return None
        source = "rule"
        if v.value == "?":
            if self.t < self.next_arbitration_t:   # Spark au plus une fois toutes les 10 s
                return None
            self.state = State.ARBITRAGE
            try:
                v = self.agent.arbitrate(self.step, list(self.keyframes),
                                         self.window[-self.debounce_frames:])
            except Exception:
                v = None
            self.model_calls["spark"] += 1
            v = self._safe_arbitration(v)
            self.verdict = v.value
            self.next_arbitration_t = self.t + self.arbitration_cooldown
            self._event("arbitrate", verdict=v.value, evidence=v.evidence)
            if v.value == "0":
                self.out.say(v.message or DEFAULT_ADVICE)
            elif v.value == "eps":
                source = "muse-spark"
        if v.value == "1":
            self._validate(v)
            return None
        if v.value == "eps":
            self._anomaly(v, source=source)
            return None
        if self.state == State.ARBITRAGE:
            self.state = State.OBSERVATION
            return None
        return v  # "0" discret

    def _required_parts(self) -> list[str]:
        """Pièces citées par les règles de succès de l'étape en cours (CORE-R10)."""
        parts = []
        for rule in self.step.get("success", []):
            for key in ("part", "a", "b"):
                if key in rule and rule[key] not in parts:
                    parts.append(rule[key])
        return parts

    def _check_framing(self) -> None:
        """Perte du cadrage : pièce requise invisible depuis `framing_timeout_s` (CORE-R10)."""
        if self.t < self.next_framing_t:
            return
        for part in self._required_parts():
            if self.t - self.last_seen.get(part, 0.0) >= self.framing_timeout_s:
                self.out.say(f"Je ne vois plus {PART_FRENCH.get(part, part)}. "
                             "Replace le téléphone face au plateau.")
                self._event("framing_lost", part=part)
                self.next_framing_t = self.t + FRAMING_COOLDOWN_S
                return

    def _validate(self, v: Verdict) -> None:
        self.state = State.ETAPE_VALIDEE
        self._event("validated", step=self.step["id"], evidence=v.evidence)
        self.out.say("C'est bon.")
        if self.k + 1 < len(self.procedure["steps"]):
            self._enter_step(self.k + 1)
        elif "dynamic_test" in self.procedure:
            self._enter_dynamic()
        else:
            self._close(success=True)

    @staticmethod
    def _safe_arbitration(v: Any) -> Verdict:
        """Un arbitrage ne valide jamais : `eps` ou `0`, sinon repli (CORE-R7.5, AGT-R2)."""
        if isinstance(v, Verdict) and v.value in ("eps", "0"):
            return v
        evidence = getattr(v, "evidence", None) if isinstance(v, Verdict) else None
        evidence = dict(evidence) if isinstance(evidence, dict) else {}
        evidence["ignore"] = "Spark ne valide jamais : on attend que la mesure SAM confirme"
        message = getattr(v, "message", None) if isinstance(v, Verdict) else None
        return Verdict("0", None, evidence, message or DEFAULT_ADVICE)

    def _anomaly(self, v: Verdict, source: str = "rule") -> None:
        self.state = State.ANOMALIE
        try:
            text, part = self.agent.explain(self.step, v, list(self.keyframes))
        except Exception:
            text, part = None, None
        self.model_calls["spark"] += 1
        if not isinstance(text, str) or not text:
            text = v.message or FALLBACK_PROBLEM  # CORE-R5.4 : agent muet, message de la règle
        if not isinstance(part, str) or part not in self.procedure.get("parts", {}):
            part = None
        self.out.say(text)
        self.out.highlight([part] if part else self.step.get("highlight", []), "red")
        self._event("anomaly", step=self.step["id"], message=v.message,
                    evidence=v.evidence, source=source)
        self.suppressed[v.message or ""] = self.t + self.cooldown
        self.window, self.user_done = [], False
        self.state = State.OBSERVATION

    def _suppressed(self, v: Verdict) -> bool:
        return self.t < self.suppressed.get(v.message or "", -1.0)

    def _enter_dynamic(self) -> None:
        self.state = State.ESSAI_DYNAMIQUE
        self.window, self.dynamic_t0, self.fail_streak = [], None, 0
        self.out.say(self.procedure["dynamic_test"]["instruction"])
        self._event("dynamic_start")

    def _check_dynamic(self) -> None:
        test = self.procedure["dynamic_test"]
        m = self.window[-1]
        if holds(test["must_hold"], [m]):
            self.fail_streak = 0
            if self.dynamic_t0 is None:
                self.dynamic_t0 = m.t
            if m.t - self.dynamic_t0 >= test["duration_s"]:
                self._close(success=True)
            return
        self.dynamic_t0 = None          # on recompte depuis la prochaine image correcte
        self.fail_streak += 1
        if self.fail_streak >= self.debounce_frames:
            v = Verdict("eps", test["must_hold"][0], {"frame": m.frame_index},
                        "La chaîne n'est pas restée en place pendant la rotation.")
            self.k = len(self.procedure["steps"]) - 1   # on reprend à la dernière étape
            self._anomaly(v)
            self.out.say(self.step["instruction"])

    def _close(self, success: bool) -> None:
        self.state = State.CLOTURE
        report = {"procedure": self.procedure["id"], "success": success,
                  "events": [e for e in self.log if e["event"] in ("validated", "anomaly")],
                  "model_calls": dict(self.model_calls)}
        self._safe_save(report)
        self.out.say("Réparation validée. Je l'ai ajoutée à l'historique de ton vélo.")
        self._event("closed", success=success)

    def _event(self, event: str, **data) -> None:
        self.log.append({"t": round(self.t, 2), "event": event, "state": self.state.value,
                         "model_calls": dict(self.model_calls), **data})
