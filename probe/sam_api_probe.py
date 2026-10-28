"""
FixLoop - sonde SAM 3.1 via la Meta Model API (jour 1).

Question à trancher : SAM 3.1 segmente-t-il bien chaîne, plateau et dérailleur
sur une vidéo de TON vélo, et le taux de contact chaîne/plateau chute-t-il
nettement quand la chaîne déraille ?

Ce que fait le script :
  1. réduit la vidéo (10 images/s, 960 px de large, H.264) avec ffmpeg
     pour limiter le coût et le volume de réponse ;
  2. la téléverse une seule fois (Files API) ;
  3. lance une requête sam-3.1 par pièce, en parallèle (l'API n'accepte
     qu'un concept par requête) ;
  4. décode les masques avec meta-sam-parser et calcule, image par image,
     la part du bord du plateau couverte par la chaîne ;
  5. écrit une vidéo annotée, un CSV, une courbe et un résumé.

Usage :
  python probe/sam_api_probe.py --video data/velo.mp4
  python probe/sam_api_probe.py --video data/velo.mov --fps 5 --max-seconds 40
  python probe/sam_api_probe.py --video data/velo.mp4 \
      --prompts-json '{"chain":"bike chain","chainring":"front chainring","derailleur":"rear derailleur"}'

Sorties (probe_out/) : annotated.mp4, metrics.csv, contact_plot.png, summary.json,
raw_<pièce>.txt (sortie brute de SAM, utile pour déboguer).
"""

import argparse
import asyncio
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from meta_sam_parser import decode_mask_to_raster, parse_responses_stream, video_segmentation_format
from openai import AsyncOpenAI

BASE_URL = "https://api.meta.ai/v1"
DEFAULT_PROMPTS = {
    "chain": "bicycle chain",
    "chainring": "chainring",
    "derailleur": "rear derailleur",
}
COLORS = {"chain": (0, 200, 255), "chainring": (255, 120, 0), "derailleur": (180, 0, 220)}  # BGR


# ---------------------------------------------------------------- préparation
def preprocess(src: Path, dst: Path, fps: float, width: int, max_seconds: float | None) -> None:
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg introuvable : installe-le (voir le guide), puis relance.")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-vf", f"fps={fps},scale='min({width},iw)':-2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-an", str(dst)]
    subprocess.run(cmd, check=True)


def read_frames(path: Path) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    return frames


# ---------------------------------------------------------------- appels SAM
async def segment(client: AsyncOpenAI, file_id: str, prompt: str):
    stream = await client.responses.create(
        model="sam-3.1",
        input=[{
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_video", "file_id": file_id},
            ],
        }],
        metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
        stream=True,
    )
    return await parse_responses_stream(stream, video_segmentation_format()).final_result()


def masks_by_frame(result, h: int, w: int, conf_thr: float) -> dict[int, tuple[np.ndarray, float, int]]:
    """frame_index -> (masque fusionné plein cadre, meilleure confiance, nb d'objets gardés)."""
    out: dict[int, list] = {}
    for rec in result.records:
        if rec.kind != "mask" or rec.frame is None:
            continue
        conf = rec.confidence if rec.confidence is not None else 1.0
        if conf < conf_thr:
            continue
        fi = rec.frame.frame_index
        if fi not in out:
            out[fi] = [np.zeros((h, w), dtype=bool), 0.0, 0]
        mh, mw = rec.mask.height, rec.mask.width
        raster = np.frombuffer(decode_mask_to_raster(rec.mask), dtype=np.uint8).reshape(mh, mw).astype(bool)
        # Le masque couvre la boîte : on le replace aux coordonnées de la boîte dans l'image.
        x0, y0 = rec.bounds.left, rec.bounds.top
        x1, y1 = min(x0 + mw, w), min(y0 + mh, h)
        out[fi][0][y0:y1, x0:x1] |= raster[: y1 - y0, : x1 - x0]
        out[fi][1] = max(out[fi][1], conf)
        out[fi][2] += 1
    return {k: tuple(v) for k, v in out.items()}


# ---------------------------------------------------------------- géométrie
def outer_edge(mask: np.ndarray, px: int) -> np.ndarray:
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    edge = np.zeros(mask.shape, dtype=np.uint8)
    cv2.drawContours(edge, cnts, -1, 1, thickness=px)
    return edge.astype(bool)


def contact_ratio(a: np.ndarray | None, b: np.ndarray | None, dilate_px: int, edge_px: int) -> float:
    """Part du bord extérieur de B couverte par A dilaté. NaN si une pièce manque."""
    if a is None or b is None or not a.any() or not b.any():
        return float("nan")
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1))
    a_d = cv2.dilate(a.astype(np.uint8), k).astype(bool)
    edge = outer_edge(b, edge_px)
    return float((edge & a_d).sum() / max(int(edge.sum()), 1))


