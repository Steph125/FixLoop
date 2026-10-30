"""Chargement et validation des fiches de réparation."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "spec" / "procedure_schema.json"
PROCEDURES_DIR = ROOT / "procedures"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_procedure(path: str | Path) -> dict:
    proc = json.loads(Path(path).read_text(encoding="utf-8"))
    jsonschema.validate(proc, load_schema())
    for step in proc["steps"]:
        for rule in step.get("success", []) + step.get("anomaly", []):
            for key in ("part", "a", "b"):
                if key in rule and rule[key] not in proc["parts"]:
                    raise ValueError(f"{proc['id']}/{step['id']} : pièce inconnue '{rule[key]}'")
    return proc


def load_all(directory: str | Path = PROCEDURES_DIR) -> dict[str, dict]:
    return {p["id"]: p for p in (load_procedure(f) for f in sorted(Path(directory).glob("*.json")))}
