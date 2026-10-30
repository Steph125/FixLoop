"""Journal des coûts des modèles (spec/05-session-server, SRV-R8).

Chaque appel à un modèle y est noté avec son coût estimé selon la table de
`steering/tech.md` section 3. Ce sont des estimations : la vérification se fait
sur la page Usage de Meta (SRV-R8.5). Persistance : `data/costs/<AAAA-MM-JJ>.jsonl`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PRICES = {  # steering/tech.md section 3 — à vérifier sur la page Pricing avant le 2 nov.
    ("sam-3.1", "image"): 2.50 / 1000,          # par image
    ("sam-3.1", "video"): 0.20 / 1000,          # par image, minimum 50 par requête
    ("muse-spark-1.3", "in"): 1.25 / 1e6,       # par jeton d'entrée
    ("muse-spark-1.3", "out"): 4.25 / 1e6,      # par jeton de sortie
    ("muse-wonder-1.0", "in"): 4.00 / 1e6,
    ("muse-wonder-1.0", "out"): 20.0 / 1e6,
    ("muse-voice-transcribe-1.0", "second"): 0.18 / 3600,  # par seconde d'audio
}

VIDEO_MIN_IMAGES = 50  # facturation minimale par requête vidéo (PERC-R7.2)

DEFAULT_ROOT = Path("data/costs")

# Jetons Spark estimés quand l'API ne rend pas d'usage (design 05, section 5).
SPARK_ESTIMATED_IN_PER_IMAGE = 1500
SPARK_ESTIMATED_OUT = 200


def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


class CostLog:
    """Journal en mémoire + JSONL par jour. Un coût inconnu vaut 0, sans lever."""

    def __init__(self, root: str | Path = DEFAULT_ROOT):
        self.root = Path(root)
        self.entries: list[dict] = []
        self._load_today()

    def add(self, model: str, kind: str, units: float, seconds: float, ok: bool,
            session_id: str | None = None, **extra) -> float:
        """Journalise un appel et rend son coût estimé en dollars (SRV-R8.1)."""
        billed = units
        if (model, kind) == ("sam-3.1", "video"):
            billed = max(units, VIDEO_MIN_IMAGES)
        price = PRICES.get((model, kind), 0.0)
        cost = billed * price
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "day": _today(),
                 "model": model, "kind": kind, "units": units, "billed": billed,
                 "seconds": seconds, "ok": ok, "session_id": session_id,
                 "cost_usd": cost, "estimated": bool(extra.get("estimated", False)),
                 **{k: v for k, v in extra.items() if k != "estimated"}}
        self.entries.append(entry)
        self._append(entry)
        return cost

    def session_total(self, session_id: str) -> float:
        return sum(e["cost_usd"] for e in self.entries if e["session_id"] == session_id)

    def day_total(self, day: str | None = None) -> float:
        day = day or _today()
        if day == _today():
            return sum(e["cost_usd"] for e in self.entries if e["day"] == day)
        return sum(e["cost_usd"] for e in self._read_day(day))

    def by_model(self, day: str | None = None) -> dict[str, float]:
        day = day or _today()
        entries = self.entries if day == _today() else self._read_day(day)
        out: dict[str, float] = {}
        for e in entries:
            if e["day"] == day:
                out[e["model"]] = out.get(e["model"], 0.0) + e["cost_usd"]
        return out

    # ------------------------------------------------------------------ persistance
    def _path(self, day: str) -> Path:
        return self.root / f"{day}.jsonl"

    def _load_today(self) -> None:
        self.entries.extend(self._read_day(_today()))

    def _read_day(self, day: str) -> list[dict]:
        path = self._path(day)
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def _append(self, entry: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._path(entry["day"]).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
