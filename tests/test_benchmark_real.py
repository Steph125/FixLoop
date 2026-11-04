"""Chemin réel du benchmark (spec/08-evaluation, EVAL-T6).

2 extraits vidéo synthétiques (écrits avec OpenCV dans tmp_path) passent par
le chemin EN LIGNE avec un faux client SAM et un faux Spark, puis par le
chemin `--offline` (caches seuls) : `results.csv` identiques (EVAL-R5.1).
Aucun appel réseau. Le transport async (`segment_video`) est couvert par
`tests/test_perception_live.py` (hors sandbox) ; ici, le faux SAM fournit les
mêmes sorties brutes, relues par le vrai parser.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import benchmark as bench  # noqa: E402
from fakes import FakeAgent, FakeSamClient  # noqa: E402
from test_replay_real import sim_raws, write_mp4  # noqa: E402

FPS, N_FRAMES = 10, 60  # 6 s à 10 images/s


def write_clip_video(path, n_off_frames):
    write_mp4(path, N_FRAMES)
    return sim_raws(N_FRAMES, n_off_frames)


def write_clips_and_labels(work):
    v1, v2 = work / "s1.mp4", work / "s2.mp4"
    raws1 = write_clip_video(v1, 30)  # 3 s off puis 3 s on
    raws2 = write_clip_video(v2, 60)  # 6 s off
    clips = work / "clips.csv"
    with clips.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "file", "duration_s", "lighting", "angle",
                    "distance", "scenario", "split"])
        w.writerow(["s1", str(v1), "6", "jour", "face", "30cm", "S1", "test"])
        w.writerow(["s2", str(v2), "6", "jour", "face", "30cm", "S1", "test"])
    labels = work / "labels.csv"
    with labels.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "t", "state", "done"])
        for t in range(6):
            w.writerow(["s1", str(t), "off" if t < 3 else "on",
                        "1" if t in (2, 4) else "0"])
        for t in range(6):
            w.writerow(["s2", str(t), "off", "1" if t == 2 else "0"])
    return {"s1": raws1, "s2": raws2}


class FakeSparkOnly:
    """Faux Spark pour l'approche Spark seul (réponses fixées, sans réseau)."""

    def __init__(self, verdict="reussie"):
        self.verdict, self.model = verdict, "muse-spark-1.3"

    def spark_only_verdict(self, images, step):
        return {"verdict": self.verdict, "confiance": 0.9, "raison": "faux Spark"}


def run_online(work, raws_by_clip, sam_cache, spark_cache):
    """Chemin EN LIGNE avec faux clients : segmentation, mesures, 3 approches."""
    from fixloop.cached_models import CachedAgent
    from fixloop.procedures import load_all
    clips = bench.read_clips(work / "clips.csv")
    labels = bench.read_labels(work / "labels.csv")
    procedure = load_all()["chain_off_chainring"]
    rows = []
    for clip in clips:
        sam = FakeSamClient(texts={"bicycle chain": raws_by_clip[clip["clip"]]["chain"],
                                   "chainring": raws_by_clip[clip["clip"]]["chainring"]})
        sam_dir = sam_cache / clip["clip"]
        sam_dir.mkdir(parents=True, exist_ok=True)
        merged = {"chain": sam.texts["bicycle chain"],
                  "chainring": sam.texts["chainring"]}
        for part, text in merged.items():  # cache brut, comme segment_video
            (sam_dir / f"raw_{part}.txt").write_text(text, encoding="utf-8")
        frames, keyframes = bench.clip_frames(clip["file"], merged, procedure)
        fixloop = CachedAgent(FakeAgent(), spark_cache / "fixloop.json")
        spark = CachedAgent(FakeSparkOnly(), spark_cache / "spark_only.json")
        step = procedure["steps"][1]
        ran = bench.run_clip_real(clip["clip"], labels[clip["clip"]],
                                  "chain_off_chainring", procedure,
                                  ["rules", "fixloop", "spark"], ["replay", "live"],
                                  frames, keyframes, fixloop,
                                  lambda img: spark.spark_only([img], step))
        for setting, approach, session, measures, res in ran:
            events = res["events"] if approach == "spark" else session.log
            extra = res["calls"] if approach == "spark" else 0
            rows.append(bench.result_row(clip["clip"], approach, setting, events,
                                         measures, labels[clip["clip"]], extra))
    return rows


