"""Benchmark de 3 approches sur des extraits étiquetés (spec/08-evaluation, EVAL-T6).

Usage : python scripts/benchmark.py --clips eval/benchmark/clips.csv --labels eval/benchmark/labels.csv
       --procedure chain_off_chainring --approaches spark,rules,fixloop --settings replay,live
       [--offline] [--fake] [--yes] [--out eval/benchmark] [--costs-root data/costs]

Modes : en ligne (SAM + Spark réels, EVAL-T7, pas pour cette série), `--offline`
(mesures et réponses depuis les caches, EVAL-R5.1), `--fake` (scène synthétique
`sim.py`, aucun réseau : prouve que le script tourne, EVAL-T6).
Le coût est estimé avant tout appel (EVAL-R6.1) et confirmé sauf `--yes` ;
au-delà de 30 $ (EVAL-R6.2), le script s'arrête.
"""

import argparse
import asyncio
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixloop.benchmark import (CannedAgent, NoSparkAgent, drive_measures, drive_session,  # noqa: E402
                               false_reminder_recall, false_validations, image_confusion,
                               missed_validations, read_clips, read_labels,
                               run_spark_only, validation_delays, approach_counts)
from fixloop.cached_models import CachedAgent  # noqa: E402
from fixloop.costs import CostLog  # noqa: E402

SAM_VIDEO_RATE = 0.20 / 1000  # $ par image vidéo (steering/tech.md, section 3)
SPARK_CALL_EST = 0.01  # $ par appel Spark avec images (design 08, section 5)
BUDGET_USD = 30.0  # EVAL-R6.2
SAM_PARTS = 2  # chaîne + plateau (live_parts)
SAM_FPS = 10.0
SPARK_MODEL_DEFAULT = "muse-spark-1.3"  # EVAL-D5 : `--model` pour Spark seul

RESULT_COLUMNS = ["clip", "approach", "setting", "false_validations",
                  "transition_validations", "missed_validations",
                  "delay_median_s", "delay_max_s", "recall_total",
                  "recall_signaled", "spark_calls", "sam_images", "cost_usd_est"]


def estimate(clips, labels_by_clip, approaches, settings):
    """Coût estimé avant tout appel (EVAL-R6.1)."""
    sam_images, spark_calls = 0, 0
    for clip in clips:
        rows = labels_by_clip.get(clip["clip"], [])
        duration = max([r["t"] for r in rows] + [0]) + 1
        dones = sum(r["done"] for r in rows)
        if "rules" in approaches or "fixloop" in approaches:
            sam_images += duration * SAM_FPS * SAM_PARTS
        if "fixloop" in approaches:
            spark_calls += len(settings) * 3  # arbitrage + explications, ordre de grandeur
        if "spark" in approaches:
            spark_calls += len(settings) * (duration / 3 + dones)
    sam_usd = sam_images * SAM_VIDEO_RATE
    spark_usd = spark_calls * SPARK_CALL_EST
    return {"sam_images": sam_images, "spark_calls": spark_calls,
            "sam_usd": sam_usd, "spark_usd": spark_usd,
            "total_usd": sam_usd + spark_usd}


def labels_to_segments(rows):
    """Lignes d'étiquettes -> [(sorte sim, secondes)] ; `transition` prolonge."""
    segments, last = [], "off"
    for row in sorted(rows, key=lambda r: r["t"]):
        kind = row["state"] if row["state"] in ("on", "off", "hidden") else last
        if segments and segments[-1][0] == kind:
            segments[-1] = (kind, segments[-1][1] + 1)
        else:
            segments.append((kind, 1))
        last = kind
    return segments


def summarize(delays):
    if not delays:
        return "", ""
    return (round(statistics.median(delays), 2),
            round(max(delays), 2))


