"""Étiquetage seconde par seconde d'un extrait (spec/08, design section 2, EVAL-T2).

Usage : python scripts/label_clip.py --video data/eval/velo3.mp4 --clip c01 --labels eval/benchmark/labels.csv

Touches : o = off (tombée), f = on (en place, « faite »), t = transition,
h = hidden (masquée), espace = « c'est fait » à cette seconde,
n/p = seconde suivante/précédente, q = enregistrer et quitter.
L'outil relit le CSV existant (reprise) et écrit une ligne par seconde.
Fenêtre tkinter (l'OpenCV du projet est sans affichage), chaque seconde
rejouée en boucle. La partie interactive demande un écran ; les fonctions
pures sont testées.
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


PLAY_FPS = 10  # images montrées par seconde de vidéo (la seconde est rejouée en boucle)
LETTERS = {"off": "o", "on": "f", "transition": "t", "hidden": "h"}


def frames_of_second(cap, sec: int, fps: float, width: int = 960) -> list:
    """Images de la seconde `sec` (environ PLAY_FPS), réduites à `width` px au plus."""
    import cv2
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(sec * fps)))
    step = max(1, int(round(fps / PLAY_FPS)))
    out = []
    for j in range(max(1, int(round(fps)))):
        ok, img = cap.read()
        if not ok:
            break
        if j % step == 0:
            if img.shape[1] > width:
                img = cv2.resize(img, (width, width * img.shape[0] // img.shape[1]))
            out.append(img)
    return out


def timeline(states: list, labelled: set, done: set, cur: int) -> str:
    """Une lettre par seconde (· = pas encore étiquetée, ! = « c'est fait »), [ ] = seconde courante."""
    cells = []
    for t, s in enumerate(states):
        cell = (LETTERS[s] if t in labelled else "·") + ("!" if t in done else "")
        cells.append(f"[{cell}]" if t == cur else f" {cell} ")
    return "".join(cells)


def resume_labelled(states: list, done_at: list, seconds: int) -> set:
    """Secondes déjà étiquetées à la reprise.

    Un extrait relu tout en `transition` sans aucun « c'est fait » est un
    enregistrement vide (fenêtre fermée sans étiqueter) : rien n'est repris.
    """
    if not states or (all(s == "transition" for s in states) and not done_at):
        return set()
    return set(range(min(len(states), seconds)))


def main() -> None:
    """Fenêtre tkinter (livré avec Python) : l'OpenCV du projet est sans affichage."""
    import base64
    import tkinter as tk

    import cv2
    ap = argparse.ArgumentParser(description="Étiquette un extrait seconde par seconde.")
    ap.add_argument("--video", required=True)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--labels", required=True)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"vidéo illisible : {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    seconds = max(1, round(total / fps))
    states, done_at = read_done(args.labels, args.clip)
    labelled = resume_labelled(states, done_at, seconds)  # reprise : déjà étiquetées
    states = (states + ["transition"] * seconds)[:seconds]
    done = set(done_at)
    view = {"cur": 0, "images": [], "i": 0}
    print(f"{args.clip} : {seconds} s. o/f/t/h = état, espace = c'est fait, q = sauver.")

    root = tk.Tk()
    root.title(f"FixLoop : étiquetage {args.clip}")
    picture = tk.Label(root)
    picture.pack()
    status = tk.Label(root, font=("Consolas", 12), justify="left")
    status.pack(anchor="w", padx=8)
    buttons = tk.Frame(root)
    buttons.pack(anchor="w", padx=8, pady=4)
    tk.Label(root, justify="left", font=("Segoe UI", 10),
             text="Touches : o tombée, f en place, t bouge, h cachée, espace « c'est fait », "
                  "n / → suivante, p / ← précédente, q enregistrer. Si les touches ne "
                  "répondent pas, clique sur l'image ou utilise les boutons.").pack(anchor="w", padx=8,
                                                                                  pady=4)

    def load_second() -> None:
        view["images"] = [tk.PhotoImage(data=base64.b64encode(
            cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 1])[1].tobytes()))
            for img in frames_of_second(cap, view["cur"], fps)]
        view["i"] = 0
        refresh()

    def refresh() -> None:
        cur = view["cur"]
        state = states[cur] if cur in labelled else "(à étiqueter)"
        said = "   « c'est fait »" if cur in done else ""
        status.config(text=f"{args.clip}   seconde {cur} / {seconds - 1}   état : {state}{said}\n"
                           f"{timeline(states, labelled, done, cur)}")

    def play() -> None:
        if view["images"]:
            picture.config(image=view["images"][view["i"] % len(view["images"])])
            view["i"] += 1
        root.after(1000 // PLAY_FPS, play)

    def go(delta: int) -> None:
        view["cur"] = min(seconds - 1, max(0, view["cur"] + delta))
        load_second()

    def set_state(state: str) -> None:
        cur = view["cur"]
        states[cur] = state
        labelled.add(cur)
        if cur < seconds - 1:
            go(1)
        else:
            refresh()

    def toggle_done() -> None:
        done.symmetric_difference_update({view["cur"]})
        refresh()

    def on_key(event) -> None:
        key = (event.char or "").lower()
        if key == "q":
            root.destroy()
        elif key == " ":
            toggle_done()
        elif key == "n" or event.keysym == "Right":
            go(1)
        elif key == "p" or event.keysym == "Left":
            go(-1)
        elif state_for_key(key) is not None:
            set_state(state_for_key(key))

    for text, action in (("◀ précédente", lambda: go(-1)),
                         ("o tombée", lambda: set_state("off")),
                         ("f en place", lambda: set_state("on")),
                         ("t bouge", lambda: set_state("transition")),
                         ("h cachée", lambda: set_state("hidden")),
                         ("« c'est fait »", toggle_done),
                         ("suivante ▶", lambda: go(1)),
                         ("Enregistrer et quitter", root.destroy)):
        tk.Button(buttons, text=text, command=action, takefocus=0).pack(side="left", padx=2)
    root.bind_all("<Key>", on_key)  # quel que soit l'élément qui a le focus
    picture.bind("<Button-1>", lambda e: root.focus_force())
    root.protocol("WM_DELETE_WINDOW", root.destroy)  # fermer la fenêtre = enregistrer aussi
    load_second()
    play()
    root.lift()
    root.attributes("-topmost", True)
    root.after(500, lambda: root.attributes("-topmost", False))
    root.focus_force()
    root.mainloop()
    cap.release()

    if not labelled:
        print("Rien d'étiqueté : fichier inchangé. Relance la commande et étiquette chaque seconde.")
        return
    write_labels_csv(args.labels, rows_for_clip(args.clip, states, sorted(done)))
    missing = [t for t in range(seconds) if t not in labelled]
    print(f"{len(states)} s enregistrées -> {args.labels}")
    if missing:
        print(f"ATTENTION : secondes non étiquetées (notées transition) : {missing}. "
              "Relance la même commande pour les compléter.")


if __name__ == "__main__":
    main()
