"""Commandes vocales (spec/04-memory-voice, VOX-R2).

`normalize` et `CommandDetector` : purs, sans réseau. Le pont Transcribe
(`VoiceBridge`, VOX-T3) appellera `feed` avec les transcriptions finales.
"""

from __future__ import annotations

import re
import unicodedata

COMMANDS = {  # design 04, section 2.2 : formes deja normalisees (VOX-T6)
    "done": ["c est fait", "j ai fini", "c est fini", "j ai termine", "c est termine", "c est bon"],
    "help": ["aide moi", "aidemoi", "aidez moi", "aide", "je n y arrive pas", "au secours"],  # « aidemoi » : transcription réelle (eval/day3)
    "repeat": ["repete", "repeter", "redis", "pardon"],
}
_PRIORITY = ("done", "help", "repeat")  # si plusieurs commandes : done d'abord
_NEGATION = frozenset({"pas", "n", "ne", "jamais"})  # VOX-R2.6 : annulent la forme


def normalize(text: str) -> str:
    """Minuscules, sans accents, apostrophes et ponctuation en espaces (VOX-R2.1)."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _occurs(words: list[str], form: str) -> list[int]:
    """Positions (index de mot) où la forme apparaît en mots entiers et contigus."""
    parts = form.split()
    return [i for i in range(len(words) - len(parts) + 1) if words[i:i + len(parts)] == parts]


def _negated(words: list[str], start: int, length: int) -> bool:
    """VOX-R2.6 : négation dans les 3 mots avant, ou « pas » juste après."""
    if any(w in _NEGATION for w in words[max(0, start - 3):start]):
        return True
    return start + length < len(words) and words[start + length] == "pas"


class CommandDetector:
    """Détecte done/help/repeat dans les transcriptions finales (VOX-R2.1 à R2.6)."""

    def __init__(self, cooldown_s: float = 2.0, mute_tail_s: float = 0.5):
        self.cooldown_s = cooldown_s
        self.mute_tail_s = mute_tail_s
        self._speaking = False
        self.mute_until = 0.0
        self.last_trigger: dict[str, float] = {}
        self.history: list[dict] = []  # journal (transcription normalisée, VOX-T4)

    def speaking(self, on: bool, t: float) -> None:
        """Signalé par l'appli au début / à la fin de la synthèse vocale."""
        self._speaking = on
        if not on:
            self.mute_until = t + self.mute_tail_s

    def feed(self, final_text: str, t: float) -> str | None:
        """Rend "done" | "help" | "repeat" | None."""
        if self._speaking or t < self.mute_until:  # VOX-R2.4 : ne pas s'entendre
            return None
        norm = normalize(final_text)
        words = norm.split()
        for cmd in _PRIORITY:
            for form in COMMANDS[cmd]:
                parts = form.split()
                if any(not _negated(words, i, len(parts)) for i in _occurs(words, form)):
                    if t - self.last_trigger.get(cmd, -1e9) < self.cooldown_s:  # VOX-R2.3
                        return None
                    self.last_trigger[cmd] = t
                    self.history.append({"t": t, "command": cmd, "text": norm})
                    return cmd
        return None  # VOX-R2.2


# ------------------------------------------------------------------ pont Transcribe (VOX-T3)

WS_URL = "wss://api.meta.ai/v1/asr/realtime"
MODEL = "muse-voice-transcribe-1.0"  # doc Meta \u00ab Speech to text \u00bb, lue le 1er nov.
RATE = 24000  # VOX-R1.2 : fr\u00e9quence native de Transcribe, pas de r\u00e9\u00e9chantillonnage c\u00f4t\u00e9 Meta
FRAME_MS = 80
FRAME_BYTES = RATE * 2 * FRAME_MS // 1000  # 3 840 octets : 1 920 \u00e9chantillons PCM16 mono
KEYWORDS = ["c'est fait", "aide-moi", "r\u00e9p\u00e8te", "plateau", "cha\u00eene"]
MAX_AHEAD_S = 5.0  # jamais plus de 5 s d\u2019audio en avance (doc Meta)
MAX_RETRIES = 3  # VOX-R3.2 : 3 reconnexions (1 s, 2 s, 4 s), puis abandon de la voix
RETRY_DELAYS = (1.0, 2.0, 4.0)
CLOSE_TIMEOUT_S = 5.0


def handshake(api_key: str) -> dict:
    """Premi\u00e8re trame texte : la cl\u00e9 va dans le message, pas dans l\u2019en-t\u00eate (design 04, 2.1)."""
    return {"authorization": {"accessToken": f"Bearer {api_key}"}, "model": MODEL,
            "audioEncoding": "PCM_24KHZ", "mode": "ENDPOINTING", "partialMode": "CUMULATIVE",
            "emitAudioProgress": False, "languageBias": ["French"], "keywords": KEYWORDS}


