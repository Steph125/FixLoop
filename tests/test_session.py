"""Contrôle d'accès et logique de session synchrones (spec/05-session-server).

Sans FastAPI ni boucle asyncio : testé ici. Seule la boucle d'I/O WebSocket
(`LiveSession.run`) demande un environnement réseau (ignorée ici, [~]).
"""

import pytest

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


def test_keyframe_cropped_with_chainring_box():
    import concurrent.futures as cf
    import queue

    import numpy as np

    from fixloop.agent import crop_around
    from fixloop.perception import ImageResult, PartResult
    ws, sess = make_live({5: "off"})
    sess._out_queue = queue.Queue()

    class Event:
        def set(self):
            pass

    sess._work_event = Event()
    sess.t0_ms = 0
    sess.clock = lambda: 100.0
    jpeg = jpeg_bytes()  # 160 x 120
    mask = np.zeros((120, 160), bool)
    mask[30:70, 40:80] = True
    box = (40, 30, 80, 70)
    res = ImageResult(5, 5.0, {"chainring": PartResult(mask, 0.9, box, "M", 1)},
                      {"total_s": 0.0, "attempts": {}}, None, 160, 120)
    sess.pending_frames[5] = (5000, jpeg, 99.9)
    fut = cf.Future()
    fut.set_result(res)
    sess._on_result(fut, 5)  # AGT-R3.1, R3.2 : gros plan transmis avec la boîte
    kind, payload, _ = sess.work.take()
    assert kind == "measure"
    _, keyframe = payload
    assert keyframe is not None
    assert np.array_equal(keyframe, crop_around(sess._decode(jpeg), box, margin=0.6))


def test_malformed_hello_is_rejected():
    reg = make_reg(Limits(), code=None)
    kind, body = reg.hello({"type": "hello"}, "10.0.0.1", now=100.0)
    assert (kind, body["code"]) == ("error", "bad_message")


def test_client_time_to_session_time():
    from server.session import session_time
    assert session_time(12_000, 10_000) == 2.0  # SRV-R4.5 : secondes depuis start


def test_result_filters_stale_and_out_of_order():
    from server.session import check_result
    assert check_result(1.2, 7, 5) == "ok"
    assert check_result(6.0, 9, 5) == "stale"  # SRV-R4.3 : plus vieux que 5 s
    assert check_result(5.0, 7, 7) == "ok"  # limite incluse
    assert check_result(0.4, 4, 5) == "out_of_order"  # index inférieur au dernier appliqué


def test_work_queue_keeps_only_latest_measure():
    from server.session import WorkQueue
    q = WorkQueue()
    for i in range(5):
        q.put_measure(f"m{i}", None)
    assert q.dropped_measures == 4  # SRV-R5.3 : 1 seule appliquée ensuite
    assert q.take() == ("measure", "m4", None)
    assert q.take() is None


def test_work_queue_never_drops_controls_and_keeps_order():
    from server.session import WorkQueue
    q = WorkQueue()
    q.put_measure("m1", None)
    q.put_control("done", None)
    q.put_measure("m2", None)
    q.put_control("command", "help")
    assert [q.take()[0] for _ in range(3)] == ["done", "measure", "command"]  # SRV-R5.4
    assert q.dropped_measures == 1


def test_step_thresholds_and_labels():
    from server.session import label_for, step_thresholds
    step = {"success": [{"type": "contact_ratio_max", "a": "chain", "b": "chainring",
                         "threshold": 0.18}],
            "anomaly": [{"type": "contact_ratio_min", "a": "chain", "b": "chainring",
                         "threshold": 0.26, "message": "x"}]}
    assert step_thresholds(step) == (0.18, 0.26)
    assert label_for(0.09, 0.18, 0.26) == "en place"  # SRV-R6.2
    assert label_for(0.34, 0.18, 0.26) == "tombée"
    assert label_for(0.22, 0.18, 0.26) == "incertain"
    assert label_for(float("nan"), 0.18, 0.26) == "non vu"
    assert label_for(None, 0.18, 0.26) == "non vu"


def test_queue_output_emits_in_order():
    import queue

    from server.session import QueueOutput
    out, box = queue.Queue(), queue.Queue()
    qo = QueueOutput(None, box)
    qo.say("C'est bon.")
    qo.highlight(["chain"], "red")
    qo.state({"state": "OBSERVATION"})
    assert box.get_nowait() == {"type": "say", "text": "C'est bon."}  # SRV-R6.1 : dans l'ordre
    assert box.get_nowait() == {"type": "highlight", "parts": ["chain"], "color": "red"}
    assert box.get_nowait() == {"type": "state", "state": "OBSERVATION"}


