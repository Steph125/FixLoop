"""Orchestration des sessions (spec/05-session-server).

Sans FastAPI : ce module ne manipule que des dicts JSON et des octets
(duck-typing du WebSocket), pour que la logique soit testable sans réseau.
Le câblage WebSocket et HTTP vit dans `server/app.py`.
"""

from __future__ import annotations

import os
import secrets
import time
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
                 procedures: dict | None = None):
        self.limits = limits or Limits()
        self.access_code = access_code
        self.procedures = procedures if procedures is not None else {}
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