def parse_event(raw: str) -> tuple:
    """Un \u00e9v\u00e9nement serveur -> (sorte, donn\u00e9es) ; les sortes inconnues rendent `unknown`."""
    import json
    try:
        ev = json.loads(raw)
    except (ValueError, TypeError):
        return "unknown", {}
    if not isinstance(ev, dict):
        return "unknown", {}
    kind = ev.get("type")
    if kind is None and "sessionId" in ev:
        return "ack", {"sessionId": ev["sessionId"]}  # accus\u00e9 sans champ type
    if kind == "speechComplete":
        return kind, {"turnId": ev.get("turnId"), "transcript": ev.get("transcript", "")}
    if kind == "transcript":
        return kind, {"transcript": ev.get("transcript", ""), "final": ev.get("final")}
    if kind in ("speechStart", "speechEnd", "audioProgress"):
        return kind, {"turnId": ev.get("turnId")}
    if kind == "error":
        return kind, {"message": ev.get("message", "")}
    return "unknown", ev


def split_frames(pcm: bytes) -> list:
    """D\u00e9coupe l\u2019audio en trames de 80 ms, derni\u00e8re compl\u00e9t\u00e9e de silence."""
    return [bytes(pcm[i:i + FRAME_BYTES].ljust(FRAME_BYTES, b"\0"))
            for i in range(0, len(pcm), FRAME_BYTES)] if pcm else []


class VoiceBridge:
    """Relaye l\u2019audio du t\u00e9l\u00e9phone \u00e0 Muse Voice Transcribe, via le serveur (VOX-R1.1, VOX-D1).

    `on_final(transcript, t)` est appel\u00e9 sur chaque `speechComplete` (VOX-R1.3).
    Apr\u00e8s 3 \u00e9checs, la voix est abandonn\u00e9e pour la session (VOX-R3.2).
    """

    def __init__(self, api_key: str, on_final=None, ws_url: str = WS_URL,
                 clock=None, costs=None, session_id: str | None = None) -> None:
        self.api_key = api_key
        self.on_final = on_final
        self.ws_url = ws_url
        self.clock = clock if clock is not None else __import__("time").monotonic
        self.costs = costs  # CostLog (SRV-R8), comme SparkAgent
        self.session_id = session_id
        self.seconds_sent = 0.0
        self.failures = 0
        self.last_error: str | None = None
        self.started = False
        self._ws = None
        self._recv_task = None
        self._frames = 0
        self._first_frame_t: float | None = None

    async def start(self) -> bool:
        """Ouvre la session Transcribe ; rend False apr\u00e8s 3 relances rat\u00e9es."""
        import asyncio
        import json

        import websockets
        for attempt in range(MAX_RETRIES + 1):
            try:
                ws = await websockets.connect(self.ws_url, max_size=None, open_timeout=15)
                await ws.send(json.dumps(handshake(self.api_key)))
                ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if not isinstance(ack, dict) or "type" in ack:
                    raise ConnectionError(f"pas d\u2019accus\u00e9 de r\u00e9ception : {str(ack)[:120]}")
                self._ws = ws
                self._recv_task = asyncio.get_running_loop().create_task(self._receive())
                self.started = True
                return True
            except Exception as e:  # refus, coupure, d\u00e9lai : on relance (design 04, 2.3)
                self.failures += 1
                self.last_error = f"{type(e).__name__}"
                try:
                    await ws.close()  # type: ignore[possibly-undefined]
                except Exception:
                    pass
                self._ws = None
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
        return False

    async def push_audio(self, pcm: bytes) -> None:
        """Envoie l\u2019audio (trames de 80 ms) ; abandonne silencieusement si la voix est coup\u00e9e."""
        if not self.started or self._ws is None:
            return
        for frame in split_frames(bytes(pcm)):
            await self._pace()
            try:
                await self._ws.send(frame)
            except Exception:
                self.failures += 1
                self.started = False
                self._ws = None
                return
            self._frames += 1

    async def _pace(self) -> None:
        """Jamais plus de 5 s d\u2019audio en avance sur le temps r\u00e9el (doc Meta)."""
        import asyncio
        now = self.clock()
        if self._first_frame_t is None:
            self._first_frame_t = now
            return
        ahead = (self._first_frame_t + self._frames * FRAME_MS / 1000) - now
        if ahead > MAX_AHEAD_S:
            await asyncio.sleep(ahead - MAX_AHEAD_S)

    async def stop(self) -> float:
        """Ferme le flux (`endStream`) et rend les secondes transmises (VOX-R4.1, R4.2)."""
        import asyncio
        import json
        seconds = self._frames * FRAME_MS / 1000
        self.seconds_sent = seconds
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "endStream"}))
            except Exception:
                pass
            if self._recv_task is not None:  # lecture jusqu\u2019\u00e0 la fermeture (code 1000)
                try:
                    await asyncio.wait_for(asyncio.shield(self._recv_task), CLOSE_TIMEOUT_S)
                except Exception:
                    self._recv_task.cancel()
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws, self._recv_task, self.started = None, None, False
        if self.costs is not None and seconds > 0:
            try:
                self.costs.add(model=MODEL, kind="second", units=seconds, seconds=seconds,
                               ok=True, session_id=self.session_id)
            except Exception:
                pass
        return seconds

    async def _receive(self) -> None:
        """Lit les \u00e9v\u00e9nements ; appelle `on_final` sur chaque tour de parole (VOX-R1.3)."""
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    continue
                kind, data = parse_event(raw)
                if kind == "speechComplete" and self.on_final is not None:
                    self.on_final(data["transcript"], self.clock())
                elif kind == "error":
                    self.failures += 1
                    self.last_error = data.get("message")
        except Exception:
            pass
