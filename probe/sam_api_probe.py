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
  python probe/sam_api_probe.py --video data/velo.mov --chunk-seconds 5   # morceaux plus courts si ça coupe
  python probe/sam_api_probe.py --video data/velo.mp4 \
      --prompts-json '{"chain":"bike chain","chainring":"front chainring","derailleur":"rear derailleur"}'

Sorties (probe_out/) : annotated.mp4, metrics.csv, contact_plot.png, summary.json,
raw_<pièce>.txt (sortie brute de SAM, utile pour déboguer).
"""

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
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
from meta_sam_parser import (
    CompletedOutcome,
    ResponsesStreamError,
    decode_mask_to_raster,
    parse_responses_stream,
    video_segmentation_format,
)
from openai import APIConnectionError, AsyncOpenAI

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


RETRYABLE = (APIConnectionError, ResponsesStreamError, ConnectionError, TimeoutError)


async def segment_with_retry(client: AsyncOpenAI, file_id: str, key: str, prompt: str, attempts: int = 3):
    """Relance une requête coupée par le réseau (connexion fermée par le serveur, Wi-Fi…)."""
    for attempt in range(1, attempts + 1):
        try:
            t0 = time.time()
            res = await segment(client, file_id, prompt)
            print(f"  {key:<11} terminé en {time.time() - t0:.0f} s")
            return res
        except RETRYABLE as e:
            print(f"  {key:<11} connexion coupée après {time.time() - t0:.0f} s ({type(e).__name__})")
            if attempt == attempts:
                raise
            wait = 10 * attempt
            print(f"  {key:<11} nouvel essai dans {wait} s ({attempt + 1}/{attempts})")
            await asyncio.sleep(wait)


def parse_raw(text: str):
    """Relit une sortie brute SAM enregistrée, sans appel API."""
    parser = video_segmentation_format().create_parser()
    list(parser.push(text))
    return parser.finish(CompletedOutcome()).result


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def plan_chunks(n_frames: int, chunk_frames: int, min_frames: int = 50) -> list[tuple[int, int]]:
    """Découpe [0, n_frames) en morceaux ; un dernier morceau trop court est fusionné au précédent."""
    if chunk_frames <= 0 or chunk_frames >= n_frames:
        return [(0, n_frames)]
    starts = list(range(0, n_frames, chunk_frames))
    if len(starts) > 1 and n_frames - starts[-1] < min_frames:
        starts.pop()
    return [(a, starts[i + 1] if i + 1 < len(starts) else n_frames) for i, a in enumerate(starts)]


def extract_chunk(src: Path, dst: Path, a: int, b: int, fps: float) -> None:
    """Extrait les images [a, b) de la vidéo préparée, à l'image près."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                    "-vf", f"select=between(n\\,{a}\\,{b - 1}),setpts=N/({fps}*TB)", "-r", str(fps),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-an", str(dst)], check=True)


FRAME_MARK = re.compile(r"<(\d+)f>")


def shift_frames(text: str, offset: int) -> str:
    """Décale les numéros d'image d'une sortie SAM (les données de masque ne contiennent jamais '<')."""
    if not text:
        return ""
    text = FRAME_MARK.sub(lambda m: f"<{int(m.group(1)) + offset}f>", text)
    return text if text.endswith("\n") else text + "\n"


def masks_by_frame(result, h: int, w: int, conf_thr: float,
                   largest: bool = False) -> dict[int, tuple[np.ndarray, float, int]]:
    """frame_index -> (masque plein cadre, meilleure confiance, nb d'objets gardés).

    largest=True garde seulement le plus gros objet de chaque image (ex. le plateau avant
    plutôt que les pignons arrière, que SAM appelle aussi « chainring »).
    """
    per_frame: dict[int, list] = {}
    for rec in result.records:
        if rec.kind != "mask" or rec.frame is None:
            continue
        conf = rec.confidence if rec.confidence is not None else 1.0
        if conf < conf_thr:
            continue
        mh, mw = rec.mask.height, rec.mask.width
        raster = np.frombuffer(decode_mask_to_raster(rec.mask), dtype=np.uint8).reshape(mh, mw).astype(bool)
        # Le masque couvre la boîte : on le replace aux coordonnées de la boîte dans l'image.
        m = np.zeros((h, w), dtype=bool)
        x0, y0 = rec.bounds.left, rec.bounds.top
        x1, y1 = min(x0 + mw, w), min(y0 + mh, h)
        m[y0:y1, x0:x1] = raster[: y1 - y0, : x1 - x0]
        per_frame.setdefault(rec.frame.frame_index, []).append((m, conf))
    out = {}
    for fi, objs in per_frame.items():
        if largest:
            m, conf = max(objs, key=lambda mc: int(mc[0].sum()))
            out[fi] = (m, conf, 1)
        else:
            out[fi] = (np.any([o[0] for o in objs], axis=0), max(o[1] for o in objs), len(objs))
    return out


