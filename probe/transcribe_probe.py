"""Sonde Muse Voice Transcribe (spec/04-memory-voice, VOX-T1).

Envoie un enregistrement de ta voix à `muse-voice-transcribe-1.0` et affiche ce que FixLoop en ferait :
transcriptions, commandes détectées (« c'est fait », « aide-moi », « répète »), délai après la fin de chaque phrase.

Deux voies (doc Meta « Speech to text ») :
  - realtime : WebSocket wss://api.meta.ai/v1/asr/realtime, mode ENDPOINTING, PCM16 24 kHz, trames de 80 ms
               envoyées au rythme réel (c'est la voie utilisée par le serveur) ;
  - file     : POST https://api.meta.ai/v1/asr/transcribe (fichier WAV), pour comparer.

Prépare un enregistrement (téléphone, dictaphone…) où tu dis, avec 2 s de silence entre chaque phrase :
  « c'est fait » · « aide-moi » · « je n'ai pas fini » · « répète » · « c'est quoi ce bruit » · « c'est bon »
Aucun autre nom ni information personnelle dans l'enregistrement.

Usage (PowerShell, une commande par ligne) :
  python probe/transcribe_probe.py --audio data/voix_commandes.m4a
  python probe/transcribe_probe.py --audio data/voix_commandes.m4a --mode both

Coût : 0,18 $ par heure d'audio ; un enregistrement de 30 s coûte moins d'un centime par voie.
Sorties : eval/day3/transcribe_probe.json (événements et mesures, sans audio).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from fixloop.voice import CommandDetector, normalize  # noqa: E402

MODEL = "muse-voice-transcribe-1.0"
WS_URL = "wss://api.meta.ai/v1/asr/realtime"
FILE_URL = "https://api.meta.ai/v1/asr/transcribe"
RATE = 24000
FRAME_MS = 80
FRAME_BYTES = RATE * 2 * FRAME_MS // 1000          # 3 840 octets
PRICE_PER_HOUR = 0.18
KEYWORDS = ["c'est fait", "aide-moi", "répète", "plateau", "chaîne"]
OUT = ROOT / "eval" / "day3" / "transcribe_probe.json"


def to_wav_24k(src: Path, dst: Path) -> None:
    """Convertit n'importe quel audio en WAV mono PCM16 24 kHz (commande donnée par la doc Meta)."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(RATE),
                    "-c:a", "pcm_s16le", "-map_metadata", "-1", str(dst)], check=True)


