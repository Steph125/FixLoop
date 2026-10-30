"""Protocole WebSocket (spec/05-session-server, SRV-T3).

Aucune dépendance externe : validation des messages JSON de contrôle et décodage
de l'en-tête binaire (design 05, section 3). Un message invalide rend None : la
session l'ignore et le journalise sans fermer (SRV-R3.1).
"""

import json
import struct

MSG_AUDIO = 0x01  # PCM16 mono 16 kHz, morceaux de 100 ms
MSG_IMAGE = 0x02  # JPEG
MAX_IMAGE_BYTES = 200 * 1024  # SRV-R3.3 : au-delà, l'image est ignorée
HEADER_LEN = 9  # 1 octet de type + 8 octets d'horodatage client (ms, gros-boutiste)

COMMANDS = ("repeat", "help")

# type -> champs requis (nom -> types acceptés). Les champs en plus sont permis.
_CLIENT_SPEC = {
    "hello": {"bike_id": (str,), "client": (dict,)},
    "start": {},
    "user_done": {"t_ms": (int,)},
    "command": {"cmd": (str,), "t_ms": (int,)},
    "speaking": {"on": (bool,), "t_ms": (int,)},
    "pause": {},
    "resume": {},
    "stop": {},
}

# champs permis mais non requis.
_CLIENT_OPTIONAL = {
    "hello": {"access_code": (str, type(None))},
}


def _bad(value, types):
    if isinstance(value, bool) and int in types:
        return True  # True n'est pas un t_ms
    return not isinstance(value, types)


def parse_client_message(raw) -> dict | None:
    """Valide un message de contrôle client ; None si invalide (SRV-R3.1)."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = bytes(raw).decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
    if not isinstance(raw, dict):
        return None
    kind = raw.get("type")
    if not isinstance(kind, str) or kind not in _CLIENT_SPEC:
        return None
    for field, types in _CLIENT_SPEC[kind].items():
        if field not in raw or _bad(raw[field], types):
            return None
        if field == "t_ms" and raw[field] < 0:
            return None
    for field, types in _CLIENT_OPTIONAL.get(kind, {}).items():
        if field in raw and _bad(raw[field], types):
            return None
    if kind == "command" and raw["cmd"] not in COMMANDS:
        return None
    return raw


def parse_binary(data: bytes) -> dict | None:
    """Décode un message binaire -> {kind, t_ms, payload, too_big} ; None si malformé.

    `too_big` : image de plus de 200 ko, à ignorer (SRV-R3.3).
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) < HEADER_LEN:
        return None
    marker, t_ms = data[0], struct.unpack(">Q", bytes(data[1:9]))[0]
    if marker == MSG_AUDIO:
        kind = "audio"
    elif marker == MSG_IMAGE:
        kind = "image"
    else:
        return None
    payload = bytes(data[HEADER_LEN:])
    return {"kind": kind, "t_ms": t_ms, "payload": payload,
            "too_big": kind == "image" and len(payload) > MAX_IMAGE_BYTES}
