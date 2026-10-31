"""Serveur HTTP FixLoop (spec/05-session-server, SRV-T1).

FastAPI : fichiers statiques (`web/`), `/api/health`, `/api/procedures`.
La clé API ne quitte jamais le serveur ; le navigateur ne la voit pas.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from fixloop.procedures import load_all

ROOT = Path(__file__).resolve().parent.parent


def _version() -> str:
    """Sha git court, `FIXLOOP_VERSION`, ou `dev` (SRV-R1.2)."""
    tag = os.environ.get("FIXLOOP_VERSION")
    if tag:
        return tag
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, cwd=ROOT, timeout=5)
        sha = out.stdout.strip()
        return sha if out.returncode == 0 and sha else "dev"
    except Exception:
        return "dev"


def create_app(procedures: dict | None = None) -> FastAPI:
    """Fabrique l'application ; `procedures` injectable pour les tests."""
    load_dotenv(ROOT / ".env")  # MODEL_API_KEY, côté serveur uniquement (jamais journalisée)
    procedures = procedures if procedures is not None else load_all()
    app = FastAPI(title="FixLoop")
    app.state.procedures = procedures
    live = os.environ.get("FIXLOOP_FAKE_MODELS") != "1"
    code_required = bool(os.environ.get("FIXLOOP_ACCESS_CODE"))
    from server.session import SessionRegistry, limits_from_env
    app.state.registry = SessionRegistry(limits_from_env(),
                                         access_code=os.environ.get("FIXLOOP_ACCESS_CODE"),
                                         procedures=procedures)  # SRV-R2

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": _version(), "live": live,
                "access_code_required": code_required}  # SRV-R1.2 : sans appel aux modèles

    @app.get("/api/procedures")
    def procedures_list() -> list:
        return [{"id": p["id"], "title": p["title"]} for p in procedures.values()]  # SRV-R1.3

    @app.get("/api/costs")
    def costs_today(access_code: str | None = None):
        """Totaux du jour par modèle, protégés par le code d'accès (SRV-R8.4)."""
        from datetime import date

        from fastapi.responses import JSONResponse

        from fixloop.costs import CostLog
        required = os.environ.get("FIXLOOP_ACCESS_CODE")
        if required is not None and access_code != required:
            return JSONResponse(status_code=403, content={"detail": "Code d'accès refusé."})
        log = CostLog()
        return {"day": date.today().isoformat(), "total_usd": round(log.day_total(), 6),
                "by_model": {m: round(c, 6) for m, c in log.by_model().items()}}

    web = ROOT / "web"
    if web.is_dir():  # SRV-R1.1 : l'appli statique arrive avec 06-phone-app
        app.mount("/", StaticFiles(directory=web, html=True), name="web")

    @app.websocket("/ws/session")
    async def ws_session(ws):  # SRV-R4 : une session en direct par connexion
        from server.session import LiveSession, build_models
        from fixloop.costs import CostLog
        await ws.accept()
        ip = ws.client.host if ws.client else "unknown"
        models = build_models(app.state.procedures, CostLog(),
                              fake=os.environ.get("FIXLOOP_FAKE_MODELS") == "1")
        session = LiveSession(ws, app.state.registry, ip, app.state.procedures,
                              models, app.state.registry.limits)
        await session.run()

    return app


app = create_app()
