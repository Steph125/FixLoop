"""Copies transformées des extraits filmés : test de robustesse (spec/08-evaluation, EVAL-R9, EVAL-T11).

Usage : python scripts/augment_clips.py --clips eval/benchmark/clips.csv --labels eval/benchmark/labels.csv
       [--variants zoom13,shift,dark,bright,blur_noise,lowq,rotate4]
       [--out-video data/eval/aug] [--out eval/benchmark/robust] [--sam-cache data/eval/sam]

Chaque variante est un filtre ffmpeg déterministe appliqué à tout l'extrait : mêmes
paramètres pour chaque image, bruit à graine fixe, même nombre d'images, même cadence,
même taille. Aucune panne ni réparation n'est créée, donc les étiquettes de l'original
restent vraies et sont copiées (EVAL-R9.2). SAM 3.1 recalcule ensuite masques et
mesures sur chaque copie avec `benchmark.py` (EVAL-R9.3). Les copies ne sont jamais
des extraits filmés : `split = robust`, fichiers à part (EVAL-R9.4, EVAL-D7).

Zoom : centré sur le plateau mesuré par SAM sur l'original si son cache existe
(`--sam-cache`), sinon sur le centre de l'image. Les vidéos vont dans `data/` (jamais
commitées) ; `robust/clips.csv` et `robust/labels.csv` sont commitées. Aucun appel réseau.
"""

import argparse
import csv
import math
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VARIANTS = {
    "zoom13": {"family": "distance", "what": "recadrage 1/1,3 autour du plateau"},
    "shift": {"family": "cadrage", "what": "recadrage 90 % décalé vers un coin"},
    "dark": {"family": "lumière", "what": "sous-exposition (gamma 0,75)"},
    "bright": {"family": "lumière", "what": "surexposition (gamma 1,25, contraste 0,85)"},
    "blur_noise": {"family": "qualité", "what": "flou 1,5 px et bruit à graine fixe"},
    "lowq": {"family": "qualité", "what": "demi-résolution et compression forte"},
    "rotate4": {"family": "caméra", "what": "rotation de 4°, coins noirs recadrés"},
}
DEFAULT_VARIANTS = tuple(VARIANTS)
CRF = {"lowq": 38}  # compression forte ; 23 partout ailleurs, comme le replay
COLUMNS = ["clip", "file", "duration_s", "lighting", "angle", "distance", "scenario",
           "split", "source", "transform"]


