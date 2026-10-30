"""Historique du vélo (spec/04-memory-voice, MEM-R1 à R3).

`WonderMemory` implémente le protocole `Memory` de la session. Sans Wonder pour
l'instant (MEM-T1) : `load` rend « aucun » si l'historique est vide, sinon les
5 dernières entrées en texte brut ; les appels Wonder arrivent avec MEM-T4.
Écriture atomique (temporaire puis renommage). Seuls les champs connus sont
conservés : ni image, ni audio, ni transcription, ni donnée personnelle.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODEL = "muse-wonder-1.0"
BIKE_ID = re.compile(r"^[a-z0-9-]{4,32}$")
FALLBACK_LINES = 5


class WonderMemory:
    def __init__(self, root: str | Path = Path("data/bikes"), client=None, model: str = MODEL):
        self.root = Path(root)
        self.client = client  # câblé par MEM-T4 ; ignoré d'ici là
        self.model = model
        self.calls: list[dict] = []

    # ------------------------------------------------------------------ lecture
    def load(self, bike_id: str) -> str:
        """Synthèse (< 60 mots), « aucun », ou texte brut de repli (MEM-R1)."""
        self._check(bike_id)
        entries = self._read(bike_id)["entries"]
        if not entries:
            return "aucun"  # MEM-R1.5 : pas d'appel Wonder
        lines = [f"{e['date']} : {e.get('title') or e['procedure']}, "
                 f"{'réussie' if e['success'] else 'échouée'}"
                 for e in entries[-FALLBACK_LINES:]]
        return "\n".join(lines)  # MEM-R1.6 : repli texte brut

    def repeated(self, bike_id: str, procedure: str, days: int = 30) -> int:
        """Occurrences de la fiche sur les `days` derniers jours (MEM, design 1.2)."""
        self._check(bike_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        n = 0
        for e in self._read(bike_id)["entries"]:
            if e["procedure"] != procedure:
                continue
            try:
                when = datetime.fromisoformat(e["date"])
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= since:
                n += 1
        return n

    # ------------------------------------------------------------------ écriture
    def save(self, bike_id: str, report: dict) -> None:
        """Ajoute une entrée (MEM-R2.1), sans `summary` sans Wonder (MEM-R2.3)."""
        self._check(bike_id)
        entry = {
            "date": report.get("date") or datetime.now(timezone.utc).isoformat(),
            "procedure": report["procedure"],
            "success": bool(report["success"]),
            "duration_s": report.get("duration_s"),
            "steps_validated": list(report.get("steps_validated", [])),
            "anomalies": list(report.get("anomalies", [])),
            "model_calls": dict(report.get("model_calls", {})),
        }
        if report.get("title"):
            entry["title"] = report["title"]
        if report.get("summary"):  # phrase Wonder (MEM-T4) ; absente sinon
            entry["summary"] = report["summary"]
        data = self._read(bike_id)
        if not data["entries"] and "created" not in data:
            data["created"] = datetime.now(timezone.utc).isoformat()
        data["entries"].append(entry)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(bike_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)  # MEM-R2.4 : atomique

    # ------------------------------------------------------------------ internes
    @staticmethod
    def _check(bike_id: str) -> None:
        if not isinstance(bike_id, str) or not BIKE_ID.match(bike_id):
            raise ValueError(f"bike_id invalide : {bike_id!r}")

    def _path(self, bike_id: str) -> Path:
        return self.root / f"{bike_id}.json"

    def _read(self, bike_id: str) -> dict:
        path = self._path(bike_id)
        if not path.exists():
            return {"bike_id": bike_id, "entries": []}
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("bike_id", bike_id)
        data.setdefault("entries", [])
        return data
