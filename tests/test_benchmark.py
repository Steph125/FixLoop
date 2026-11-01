"""Benchmark de 3 approches (spec/08-evaluation, EVAL-R4).

EVAL-T3 : mesures de la section 4 du design sur 2 extraits synthétiques.
EVAL-T4 : approches règles SAM et FixLoop (NoSparkAgent, réglages replay/live).
EVAL-T5 : approche Spark seul (machine minimale, cache des réponses).
Aucun appel réseau : faux clients et scènes `fixloop/sim.py`.
"""

from fixloop.benchmark import (
    ON_MAX, OFF_MIN,
    classify_contact,
    false_reminder_recall,
    false_validations,
    approach_counts,
    image_confusion,
    label_at,
    missed_validations,
    on_segments,
    read_clips,
    read_labels,
    validation_delays,
)


def labels(rows):
    return [{"t": t, "state": s, "done": d} for t, s, d in rows]


def test_false_validation_counts_off_and_hidden():
    lab = labels([(0, "off", 0), (1, "off", 0), (2, "off", 0), (3, "off", 0),
                  (4, "off", 0), (5, "transition", 0), (6, "off", 0), (7, "off", 0),
                  (8, "off", 0), (9, "off", 0), (10, "hidden", 0), (11, "hidden", 0),
                  (12, "on", 0), (13, "on", 0), (14, "on", 0)])
    events = [{"event": "validated", "t": 2.0}, {"event": "validated", "t": 5.0},
              {"event": "validated", "t": 7.0}, {"event": "validated", "t": 11.0},
              {"event": "validated", "t": 13.0}]
    out = false_validations(events, lab)
    assert out["false"] == 3  # EVAL-R4.1 : 2 s et 7 s (off), 11 s (hidden)
    assert out["transition"] == 1  # 5 s : à part, pas une fausse validation
    assert len(out["details"]) == 3


def test_dynamic_close_counts_as_validation():
    lab = labels([(i, "off", 0) for i in range(6)])
    events = [{"event": "dynamic_start", "t": 1.0},
              {"event": "closed", "t": 4.0, "success": True}]
    assert false_validations(events, lab)["false"] == 1  # clôture du test dynamique


def test_missed_validation_and_delay_with_done():
    lab = labels([(i, "on", 1 if i == 2 else 0) for i in range(10)])
    assert missed_validations([{"event": "validated", "t": 6.0}], lab,
                              require_done=True, done_times=[2.0]) == 0
    assert validation_delays([{"event": "validated", "t": 6.0}], lab,
                             require_done=True, done_times=[2.0]) == [4.0]
    assert missed_validations([], lab, require_done=True, done_times=[2.0]) == 1
    assert validation_delays([], lab, require_done=True, done_times=[2.0]) == []


def test_missed_validation_needs_five_stable_seconds():
    lab = labels([(i, "on", 0) for i in range(4)])
    assert missed_validations([], lab) == 0  # EVAL-R4.2 : moins de 5 s, pas manquée


def test_missed_validation_waits_for_done_when_required():
    lab = labels([(i, "on", 0) for i in range(8)])
    assert missed_validations([], lab, require_done=True, done_times=[]) == 0


def test_false_reminder_recall_within_ten_seconds():
    lab = labels([(0, "off", 0), (1, "off", 0), (2, "off", 0), (3, "off", 1),
                  (4, "off", 0), (5, "on", 0), (6, "on", 0), (7, "on", 0),
                  (8, "off", 1), (9, "off", 0)] + [(i, "off", 0) for i in range(10, 20)])
    events = [{"event": "anomaly", "t": 5.0}]
    out = false_reminder_recall(events, lab)
    assert out == {"total": 2, "signaled": 1}  # EVAL-R4.4 : 3 s signalée, 8 s non


def test_image_confusion_excludes_transition():
    from fixloop.models import Measures
    ms = [Measures(i, float(i), {"chain": True, "chainring": True},
                   {("chain", "chainring"): c})
          for i, c in enumerate([0.07, 0.30, 0.22, float("nan")])]
    lab = labels([(0, "on", 0), (1, "off", 0), (2, "transition", 0), (3, "on", 0)])
    out = image_confusion(ms, lab)
    assert out[("en place", "on")] == 1  # 0,07 <= 0,18 contre on
    assert out[("tombée", "off")] == 1  # 0,30 >= 0,26 contre off
    assert out[("non vu", "on")] == 1  # NaN contre on
    assert sum(out.values()) == 3  # la transition est exclue (EVAL-R4.5)


def test_classify_contact_thresholds():
    assert classify_contact(0.18) == "en place"
    assert classify_contact(0.26) == "tombée"
    assert classify_contact(0.22) == "incertain"
    assert classify_contact(float("nan")) == "non vu"
    assert classify_contact(None) == "non vu"
    assert ON_MAX == 0.18 and OFF_MIN == 0.26  # seuils de la fiche


def test_label_at_uses_floor_and_missing_is_transition():
    lab = labels([(0, "off", 0), (1, "off", 1), (2, "on", 0)])
    assert label_at(lab, 1.9) == "off"
    assert label_at(lab, 2.0) == "on"
    assert label_at(lab, 9.0) == "transition"  # seconde inconnue : neutre


def test_on_segments_groups_consecutive_seconds():
    lab = labels([(0, "on", 0), (1, "on", 0), (2, "off", 0), (3, "on", 0),
                  (4, "on", 0), (5, "on", 0), (6, "on", 0), (7, "on", 0)])
    assert on_segments(lab) == [(0, 2), (3, 8)]


def test_approach_counts_spark_calls_and_sam_images():
    from fixloop.models import Measures
    events = [{"event": "diagnose", "t": 0.0, "model_calls": {"spark": 1, "wonder": 1}},
              {"event": "step", "t": 1.0, "model_calls": {"spark": 3, "wonder": 1}}]
    ms = [Measures(i, float(i), {"chain": True, "chainring": True},
                   {("chain", "chainring"): 0.07}) for i in range(5)]
    assert approach_counts(events, ms) == {"spark_calls": 3, "sam_images": 5}
    assert approach_counts([], []) == {"spark_calls": 0, "sam_images": 0}  # EVAL-R4.6


def test_read_labels_and_clips(tmp_path):
    import csv
    lp = tmp_path / "labels.csv"
    with lp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "t", "state", "done"])
        w.writerow(["c01", "0", "off", "0"])
        w.writerow(["c01", "1", "off", "1"])
    assert read_labels(lp) == {"c01": [{"t": 0, "state": "off", "done": 0},
                                       {"t": 1, "state": "off", "done": 1}]}
    cp = tmp_path / "clips.csv"
    with cp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "file", "duration_s", "lighting", "angle",
                    "distance", "scenario", "split"])
        w.writerow(["c01", "c01.mp4", "15", "jour", "face", "30cm", "S1", "test"])
    clips = read_clips(cp)
    assert clips[0]["clip"] == "c01" and clips[0]["split"] == "test"


def test_read_labels_rejects_bad_state(tmp_path):
    import pytest
    lp = tmp_path / "labels.csv"
    lp.write_text("clip,t,state,done\nc01,0,flou,0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_labels(lp)
