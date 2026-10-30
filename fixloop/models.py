"""Types partagés entre modules (spec/01-core-loop/design.md, section 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

VerdictValue = Literal["0", "1", "?", "eps"]


@dataclass
class FrameMasks:
    frame_index: int
    t: float                                   # secondes depuis le début de la session
    masks: dict[str, np.ndarray]               # pièce -> masque booléen plein cadre (H, W)
    confidence: dict[str, float] = field(default_factory=dict)


@dataclass
class Measures:
    frame_index: int
    t: float
    detected: dict[str, bool]
    contact: dict[tuple[str, str], float]      # (a, b) -> taux de contact, NaN si une pièce manque


@dataclass
class Verdict:
    value: VerdictValue
    rule: dict | None = None                   # règle qui a décidé
    evidence: dict = field(default_factory=dict)
    message: str | None = None