def run_clip_fake(clip, rows, procedure, approaches, settings, costs):
    """Un extrait synthétique, sans réseau (EVAL-T6)."""
    from fixloop.procedures import load_all
    step = load_all()[procedure]["steps"][1]  # étape de remise évaluée
    segments = labels_to_segments(rows)
    done_at = [float(r["t"]) for r in rows if r["done"] == 1]
    out = []
    for setting in settings:
        if "rules" in approaches:
            session, measures = drive_session(procedure, segments, done_at, setting,
                                              agent=NoSparkAgent(procedure))
            out.append((setting, "rules", session, measures, None))
        if "fixloop" in approaches:
            session, measures = drive_session(procedure, segments, done_at, setting,
                                              agent=CannedAgent(procedure))
            out.append((setting, "fixloop", session, measures, None))
        if "spark" in approaches:
            kinds = [k for k, s in segments for _ in range(s)]
            images = [(float(i), None) for i in range(len(kinds))]
            canned = CannedAgent(procedure)
            res = run_spark_only(images, done_at,
                                 lambda img: canned.spark_only_verdict([img], step))
            out.append((setting, "spark", None, [], res))
    return out, segments


def result_row(clip, approach, setting, events, measures, labels, spark_extra=0,
               procedure="chain_off_chainring"):
    """Une ligne de `results.csv` (EVAL-R7.3)."""
    from fixloop.procedures import load_all
    require_done = any(s.get("requires_done")
                       for s in load_all()[procedure]["steps"])
    fv = false_validations(events, labels)
    done_times = [float(r["t"]) for r in labels if r["done"] == 1]
    delays = validation_delays(events, labels, require_done, done_times)
    med, mx = summarize(delays)
    recall = false_reminder_recall(events, labels)
    counts = approach_counts(events, measures)
    spark_calls = counts["spark_calls"] + spark_extra
    if approach == "rules":  # EVAL-R3.2 : `NoSparkAgent` compté par la session, aucun appel réel
        spark_calls = 0
    sam_images = counts["sam_images"]
    sam_cost = max(sam_images, 50) * SAM_VIDEO_RATE if sam_images else 0.0
    cost = sam_cost + spark_calls * SPARK_CALL_EST  # Spark seul : aucun appel SAM
    return {"clip": clip, "approach": approach, "setting": setting,
            "false_validations": fv["false"],
            "transition_validations": fv["transition"],
            "missed_validations": missed_validations(events, labels, require_done,
                                                     done_times),
            "delay_median_s": med, "delay_max_s": mx,
            "recall_total": recall["total"], "recall_signaled": recall["signaled"],
            "spark_calls": spark_calls, "sam_images": sam_images,
            "cost_usd_est": round(cost, 4)}


def resolve_video(clip, clips_path):
    """Chemin vidéo d'un extrait : tel quel, sinon relatif à `clips.csv`."""
    video = Path(clip["file"])
    if not video.is_file():
        video = Path(clips_path).parent / clip["file"]
    if not video.is_file():
        sys.exit(f"vidéo introuvable : {clip['file']} (EVAL-T1, tourner avant d'exécuter)")
    return video


def read_sam_cache(sam_dir, procedure) -> dict:
    """Sorties brutes SAM depuis le cache, sans aucun appel (EVAL-R5.1)."""
    from fixloop.perception import live_parts
    merged = {}
    for part in live_parts(procedure):
        path = Path(sam_dir) / f"raw_{part}.txt"
        if not path.is_file():
            raise RuntimeError(f"cache SAM brut manquant : {path} "
                               "(passer d'abord en ligne, EVAL-T7)")
        merged[part] = path.read_text(encoding="utf-8")
    return merged


def fetch_online(video, procedure, sam_dir) -> dict:
    """Segmente une vidéo avec SAM 3.1 (auteur, EVAL-T7) ; cache par morceau."""
    from fixloop.perception import segment_video
    asyncio.run(segment_video(str(video), procedure, str(sam_dir)))
    return read_sam_cache(sam_dir, procedure)


