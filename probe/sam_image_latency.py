"""
FixLoop - test du mode image par image (latence de SAM 3.1).

Question : en envoyant une image à la fois (comme le ferait l'appli en direct),
combien de temps faut-il pour obtenir le verdict « chaîne en place / tombée » ?

Pour chaque image choisie dans ta vidéo :
  - une requête sam-3.1 par pièce (chaîne et plateau), les deux en même temps ;
  - on mesure le temps jusqu'au premier octet et le temps total ;
  - on calcule le taux de contact et l'état, comme dans la fiche chain_off_chainring.

Usage :
  python probe/sam_image_latency.py --video data/velo2.mov
  python probe/sam_image_latency.py --video data/velo2.mov --times 5,10,20,30,45 --width 640
  python probe/sam_image_latency.py --video data/velo2.mov --video-metrics probe_out2/metrics.csv

Sorties (latency_out/) : latency.csv, summary.json, une image annotée par instant testé.
"""

import argparse
import asyncio
import base64
import csv
import json
import os
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from meta_sam_parser import decode_mask_to_raster, image_segmentation_format, parse_responses_stream
from openai import AsyncOpenAI

from sam_api_probe import BASE_URL, RETRYABLE, contact_ratio, state_label

PARTS = {"chain": "bicycle chain", "chainring": "chainring"}
LARGEST = {"chainring"}
COLORS = {"chain": (0, 200, 255), "chainring": (255, 120, 0)}  # BGR


def grab_frames(video: Path, times: list[float], width: int) -> list[tuple[float, np.ndarray]]:
    cap = cv2.VideoCapture(str(video))
    out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            print(f"  t={t}s : image introuvable, ignorée")
            continue
        h0, w0 = f.shape[:2]
        if w0 > width:
            f = cv2.resize(f, (width, int(h0 * width / w0)))
        out.append((t, f))
    cap.release()
    return out


