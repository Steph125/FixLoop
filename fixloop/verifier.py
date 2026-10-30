"""Verdict d'une étape (spec/state_machine.md, section « Verdict d'une étape »)."""

from __future__ import annotations

import math

from .models import Measures, Verdict

DEFAULT_DEBOUNCE = 4


def eval_rule(rule: dict, m: Measures) -> bool:
    """Vrai si la règle est satisfaite sur cette image. Une mesure absente (NaN) n'est jamais vraie."""
    t = rule["type"]
    if t == "detected":
        return m.detected.get(rule["part"], False)
    if t == "absent":
        return not m.detected.get(rule["part"], False)
    value = m.contact.get((rule["a"], rule["b"]), float("nan"))
    if math.isnan(value):
        return False
    if t == "contact_ratio_min":
        return value >= rule["threshold"]
    if t == "contact_ratio_max":
        return value <= rule["threshold"]
    raise ValueError(f"type de règle inconnu : {t}")


def _evidence(window: list[Measures]) -> dict:
    last = window[-1]
    return {"frame": last.frame_index, "detected": last.detected,
            "contact": {f"{a}/{b}": round(v, 3) for (a, b), v in last.contact.items()}}


def verify(step: dict, window: list[Measures], user_done: bool) -> Verdict:
    """Verdict sur les N dernières mesures. Priorité : anomalie > succès > incertain > en cours."""
    n = step.get("debounce_frames", DEFAULT_DEBOUNCE)
    if len(window) < n:
        return Verdict("0")
    recent = window[-n:]

    for rule in step.get("anomaly", []):
        if rule.get("when", "always") == "after_done" and not user_done:
            continue
        if all(eval_rule(rule, m) for m in recent):
            return Verdict("eps", rule, _evidence(recent), rule.get("message"))

    success = all(all(eval_rule(r, m) for r in step["success"]) for m in recent)
    if success and (user_done or not step.get("requires_done", False)):
        return Verdict("1", None, _evidence(recent))

    if user_done:
        return Verdict("?", None, _evidence(recent))
    return Verdict("0")


def holds(rules: list[dict], window: list[Measures]) -> bool:
    """Vrai si toutes les règles sont vraies sur toute la fenêtre (essai dynamique)."""
    return bool(window) and all(all(eval_rule(r, m) for r in rules) for m in window)