def test_keyframe_crop_around_chainring_box():
    import numpy as np

    from server.session import keyframe_image
    img = np.zeros((100, 200, 3), np.uint8)
    crop = keyframe_image(img, (80, 20, 120, 60))  # SRV-R4.4 / AGT-R3.2 : gros plan plateau
    assert crop.shape[1] <= img.shape[1] and crop.shape[0] <= img.shape[0]
    assert crop.shape[0] > 40 and crop.shape[1] > 40  # boîte + marge de 60 %
    assert keyframe_image(img, None).shape == img.shape  # sans boîte : image entière


def test_overlay_message_shape():
    from fixloop.perception import PartResult

    from server.session import overlay_for
    parts = {"chain": PartResult(mask=None, confidence=0.9, box=(1, 2, 3, 4),
                                 svg_path="M 1,2 L 3,4 Z", n_objects=1)}
    msg = overlay_for(7, 1500, 80, 60, parts, 0.09, "en place", "0", 12.5)
    assert msg["type"] == "overlay"  # SRV-R6.2
    assert (msg["frame_index"], msg["t_ms"], msg["w"], msg["h"]) == (7, 1500, 80, 60)
    assert msg["parts"] == {"chain": {"path": "M 1,2 L 3,4 Z", "color": "blue"}}
    assert (msg["contact"], msg["label"], msg["verdict"]) == (0.09, "en place", "0")
    red = overlay_for(7, 1500, 80, 60, parts, 0.34, "tombée", "eps", 12.5,
                      red_parts={"chain"})
    assert red["parts"]["chain"]["color"] == "red"  # anomalie : pièce en rouge


# ---------------------------------------------------------- boucle (ignorée ici)

def arun(coro):
    import asyncio
    try:
        return asyncio.run(coro)
    except OSError:
        coro.close()  # évite "coroutine was never awaited" dans les avertissements
        pytest.skip("boucle asyncio interdite ici : à vérifier hors sandbox")


def jpeg_bytes(w=160, h=120):
    import cv2
    import numpy as np
    ok, buf = cv2.imencode(".jpg", np.zeros((h, w, 3), np.uint8))
    assert ok
    return bytes(buf)


def result_for(kind, fi, t):
    import numpy as np

    from fixloop.perception import ImageResult, PartResult
    from fixloop.sim import frame as sim_frame
    fm = sim_frame(kind, fi, t)
    parts = {}
    for p, mask in fm.masks.items():
        ys, xs = np.nonzero(mask)
        parts[p] = PartResult(mask, 0.9, (int(xs.min()), int(ys.min()),
                                         int(xs.max()) + 1, int(ys.max()) + 1), "", 1)
    return ImageResult(fi, t, parts, {"total_s": 0.01, "attempts": {}}, None, 160, 120)


class ManualPerception:
    """Perception factice à complétion manuelle : `kinds[fi]` donne les masques."""

    def __init__(self, kinds):
        self.kinds = kinds
        self.futs = {}

    def try_submit(self, jpeg, fi, t):
        import asyncio
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self.futs[fi] = (fut, t)

        async def done():
            await fut
            return result_for(self.kinds[fi], fi, t)

        return loop.create_task(done())

    def complete(self, fi):
        self.futs[fi][0].set_result(None)


class FakeWS:
    """WebSocket factice : file d'entrée pilotée, envois enregistrés."""

    def __init__(self):
        import collections
        self.incoming = collections.deque()
        self.sent = []
        self.closed = False

    async def receive(self):
        import asyncio
        while not self.incoming and not self.closed:
            await asyncio.sleep(0.01)
        if self.closed and not self.incoming:
            raise ConnectionError("client parti")
        return self.incoming.popleft()

    async def send_text(self, data):
        import json
        self.sent.append(json.loads(data))

    async def close(self):
        self.closed = True

    def feed_text(self, obj):
        import json
        self.incoming.append({"text": json.dumps(obj)})

    def feed_image(self, t_ms):
        import struct
        self.incoming.append({"bytes": struct.pack(">Q", t_ms) + jpeg_bytes()})


def make_live(kinds, clock=None):
    import asyncio

    from fakes import FakeAgent, FakeMemory
    from fixloop.procedures import load_all
    from server.session import Limits, LiveSession, Models, SessionRegistry
    procs = load_all()
    models = Models(lambda proc: ManualPerception(kinds), FakeAgent(), FakeMemory(), None)
    ws = FakeWS()
    sess = LiveSession(ws, SessionRegistry(Limits(), procedures=procs), "127.0.0.1",
                       procs, models, Limits(), clock=clock)
    return ws, sess


