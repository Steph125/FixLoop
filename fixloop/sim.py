"""Scène synthétique (plateau + chaîne) pour tester la logique sans vidéo ni API.

Imite ce que SAM 3.1 a renvoyé sur la vraie vidéo du 29 oct. (eval/day1) :
- chaîne EN PLACE : SAM fond la chaîne posée sur les dents dans le plateau, il ne reste que
  les deux brins qui arrivent tangents au plateau -> contact faible ;
- chaîne TOMBÉE : la chaîne repose le long du haut du plateau -> contact élevé.
"""

from __future__ import annotations

import cv2
import numpy as np

from .models import FrameMasks

H, W = 400, 400
CENTER, RADIUS = (260, 200), 80


def _chainring() -> np.ndarray:
    m = np.zeros((H, W), np.uint8)
    cv2.circle(m, CENTER, RADIUS, 1, -1)
    return m.astype(bool)


def _chain_on() -> np.ndarray:
    """Deux brins tangents (haut et bas) qui s'arrêtent au bord du plateau."""
    m = np.zeros((H, W), np.uint8)
    cx, cy = CENTER
    cv2.line(m, (0, cy - RADIUS - 4), (cx - 20, cy - RADIUS - 4), 1, thickness=8)
    cv2.line(m, (0, cy + RADIUS + 4), (cx - 20, cy + RADIUS + 4), 1, thickness=8)
    return m.astype(bool)


def _chain_off() -> np.ndarray:
    """Chaîne tombée qui repose le long de la moitié haute du plateau."""
    m = np.zeros((H, W), np.uint8)
    cv2.ellipse(m, CENTER, (RADIUS + 6, RADIUS + 6), 0, 180, 360, 1, thickness=12)
    cv2.line(m, (0, CENTER[1] - 40), (CENTER[0] - RADIUS, CENTER[1] - 10), 1, thickness=10)
    return m.astype(bool)


def frame(kind: str, i: int, t: float) -> FrameMasks:
    """kind : 'on' (chaîne en place), 'off' (tombée) ou 'hidden' (chaîne cachée par la main)."""
    masks = {"chainring": _chainring()}
    if kind == "on":
        masks["chain"] = _chain_on()
    elif kind == "off":
        masks["chain"] = _chain_off()
    elif kind != "hidden":
        raise ValueError(kind)
    return FrameMasks(frame_index=i, t=t, masks=masks, confidence={k: 0.9 for k in masks})
