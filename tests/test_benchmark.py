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


def test_no_spark_agent_answers_without_calling():
    from fixloop.benchmark import NoSparkAgent
    from fixloop.procedures import load_all
    procs = load_all()
    agent = NoSparkAgent("chain_off_chainring")
    assert agent.diagnose([], procs, "aucun") == ("chain_off_chainring", None)
    v = agent.arbitrate(procs["chain_off_chainring"]["steps"][1], [], [])
    assert v.value == "0"  # EVAL-R3.2 : incertain reste sans décision, sans appel
    text, part = agent.explain(procs["chain_off_chainring"]["steps"][1],
                               v.__class__("eps", message="Règle."), [])
    assert text == "Règle." and part is None  # message de la règle
    assert agent.help(procs["chain_off_chainring"]["steps"][1], []) != ""


def test_settings_replay_and_live():
    from fixloop.benchmark import SETTINGS, drive_session
    replay = drive_session("chain_off_chainring", [("off", 4), ("on", 6)],
                           [3.5, 5.0], "replay")
    live = drive_session("chain_off_chainring", [("off", 4), ("on", 6)],
                         [3.0, 5.0], "live")
    assert replay[0].debounce_frames == 4 and SETTINGS["replay"]["fps"] == 10.0
    assert live[0].debounce_frames == 3 and SETTINGS["live"]["fps"] == 1.0
    assert len(replay[1]) == 100 and len(live[1]) == 10  # EVAL-R3.5 : deux réglages


def test_rules_approach_closes_synthetic_clip():
    from fixloop.benchmark import drive_session, false_reminder_recall, false_validations
    from fixloop.state_machine import State
    session, measures = drive_session("chain_off_chainring", [("off", 4), ("on", 6)],
                                      [3.5, 5.0], "replay")
    assert session.state == State.CLOTURE  # EVAL-R3.2 : règles SAM seules, remise correcte
    assert session.steps_validated == ["frame_view", "engage_top_teeth", "turn_backward"]
    lab = ([{"t": i, "state": "off", "done": 1 if i == 3 else 0} for i in range(4)]
           + [{"t": i, "state": "on", "done": 0} for i in range(4, 10)])
    assert [e["event"] for e in session.log].count("validated") == 3
    assert false_validations(session.log, lab)["false"] == 0
    assert false_reminder_recall(session.log, lab) == {"total": 1, "signaled": 1}


def test_fixloop_approach_arbitrates_hidden_and_replays_offline(tmp_path):
    from fixloop.benchmark import drive_session
    from fixloop.cached_models import CachedAgent
    from fakes import FakeAgent
    cache = tmp_path / "fixloop.models.json"
    segs = [("off", 2), ("hidden", 3), ("on", 6)]
    online, _ = drive_session("chain_off_chainring", segs, [1.5, 4.0], "replay",
                              agent=CachedAgent(FakeAgent(arbitrate_to="0"), cache))
    assert any(e["event"] == "arbitrate" for e in online.log)  # EVAL-R3.3 : Spark consulté
    offline, _ = drive_session("chain_off_chainring", segs, [1.5, 4.0], "replay",
                               agent=CachedAgent(None, cache))
    assert [(e["event"], e.get("t")) for e in offline.log] == [
        (e["event"], e.get("t")) for e in online.log]  # RPL-R2.3 : identique hors ligne


def test_spark_only_machine_validates_first_success():
    from fixloop.benchmark import false_validations, run_spark_only
    answers = iter([{"verdict": "impossible_a_dire", "confiance": 0.4, "raison": "flou"},
                    {"verdict": "reussie", "confiance": 0.9, "raison": "en place"}])
    images = [(float(t), object()) for t in range(0, 9, 3)]
    out = run_spark_only(images, [3.0], lambda img: next(answers))
    assert [e["event"] for e in out["events"]] == ["validated"]
    assert out["events"][0]["t"] == 3.0 and out["calls"] == 2
    lab = [{"t": i, "state": "off", "done": 0} for i in range(10)]
    assert false_validations(out["events"], lab)["false"] == 1  # fausse validation construite