async def wait_for(pred, timeout=15.0):
    import asyncio
    async def go():
        while not pred():
            await asyncio.sleep(0.02)
    await asyncio.wait_for(go(), timeout)


def complete_all(sess):
    for fi in sorted(sess.perception.futs):
        fut, _ = sess.perception.futs[fi]
        if not fut.done():
            fut.set_result(None)


async def wait_step(sess, step_id, timeout=15.0):
    await wait_for(lambda: sess.sm is not None and sess.sm.step["id"] == step_id, timeout)


def test_full_session_closes_success():
    async def main():
        import asyncio
        ws, sess = make_live({i: ("off" if i < 9 else "on") for i in range(16)})
        run = asyncio.create_task(sess.run())
        ws.feed_text({"type": "hello", "bike_id": "velo-1"})
        await wait_for(lambda: any(m.get("type") == "hello_ack" for m in ws.sent))
        ws.feed_text({"type": "start"})
        for t in range(0, 9000, 1000):  # fi0-8 : chaîne tombée
            ws.feed_image(t)
            await asyncio.sleep(0.12)  # rythme client ≤ 10 img/s (SRV-R3.2)
        await wait_for(lambda: sess.sm is not None)
        complete_all(sess)
        await wait_step(sess, "engage_top_teeth")
        for t in (9000, 10000, 11000):  # fi9-11 : chaîne posée
            ws.feed_image(t)
            await asyncio.sleep(0.12)
        complete_all(sess)
        await wait_step(sess, "turn_backward")
        ws.feed_text({"type": "user_done"})
        for t in (12000, 13000, 16000):  # fi12-14 : essai, 4 s de rotation
            ws.feed_image(t)
            await asyncio.sleep(0.12)
        complete_all(sess)
        await wait_for(lambda: any(m.get("type") == "closed" for m in ws.sent))
        closed = [m for m in ws.sent if m.get("type") == "closed"][0]
        assert closed["success"] is True  # SRV-T5 : session complète jusqu'au bout
        said = [m["text"] for m in ws.sent if m.get("type") == "say"]
        assert any("Montre-moi" in s for s in said)
        assert any("tourne" in s for s in said)
        await ws.close()
        await asyncio.wait_for(run, 10)
        return sess
    sess = arun(main())
    assert sess.counters["stale"] == 0 and sess.counters["out_of_order"] == 0


def test_stale_result_is_dropped():
    async def main():
        import asyncio
        now = [1000.0]
        ws, sess = make_live({0: "off", 1: "off"}, clock=lambda: now[0])
        sess._out_queue = asyncio.Queue()
        sess._work_event = asyncio.Event()
        sess.t0_ms = 0
        sess.perception = sess.models.perception_factory(None)
        sess._submit(jpeg_bytes(), 0, 0)
        sess.perception.complete(0)
        await asyncio.sleep(0.05)
        sess._submit(jpeg_bytes(), 1, 1000)
        now[0] += 6.0  # le résultat met 6 s à revenir...
        sess.perception.complete(1)
        await asyncio.sleep(0.05)
        overlays = [m["frame_index"] for m in list(sess._out_queue._queue)
                    if m.get("type") == "overlay"]
        return sess, overlays
    sess, overlays = arun(main())
    assert sess.counters["stale"] == 1  # SRV-R4.3 : plus vieux que 5 s, écarté
    assert overlays == [0]


def test_out_of_order_result_is_dropped():
    async def main():
        import asyncio
        ws, sess = make_live({1: "off", 2: "off"})
        sess._out_queue = asyncio.Queue()
        sess._work_event = asyncio.Event()
        sess.t0_ms = 0
        sess.perception = sess.models.perception_factory(None)
        sess._submit(jpeg_bytes(), 1, 1000)
        sess._submit(jpeg_bytes(), 2, 2000)
        sess.perception.complete(2)
        await asyncio.sleep(0.05)
        sess.perception.complete(1)
        await asyncio.sleep(0.05)
        overlays = [m["frame_index"] for m in list(sess._out_queue._queue)
                    if m.get("type") == "overlay"]
        return sess, overlays
    sess, overlays = arun(main())
    assert sess.counters["out_of_order"] == 1  # SRV-R4.3 : antérieur au dernier appliqué
    assert overlays == [2]


