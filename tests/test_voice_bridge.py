"""Pont Muse Voice Transcribe (spec/04-memory-voice, VOX-T3).

Le synchrone (protocole, découpage) est testé ici. Le bout-en-bout contre un
faux serveur WebSocket local demande des sockets : ignoré ici sur la cause
nommée `PermissionError` (WinError 10013), à vérifier hors sandbox.
"""

import pytest

from fixloop.voice import (FRAME_BYTES, FRAME_MS, KEYWORDS, MODEL, RATE,
                           VoiceBridge, handshake, parse_event, split_frames)


def test_audio_constants_match_transcribe_native_format():
    assert RATE == 24000  # VOX-R1.2 : fréquence native de Transcribe
    assert FRAME_MS == 80  # 80 ms par trame
    assert FRAME_BYTES == 3840  # 1 920 échantillons PCM16 mono
    assert KEYWORDS == ["c'est fait", "aide-moi", "répète", "plateau", "chaîne"]


def test_handshake_shape():
    hs = handshake("cle-test")
    assert hs["authorization"] == {"accessToken": "Bearer cle-test"}  # clé en 1re trame
    assert hs["model"] == MODEL == "muse-voice-transcribe-1.0"
    assert hs["audioEncoding"] == "PCM_24KHZ"  # VOX-R1.2
    assert hs["mode"] == "ENDPOINTING"  # VOX-R1.3 : commandes vocales
    assert hs["languageBias"] == ["French"]
    assert "c'est fait" in hs["keywords"]


def test_parse_event_kinds():
    assert parse_event('{"sessionId": "abc"}')[0] == "ack"  # accusé sans champ type
    kind, data = parse_event('{"type": "speechComplete", "turnId": "t1", "transcript": "c est fait"}')
    assert kind == "speechComplete" and data["transcript"] == "c est fait"  # VOX-R1.3
    assert parse_event('{"type": "speechStart", "turnId": "t1"}')[0] == "speechStart"
    assert parse_event('{"type": "transcript", "transcript": "c", "final": false}')[0] == "transcript"
    assert parse_event('{"type": "error", "message": "quota"}') == (
        "error", {"message": "quota"})
    assert parse_event('{"type": "futur", "x": 1}')[0] == "unknown"  # types inconnus ignorés


def test_split_frames_pads_last():
    assert split_frames(b"") == []
    one = split_frames(bytes(FRAME_BYTES))
    assert len(one) == 1 and len(one[0]) == FRAME_BYTES
    two = split_frames(bytes(FRAME_BYTES + 10))
    assert len(two) == 2 and all(len(f) == FRAME_BYTES for f in two)  # dernière complétée
    assert two[1][:10] == bytes(10) and two[1][10:] == bytes(FRAME_BYTES - 10)


# ------------------------------------------------- bout-en-bout (faux serveur)

def arun(coro):
    import asyncio
    import socket
    try:
        probe = socket.socketpair()  # sonde synchrone : pas de demi-boucle asyncio
        probe[0].close()
        probe[1].close()
    except PermissionError:  # sockets interdits (WinError 10013) ; un TimeoutError est un vrai échec
        coro.close()
        pytest.skip("faux serveur WebSocket interdit ici : à vérifier hors sandbox")
    try:
        return asyncio.run(coro)
    except PermissionError:
        pytest.skip("sockets interdits ici : à vérifier hors sandbox")