def test_spark_only_anomaly_on_failure_after_done():
    from fixloop.benchmark import run_spark_only
    answers = iter([{"verdict": "ratee", "confiance": 0.8, "raison": "tombée"},
                    {"verdict": "ratee", "confiance": 0.8, "raison": "tombée"}])
    images = [(float(t), object()) for t in range(0, 9, 3)]
    out = run_spark_only(images, [1.0], lambda img: next(answers))
    kinds = [e["event"] for e in out["events"]]
    assert kinds == ["anomaly"]  # EVAL-R3.1 : « ratée » après « c'est fait »
    assert out["events"][0]["t"] == 1.0  # requête à l'instant du done, puis arrêt


def test_spark_only_queries_done_instants():
    from fixloop.benchmark import run_spark_only
    seen = []
    images = [(float(t), object()) for t in range(0, 12, 3)]
    run_spark_only(images, [4.0],
                   lambda img: seen.append(img) or {"verdict": "", "confiance": 0.0,
                                                    "raison": None})
    assert len(seen) == 5  # 0, 3, 6, 9 + le « c'est fait » de t = 4


def test_spark_only_answers_are_cached(tmp_path):
    from fixloop.cached_models import CachedAgent, OfflineError
    import pytest

    class FakeSparkOnly:
        def __init__(self, answers):
            self.answers, self.model, self.n = answers, "muse-spark-1.3", 0

        def spark_only_verdict(self, images, step):
            self.n += 1
            return dict(self.answers[min(self.n - 1, len(self.answers) - 1)])

    cache = tmp_path / "spark_only.json"
    online = CachedAgent(FakeSparkOnly([{"verdict": "reussie", "confiance": 0.9,
                                         "raison": "ok"}]), cache)
    first = online.spark_only(["img"], {"id": "s"})
    assert first["verdict"] == "reussie"
    offline = CachedAgent(None, cache)
    assert offline.spark_only(["img"], {"id": "s"}) == first  # EVAL-R5.2
    with pytest.raises(OfflineError):
        CachedAgent(None, tmp_path / "vide.json").spark_only(["autre"], {"id": "s"})


def test_benchmark_script_runs_offline_fake_on_synthetic_clips(tmp_path):
    import csv
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    work = tmp_path / "bench"
    work.mkdir()
    clips, labels = work / "clips.csv", work / "labels.csv"
    with clips.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "file", "duration_s", "lighting", "angle",
                    "distance", "scenario", "split"])
        w.writerow(["s1", "sim", "10", "jour", "face", "30cm", "S1", "test"])
        w.writerow(["s2", "sim", "10", "jour", "face", "30cm", "S1", "test"])
    rows = ([("s1", t, "off" if t < 4 else "on", 1 if t in (3, 5) else 0)
             for t in range(10)]
            + [("s2", t, "off", 1 if t == 3 else 0) for t in range(10)])
    with labels.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "t", "state", "done"])
        w.writerows(rows)
    out, costs = work / "out", work / "costs"
    r = subprocess.run(
        [sys.executable, "scripts/benchmark.py", "--clips", str(clips),
         "--labels", str(labels), "--procedure", "chain_off_chainring",
         "--approaches", "rules,fixloop,spark", "--settings", "replay,live",
         "--offline", "--fake", "--yes", "--out", str(out),
         "--costs-root", str(costs)],
        capture_output=True, text=True, cwd=root)
    assert r.returncode == 0, r.stderr  # EVAL-T6 : tourne en --offline sur synthétique
    got = {(x["clip"], x["approach"], x["setting"]): x for x in
           csv.DictReader((out / "results.csv").open(encoding="utf-8"))}
    assert len(got) == 2 * 3 * 2  # 2 extraits x 3 approches x 2 réglages
    assert got[("s1", "rules", "replay")]["false_validations"] == "0"
    assert got[("s1", "spark", "replay")]["false_validations"] == "1"
    assert float(got[("s1", "rules", "replay")]["cost_usd_est"]) >= 0
    assert list((costs).glob("*.jsonl")) != []  # EVAL-R7.3 : journal des coûts


def test_read_labels_rejects_bad_state(tmp_path):
    import pytest
    lp = tmp_path / "labels.csv"
    lp.write_text("clip,t,state,done\nc01,0,flou,0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_labels(lp)
