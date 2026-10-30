"""Mesures géométriques sur les masques SAM : détection et taux de contact."""

from __future__ import annotations

import cv2
import numpy as np

from .models import FrameMasks, Measures

DEFAULT_DILATE_PX = 6
DEFAULT_EDGE_PX = 6


def outer_edge(mask: np.ndarray, px: int = DEFAULT_EDGE_PX) -> np.ndarray:
    """Bord extérieur du masque, d'épaisseur px."""
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    edge = np.zeros(mask.shape, dtype=np.uint8)
    cv2.drawContours(edge, cnts, -1, 1, thickness=px)
    return edge.astype(bool)


def contact_ratio(a: np.ndarray | None, b: np.ndarray | None,
                  dilate_px: int = DEFAULT_DILATE_PX, edge_px: int = DEFAULT_EDGE_PX) -> float:
    """Part du bord extérieur de B couverte par A dilaté. NaN si une pièce manque."""
    if a is None or b is None or not a.any() or not b.any():
        return float("nan")
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1))
    a_d = cv2.dilate(a.astype(np.uint8), k).astype(bool)
    edge = outer_edge(b, edge_px)
    return float((edge & a_d).sum() / max(int(edge.sum()), 1))


def contact_pairs(procedure: dict) -> set[tuple[str, str]]:
    """Toutes les paires (a, b) dont une règle de la fiche a besoin."""
    rules = []
    for step in procedure["steps"]:
        rules += step.get("success", []) + step.get("anomaly", [])
    rules += procedure.get("dynamic_test", {}).get("must_hold", [])
    return {(r["a"], r["b"]) for r in rules if r["type"].startswith("contact_ratio")}


def measure(fm: FrameMasks, procedure: dict, dilate_px: int = DEFAULT_DILATE_PX,
            edge_px: int = DEFAULT_EDGE_PX) -> Measures:
    detected = {p: bool(fm.masks.get(p) is not None and fm.masks[p].any()) for p in procedure["parts"]}
    contact = {(a, b): contact_ratio(fm.masks.get(a), fm.masks.get(b), dilate_px, edge_px)
               for a, b in contact_pairs(procedure)}
    return Measures(frame_index=fm.frame_index, t=fm.t, detected=detected, contact=contact)
