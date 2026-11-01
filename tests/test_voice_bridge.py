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