def test_bridge_forwards_audio_and_reports_final():
    async def main():
        import asyncio
        import json

        import websockets

        received = {"handshake": None, "frames": 0, "end": False}

        async def fake(ws):
            received["handshake"] = json.loads(await ws.recv())
            await ws.send(json.dumps({"sessionId": "faux-1"}))
            async for raw in ws:
                if isinstance(raw, bytes):
                    received["frames"] += 1
                    if received["frames"] == 2:  # commande après 2 trames
                        await ws.send(json.dumps({"type": "speechComplete", "turnId": "t1",
                                                 "transcript": "c'est fait"}))
                elif json.loads(raw).get("type") == "endStream":
                    received["end"] = True
                    await ws.close(code=1000)

        async with websockets.serve(fake, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            finals = []
            bridge = VoiceBridge("cle-test", on_final=lambda text, t: finals.append(text),
                                 ws_url=f"ws://127.0.0.1:{port}")
            assert await bridge.start() is True
            assert received["handshake"]["mode"] == "ENDPOINTING"
            await bridge.push_audio(bytes(2 * FRAME_BYTES))
            await asyncio.sleep(0.3)
            assert finals == ["c'est fait"]  # VOX-R1.3 : détecté sur speechComplete
            assert received["frames"] == 2
            await bridge.stop()
            assert received["end"] is True  # VOX-R4.1 : endStream à la clôture
            assert bridge.seconds_sent == pytest.approx(0.16)
            return bridge
    bridge = arun(main())
    assert bridge.failures == 0


def test_bridge_gives_up_after_refused_handshake():
    async def main():
        import json

        import websockets

        tries = 0

        async def fake(ws):
            nonlocal tries
            tries += 1
            await ws.recv()  # handshake
            await ws.send(json.dumps({"type": "error", "message": "refusé"}))
            await ws.close(code=1013)  # refus de charge (design 04, section 2.1)

        async with websockets.serve(fake, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            bridge = VoiceBridge("cle-test", ws_url=f"ws://127.0.0.1:{port}")
            assert await bridge.start() is False  # VOX-R3.2 : abandon après 3 relances
            assert tries == 4  # 1 essai + 3 reconnexions
            return bridge
    bridge = arun(main())
    assert bridge.failures >= 3


def test_bridge_keeps_close_reason_and_restarts():
    async def main():
        import asyncio
        import json

        import websockets

        connections = 0

        async def fake(ws):
            nonlocal connections
            connections += 1
            await ws.recv()
            await ws.send(json.dumps({"sessionId": f"faux-{connections}"}))
            if connections == 1:
                await ws.recv()  # une trame, puis fermeture par le serveur
                await ws.close(code=1011, reason="trop de charge")
                return
            async for _ in ws:
                pass

        async with websockets.serve(fake, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            bridge = VoiceBridge("cle-test", ws_url=f"ws://127.0.0.1:{port}")
            assert await bridge.start() is True
            for _ in range(200):
                await bridge.push_audio(bytes(FRAME_BYTES))
                if not bridge.started:
                    break
                await asyncio.sleep(0.01)
            assert bridge.started is False
            assert "1011" in bridge.last_error and "trop de charge" in bridge.last_error
            sent = bridge._frames
            assert await bridge.start() is True  # VOX-R3.3 : même pont, nouvelle liaison
            await bridge.push_audio(bytes(FRAME_BYTES))
            assert bridge.started is True
            await bridge.stop()
            assert bridge.seconds_sent == pytest.approx((sent + 1) * FRAME_MS / 1000)  # tout est compté
    arun(main())


def test_bridge_error_message_never_shows_the_key():
    async def main():
        import asyncio
        import json

        import websockets

        async def fake(ws):
            await ws.recv()
            await ws.send(json.dumps({"sessionId": "faux"}))
            await ws.send(json.dumps({"type": "error", "message": "clé cle-secrete refusée"}))
            await ws.close(code=1008, reason="cle-secrete")

        async with websockets.serve(fake, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            bridge = VoiceBridge("cle-secrete", ws_url=f"ws://127.0.0.1:{port}")
            assert await bridge.start() is True
            for _ in range(200):
                await bridge.push_audio(bytes(FRAME_BYTES))
                if not bridge.started:
                    break
                await asyncio.sleep(0.01)
            assert bridge.started is False
            assert "refusée" in bridge.last_error  # le message du serveur reste, sans la clé
            assert "cle-secrete" not in bridge.last_error
    arun(main())


def test_bridge_survives_failing_callback():
    async def main():
        import asyncio
        import json

        import websockets

        async def fake(ws):
            await ws.recv()
            await ws.send(json.dumps({"sessionId": "faux"}))
            for text in ("un", "deux"):
                await ws.send(json.dumps({"type": "speechComplete", "turnId": text, "transcript": text}))
            async for _ in ws:
                pass

        seen = []

        def on_final(text, t):
            seen.append(text)
            if text == "un":
                raise ValueError("boom")

        async with websockets.serve(fake, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            bridge = VoiceBridge("cle-test", on_final=on_final, ws_url=f"ws://127.0.0.1:{port}")
            assert await bridge.start() is True
            await asyncio.sleep(0.3)
            assert seen == ["un", "deux"]  # une erreur ne coupe pas la lecture
            await bridge.stop()
    arun(main())


def test_stopping_twice_logs_the_seconds_once():
    """Essai réel du 4 nov. : `_voice_run` et `_stop_voice` arrêtent tous deux le pont, 15,12 s comptées deux fois."""
    import asyncio

    class Costs:
        def __init__(self):
            self.units = []

        def add(self, **kw):
            self.units.append(kw["units"])

    costs = Costs()
    bridge = VoiceBridge("cle-test", costs=costs, session_id="s1")
    bridge._frames = 10

    async def main():
        await bridge.stop()
        await bridge.stop()
        bridge._frames = 15  # reconnexion : seules les nouvelles secondes comptent
        await bridge.stop()

    asyncio.run(main())
    assert costs.units == [pytest.approx(0.8), pytest.approx(0.4)]
    assert bridge.seconds_sent == pytest.approx(1.2)