def test_fps_guard_caps_images_per_second():
    from server.session import FpsGuard
    g = FpsGuard(10)  # SRV-R3.2 : 10 img/s max
    assert all(g.allow(100.0 + i * 0.05) for i in range(10))
    assert not g.allow(100.0 + 10 * 0.05)  # 11e image dans la même seconde : écartée
    assert g.allow(101.05)  # fenêtre glissante : acceptée ensuite


def test_result_errors_map_to_close_codes():
    from server.session import STOP_PHRASE, map_result_error
    assert map_result_error("Clé API refusée") == (
        "api_key", "Ta clé API est refusée. Vérifie-la puis reconnecte-toi.")  # SRV-R7.1
    assert map_result_error("Crédit épuisé")[0] == "budget"  # SRV-R7.2
    assert map_result_error("Trop de requêtes")[0] == "budget"
    assert STOP_PHRASE == "Je dois m'arrêter : plus de crédit pour aujourd'hui."
    assert map_result_error("Cadrage perdu") is None  # erreur douce : on continue
    assert map_result_error(None) is None


def test_watchdog_states():
    from server.session import SLOW_PHRASE, watchdog_state
    assert watchdog_state(3.0, True) == "ok"
    assert watchdog_state(16.0, True) == "warn"  # SRV-R7.3 : dire le retard à 15 s
    assert SLOW_PHRASE == "La connexion est lente, je continue d'essayer."
    assert watchdog_state(20.0, False) == "ok"  # dit il y a moins d'1 min : silence
    assert watchdog_state(61.0, False) == "abandon"  # 60 s sans résultat : abandon


def test_worker_stops_after_three_consecutive_errors():
    from server.session import LiveSession
    sess = LiveSession.__new__(LiveSession)
    sess.consec_errors = 0
    assert sess.note_worker_error() is False
    assert sess.note_worker_error() is False
    assert sess.note_worker_error() is True  # 3e de suite -> arrêt
    sess.note_worker_ok()
    assert sess.note_worker_error() is False  # un succès remet à zéro


def test_closed_summary_counts_rejections():
    from server.session import summary_for
    assert summary_for({"dropped": 2, "stale": 1, "out_of_order": 0, "autre": 9}) == {
        "dropped": 2, "stale": 1, "out_of_order": 0}  # SRV-R6.3 : résumé joint à closed


def test_journal_writes_events_counters_and_costs_without_images(tmp_path):
    import json

    from server.session import SessionRecorder
    rec = SessionRecorder(root=tmp_path / "sessions", recordings_root=tmp_path / "rec")
    events = [{"event": "diagnose", "t": 0.0, "procedure": "chain_off_chainring"},
              {"event": "anomaly", "t": 3.5, "step": "x", "message": "m",
               "image": b"\xff\xd8jpeg", "key": "MODEL_API_KEY=secret"}]
    path = rec.finish("abc123", {"bike_id": "velo-1", "success": True, "events": events,
                                 "counters": {"dropped": 1}, "latencies": [12.5],
                                 "costs": {"session_usd": 0.02}})
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["session_id"] == "abc123"  # SRV-R9.1 : méta + compteurs + coûts
    assert lines[0]["costs"] == {"session_usd": 0.02} and lines[0]["latencies"] == [12.5]
    assert [e["event"] for e in lines[1:]] == ["diagnose", "anomaly"]
    text = path.read_text(encoding="utf-8")
    assert "MODEL_API_KEY" not in text and "jpeg" not in text  # SRV-R9.2 : ni image ni clé


def test_recordings_only_when_enabled(tmp_path):
    from server.session import SessionRecorder
    off = SessionRecorder(root=tmp_path / "s", recordings_root=tmp_path / "r", record=False)
    assert off.record_image("abc", 3, b"jpeg") is None  # SRV-R9.3 : inactif par défaut
    assert not list((tmp_path / "r").glob("*")) if (tmp_path / "r").exists() else True
    on = SessionRecorder(root=tmp_path / "s", recordings_root=tmp_path / "r", record=True)
    img = on.record_image("abc", 3, b"jpeg")
    raw = on.record_raw("abc", 3, "<0f>1\n")
    assert img is not None and img.exists() and raw is not None and raw.exists()
    assert (tmp_path / "r" / "abc").is_dir()


def test_fake_models_run_without_network():
    from fixloop.procedures import load_all
    from server.session import build_models
    models = build_models(load_all(), costs=None, fake=True)  # SRV-R10.2, aucun réseau
    pid, raison = models.agent.diagnose([], load_all(), "")
    assert pid == "chain_off_chainring"
    assert models.memory.repeated("velo", "chain_off_chainring") == 0
    perc = models.perception_factory(next(iter(load_all().values())))
    res = perc.done_sync(0, 0.0)
    assert set(res.parts) == {"chain", "chainring"}  # scène synthétique (sim)
    assert res.parts["chainring"].svg_path.startswith("M")
    assert res.error is None


