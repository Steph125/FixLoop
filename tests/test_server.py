"""Serveur de session (spec/05-session-server). Sans réseau : TestClient en mémoire."""

import pytest

try:
    from fastapi.testclient import TestClient

    from server.app import create_app
except ImportError as e:  # fastapi/httpx absents : à vérifier hors sandbox
    pytest.skip(f"dépendances serveur absentes : {e}", allow_module_level=True)


def test_health_is_ok_without_models():
    c = TestClient(create_app())
    r = c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True  # SRV-R1.2 : sans appel aux modèles
    assert set(body) == {"ok", "version", "live", "access_code_required"}
    assert isinstance(body["version"], str) and body["version"]


def test_procedures_lists_loaded_cards():
    c = TestClient(create_app())
    r = c.get("/api/procedures")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert "chain_off_chainring" in ids  # SRV-R1.3
    assert all(set(p) == {"id", "title"} for p in r.json())


def test_costs_needs_access_code(monkeypatch):
    monkeypatch.setenv("FIXLOOP_ACCESS_CODE", "sésame")
    c = TestClient(create_app())
    assert c.get("/api/costs").status_code == 403  # SRV-R8.4 : sans code
    r = c.get("/api/costs", params={"access_code": "sésame"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"day", "total_usd", "by_model"}  # totaux du jour par modèle
    monkeypatch.delenv("FIXLOOP_ACCESS_CODE")
    assert TestClient(create_app()).get("/api/costs").status_code == 200  # code non défini