def read_pcm(wav_path: Path) -> bytes:
    with wave.open(str(wav_path), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == RATE
        return w.readframes(w.getnframes())


def handshake(key: str) -> dict:
    return {"authorization": {"accessToken": f"Bearer {key}"}, "model": MODEL,
            "audioEncoding": "PCM_24KHZ", "mode": "ENDPOINTING", "partialMode": "CUMULATIVE",
            "emitAudioProgress": False, "languageBias": ["French"], "keywords": KEYWORDS}


# ------------------------------------------------------------------ voie temps réel
async def run_realtime(key: str, pcm: bytes) -> dict:
    import websockets

    events: list[dict] = []
    detector = CommandDetector()
    t0 = None
    async with websockets.connect(WS_URL, max_size=None, open_timeout=15) as ws:
        await ws.send(json.dumps(handshake(key)))
        ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if "type" in ack:                      # un accusé n'a pas de champ type
            raise RuntimeError(f"pas d'accusé de réception : {ack}")
        print(f"  session ouverte : {ack.get('sessionId')}")

        async def sender():
            nonlocal t0
            t0 = time.monotonic()
            silence = bytes(FRAME_BYTES)
            frames = [pcm[i:i + FRAME_BYTES] for i in range(0, len(pcm), FRAME_BYTES)]
            frames += [silence] * (2000 // FRAME_MS)              # 2 s de silence pour clore le dernier tour
            for n, fr in enumerate(frames):
                await ws.send(fr)
                # rythme réel : la trame n part à t0 + n × 80 ms
                delay = t0 + (n + 1) * FRAME_MS / 1000 - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
            await ws.send(json.dumps({"type": "endStream"}))

        send_task = asyncio.create_task(sender())
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                ev = json.loads(raw)
                wall = time.monotonic() - (t0 or time.monotonic())
                ev_out = {"wall_s": round(wall, 3), **{k: v for k, v in ev.items() if k != "sessionId"}}
                kind = ev.get("type")
                if kind == "speechComplete":
                    audio_s = ev.get("audioProcessedMs", 0) / 1000
                    ev_out["latency_s"] = round(wall - audio_s, 3)
                    cmd = detector.feed(ev.get("transcript", ""), wall)
                    ev_out["command"] = cmd
                    print(f"  [{wall:6.2f} s] « {ev.get('transcript')} » → commande : {cmd} "
                          f"(délai {ev_out['latency_s']:.2f} s)")
                elif kind == "error":
                    print(f"  ERREUR : {ev.get('message')}")
                events.append(ev_out)
        finally:
            await send_task
    return {"events": events}


# ------------------------------------------------------------------ voie fichier
def run_file(key: str, wav_path: Path) -> dict:
    import httpx

    settings = {k: v for k, v in handshake(key).items() if k != "authorization"}
    settings["mode"] = "ENDPOINTING"
    t0 = time.monotonic()
    with wav_path.open("rb") as fh:
        r = httpx.post(FILE_URL, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                       files={"request": (None, json.dumps(settings), "application/json"),
                              "audio": (wav_path.name, fh, "audio/wav")}, timeout=120)
    took = time.monotonic() - t0
    if r.status_code != 200:
        print(f"  ERREUR HTTP {r.status_code} : {r.text[:300]}")
        return {"status": r.status_code, "seconds": round(took, 2)}
    data = r.json()
    detector = CommandDetector()
    turns = []
    for turn in data.get("turns", []):
        cmd = detector.feed(turn.get("transcript", ""), turn.get("endMs", 0) / 1000)
        turns.append({**turn, "command": cmd})
        print(f"  [{turn.get('startMs', 0) / 1000:6.2f} s] « {turn.get('transcript')} » → commande : {cmd}")
    if not turns:
        print(f"  transcription : « {data.get('transcript')} »")
    return {"status": 200, "seconds": round(took, 2), "transcript": data.get("transcript"),
            "audioDurationMs": data.get("audioDurationMs"), "turns": turns}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True, help="enregistrement de ta voix (m4a, mp3, wav…)")
    ap.add_argument("--mode", choices=["realtime", "file", "both"], default="realtime")
    ap.add_argument("--yes", action="store_true", help="ne pas demander de confirmation")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        sys.exit("MODEL_API_KEY absente de .env")

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "voix_24k.wav"
        to_wav_24k(Path(args.audio), wav)
        pcm = read_pcm(wav)
        seconds = len(pcm) / (RATE * 2)
        ways = 2 if args.mode == "both" else 1
        cost = seconds / 3600 * PRICE_PER_HOUR * ways
        print(f"Audio : {seconds:.1f} s. Coût estimé : {cost:.4f} $ ({ways} voie(s)).")
        if not args.yes and input("Continuer ? [o/N] ").strip().lower() not in ("o", "oui", "y"):
            return

        result = {"date": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL, "audio_s": round(seconds, 2),
                  "settings": {k: v for k, v in handshake("x").items() if k != "authorization"}}
        if args.mode in ("realtime", "both"):
            print("Voie temps réel (WebSocket, ENDPOINTING) :")
            result["realtime"] = asyncio.run(run_realtime(key, pcm))
        if args.mode in ("file", "both"):
            print("Voie fichier (POST /asr/transcribe) :")
            result["file"] = run_file(key, wav)

    lat = [e["latency_s"] for e in result.get("realtime", {}).get("events", []) if "latency_s" in e]
    if lat:
        lat.sort()
        result["latency_median_s"] = lat[len(lat) // 2]
        print(f"Délai après la fin de phrase : médiane {result['latency_median_s']:.2f} s, max {lat[-1]:.2f} s "
              f"(cible ≤ 2 s, VOX-R1.4).")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Résultats : {OUT.relative_to(ROOT)}")
    _ = normalize  # importée pour vérifier que le module voix est présent


if __name__ == "__main__":
    main()
