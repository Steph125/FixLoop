"""Perception SAM 3.1 : partie commune (spec/02-perception, PERC-T3).

Regroupe la logique sans réseau partagée par le mode image et le mode vidéo :
placement des masques plein cadre, sélection largest/union, filtre de confiance,
relecture des sorties brutes, découpage en morceaux. Les sondes `probe/` restent
inchangées (preuves datées) ; ce module en reprend le comportement mesuré.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from meta_sam_parser import (
    CompletedOutcome,
    ResponsesStreamError,
    decode_mask_to_raster,
    image_segmentation_format,
    video_segmentation_format,
)
from openai import APIConnectionError


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


CONF_THR = _env_float("FIXLOOP_SAM_CONF", 0.4)
LIVE_WIDTH = _env_int("FIXLOOP_SAM_WIDTH", 848)
MAX_IN_FLIGHT = _env_int("FIXLOOP_SAM_INFLIGHT", 3)
CHUNK_SECONDS = _env_float("FIXLOOP_SAM_CHUNK_S", 10.0)
VIDEO_FPS = 10.0

RETRYABLE = (APIConnectionError, ResponsesStreamError, ConnectionError, TimeoutError)


@dataclass
class PartResult:
    """Masque d'une pièce sur une image (coordonnées plein cadre)."""

    mask: np.ndarray | None
    confidence: float = 0.0
    box: tuple[int, int, int, int] | None = None  # x0, y0, x1, y1
    svg_path: str | None = None  # rempli par PERC-T6
    n_objects: int = 0


@dataclass
class ImageResult:
    """Résultat du mode image pour une image (complété par PERC-T4)."""

    frame_index: int
    t: float
    parts: dict[str, PartResult] = field(default_factory=dict)
    timing: dict = field(default_factory=dict)
    error: str | None = None


def parse_raw(text: str, video: bool = True) -> Any:
    """Relit une sortie brute SAM enregistrée, sans appel API (PERC-R5.1)."""
    fmt = video_segmentation_format() if video else image_segmentation_format()
    parser = fmt.create_parser()
    list(parser.push(text))
    return parser.finish(CompletedOutcome()).result


def lines_for(text: str, frames: set[int] | None) -> str:
    """Ne garde que les lignes <Nf> des images voulues (PERC-R5.2)."""
    if frames is None:
        return text
    keep = []
    for line in text.splitlines(keepends=True):
        m = re.match(r"<(\d+)f>", line)
        if m and int(m.group(1)) in frames:
            keep.append(line)
    return "".join(keep)


def masks_from_records(records: Any, h: int, w: int, conf_thr: float = CONF_THR,
                       largest: bool = False) -> dict[int, PartResult]:
    """Records SAM -> un PartResult par image (PERC-R1.3 à R1.6).

    Filtre `confidence >= conf_thr` (absente = 1,0), replace chaque masque de
    boîte à (left, top) en le tronquant au cadre, garde le plus gros objet si
    `largest` sinon fusionne (union). Les images sans objet retenu sont absentes
    du résultat. Les records sans image (mode image) vont à la clé 0.
    """
    per_frame: dict[int, list[tuple[np.ndarray, float]]] = {}
    for rec in records:
        if getattr(rec, "kind", None) != "mask":
            continue
        frame = getattr(rec, "frame", None)
        fi = frame.frame_index if frame is not None else 0
        conf = rec.confidence if rec.confidence is not None else 1.0
        if conf < conf_thr:
            continue
        mh, mw = rec.mask.height, rec.mask.width
        raster = np.frombuffer(decode_mask_to_raster(rec.mask), dtype=np.uint8)
        raster = raster.reshape(mh, mw).astype(bool)
        x0, y0 = int(rec.bounds.left), int(rec.bounds.top)
        sx0, sy0 = max(0, -x0), max(0, -y0)
        x0c, y0c = max(0, x0), max(0, y0)
        x1c, y1c = min(x0 + mw, w), min(y0 + mh, h)
        if x1c <= x0c or y1c <= y0c:
            continue
        full = np.zeros((h, w), dtype=bool)
        full[y0c:y1c, x0c:x1c] = raster[sy0:sy0 + y1c - y0c, sx0:sx0 + x1c - x0c]
        per_frame.setdefault(fi, []).append((full, conf))
    out: dict[int, PartResult] = {}
    for fi, objs in per_frame.items():
        if largest:
            m, conf = max(objs, key=lambda mc: int(mc[0].sum()))
            ys, xs = np.nonzero(m)
            box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
            out[fi] = PartResult(mask=m, confidence=conf, box=box, n_objects=1)
        else:
            m = np.logical_or.reduce([o[0] for o in objs])
            ys, xs = np.nonzero(m)
            box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
            out[fi] = PartResult(mask=m, confidence=max(o[1] for o in objs),
                                 box=box, n_objects=len(objs))
    return out


FRAME_MARK = re.compile(r"<(\d+)f>")


def shift_frames(text: str, offset: int) -> str:
    """Décale les numéros d'image d'une sortie SAM (PERC-R3.4)."""
    if not text:
        return ""
    text = FRAME_MARK.sub(lambda m: f"<{int(m.group(1)) + offset}f>", text)
    return text if text.endswith("\n") else text + "\n"


def plan_chunks(n_frames: int, chunk_frames: int, min_frames: int = 50) -> list[tuple[int, int]]:
    """Découpe [0, n_frames) ; un dernier morceau < min_frames fusionné (PERC-R3.2)."""
    if chunk_frames <= 0 or chunk_frames >= n_frames:
        return [(0, n_frames)]
    starts = list(range(0, n_frames, chunk_frames))
    if len(starts) > 1 and n_frames - starts[-1] < min_frames:
        starts.pop()
    return [(a, starts[i + 1] if i + 1 < len(starts) else n_frames) for i, a in enumerate(starts)]