def even(x: float) -> int:
    return max(2, int(x) // 2 * 2)


def inscribed_scale(w: int, h: int, degrees: float) -> float:
    """Échelle du plus grand rectangle de même forme, sans coin noir, après rotation."""
    t = math.radians(abs(degrees))
    a = w / h
    return min(1 / (math.cos(t) + a * math.sin(t)), 1 / (math.cos(t) + math.sin(t) / a))


def crop_around(w: int, h: int, cw: int, ch: int, center) -> tuple[int, int]:
    """Coin haut gauche d'un recadrage cw x ch centré sur `center`, gardé dans l'image."""
    cx, cy = center if center is not None else (w / 2, h / 2)
    x = min(max(0, int(cx - cw / 2)), w - cw)
    y = min(max(0, int(cy - ch / 2)), h - ch)
    return x, y


def filter_for(variant: str, w: int, h: int, center=None) -> str:
    """Filtre ffmpeg d'une variante (mêmes paramètres pour tout l'extrait)."""
    back = f"scale={w}:{h}"  # même taille que l'original
    if variant == "zoom13":
        cw, ch = even(w / 1.3), even(h / 1.3)
        x, y = crop_around(w, h, cw, ch, center)
        return f"crop={cw}:{ch}:{x}:{y},{back}"
    if variant == "shift":
        cw, ch = even(w * 0.9), even(h * 0.9)
        cx, cy = center if center is not None else (w / 2, h / 2)
        # décalé vers le haut à gauche, sauf si le plateau sortirait du cadre
        x, y = (w - cw, h - ch) if (cx > 0.85 * w or cy > 0.85 * h) else (0, 0)
        return f"crop={cw}:{ch}:{x}:{y},{back}"
    if variant == "dark":
        return "eq=gamma=0.75:brightness=-0.06"
    if variant == "bright":
        return "eq=gamma=1.25:contrast=0.85:brightness=0.06"
    if variant == "blur_noise":
        return "gblur=sigma=1.5,noise=alls=12:allf=t+u:all_seed=7"
    if variant == "lowq":
        return f"scale={even(w / 2)}:{even(h / 2)},{back}"
    if variant == "rotate4":
        s = inscribed_scale(w, h, 4.0)
        cw, ch = even(w * s), even(h * s)
        return (f"rotate=4*PI/180:fillcolor=black,"
                f"crop={cw}:{ch}:{(w - cw) // 2}:{(h - ch) // 2},{back}")
    raise ValueError(f"variante inconnue : {variant}")


def transform(src, dest, variant: str, w: int, h: int, center=None) -> None:
    """Une copie : filtre, H.264, sans son ni métadonnées (lieu, date), mêmes images."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg introuvable : installe-le puis relance.")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(src),
           "-vf", filter_for(variant, w, h, center), "-fps_mode", "passthrough",
           "-an", "-map_metadata", "-1", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", str(CRF.get(variant, 23)), "-pix_fmt", "yuv420p", "-threads", "1",
           "-movflags", "+faststart", str(dest)]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        tail = result.stderr.decode("utf-8", "replace").strip().splitlines()[-5:]
        raise RuntimeError(f"ffmpeg en échec (code {result.returncode}) sur {src} ({variant}) :\n"
                           + "\n".join(tail))


def video_info(path) -> tuple[int, float, int, int]:
    """(images, cadence, largeur, hauteur) lus par OpenCV."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"vidéo illisible : {path}")
    info = (int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), float(cap.get(cv2.CAP_PROP_FPS)),
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    return info


def check_copy(src_info, dest) -> None:
    """Même chronologie que l'original (EVAL-R9.2), sinon erreur."""
    n, fps, w, h = src_info
    dn, dfps, dw, dh = video_info(dest)
    if abs(dn - n) > 1 or abs(dfps - fps) > 0.05 or (dw, dh) != (w, h):
        raise RuntimeError(f"copie non conforme {dest} : {dn} images à {dfps:.2f}/s en {dw}x{dh}, "
                           f"original {n} images à {fps:.2f}/s en {w}x{h}")


def chainring_center(sam_dir, w: int, h: int):
    """Centre médian du plateau mesuré par SAM sur l'original, ou None sans cache."""
    raw = Path(sam_dir) / "raw_chainring.txt"
    if not raw.is_file():
        return None
    import numpy as np
    from fixloop.perception import assemble_frames
    frames = assemble_frames({"chainring": raw.read_text(encoding="utf-8")}, h, w, 10.0,
                             {"chainring": "largest"})  # AGENTS règle 2 : le plus gros objet
    xs, ys = [], []
    for fm in frames:
        mask = fm.masks.get("chainring")
        if mask is not None and mask.any():
            yy, xx = np.nonzero(mask)
            xs.append(float(xx.mean()))
            ys.append(float(yy.mean()))
    return (statistics.median(xs), statistics.median(ys)) if xs else None


def copy_labels(rows: list[dict], clip_id: str) -> list[dict]:
    """Étiquettes de l'original, seconde par seconde, sous le nom de la copie."""
    return [{"clip": clip_id, "t": r["t"], "state": r["state"], "done": r["done"]} for r in rows]


def robust_row(clip: dict, variant: str, file: str) -> dict:
    """Ligne de `robust/clips.csv` : matrice de l'original, `split = robust`."""
    row = {k: clip.get(k, "") for k in COLUMNS}
    row.update({"clip": f"{clip['clip']}-{variant}", "file": file, "split": "robust",
                "source": clip["clip"], "transform": variant})
    return row


def read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, fields, rows) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description="Copies transformées des extraits (EVAL-R9).")
    ap.add_argument("--clips", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    ap.add_argument("--out-video", default="data/eval/aug", help="vidéos (jamais commitées)")
    ap.add_argument("--out", default="eval/benchmark/robust", help="clips.csv et labels.csv")
    ap.add_argument("--sam-cache", default="data/eval/sam",
                    help="sorties SAM de l'original, pour centrer le zoom sur le plateau")
    args = ap.parse_args(argv)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    for v in variants:
        if v not in VARIANTS:
            sys.exit(f"variante inconnue : {v} (choix : {', '.join(VARIANTS)})")

    from benchmark import resolve_video  # même résolution des chemins que le benchmark
    labels: dict[str, list] = {}
    for r in read_csv(args.labels):
        labels.setdefault(r["clip"], []).append(r)
    clips = [c for c in read_csv(args.clips) if c.get("split", "test") == "test"]
    rows, label_rows = [], []
    for clip in clips:
        if clip["clip"] not in labels:
            sys.exit(f"extrait sans étiquettes : {clip['clip']} (étiqueter avant, EVAL-R1.4)")
        src = resolve_video(clip, args.clips)
        info = video_info(src)
        center = chainring_center(Path(args.sam_cache) / clip["clip"], info[2], info[3])
        for variant in variants:
            dest = Path(args.out_video) / f"{clip['clip']}-{variant}.mp4"
            transform(src, dest, variant, info[2], info[3], center)
            check_copy(info, dest)
            rows.append(robust_row(clip, variant, dest.as_posix()))
            label_rows += copy_labels(labels[clip["clip"]], f"{clip['clip']}-{variant}")
        where = "plateau mesuré par SAM" if center else "centre de l'image"
        print(f"{clip['clip']} : {len(variants)} copies ({info[0]} images, zoom sur le {where})")
    write_csv(Path(args.out) / "clips.csv", COLUMNS, rows)
    write_csv(Path(args.out) / "labels.csv", ["clip", "t", "state", "done"], label_rows)
    print(f"{len(rows)} copies -> {args.out_video} ; {args.out}/clips.csv, {args.out}/labels.csv")
    print("Ensuite (SAM recalcule tout ; coût estimé affiché avant confirmation) :\n"
          f"  python scripts/benchmark.py --clips {args.out}/clips.csv --labels {args.out}/labels.csv "
          f"--out {args.out} --spark-cache {args.out}/cache --approaches rules,fixloop --settings live")
    return {"copies": len(rows), "clips": len(clips)}


if __name__ == "__main__":
    main()
