"""Essai réel de Muse Spark sur des images de ta vidéo (4 appels, quelques centimes).

1. diagnostic sur des images « chaîne tombée » : doit choisir la fiche chain_off_chainring ;
2. arbitrage sur des images « chaîne en place » : doit répondre réussie ;
3. arbitrage sur des images « chaîne tombée » : doit répondre ratée ;
4. explication d'une anomalie : une phrase à lire + la pièce à surligner.

Les images envoyées sont des gros plans du plateau, recadrés avec les boîtes que SAM a déjà trouvées
(probe_out2/raw_chainring.txt, aucun nouvel appel SAM). --no-crop envoie l'image entière pour comparer.

Usage : python scripts/try_agent.py --video data/velo2.mov --off 5,10 --on 25,35
"""

import argparse
import json
import re
import sys
from pathlib import Path

import cv2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixloop.agent import SparkAgent, crop_around  # noqa: E402
from fixloop.geometry import measure  # noqa: E402
from fixloop.models import FrameMasks  # noqa: E402
from fixloop.models import Verdict  # noqa: E402
from fixloop.procedures import load_all  # noqa: E402


def lines_for(text: str, frames: set[int] | None) -> str:
    """Ne garde que les lignes <Nf>… des images voulues (le parser décode chaque masque, c'est lent)."""
    if frames is None:
        return text
    keep = []
    for line in text.splitlines(keepends=True):
        m = re.match(r"<(\d+)f>", line)
        if m and int(m.group(1)) in frames:
            keep.append(line)
    return "".join(keep)


def chainring_boxes(raw_path: str, fps: float, frames: set[int] | None = None) -> tuple[dict[int, tuple], tuple[int, int]] | None:
    """frame -> boîte du plus gros « chainring » (plateau avant), lue dans la sortie SAM déjà enregistrée."""
    path = Path(raw_path)
    if not path.exists():
        return None
    from meta_sam_parser import CompletedOutcome, video_segmentation_format
    text = path.read_text(encoding="utf-8")
    size = re.search(r";w=(\d+);h=(\d+)", text)
    parser = video_segmentation_format().create_parser()
    list(parser.push(lines_for(text, frames)))
    res = parser.finish(CompletedOutcome()).result
    boxes = {}
    for r in res.records:
        if r.kind != "box":
            continue
        b = (r.left, r.top, r.right, r.bottom)
        area = (b[2] - b[0]) * (b[3] - b[1])
        fi = r.frame.frame_index
        if fi not in boxes or area > (boxes[fi][2] - boxes[fi][0]) * (boxes[fi][3] - boxes[fi][1]):
            boxes[fi] = b
    return boxes, (int(size.group(1)), int(size.group(2))) if size else (848, 464)


def crop_frames(frames, times, boxes_info, fps):
    if boxes_info is None:
        print("  (pas de boîtes SAM trouvées : images entières envoyées)")
        return frames
    boxes, (bw, bh) = boxes_info
    out = []
    for f, t in zip(frames, times):
        b = boxes.get(round(t * fps))
        if b is None:
            out.append(f)
            continue
        sx, sy = f.shape[1] / bw, f.shape[0] / bh
        out.append(crop_around(f, (int(b[0] * sx), int(b[1] * sy), int(b[2] * sx), int(b[3] * sy)), margin=0.6))
    return out


def sam_window(raw_dir: str, t: float, fps: float, proc: dict, n: int = 4) -> list:
    """Les n dernières mesures SAM avant l'instant t, recalculées depuis les sorties déjà enregistrées."""
    import numpy as np
    from meta_sam_parser import CompletedOutcome, decode_mask_to_raster, video_segmentation_format
    wanted = set(range(round(t * fps) - n + 1, round(t * fps) + 1))
    masks: dict[int, dict] = {fi: {} for fi in wanted}
    size = None
    for part in ("chain", "chainring"):
        path = Path(raw_dir) / f"raw_{part}.txt"
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        m = re.search(r";w=(\d+);h=(\d+)", text)
        size = (int(m.group(1)), int(m.group(2))) if m else (848, 464)
        parser = video_segmentation_format().create_parser()
        list(parser.push(lines_for(text, wanted)))
        objs: dict[int, list] = {}
        for r in parser.finish(CompletedOutcome()).result.records:
            if r.kind != "mask" or r.frame is None or r.frame.frame_index not in wanted:
                continue
            w, h = size
            full = np.zeros((h, w), bool)
            ras = np.frombuffer(decode_mask_to_raster(r.mask), np.uint8).reshape(r.mask.height, r.mask.width)
            x0, y0 = r.bounds.left, r.bounds.top
            x1, y1 = min(x0 + r.mask.width, w), min(y0 + r.mask.height, h)
            full[y0:y1, x0:x1] = ras[: y1 - y0, : x1 - x0].astype(bool)
            objs.setdefault(r.frame.frame_index, []).append(full)
        for fi, lst in objs.items():
            if proc.get("select", {}).get(part) == "largest":
                masks[fi][part] = max(lst, key=lambda x: int(x.sum()))
            else:
                masks[fi][part] = np.any(lst, axis=0)
    return [measure(FrameMasks(fi, fi / fps, masks[fi]), proc) for fi in sorted(wanted)]


