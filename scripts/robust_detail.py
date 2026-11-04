"""Détail par extrait et par copie : la remise est-elle validée ? (spec/08-evaluation, EVAL-R9.5).

Un 0 fausse validation ne prouve rien si rien n'est validé, et `missed_validations` ne regarde que les
segments `on` de 5 s ou plus après un « c'est fait ». Ce script dit donc, au réglage `live` et pour les
règles SAM, si la remise est validée, ce que SAM voit et les images mal lues.

Hors ligne, aucun appel : relit les sorties SAM en cache (`data/eval/sam/<clip>`), ne décode que
l'image utile de chaque seconde, et refuse d'écrire si ses totaux diffèrent de ceux du benchmark.

Usage : python scripts/robust_detail.py
"""

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark import SAM_FPS, read_sam_cache, resolve_video, setting_view  # noqa: E402
from fixloop.benchmark import (NoSparkAgent, classify_contact, drive_measures,  # noqa: E402
                               false_validations, image_confusion, label_at, missed_validations,
                               read_labels, validated_events)

PID = "chain_off_chainring"
COLUMNS = ["clip", "source", "transform", "sam_silent", "images_live", "chain_seen", "chainring_seen",
           "engage_t", "engage_label", "false_validations", "transition_validations",
           "missed_validations", "off_read_seated", "on_read_fallen"]


