"""Étiquetage seconde par seconde d'un extrait (spec/08, design section 2, EVAL-T2).

Usage : python scripts/label_clip.py --video data/eval/velo3.mp4 --clip c01 --labels eval/benchmark/labels.csv

Touches : o = off (tombée), f = on (en place, « faite »), t = transition,
h = hidden (masquée), espace = « c'est fait » à cette seconde,
n/p = seconde suivante/précédente, q = enregistrer et quitter.
L'outil relit le CSV existant (reprise) et écrit une ligne par seconde.
La partie interactive demande un écran ; les fonctions pures sont testées.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KEY_TO_STATE = {"o": "off", "f": "on", "t": "transition", "h": "hidden"}
STATES = ("off", "on", "transition", "hidden")


def state_for_key(key: str) -> str | None:
    """Touche -> état, ou None si la touche ne labellise pas."""
    return KEY_TO_STATE.get(key.lower())


def rows_for_clip(clip: str, states: list, done_at: list[int]) -> list[dict]:
    """États par seconde + instants de « c'est fait » -> lignes `labels.csv`."""
    done = set(done_at)
    rows = []
    for t, state in enumerate(states):
        if state not in STATES:
            raise ValueError(f"état inconnu : {state!r}")
        rows.append({"clip": clip, "t": t, "state": state,
                     "done": 1 if t in done else 0})
    return rows


def read_done(path: str | Path, clip: str) -> tuple[list, list[int]]:
    """Relit les lignes existantes d'un extrait (reprise d'étiquetage)."""
    path = Path(path)
    if not path.exists():
        return [], []
    rows = [r for r in csv.DictReader(path.open(encoding="utf-8")) if r["clip"] == clip]
    if not rows:
        return [], []
    states = [r["state"] for r in sorted(rows, key=lambda r: int(r["t"]))]
    done_at = [int(r["t"]) for r in rows if int(r["done"]) == 1]
    return states, done_at


def write_labels_csv(path: str | Path, rows: list[dict]) -> None:
    """Écrit (ou remplace) les lignes : une par seconde et par extrait."""
    path = Path(path)
    kept = []
    if path.exists():
        clips = {r["clip"] for r in rows}
        kept = [r for r in csv.DictReader(path.open(encoding="utf-8"))
                if r["clip"] not in clips]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["clip", "t", "state", "done"])
        w.writeheader()
        w.writerows(kept + rows)


def main() -> None:
    import cv2
    ap = argparse.ArgumentParser(description="Étiquette un extrait seconde par seconde.")
    ap.add_argument("--video", required=True)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--labels", required=True)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    seconds = max(1, round(total / fps))
    states, done_at = read_done(args.labels, args.clip)
    states += ["transition"] * (seconds - len(states))
    done = set(done_at)
    cur = 0
    print(f"{args.clip} : {seconds} s. o/f/t/h = état, espace = c'est fait, q = sauver.")
    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(cur * fps))
        ok, img = cap.read()
        if not ok:
            break
        mark = "*" if cur in done else " "
        cv2.imshow(f"{args.clip} t={cur}s [{states[cur]}]{mark}",
                   cv2.resize(img, (min(960, img.shape[1]),
                                    min(960, img.shape[1]) * img.shape[0] // img.shape[1])))
        key = chr(cv2.waitKey(0) & 0xFF)
        if key == "q":
            break
        elif key == " ":
            if cur in done:
                done.remove(cur)
            else:
                done.add(cur)
        elif key == "n":
            cur = min(seconds - 1, cur + 1)
        elif key == "p":
            cur = max(0, cur - 1)
        elif state_for_key(key) is not None:
            states[cur] = state_for_key(key)
            cur = min(seconds - 1, cur + 1)
    cv2.destroyAllWindows()
    write_labels_csv(args.labels, rows_for_clip(args.clip, states, sorted(done)))
    print(f"{len(states)} s étiquetées -> {args.labels}")


if __name__ == "__main__":
    main()
