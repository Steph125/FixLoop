"""Outil d'étiquetage seconde par seconde (spec/08, design section 2).

La boucle interactive demande un écran et une vidéo ; seules les fonctions
pures sont testées ici (EVAL-T2 utilisera l'outil sur les 20 extraits).
"""

import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).resolve().parent.parent / "scripts" / "label_clip.py"
    spec = importlib.util.spec_from_file_location("label_clip", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_key_mapping_covers_four_states():
    lc = load()
    assert lc.KEY_TO_STATE == {"o": "off", "f": "on", "t": "transition", "h": "hidden"}
    assert lc.state_for_key("O") == "off" and lc.state_for_key("x") is None


def test_rows_for_clip_marks_done_seconds():
    lc = load()
    rows = lc.rows_for_clip("c01", ["off", "off", "on"], [1])
    assert rows == [{"clip": "c01", "t": 0, "state": "off", "done": 0},
                    {"clip": "c01", "t": 1, "state": "off", "done": 1},
                    {"clip": "c01", "t": 2, "state": "on", "done": 0}]
    import pytest
    with pytest.raises(ValueError):
        lc.rows_for_clip("c01", ["flou"], [])


def test_write_labels_csv_replaces_clip_and_keeps_others(tmp_path):
    lc = load()
    path = tmp_path / "labels.csv"
    lc.write_labels_csv(path, lc.rows_for_clip("c01", ["off", "on"], []))
    lc.write_labels_csv(path, lc.rows_for_clip("c02", ["hidden"], [0]))
    lc.write_labels_csv(path, lc.rows_for_clip("c01", ["on", "on"], [1]))
    import csv
    got = list(csv.DictReader(path.open(encoding="utf-8")))
    c01 = [r for r in got if r["clip"] == "c01"]
    assert [(r["t"], r["state"], r["done"]) for r in c01] == [
        ("0", "on", "0"), ("1", "on", "1")]  # remplacé, pas doublé
    assert any(r["clip"] == "c02" for r in got)
    states, done = lc.read_done(path, "c01")
    assert (states, done) == (["on", "on"], [1])  # reprise d'étiquetage