def test_fake_perception_replays_raw_files():
    from pathlib import Path

    import pytest

    from server.session import SimPerception
    for name in ("raw_chain.txt", "raw_chainring.txt"):
        if not (Path("probe_out2") / name).exists():
            pytest.skip("probe_out2/ absent : rejouet brut sauté")
    perc = SimPerception.from_raw("probe_out2", h=464, w=848)  # SRV-R10.2 : ou raw_*.txt
    res = perc.done_sync(0, 0.0)
    assert set(res.parts) == {"chain", "chainring"}
    assert res.parts["chain"].mask.shape == (464, 848)


def test_session_limits_cost_and_duration():
    from server.session import Limits, check_session_limits
    lim = Limits(max_cost_usd=1.5, max_minutes=10)
    assert check_session_limits(0.4, 120.0, lim) == "ok"
    assert check_session_limits(1.5, 120.0, lim) == "ok"  # SRV-R8.2 : au-delà de 1,50 $
    assert check_session_limits(1.51, 120.0, lim) == "cost"
    assert check_session_limits(0.4, 600.0, lim) == "duration"  # ...ou 10 min


def test_new_session_refused_beyond_daily_budget():
    from server.session import Limits, SessionRegistry
    total = [11.0]
    reg = SessionRegistry(Limits(daily_budget_usd=10.0), access_code=None,
                          procedures=PROCS, day_total=lambda: total[0])
    for _ in range(6):
        kind, body = reg.hello(hello(), "10.0.0.1", now=100.0)
        assert (kind, body["code"]) == ("error", "budget")  # SRV-R8.3
    assert reg.live_count == 0
    total[0] = 0.0
    assert reg.hello(hello(), "10.0.0.1", now=200.0)[0] == "hello_ack"  # budget OK de
    # nouveau, et sans blocage IP : le refus budget n'est pas une attaque


def test_stop_closes_unsuccessful():
    async def main():
        import asyncio
        ws, sess = make_live({i: "off" for i in range(9)})
        run = asyncio.create_task(sess.run())
        ws.feed_text({"type": "hello", "bike_id": "velo-1"})
        await wait_for(lambda: any(m.get("type") == "hello_ack" for m in ws.sent))
        ws.feed_text({"type": "start"})
        for t in range(0, 9000, 1000):
            ws.feed_image(t)
            await asyncio.sleep(0.12)
        await wait_for(lambda: sess.sm is not None)
        complete_all(sess)
        await wait_step(sess, "engage_top_teeth")
        ws.feed_text({"type": "stop"})
        await wait_for(lambda: any(m.get("type") == "closed" for m in ws.sent))
        closed = [m for m in ws.sent if m.get("type") == "closed"][0]
        assert closed["success"] is False  # SRV-R6.3 : arrêt demandé, non réussi
        await asyncio.wait_for(run, 10)
    arun(main())


def test_fatal_result_error_closes_with_code():
    async def main():
        import asyncio
        from fixloop.perception import ImageResult
        ws, sess = make_live({0: "off"})
        run = asyncio.create_task(sess.run())
        ws.feed_text({"type": "hello", "bike_id": "velo-1"})
        await wait_for(lambda: any(m.get("type") == "hello_ack" for m in ws.sent))
        ws.feed_text({"type": "start"})
        for t in (0, 1000, 2000):
            ws.feed_image(t)
            await asyncio.sleep(0.12)
        await wait_for(lambda: sess.sm is not None)
        for fi in sorted(sess.perception.futs):
            fut, _ = sess.perception.futs[fi]
            if not fut.done():
                fut.set_result(None)
        await wait_for(lambda: sess.sm is not None)

        async def boom():
            return ImageResult(9, 9.0, {}, {"total_s": 0.0, "attempts": {}},
                               "Clé API refusée", 160, 120)

        sess.pending_frames[9] = (9000, jpeg_bytes(), sess.clock())
        task = asyncio.get_running_loop().create_task(boom())
        task.add_done_callback(lambda t: sess._on_result(t, 9))
        await wait_for(lambda: any(m.get("type") == "error" for m in ws.sent))
        err = [m for m in ws.sent if m.get("type") == "error"][0]
        assert err["code"] == "api_key"  # SRV-R7.2 : clé refusée -> error puis fermeture
        await asyncio.wait_for(run, 10)
    arun(main())
