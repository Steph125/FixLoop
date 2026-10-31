"""Contrôle d'accès et logique de session synchrones (spec/05-session-server).

Sans FastAPI ni boucle asyncio : testé ici. Seule la boucle d'I/O WebSocket
(`LiveSession.run`) demande un environnement réseau (ignorée ici, [~]).
"""

from server.session import Limits, SessionRegistry

PROCS = {"chain_off_chainring": {}}


def make_reg(limits=None, code="sésame"):
    return SessionRegistry(limits or Limits(), access_code=code, procedures=PROCS)


def hello(bike="velo-1", code="sésame", client=None):
    return {"type": "hello", "bike_id": bike, "access_code": code,
            "client": client or {"ua": "test", "w": 800, "h": 600}}


def test_hello_ok_returns_ack_with_limits():
    reg = make_reg(Limits(), code="sésame")
    kind, body = reg.hello(hello(), "10.0.0.1", now=100.0)
    assert kind == "hello_ack"  # SRV-R2.1
    assert body["session_id"] and body["limits"] == {
        "max_minutes": 10, "max_cost_usd": 1.5, "fps": 1}
    assert "chain_off_chainring" in body["procedures"]


def test_hello_wrong_code_is_denied():
    reg = make_reg(Limits(), code="sésame")
    kind, body = reg.hello(hello(code="faux"), "10.0.0.1", now=100.0)
    assert (kind, body["code"]) == ("error", "access_denied")  # SRV-R2.2
    assert reg.live_count == 0


def test_hello_without_code_when_required_is_denied():
    reg = make_reg(Limits(), code="sésame")
    msg = hello()
    del msg["access_code"]
    kind, body = reg.hello(msg, "10.0.0.1", now=100.0)
    assert (kind, body["code"]) == ("error", "access_denied")


def test_hello_without_code_when_open_is_accepted():
    reg = make_reg(Limits(), code=None)
    kind, _ = reg.hello(hello(code=None), "10.0.0.1", now=100.0)
    assert kind == "hello_ack"


def test_third_session_is_busy():
    reg = make_reg(Limits(max_sessions=2), code=None)
    sid1 = reg.hello(hello(), "10.0.0.1", now=100.0)[1]["session_id"]
    assert reg.hello(hello(), "10.0.0.2", now=101.0)[0] == "hello_ack"
    kind, body = reg.hello(hello(), "10.0.0.3", now=102.0)
    assert (kind, body["code"]) == ("error", "busy")  # SRV-R2.3
    assert reg.live_count == 2
    reg.release(sid1)
    kind, _ = reg.hello(hello(), "10.0.0.3", now=104.0)
    assert kind == "hello_ack"  # une place libérée : accepté


def test_ip_blocked_after_six_refusals_in_a_minute():
    reg = make_reg(Limits(), code="sésame")
    for i in range(5):
        kind, _ = reg.hello(hello(code="faux"), "10.0.0.9", now=100.0 + i)
        assert kind == "error"
    kind, body = reg.hello(hello(code="faux"), "10.0.0.9", now=105.0)
    assert (kind, body["code"]) == ("error", "access_denied")
    kind, _ = reg.hello(hello(), "10.0.0.9", now=106.0)
    assert kind == "error"  # SRV-R2.4 : connexions refusées pendant 5 min, même avec le bon code
    kind, _ = reg.hello(hello(), "10.0.0.9", now=106.0 + 301.0)
    assert kind == "hello_ack"  # après 5 min : accepté de nouveau
    kind, _ = reg.hello(hello(), "10.0.0.8", now=107.0)
    assert kind == "hello_ack"  # une autre IP n'est pas bloquée par ces refus


def test_refusals_are_per_ip_and_expire():
    reg = make_reg(Limits(), code="sésame")
    for i in range(5):
        reg.hello(hello(code="faux"), "10.0.0.8", now=100.0 + i)
    kind, _ = reg.hello(hello(), "10.0.0.8", now=200.0)
    assert kind == "hello_ack"  # SRV-R2.4 : refusés d'il y a plus d'1 min oubliés


def test_malformed_hello_is_rejected():
    reg = make_reg(Limits(), code=None)
    kind, body = reg.hello({"type": "hello"}, "10.0.0.1", now=100.0)
    assert (kind, body["code"]) == ("error", "bad_message")