def clip_frames(video, merged: dict, procedure):
    """Sorties brutes + vidéo -> mesures SAM et images clés recadrées (sync)."""
    import cv2
    import numpy as np
    from fixloop.agent import crop_around
    from fixloop.perception import assemble_frames
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"vidéo illisible : {video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or SAM_FPS
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frames = assemble_frames(merged, h, w, SAM_FPS, procedure.get("select", {}))
    if not frames:  # SAM muet sur tout l'extrait : un résultat, pas une panne (rien n'est validé)
        cap.release()
        print(f"{video} : aucune image segmentée (SAM muet)")
        return [], []
    wanted = {int(round(fm.t * src_fps)) for fm in frames}  # seulement celles-ci en RAM
    picked, last, j = {}, None, 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if j in wanted:
            picked[j] = img
        last = img
        j += 1
    cap.release()
    if last is None:
        raise RuntimeError(f"vidéo vide : {video}")
    keyframes = []
    for fm in frames:
        bgr = picked.get(int(round(fm.t * src_fps)), last)
        ring = fm.masks.get("chainring")
        if ring is not None and ring.any() and ring.shape == bgr.shape[:2]:
            ys, xs = np.nonzero(ring)
            box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
            try:
                keyframes.append(crop_around(bgr, box))
                continue
            except Exception:
                pass
        keyframes.append(bgr)
    return frames, keyframes


def setting_view(measures: list, keyframes: list, setting: str):
    """Réglage `replay` (toutes les images) ou `live` (1 image/s, EVAL-R3.5)."""
    if setting != "live":
        return list(measures), list(keyframes)
    picked = []
    for second in range(int(max(m.t for m in measures)) + 1):
        picked.append(min(range(len(measures)), key=lambda i: abs(measures[i].t - second)))
    return [measures[i] for i in picked], [keyframes[i] for i in picked]


def run_clip_real(clip: str, rows: list, procedure_id: str, procedure: dict,
                  approaches: list, settings: list, frames: list, keyframes: list,
                  fixloop_agent, spark_ask):
    """Un extrait segmenté, 3 approches sur les mêmes mesures (EVAL-R3.4).

    `fixloop_agent` : `CachedAgent(SparkAgent)` en ligne, `CachedAgent(None)`
    hors ligne. `spark_ask(image)` : verdict Spark brut en cache (EVAL-T5).
    Rend `[(setting, approach, session|None, measures, res|None)]`.
    """
    from fixloop.geometry import measure
    from fixloop.procedures import load_all
    if not frames:  # aucune mesure : aucune session à conduire, aucun appel Spark
        return [(setting, approach, None, [], {"events": [], "calls": 0})
                for setting in settings for approach in approaches]
    step = load_all()[procedure_id]["steps"][1]  # étape de remise évaluée
    done_at = [float(r["t"]) for r in rows if r["done"] == 1]
    measures_all = [measure(fm, procedure) for fm in frames]
    out = []
    for setting in settings:
        ms, kf = setting_view(measures_all, keyframes, setting)
        if "rules" in approaches:
            session = drive_measures(procedure_id, ms, done_at, setting,
                                     agent=NoSparkAgent(procedure_id),
                                     keyframes=kf)
            out.append((setting, "rules", session, ms, None))
        if "fixloop" in approaches:
            session = drive_measures(procedure_id, ms, done_at, setting,
                                     agent=fixloop_agent, keyframes=kf)
            out.append((setting, "fixloop", session, ms, None))
        if "spark" in approaches:
            images = [(m.t, kf[i]) for i, m in enumerate(ms)]
            res = run_spark_only(images, done_at, spark_ask)
            out.append((setting, "spark", None, [], res))
    return out


