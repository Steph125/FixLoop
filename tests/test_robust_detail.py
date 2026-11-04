"""Détail par copie : la remise est-elle validée ? (spec/08-evaluation, EVAL-R9.5).

Un 0 fausse validation ne prouve rien si rien n'est validé. `scripts/robust_detail.py`
relit les sorties SAM en cache et vérifie que ses totaux redonnent ceux du benchmark. Aucun réseau.
"""

import csv
import sys
from functools import lru_cache
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import benchmark as bench  # noqa: E402
import robust_detail as rd  # noqa: E402
from test_replay_real import sim_raws as _sim_raws, write_mp4  # noqa: E402

PID = "chain_off_chainring"
sim_raws = lru_cache(_sim_raws)  # la même scène pour tous les tests : l'encodage des masques est lent


def procedure():
    from fixloop.procedures import load_all
    return load_all()[PID]


def labels_for(seconds, n_off, done_at=()):
    return [{"clip": "c", "t": t, "state": "off" if t < n_off else "on",
             "done": 1 if t in done_at else 0} for t in range(seconds)]


def frames_from(raws, h=400, w=400):
    from fixloop.perception import assemble_frames
    return assemble_frames(dict(raws), h, w, 10.0, procedure().get("select", {}))


def test_live_frames_keeps_nearest_image_of_each_second():
    raws = {"chain": "<0f>a\n<7f>a\n<12f>a\n", "chainring": "<25f>a\n"}
    assert rd.live_frames(raws) == {0, 12, 25}  # 10 -> 12 (2 d'écart, contre 3 pour 7) ; 20 -> 25
    assert rd.live_frames({"chain": "", "chainring": ""}) == set()


def test_detail_row_reports_validation_and_what_sam_saw():
    labels = labels_for(12, 3)
    row = rd.detail_row("c", "c", "original", frames_from(sim_raws(120, 30)), labels, PID, procedure())
    assert row["sam_silent"] == 0
    assert row["engage_t"] != "" and row["engage_label"] == "on"
    assert row["false_validations"] == 0
    assert row["chain_seen"] == row["chainring_seen"] == row["images_live"] == 12
    assert row["on_read_fallen"] == 0


def test_detail_row_counts_off_image_read_as_seated():
    labels = labels_for(12, 12)  # étiqueté `off` partout, alors que la scène passe `on` à 3 s
    row = rd.detail_row("c", "c", "dark", frames_from(sim_raws(120, 30)), labels, PID, procedure())
    assert row["off_read_seated"] > 0
    assert row["engage_label"] == "off" and row["false_validations"] >= 1


def test_detail_row_for_silent_clip():
    row = rd.detail_row("c", "c", "lowq", [], labels_for(5, 2), PID, procedure())
    assert row["sam_silent"] == 1
    assert row["images_live"] == 0 and row["engage_t"] == "" and row["engage_label"] == ""


def write_set(work, clip, raws, labels, sam_root, n_frames):
    video = work / f"{clip}.mp4"
    write_mp4(video, n_frames)
    clips = work / "clips.csv"
    with clips.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "file", "duration_s", "lighting", "angle", "distance", "scenario", "split"])
        w.writerow([clip, str(video), "12", "lampe", "face", "50cm", "S2", "test"])
    labels_path = work / "labels.csv"
    with labels_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "t", "state", "done"])
        for r in labels:
            w.writerow([clip, r["t"], r["state"], r["done"]])
    d = sam_root / clip
    d.mkdir(parents=True)
    for part, text in raws.items():
        (d / f"raw_{part}.txt").write_text(text, encoding="utf-8")
    return clips, labels_path


def full_benchmark_row(video, raws, labels):
    """Ce que `scripts/benchmark.py` écrit pour les règles SAM au réglage `live`."""
    frames, keyframes = bench.clip_frames(video, raws, procedure())
    ran = bench.run_clip_real("c", labels, PID, procedure(), ["rules"], ["live"],
                              frames, keyframes, None, None)
    rows = []
    bench.append_results(rows, _NoCosts(), "c", labels, ran, procedure=PID)
    return rows[0]


class _NoCosts:
    def add(self, **kw):
        pass


def run_main(work, clips, labels_path, sam_root, results):
    out = work / "detail.csv"
    rd.main(["--clips", str(clips), "--labels", str(labels_path), "--results", str(results),
             "--no-robust", "--sam-cache", str(sam_root), "--out", str(out)])
    return out


def write_results(path, row):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=bench.RESULT_COLUMNS)
        w.writeheader()
        w.writerow(row)


def test_main_matches_full_benchmark_and_writes_csv(tmp_path):
    raws = sim_raws(120, 30)
    labels = labels_for(12, 3, done_at=(6,))
    sam_root = tmp_path / "sam"
    clips, labels_path = write_set(tmp_path, "c", raws, labels, sam_root, 120)
    results = tmp_path / "results.csv"
    write_results(results, full_benchmark_row(tmp_path / "c.mp4", raws, labels))
    out = run_main(tmp_path, clips, labels_path, sam_root, results)
    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["clip"] for r in rows] == ["c"]
    assert rows[0]["transform"] == "original" and rows[0]["source"] == "c"
    assert rows[0]["engage_label"] == "on"


def test_main_refuses_totals_that_differ_from_benchmark(tmp_path):
    raws = sim_raws(120, 30)
    labels = labels_for(12, 3, done_at=(6,))
    sam_root = tmp_path / "sam"
    clips, labels_path = write_set(tmp_path, "c", raws, labels, sam_root, 120)
    results = tmp_path / "results.csv"
    row = full_benchmark_row(tmp_path / "c.mp4", raws, labels)
    row["false_validations"] = 7  # le benchmark dit autre chose : rien ne doit être écrit
    write_results(results, row)
    with pytest.raises(SystemExit, match="écart"):
        run_main(tmp_path, clips, labels_path, sam_root, results)
    assert not (tmp_path / "detail.csv").exists()