def test_real_online_then_offline_give_identical_results(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    raws_by_clip = write_clips_and_labels(work)
    sam_cache, spark_cache = tmp_path / "sam", tmp_path / "spark"
    online = run_online(work, raws_by_clip, sam_cache, spark_cache)
    assert len(online) == 2 * 3 * 2  # 2 extraits x 3 approches x 2 réglages

    from fixloop.cached_models import CachedAgent
    from fixloop.procedures import load_all
    procedure = load_all()["chain_off_chainring"]
    labels = bench.read_labels(work / "labels.csv")
    offline = []
    for clip_id in ("s1", "s2"):
        video = str(work / f"{clip_id}.mp4")
        merged = bench.read_sam_cache(sam_cache / clip_id, procedure)  # aucun appel
        assert merged  # relit le cache brut de la passe en ligne
        frames, keyframes = bench.clip_frames(video, merged, procedure)
        fixloop = CachedAgent(None, spark_cache / "fixloop.json")
        spark = CachedAgent(None, spark_cache / "spark_only.json")
        step = procedure["steps"][1]
        ran = bench.run_clip_real(clip_id, labels[clip_id],
                                  "chain_off_chainring", procedure,
                                  ["rules", "fixloop", "spark"], ["replay", "live"],
                                  frames, keyframes, fixloop,
                                  lambda img: spark.spark_only([img], step))
        for setting, approach, session, measures, res in ran:
            events = res["events"] if approach == "spark" else session.log
            extra = res["calls"] if approach == "spark" else 0
            offline.append(bench.result_row(clip_id, approach, setting, events,
                                            measures, labels[clip_id], extra))
    assert offline == online  # EVAL-R5.1 : hors ligne à l'identique


def test_offline_cli_refuses_missing_cache(tmp_path):
    import subprocess
    work = tmp_path / "work"
    work.mkdir()
    write_clips_and_labels(work)
    out = work / "out"
    r = subprocess.run(
        [sys.executable, "scripts/benchmark.py", "--clips", str(work / "clips.csv"),
         "--labels", str(work / "labels.csv"), "--offline", "--yes",
         "--out", str(out), "--costs-root", str(work / "costs"),
         "--sam-cache", str(work / "sam"), "--spark-cache", str(work / "spark")],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert r.returncode != 0  # --offline sans cache : arrêt, jamais inventé
    assert "cache" in (r.stdout + r.stderr).lower()


def test_rules_row_counts_no_spark_call():
    import benchmark as bench
    events = [{"event": "diagnosis", "t": 0.0}, {"event": "closed", "t": 1.0,
                                                 "model_calls": {"spark": 3, "wonder": 2}}]
    labels = [{"clip": "c", "t": 0, "state": "off", "done": 0}]
    row = bench.result_row("c", "rules", "replay", events, [], labels)
    assert row["spark_calls"] == 0 and row["cost_usd_est"] == 0  # EVAL-R3.2 : aucun appel Spark
    other = bench.result_row("c", "fixloop", "replay", events, [], labels)
    assert other["spark_calls"] == 3


def test_clip_with_no_segmented_frame_is_a_result_not_a_crash():
    from fixloop.procedures import load_all
    procedure = load_all()["chain_off_chainring"]
    labels = [{"clip": "c", "t": 0, "state": "on", "done": 0}]
    ran = bench.run_clip_real("c", labels, "chain_off_chainring", procedure, ["rules", "fixloop"],
                              ["live"], [], [], None, None)  # SAM muet : aucun modèle appelé
    rows = []
    bench.append_results(rows, _NoCosts(), "c", labels, ran,
                         procedure="chain_off_chainring")
    assert [r["approach"] for r in rows] == ["rules", "fixloop"]
    assert all(r["false_validations"] == 0 and r["sam_images"] == 0 for r in rows)


class _NoCosts:
    def add(self, **kw):
        pass