def append_results(rows, costs, clip_id, rows_clip, ran, procedure):
    """`ran` (faux ou réel) -> lignes de `results.csv` + journal des coûts."""
    for setting, approach, session, measures, res in ran:
        if session is None:
            events, spark_extra = res["events"], res["calls"]
        else:
            events, spark_extra = session.log, 0
        row = result_row(clip_id, approach, setting, events,
                         measures, rows_clip, spark_extra,
                         procedure=procedure)
        log_costs(costs, clip_id, row["sam_images"], row["spark_calls"])
        rows.append(row)


def add_confusion(confusion: dict, ran, rows_clip) -> None:
    """Cumule le classement par image des règles SAM (EVAL-R4.5, `transition` exclue)."""
    for setting, approach, _session, measures, _res in ran:
        if approach == "rules":
            for (pred, true), n in image_confusion(measures, rows_clip).items():
                key = (setting, true, pred)
                confusion[key] = confusion.get(key, 0) + n


def spark_cache_or_exit(path, what: str):
    """Cache Spark requis hors ligne : absent ou vide -> arrêt (EVAL-R5.1)."""
    import json
    try:
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        entries = {}
    if not entries:
        sys.exit(f"hors ligne sans cache Spark ({what}) : {path} "
                 "(passer d'abord en ligne, EVAL-T7)")
    return path


def log_costs(costs, clip, sam_images, spark_calls):
    """Journalise l'estimation dans le journal des coûts (EVAL-R7.3)."""
    costs.add(model="sam-3.1", kind="video", units=sam_images, seconds=0.0,
              ok=True, estimated=True, session_id=clip, call="benchmark")
    if spark_calls:
        costs.add(model="muse-spark-1.3", kind="in", units=spark_calls * 1500,
                  seconds=0.0, ok=True, estimated=True, session_id=clip,
                  call="benchmark")


def run_clip_online(clip, args, procedure, approaches, settings):
    """Un extrait en ligne : SAM 3.1 + Spark, caches enregistrés (EVAL-T7)."""
    from fixloop.agent import SparkAgent
    from fixloop.procedures import load_all
    video = resolve_video(clip, args.clips)
    sam_dir = Path(args.sam_cache) / clip["clip"]
    sam_dir.mkdir(parents=True, exist_ok=True)
    merged = fetch_online(video, procedure, sam_dir)  # SAM 3.1, cache par morceau
    frames, keyframes = clip_frames(video, merged, procedure)
    spark_cache = Path(args.spark_cache)
    spark_cache.mkdir(parents=True, exist_ok=True)
    procedures = load_all()
    fixloop_agent = CachedAgent(SparkAgent(procedures), spark_cache / "fixloop.json")
    spark_inner = SparkAgent(procedures, model=args.model)  # EVAL-D5
    spark_cached = CachedAgent(spark_inner, spark_cache / "spark_only.json")
    step = procedure["steps"][1]
    ask = lambda img: spark_cached.spark_only([img], step)
    labels = read_labels(args.labels)[clip["clip"]]
    return run_clip_real(clip["clip"], labels, args.procedure, procedure,
                         approaches, settings, frames, keyframes,
                         fixloop_agent, ask)