def live_frames(merged: dict) -> set[int]:
    """Images utiles au réglage `live` : la plus proche de chaque seconde, et la dernière (durée)."""
    present: set[int] = set()
    for text in merged.values():
        present |= {int(x) for x in re.findall(r"^<(\d+)f>", text, flags=re.M)}
    if not present:
        return set()
    fps, ordered = int(SAM_FPS), sorted(present)
    keep = {min(ordered, key=lambda fi: abs(fi - s * fps)) for s in range(max(present) // fps + 1)}
    return keep | {max(present)}


def detail_row(clip: str, source: str, transform: str, frames: list, labels: list,
               procedure_id: str, procedure: dict) -> dict:
    """Une ligne de `detail.csv` : `frames` vide = SAM muet sur tout l'extrait."""
    from fixloop.geometry import measure
    row = dict.fromkeys(COLUMNS, 0)
    row.update(clip=clip, source=source, transform=transform, engage_t="", engage_label="",
               sam_silent=0 if frames else 1, _confusion={})
    if not frames:
        return row
    all_m = [measure(fm, procedure) for fm in frames]
    ms, picked = setting_view(all_m, list(range(len(all_m))), "live")
    done_at = [float(r["t"]) for r in labels if r["done"] == 1]
    session = drive_measures(procedure_id, ms, done_at, "live", agent=NoSparkAgent(procedure_id),
                             keyframes=[None] * len(ms))
    engage = procedure["steps"][1]["id"]  # étape de remise évaluée, comme `run_clip_real`
    first = next((e for e in validated_events(session.log) if e.get("step") == engage), None)
    fv = false_validations(session.log, labels)
    require_done = any(s.get("requires_done") for s in procedure["steps"])
    row.update(images_live=len(ms),
               chain_seen=sum("chain" in frames[i].masks for i in picked),
               chainring_seen=sum("chainring" in frames[i].masks for i in picked),
               false_validations=fv["false"], transition_validations=fv["transition"],
               missed_validations=missed_validations(session.log, labels, require_done, done_at),
               _confusion=image_confusion(ms, labels))
    if first is not None:
        row.update(engage_t=round(float(first.get("t", 0.0)), 1),
                   engage_label=label_at(labels, first.get("t", 0.0)))
    row["off_read_seated"] = sum(1 for m in ms if label_at(labels, m.t) == "off"
                                 and classify_contact(m.contact.get(("chain", "chainring"))) == "en place")
    row["on_read_fallen"] = sum(1 for m in ms if label_at(labels, m.t) == "on"
                                and classify_contact(m.contact.get(("chain", "chainring"))) == "tombée")
    return row


def rows_for(clips_path, labels_path, sam_root, procedure) -> list[dict]:
    """Les lignes d'un `clips.csv`, sans jamais décoder les autres images."""
    import cv2
    from fixloop.perception import assemble_frames, lines_for
    labels = read_labels(labels_path)
    rows = []
    with open(clips_path, encoding="utf-8", newline="") as fh:
        clips = list(csv.DictReader(fh))
    for clip in clips:
        name = clip["clip"]
        merged = read_sam_cache(Path(sam_root) / name, procedure)
        keep = live_frames(merged)
        frames = []
        if keep:
            cap = cv2.VideoCapture(str(resolve_video(clip, clips_path)))
            h, w = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            cap.release()
            frames = assemble_frames({p: lines_for(t, keep) for p, t in merged.items()},
                                     h, w, SAM_FPS, procedure.get("select", {}))
        rows.append(detail_row(name, clip.get("source") or name, clip.get("transform") or "original",
                               frames, labels[name], PID, procedure))
        print(name, "SAM muet" if rows[-1]["sam_silent"] else
              f"remise : {rows[-1]['engage_t'] or 'non'} ({rows[-1]['engage_label'] or '-'})", flush=True)
    return rows


def check_results(rows: list[dict], results_path) -> list[str]:
    """Écarts avec `results.csv` (règles SAM, `live`) : la preuve que ce détail est le même calcul."""
    mine = {r["clip"]: r for r in rows}
    gaps = []
    with open(results_path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["approach"] != "rules" or r["setting"] != "live" or r["clip"] not in mine:
                continue
            for col, other in (("false_validations", "false_validations"),
                               ("transition_validations", "transition_validations"),
                               ("missed_validations", "missed_validations"),
                               ("images_live", "sam_images")):
                if int(mine[r["clip"]][col]) != int(float(r[other])):
                    gaps.append(f"{r['clip']} {col} : {mine[r['clip']][col]} contre {r[other]}")
    return gaps


def check_confusion(rows: list[dict], confusion_path) -> list[str]:
    """Écarts avec `confusion.csv` (`live`), s'il existe."""
    if not Path(confusion_path).is_file():
        return []
    total: dict = {}
    for r in rows:
        for (pred, true), n in r["_confusion"].items():
            total[(true, pred)] = total.get((true, pred), 0) + n
    with open(confusion_path, encoding="utf-8", newline="") as fh:
        want = {(r["label"], r["interpretation"]): int(r["images"])
                for r in csv.DictReader(fh) if r["setting"] == "live"}
    return [f"confusion {k} : {total.get(k, 0)} contre {want.get(k, 0)}"
            for k in sorted(set(total) | set(want)) if total.get(k, 0) != want.get(k, 0)]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Détail par extrait et par copie (EVAL-R9.5).")
    ap.add_argument("--clips", default="eval/benchmark/clips.csv")
    ap.add_argument("--labels", default="eval/benchmark/labels.csv")
    ap.add_argument("--results", default="eval/benchmark/results.csv")
    ap.add_argument("--robust-dir", default="eval/benchmark/robust")
    ap.add_argument("--no-robust", action="store_true", help="extraits d'origine seulement")
    ap.add_argument("--sam-cache", default="data/eval/sam")
    ap.add_argument("--out", default="eval/benchmark/robust/detail.csv")
    args = ap.parse_args(argv)

    from fixloop.procedures import load_all
    procedure = load_all()[PID]
    rows = rows_for(args.clips, args.labels, args.sam_cache, procedure)
    gaps = check_results(rows, args.results)
    gaps += check_confusion(rows, Path(args.results).parent / "confusion.csv")
    if not args.no_robust:
        robust = Path(args.robust_dir)
        copies = rows_for(robust / "clips.csv", robust / "labels.csv", args.sam_cache, procedure)
        gaps += check_results(copies, robust / "results.csv")
        gaps += check_confusion(copies, robust / "confusion.csv")
        rows += copies
    if gaps:
        sys.exit("écart avec le benchmark, rien n'est écrit :\n" + "\n".join(gaps))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} lignes -> {out}")


if __name__ == "__main__":
    main()
