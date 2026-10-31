"""Client de test : rejoue une vidéo locale vers le serveur, à 1 image/s (SRV-T10).

Envoie `user_done` aux instants donnés et affiche les messages reçus.
Aucune clé ici : elle reste côté serveur. Aucun modèle appelé ici non plus :
avec `FIXLOOP_FAKE_MODELS=1` côté serveur, la session est rejouée sans réseau.

Usage : python scripts/ws_client.py --video probe_out2/input_small.mp4 --done 18,30
Nécessite : websockets (voir requirements.txt).
"""

import argparse
import asyncio
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import websockets
except ImportError:
    sys.exit("installe d'abord les dépendances serveur : pip install -r requirements.txt")

import cv2


def jpeg_under(payload_img, max_bytes=200_000):
    for quality in (90, 80, 70, 60, 50):
        ok, buf = cv2.imencode(".jpg", payload_img,
                               [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok and len(buf) <= max_bytes:
            return bytes(buf)
    raise RuntimeError("image impossible à compresser sous 200 ko")


async def main() -> None:
    ap = argparse.ArgumentParser(description="Rejoue une vidéo vers FixLoop.")
    ap.add_argument("--video", required=True, help="vidéo locale (ex. probe_out2/input_small.mp4)")
    ap.add_argument("--url", default="ws://127.0.0.1:8000/ws/session")
    ap.add_argument("--bike", default="velo-1")
    ap.add_argument("--code", default=None, help="code d'accès si le serveur en exige un")
    ap.add_argument("--done", default="", help="instants user_done en secondes, ex. 18,30")
    ap.add_argument("--duration", type=float, default=None, help="durée rejouée en secondes")
    args = ap.parse_args()
    done_at = sorted(float(x) for x in args.done.split(",") if x.strip())

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"vidéo illisible : {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    step = max(int(round(fps)), 1)

    async with websockets.connect(args.url, max_size=2_000_000) as ws:
        hello = {"type": "hello", "bike_id": args.bike}
        if args.code is not None:
            hello["access_code"] = args.code
        await ws.send(json.dumps(hello))
        print("<", await ws.recv())
        await ws.send(json.dumps({"type": "start"}))
        t = 0
        idx = 0
        n_done = 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            if idx % step == 0:
                t_ms = int(t * 1000)
                frame = b"\x02" + struct.pack(">Q", t_ms) + jpeg_under(img)
                await ws.send(frame)
                while done_at[:n_done + 1] and t >= done_at[n_done]:
                    await ws.send(json.dumps({"type": "user_done"}))
                    print(">", "user_done", f"à {t:.0f} s")
                    n_done += 1
                t += 1.0
                if args.duration is not None and t >= args.duration:
                    break
            idx += 1
        print("fin d'envoi, écoute des messages…")
        async for raw in ws:
            msg = json.loads(raw)
            print("<", msg.get("type"), str(msg)[:220])
            if msg.get("type") in ("closed", "error"):
                break


if __name__ == "__main__":
    asyncio.run(main())