def frames_at(video: str, times: list[float]):
    cap = cv2.VideoCapture(video)
    out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if ok:
            out.append(f)
    cap.release()
    if not out:
        sys.exit(f"Aucune image lue dans {video}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--off", default="5,10", help="instants où la chaîne est tombée")
    ap.add_argument("--on", default="25,35", help="instants où la chaîne est en place")
    ap.add_argument("--raw", default="probe_out2/raw_chainring.txt", help="sortie SAM pour recadrer")
    ap.add_argument("--fps", type=float, default=10.0, help="img/s utilisé par la sonde")
    ap.add_argument("--no-crop", action="store_true", help="envoyer l'image entière")
    a = ap.parse_args()
    load_dotenv()

    procs = load_all()
    agent = SparkAgent(procs)
    step = procs["chain_off_chainring"]["steps"][1]
    t_off = [float(x) for x in a.off.split(",")]
    t_on = [float(x) for x in a.on.split(",")]
    off, on = frames_at(a.video, t_off), frames_at(a.video, t_on)
    if not a.no_crop:
        info = chainring_boxes(a.raw, a.fps, {round(t * a.fps) for t in t_off + t_on})
        off, on = crop_frames(off, t_off, info, a.fps), crop_frames(on, t_on, info, a.fps)
    Path("eval/day2").mkdir(parents=True, exist_ok=True)
    for i, im in enumerate(off + on):
        cv2.imwrite(f"eval/day2/sent_{'off' if i < len(off) else 'on'}_{i}.jpg", im)

    print("1. Diagnostic (chaîne tombée)   ->", agent.diagnose(off, procs, "Aucune réparation enregistrée."))
    proc = procs["chain_off_chainring"]
    raw_dir = str(Path(a.raw).parent)
    w_on, w_off = sam_window(raw_dir, t_on[0], a.fps, proc), sam_window(raw_dir, t_off[0], a.fps, proc)
    fmt = lambda w: [round(m.contact[("chain", "chainring")], 3) for m in w]  # noqa: E731
    print(f"   mesures SAM transmises : en place {fmt(w_on)} | tombée {fmt(w_off)}")
    v = agent.arbitrate(step, on, w_on)
    print("2. Arbitrage (chaîne en place)  ->", v.value, f"(Spark : {v.evidence.get('verdict_brut')},",
          f"confiance {v.evidence.get('confiance')})", "|", v.message, "   attendu : 0 (Spark ne valide jamais)")
    v = agent.arbitrate(step, off, w_off)
    print("3. Arbitrage (chaîne tombée)    ->", v.value, f"(Spark : {v.evidence.get('verdict_brut')},",
          f"confiance {v.evidence.get('confiance')})", "|", v.message, "   attendu : eps, ou 0 s'il doute")
    text, part = agent.explain(step, Verdict("eps", message="La chaîne n'est pas sur les dents du plateau."), off)
    print("4. Explication                  ->", text, "| pièce :", part)

    print("\nJournal des appels :")
    for c in agent.calls:
        print(" ", json.dumps({k: c[k] for k in c if k != "raw"}, ensure_ascii=False))
    Path("eval/day2/try_agent.json").write_text(json.dumps(agent.calls, indent=2, ensure_ascii=False),
                                                encoding="utf-8")
    print("Réponses complètes : eval/day2/try_agent.json ; images envoyées : eval/day2/sent_*.jpg")


if __name__ == "__main__":
    main()