def to_data_url(img: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def image_mask(result, h: int, w: int, largest: bool) -> tuple[np.ndarray | None, float]:
    objs = []
    for rec in result.records:
        if rec.kind != "mask":
            continue
        mh, mw = rec.mask.height, rec.mask.width
        raster = np.frombuffer(decode_mask_to_raster(rec.mask), dtype=np.uint8).reshape(mh, mw).astype(bool)
        m = np.zeros((h, w), dtype=bool)
        x0, y0 = rec.bounds.left, rec.bounds.top
        x1, y1 = min(x0 + mw, w), min(y0 + mh, h)
        m[y0:y1, x0:x1] = raster[: y1 - y0, : x1 - x0]
        objs.append((m, rec.confidence if rec.confidence is not None else 1.0))
    if not objs:
        return None, 0.0
    if largest:
        return max(objs, key=lambda mc: int(mc[0].sum()))
    return np.any([o[0] for o in objs], axis=0), max(o[1] for o in objs)


async def timed(stream, marks: dict):
    async for ev in stream:
        kind = ev.get("type") if isinstance(ev, dict) else getattr(ev, "type", "")
        if "first" not in marks and kind == "response.output_text.delta":
            marks["first"] = time.time()
        yield ev


async def segment_image(client: AsyncOpenAI, data_url: str, prompt: str, attempts: int = 3):
    for attempt in range(1, attempts + 1):
        marks = {}
        t0 = time.time()
        try:
            stream = await client.responses.create(
                model="sam-3.1",
                input=[{"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ]}],
                metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
                stream=True,
            )
            try:
                res = await parse_responses_stream(timed(stream, marks), image_segmentation_format()).final_result()
            finally:
                await stream.close()  # ferme proprement la connexion (évite les messages d'erreur en fin de script)
            t1 = time.time()
            first = marks.get("first", t1) - t0
            return res, first, t1 - t0, attempt
        except RETRYABLE:
            if attempt == attempts:
                raise
            await asyncio.sleep(5 * attempt)


def load_video_states(path: str | None) -> dict[float, str]:
    if not path or not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return {float(r["t_sec"]): r.get("etat", "") for r in csv.DictReader(fh)}


async def run(args):
    load_dotenv()
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        sys.exit("MODEL_API_KEY absente : lance d'abord scripts/check_setup.py.")
    times = [float(x) for x in args.times.split(",")] if args.times else None
    if times is None:
        cap = cv2.VideoCapture(args.video)
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
        cap.release()
        times = [round(dur * (i + 0.5) / args.frames, 1) for i in range(args.frames)]
    frames = grab_frames(Path(args.video), times, args.width)
    if not frames:
        sys.exit("Aucune image lue : vérifie la vidéo.")
    n_req = len(frames) * len(PARTS)
    print(f"{len(frames)} images ({frames[0][1].shape[1]}x{frames[0][1].shape[0]}), "
          f"{n_req} requêtes SAM image ({len(PARTS)} par image, en parallèle).")
    if not args.yes and input("Continuer ? [o/N] ").strip().lower() not in {"o", "oui", "y", "yes"}:
        sys.exit("Annulé.")

    out = Path(args.out_dir)
    out.mkdir(exist_ok=True)
    video_states = load_video_states(args.video_metrics)
    client = AsyncOpenAI(base_url=BASE_URL, api_key=key, timeout=120)
    rows, walls = [], []

    for t, img in frames:
        h, w = img.shape[:2]
        url = to_data_url(img)
        t0 = time.time()
        results = await asyncio.gather(*(segment_image(client, url, p) for p in PARTS.values()))
        wall = time.time() - t0
        walls.append(wall)
        masks = {}
        for (k, _), (res, first, total, attempt) in zip(PARTS.items(), results):
            m, conf = image_mask(res, h, w, k in LARGEST)
            masks[k] = m
            rows.append({"t_sec": t, "part": k, "first_byte_s": round(first, 2), "total_s": round(total, 2),
                         "attempts": attempt, "detected": int(m is not None), "confidence": round(conf, 3)})
        c = contact_ratio(masks.get("chain"), masks.get("chainring"), 6, 6)
        state, color = state_label(c, args.on_max, args.off_min)
        nearest = min(video_states, key=lambda x: abs(x - t)) if video_states else None
        vstate = video_states.get(nearest, "") if nearest is not None else ""
        for r in rows[-len(PARTS):]:
            r.update({"contact": round(c, 3) if c == c else "", "etat_image": state, "etat_video": vstate,
                      "frame_wall_s": round(wall, 2)})
        print(f"  t={t:5.1f}s  verdict en {wall:4.1f} s   contact={c:.3f}  état={state:<8}"
              + (f"  (mode vidéo : {vstate})" if vstate else ""))

        vis = img.copy()
        for k, m in masks.items():
            if m is not None:
                col = np.array(COLORS[k], dtype=np.uint8)
                vis[m] = (0.55 * vis[m] + 0.45 * col).astype(np.uint8)
        cv2.rectangle(vis, (0, 0), (w, 34), (0, 0, 0), -1)
        cv2.putText(vis, f"t={t}s  {state}  contact={c:.2f}  {wall:.1f}s", (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
        cv2.imwrite(str(out / f"frame_{t:05.1f}s.jpg"), vis)

    with (out / "latency.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)

    def q(vals, p):
        vals = sorted(vals)
        return round(vals[min(len(vals) - 1, int(p * len(vals)))], 2)

    per_part = {k: [r["total_s"] for r in rows if r["part"] == k] for k in PARTS}
    agree = [r for r in rows if r["part"] == "chain" and r["etat_video"]]
    summary = {
        "images": len(frames),
        "verdict_par_image_s": {"mediane": round(statistics.median(walls), 2), "p90": q(walls, 0.9),
                                "max": round(max(walls), 2)},
        "par_piece_total_s": {k: {"mediane": round(statistics.median(v), 2), "p90": q(v, 0.9)}
                              for k, v in per_part.items()},
        "premier_octet_mediane_s": round(statistics.median(r["first_byte_s"] for r in rows), 2),
        "relances": sum(r["attempts"] - 1 for r in rows),
        "accord_avec_mode_video": (f"{sum(r['etat_image'] == r['etat_video'] for r in agree)}/{len(agree)}"
                                   if agree else "non comparé"),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    await client.close()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nFichiers écrits dans {out.resolve()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--frames", type=int, default=10, help="nombre d'images réparties sur la vidéo (défaut 10)")
    ap.add_argument("--times", default="", help="instants précis en secondes, ex. 5,10,20 (remplace --frames)")
    ap.add_argument("--width", type=int, default=848, help="largeur envoyée à SAM (défaut 848)")
    ap.add_argument("--video-metrics", default="", help="metrics.csv du mode vidéo pour comparer les états")
    ap.add_argument("--on-max", type=float, default=0.18)
    ap.add_argument("--off-min", type=float, default=0.26)
    ap.add_argument("--out-dir", default="latency_out")
    ap.add_argument("--yes", action="store_true")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