# ---------------------------------------------------------------- programme
async def run(args) -> None:
    load_dotenv()
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        sys.exit("MODEL_API_KEY absente : lance d'abord scripts/check_setup.py.")
    prompts = json.loads(args.prompts_json) if args.prompts_json else DEFAULT_PROMPTS

    out = Path(args.out_dir)
    out.mkdir(exist_ok=True)
    small = out / "input_small.mp4"
    preprocess(Path(args.video), small, args.fps, args.width, args.max_seconds)
    frames = read_frames(small)
    if not frames:
        sys.exit("Aucune image lue après conversion : vérifie la vidéo.")
    h, w = frames[0].shape[:2]
    n_frames = len(frames)
    billed = max(n_frames, 50) * len(prompts)
    print(f"Vidéo préparée : {n_frames} images {w}x{h} à {args.fps} img/s, "
          f"{len(prompts)} requêtes SAM, environ {billed} images facturées au total.")
    if not args.yes and input("Continuer ? [o/N] ").strip().lower() not in {"o", "oui", "y", "yes"}:
        sys.exit("Annulé.")

    client = AsyncOpenAI(base_url=BASE_URL, api_key=key)
    with small.open("rb") as fh:
        uploaded = await client.files.create(file=fh, purpose="user_data")
    print(f"Vidéo téléversée : {uploaded.id}")

    t0 = time.time()
    keys = list(prompts)
    results = await asyncio.gather(*(segment(client, uploaded.id, prompts[k]) for k in keys))
    elapsed = time.time() - t0
    print(f"Segmentation terminée en {elapsed:.1f} s")

    per_part = {}
    for k, res in zip(keys, results):
        (out / f"raw_{k}.txt").write_text(res.raw_output, encoding="utf-8")
        if res.diagnostics:
            print(f"  {k}: {len(res.diagnostics)} avertissement(s) du parser (voir raw_{k}.txt)")
        if getattr(res.outcome, "status", "completed") != "completed":
            print(f"  {k}: réponse incomplète ({res.outcome})")
        per_part[k] = masks_by_frame(res, h, w, args.conf_thr)

    # métriques + vidéo annotée
    raw_video = out / "annotated_raw.mp4"
    writer = cv2.VideoWriter(str(raw_video), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (w, h))
    rows = []
    for i, frame in enumerate(frames):
        m = {k: per_part[k].get(i) for k in keys}
        chain = m.get("chain")[0] if m.get("chain") else None
        ring = m.get("chainring")[0] if m.get("chainring") else None
        der = m.get("derailleur")[0] if m.get("derailleur") else None
        c_ring = contact_ratio(chain, ring, args.dilate_px, args.edge_px)
        c_der = contact_ratio(chain, der, args.dilate_px, args.edge_px)

        vis = frame.copy()
        for k in keys:
            if m[k] is not None and m[k][0].any():
                color = np.array(COLORS.get(k, (0, 255, 0)), dtype=np.uint8)
                sel = m[k][0]
                vis[sel] = (0.55 * vis[sel] + 0.45 * color).astype(np.uint8)
        t = i / args.fps
        label = f"t={t:5.1f}s  contact chaine/plateau={c_ring:.2f}  chaine/derailleur={c_der:.2f}"
        cv2.rectangle(vis, (0, 0), (w, 30), (0, 0, 0), -1)
        cv2.putText(vis, label, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        writer.write(vis)

        row = {"frame": i, "t_sec": round(t, 2),
               "contact_chain_chainring": c_ring, "contact_chain_derailleur": c_der}
        for k in keys:
            row[f"{k}_detected"] = int(m[k] is not None)
            row[f"{k}_confidence"] = round(m[k][1], 3) if m[k] else 0.0
            row[f"{k}_objects"] = m[k][2] if m[k] else 0
            row[f"{k}_area_px"] = int(m[k][0].sum()) if m[k] else 0
        rows.append(row)
    writer.release()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_video), "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                    str(out / "annotated.mp4")], check=True)
    raw_video.unlink(missing_ok=True)

    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)

    ts = [r["t_sec"] for r in rows]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(ts, [r["contact_chain_chainring"] for r in rows], marker="o", ms=2, label="chaîne / plateau")
    ax.plot(ts, [r["contact_chain_derailleur"] for r in rows], marker="o", ms=2, label="chaîne / dérailleur")
    ax.set(xlabel="temps (s)", ylabel="taux de contact", ylim=(0, 1))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "contact_plot.png", dpi=130)

    def median(vals):
        v = [x for x in vals if x == x]
        return round(float(np.median(v)), 3) if v else None

    summary = {
        "images": n_frames,
        "duree_segmentation_s": round(elapsed, 1),
        "contact_chaine_plateau_mediane": median([r["contact_chain_chainring"] for r in rows]),
        "detection": {
            k: {
                "taux_detection": round(sum(r[f"{k}_detected"] for r in rows) / n_frames, 2),
                "confiance_moyenne_si_detecte": round(float(np.mean(
                    [r[f"{k}_confidence"] for r in rows if r[f"{k}_detected"]] or [0])), 3),
            }
            for k in keys
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nFichiers écrits dans {out.resolve()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, help="vidéo MP4 ou MOV de ton vélo")
    ap.add_argument("--fps", type=float, default=10.0, help="images/s envoyées à SAM (défaut 10)")
    ap.add_argument("--width", type=int, default=960, help="largeur max en pixels (défaut 960)")
    ap.add_argument("--max-seconds", type=float, default=60.0, help="durée max analysée (défaut 60 s)")
    ap.add_argument("--conf-thr", type=float, default=0.4, help="confiance min d'un objet (défaut 0.4)")
    ap.add_argument("--dilate-px", type=int, default=6)
    ap.add_argument("--edge-px", type=int, default=6)
    ap.add_argument("--prompts-json", default="", help="remplace les prompts par défaut")
    ap.add_argument("--out-dir", default="probe_out")
    ap.add_argument("--yes", action="store_true", help="ne pas demander de confirmation")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