def state_label(c: float, on_max: float, off_min: float) -> tuple[str, tuple[int, int, int]]:
    """Lecture de la fiche chain_off_chainring (eval/day1) : contact faible = chaîne en place."""
    if c != c:
        return "?", (200, 200, 200)
    if c <= on_max:
        return "EN PLACE", (80, 200, 80)
    if c >= off_min:
        return "TOMBEE", (60, 60, 230)
    return "?", (0, 200, 255)


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
    keys = list(prompts)
    chunk_frames = int(round(args.chunk_seconds * args.fps)) if args.chunk_seconds > 0 else 0
    chunks = plan_chunks(n_frames, max(chunk_frames, 50) if chunk_frames else 0)
    src_hash = file_hash(Path(args.video))
    raw: dict[str, dict[int, str]] = {k: {} for k in keys}
    jobs = []
    for k in keys:
        for ci, (a, b) in enumerate(chunks):
            ck = hashlib.sha256(json.dumps(
                [src_hash, args.fps, args.width, args.max_seconds, prompts[k], a, b]).encode()).hexdigest()[:16]
            f = out / f"raw_{k}_{ci:02d}.txt"
            kf = out / f"raw_{k}_{ci:02d}.key"
            if f.exists() and kf.exists() and kf.read_text().strip() == ck:
                raw[k][ci] = f.read_text(encoding="utf-8")
            else:
                jobs.append((k, ci, a, b, ck))
    reused = len(keys) * len(chunks) - len(jobs)
    if reused:
        print(f"  {reused} morceau(x) déjà segmenté(s) : réutilisé(s) sans appel API")

    billed = sum(max(b - a, 50) for _, _, a, b, _ in jobs)
    print(f"Vidéo préparée : {n_frames} images {w}x{h} à {args.fps} img/s, découpée en {len(chunks)} "
          f"morceau(x). {len(jobs)} requête(s) SAM à faire, environ {billed} images facturées.")
    if jobs and not args.yes and input("Continuer ? [o/N] ").strip().lower() not in {"o", "oui", "y", "yes"}:
        sys.exit("Annulé.")

    t0 = time.time()
    if jobs:
        client = AsyncOpenAI(base_url=BASE_URL, api_key=key, timeout=900)
        uploads: dict[int, str] = {}

        async def file_for(ci: int) -> str:
            if ci not in uploads:
                a, b = chunks[ci]
                path = small if len(chunks) == 1 else out / f"chunk_{ci:02d}.mp4"
                if len(chunks) > 1:
                    extract_chunk(small, path, a, b, args.fps)
                with path.open("rb") as fh:
                    uploads[ci] = (await client.files.create(file=fh, purpose="user_data")).id
            return uploads[ci]

        for k, ci, a, b, ck in jobs:
            label = f"{k} {ci + 1}/{len(chunks)}"
            res = await segment_with_retry(client, await file_for(ci), label, prompts[k])
            # enregistré tout de suite : en cas d'échec plus loin, ce morceau n'est pas à repayer
            (out / f"raw_{k}_{ci:02d}.txt").write_text(res.raw_output, encoding="utf-8")
            (out / f"raw_{k}_{ci:02d}.key").write_text(ck)
            raw[k][ci] = res.raw_output
    elapsed = time.time() - t0
    print(f"Segmentation terminée en {elapsed:.1f} s")

    results = []
    for k in keys:
        merged = "".join(shift_frames(raw[k][ci], a) for ci, (a, _) in enumerate(chunks))
        (out / f"raw_{k}.txt").write_text(merged, encoding="utf-8")
        results.append(parse_raw(merged))

    largest = {x.strip() for x in args.largest.split(',') if x.strip()}
    per_part = {}
    for k, res in zip(keys, results):
        if res.diagnostics:
            print(f"  {k}: {len(res.diagnostics)} avertissement(s) du parser (voir raw_{k}.txt)")
        if getattr(res.outcome, "status", "completed") != "completed":
            print(f"  {k}: réponse incomplète ({res.outcome})")
        per_part[k] = masks_by_frame(res, h, w, args.conf_thr, largest=k in largest)

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
        state, color = state_label(c_ring, args.on_max, args.off_min)
        cv2.putText(vis, state, (8, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA)
        writer.write(vis)

        row = {"frame": i, "t_sec": round(t, 2), "etat": state,
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
    ap.add_argument("--largest", default="chainring",
                    help="pièces pour lesquelles on garde seulement le plus gros objet (défaut : chainring)")
    ap.add_argument("--on-max", type=float, default=0.18, help="contact max pour « chaîne en place »")
    ap.add_argument("--off-min", type=float, default=0.26, help="contact min pour « chaîne tombée »")
    ap.add_argument("--chunk-seconds", type=float, default=10.0,
                    help="durée de chaque morceau envoyé à SAM (défaut 10 s, 0 = vidéo entière)")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
