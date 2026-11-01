"""Comparaison des approches du benchmark (spec/08-evaluation, EVAL-R4).

Fonctions pures : étiquettes seconde par seconde, événements du journal de
`Session`, mesures de la section 4 du design. Les scénarios de bout en bout
utilisent `fixloop/sim.py` (aucune vidéo réelle, aucun appel API).
"""

from __future__ import annotations

import csv
from pathlib import Path

STATES = ("off", "on", "transition", "hidden")
ON_MAX = 0.18  # seuils de la fiche chain_off_chainring
OFF_MIN = 0.26
MIN_STABLE_S = 5  # EVAL-R4.2 : segment on d'au moins 5 s
REMINDER_WINDOW_S = 10.0  # EVAL-R4.4 : anomalie dans les 10 s


# ------------------------------------------------------------------ étiquettes
def read_labels(path: str | Path) -> dict[str, list[dict]]:
    """`labels.csv` (clip,t,state,done) -> par extrait, trié par seconde."""
    out: dict[str, list[dict]] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            state = row["state"]
            if state not in STATES:
                raise ValueError(f"état inconnu : {state!r}")
            try:
                t, done = int(row["t"]), int(row["done"])
            except ValueError:
                raise ValueError(f"ligne invalide : {row!r}")
            if done not in (0, 1):
                raise ValueError(f"done invalide : {row!r}")
            out.setdefault(row["clip"], []).append({"t": t, "state": state, "done": done})
    for rows in out.values():
        rows.sort(key=lambda r: r["t"])
    return out


def read_clips(path: str | Path) -> list[dict]:
    """`clips.csv` (matrice de diversité, design 08 section 1) -> lignes."""
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def label_at(labels: list[dict], t: float) -> str:
    """Étiquette `L(t)` : état à la seconde `floor(t)` (design 08, section 4)."""
    want = int(t // 1)
    for row in labels:
        if row["t"] == want:
            return row["state"]
    return "transition"  # seconde inconnue : neutre, exclue des comptes on/off


def on_segments(labels: list[dict]) -> list[tuple[int, int]]:
    """Segments `on` maximaux, `(début, fin)` en secondes, fin exclue."""
    segments, start = [], None
    for row in labels:
        if row["state"] == "on" and start is None:
            start = row["t"]
        elif row["state"] != "on" and start is not None:
            segments.append((start, row["t"]))
            start = None
    if start is not None and labels:
        segments.append((start, labels[-1]["t"] + 1))
    return segments


# ------------------------------------------------------------------ événements
def validated_events(events: list[dict]) -> list[dict]:
    """`validated` + clôtures du test dynamique (EVAL-R4.1)."""
    dynamic = False
    out = []
    for e in events:
        if e.get("event") == "dynamic_start":
            dynamic = True
        elif e.get("event") == "validated":
            out.append(e)
        elif e.get("event") == "closed" and e.get("success") and dynamic:
            out.append(e)
    return out


def false_validations(events: list[dict], labels: list[dict]) -> dict:
    """Fausses validations : `validated` avec `L(t)` off/hidden (EVAL-R4.1)."""
    out = {"false": 0, "transition": 0, "details": []}
    for e in validated_events(events):
        state = label_at(labels, e.get("t", 0.0))
        if state in ("off", "hidden"):
            out["false"] += 1
            out["details"].append({"t": e.get("t"), "state": state})
        elif state == "transition":
            out["transition"] += 1
    return out


def _effective_start(seg_start: int, seg_end: int, require_done: bool,
                     done_times: list[float]) -> float | None:
    """Début du segment utile : après le dernier « c'est fait » si exigé."""
    if not require_done:
        return float(seg_start)
    past = [d for d in done_times if d <= seg_end]
    if not past:
        return None  # sans « c'est fait », aucune validation n'est attendue
    return max(float(seg_start), max(past))


def missed_validations(events: list[dict], labels: list[dict],
                       require_done: bool = False,
                       done_times: list[float] | tuple = ()) -> int:
    """Segments `on` de ≥ 5 s sans validation (EVAL-R4.2)."""
    done = [e.get("t", 0.0) for e in validated_events(events)]
    missed = 0
    for start, end in on_segments(labels):
        eff = _effective_start(start, end, require_done, list(done_times))
        if eff is None or end - eff < MIN_STABLE_S:
            continue
        if not any(eff <= t <= end for t in done):
            missed += 1
    return missed


def validation_delays(events: list[dict], labels: list[dict],
                      require_done: bool = False,
                      done_times: list[float] | tuple = ()) -> list[float]:
    """Délais `t_validated − max(début, done)` par segment validé (EVAL-R4.3)."""
    done = sorted(e.get("t", 0.0) for e in validated_events(events))
    delays = []
    for start, end in on_segments(labels):
        eff = _effective_start(start, end, require_done, list(done_times))
        if eff is None:
            continue
        first = next((t for t in done if eff <= t <= end), None)
        if first is not None:
            delays.append(round(first - eff, 2))
    return delays


def false_reminder_recall(events: list[dict], labels: list[dict]) -> dict:
    """Fausses remises (« c'est fait » sur off) signalées en anomalie (EVAL-R4.4)."""
    anomalies = [e.get("t", 0.0) for e in events if e.get("event") == "anomaly"]
    total, signaled = 0, 0
    for row in labels:
        if row["done"] == 1 and row["state"] == "off":
            total += 1
            if any(0 <= a - row["t"] <= REMINDER_WINDOW_S for a in anomalies):
                signaled += 1
    return {"total": total, "signaled": signaled}


def approach_counts(events: list[dict], measures: list) -> dict:
    """Appels Spark et images SAM d'un extrait (EVAL-R4.6, coût estimé en T6)."""
    calls = {"spark": 0, "wonder": 0}
    for e in events:
        if isinstance(e.get("model_calls"), dict):
            calls = e["model_calls"]
    return {"spark_calls": int(calls.get("spark", 0)), "sam_images": len(measures)}


# ------------------------------------------------------------------ par image
def classify_contact(contact: float | None, on_max: float = ON_MAX,
                     off_min: float = OFF_MIN) -> str:
    """Interprétation d'un contact (mêmes seuils que `server/session.py`)."""
    if contact is None or contact != contact:
        return "non vu"
    if contact <= on_max:
        return "en place"
    if contact >= off_min:
        return "tombée"
    return "incertain"


def image_confusion(measures: list, labels: list[dict],
                    pair: tuple[str, str] = ("chain", "chainring"),
                    on_max: float = ON_MAX, off_min: float = OFF_MIN) -> dict:
    """`(interprétation, étiquette)` par image, `transition` exclue (EVAL-R4.5)."""
    out: dict = {}
    for m in measures:
        true = label_at(labels, m.t)
        if true == "transition":
            continue
        pred = classify_contact(m.contact.get(pair), on_max, off_min)
        out[(pred, true)] = out.get((pred, true), 0) + 1
    return out