def run_clip_offline(clip, args, procedure, approaches, settings):
    """Un extrait hors ligne : caches seuls, aucun appel (EVAL-R5.1)."""
    video = resolve_video(clip, args.clips)
    sam_dir = Path(args.sam_cache) / clip["clip"]
    try:
        merged = read_sam_cache(sam_dir, procedure)
    except RuntimeError as exc:
        sys.exit(f"hors ligne sans cache SAM : {clip['clip']} ({exc})")
    frames, keyframes = clip_frames(video, merged, procedure)
    spark_cache = Path(args.spark_cache)
    fixloop_agent = CachedAgent(None, spark_cache_or_exit(spark_cache / "fixloop.json",
                                                          "FixLoop"))
    spark_cached = CachedAgent(None, spark_cache_or_exit(spark_cache / "spark_only.json",
                                                         "Spark seul"))
    step = procedure["steps"][1]
    ask = lambda img: spark_cached.spark_only([img], step)
    labels = read_labels(args.labels)[clip["clip"]]
    return run_clip_real(clip["clip"], labels, args.procedure, procedure,
                         approaches, settings, frames, keyframes,
                         fixloop_agent, ask)


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark de 3 approches (EVAL-T6).")
    ap.add_argument("--clips", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--procedure", default="chain_off_chainring")
    ap.add_argument("--approaches", default="spark,rules,fixloop")
    ap.add_argument("--settings", default="replay,live")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--out", default="eval/benchmark")
    ap.add_argument("--costs-root", default="data/costs")
    ap.add_argument("--sam-cache", default="data/eval/sam",
                    help="sorties brutes SAM par extrait (EVAL-R5.1)")
    ap.add_argument("--spark-cache", default="eval/benchmark/cache",
                    help="réponses Spark en cache (EVAL-R5.2)")
    ap.add_argument("--model", default=SPARK_MODEL_DEFAULT,
                    help="modèle Spark pour l'approche Spark seul (EVAL-D5)")
    args = ap.parse_args()

    clips = read_clips(args.clips)
    labels_by_clip = read_labels(args.labels)
    approaches = [a.strip() for a in args.approaches.split(",") if a.strip()]
    settings = [s.strip() for s in args.settings.split(",") if s.strip()]
    for clip in clips:
        if clip["clip"] not in labels_by_clip:
            sys.exit(f"extrait sans étiquettes : {clip['clip']}")

    est = estimate(clips, labels_by_clip, approaches, settings)
    print(f"estimation : {est['sam_images']:.0f} images SAM "
          f"({est['sam_usd']:.2f} $) + {est['spark_calls']:.0f} appels Spark "
          f"({est['spark_usd']:.2f} $) = {est['total_usd']:.2f} $")
    if est["total_usd"] > BUDGET_USD:
        sys.exit(f"budget dépassé : {est['total_usd']:.2f} $ > {BUDGET_USD:.0f} $ (EVAL-R6.2)")
    if not args.yes and not args.offline and not args.fake:
        answer = input("Lancer le benchmark en ligne ? [o/N] ")
        if answer.strip().lower() not in ("o", "oui", "y", "yes"):
            sys.exit("abandon (sans confirmation, aucun appel).")
    if not args.offline and not args.fake:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # MODEL_API_KEY, jamais affichée

    from fixloop.procedures import load_all
    procedure = load_all()[args.procedure]
    costs = CostLog(root=args.costs_root)
    rows = []
    confusion: dict = {}
    spark_cache = Path(args.spark_cache)
    for clip in clips:
        rows_clip = labels_by_clip[clip["clip"]]
        if args.fake:
            ran, _ = run_clip_fake(clip["clip"], rows_clip, args.procedure,
                                   approaches, settings, costs)
            append_results(rows, costs, clip["clip"], rows_clip, ran,
                           procedure=args.procedure)
        elif args.offline:
            ran = run_clip_offline(clip, args, procedure, approaches, settings)
            add_confusion(confusion, ran, rows_clip)
            append_results(rows, costs, clip["clip"], rows_clip, ran,
                           procedure=args.procedure)
        else:
            ran = run_clip_online(clip, args, procedure, approaches, settings)
            add_confusion(confusion, ran, rows_clip)
            append_results(rows, costs, clip["clip"], rows_clip, ran,
                           procedure=args.procedure)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    if confusion:  # EVAL-R4.5 : classement par image, lu par le rapport
        with (out / "confusion.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["setting", "label", "interpretation", "images"])
            for (setting, true, pred), n in sorted(confusion.items()):
                w.writerow([setting, true, pred, n])
    print(f"{len(rows)} lignes -> {out / 'results.csv'} "
          f"(journal : {args.costs_root})")


if __name__ == "__main__":
    main()
