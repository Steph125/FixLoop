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


def log_costs(costs, clip, sam_images, spark_calls):
    """Journalise l'estimation dans le journal des coûts (EVAL-R7.3)."""
    costs.add(model="sam-3.1", kind="video", units=sam_images, seconds=0.0,
              ok=True, estimated=True, session_id=clip, call="benchmark")
    if spark_calls:
        costs.add(model="muse-spark-1.3", kind="in", units=spark_calls * 1500,
                  seconds=0.0, ok=True, estimated=True, session_id=clip,
                  call="benchmark")


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

    costs = CostLog(root=args.costs_root)
    rows = []
    for clip in clips:
        rows_clip = labels_by_clip[clip["clip"]]
        if args.fake or args.offline:
            if not args.fake:
                sys.exit(f"hors ligne sans cache : {clip['clip']} "
                         "(exécution réelle EVAL-T7, pas pour cette série)")
            ran, _ = run_clip_fake(clip["clip"], rows_clip, args.procedure,
                                   approaches, settings, costs)
            for setting, approach, session, measures, res in ran:
                if approach == "spark":
                    events = res["events"]
                    spark_extra = res["calls"]
                else:
                    events = session.log
                    spark_extra = 0
                row = result_row(clip["clip"], approach, setting, events,
                                 measures, rows_clip, spark_extra,
                                 procedure=args.procedure)
                log_costs(costs, clip["clip"], row["sam_images"], row["spark_calls"])
                rows.append(row)
        else:
            sys.exit("exécution en ligne : EVAL-T7, pas pour cette série "
                     "(vidéos et clé API requises)")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} lignes -> {out / 'results.csv'} "
          f"(journal : {args.costs_root})")


if __name__ == "__main__":
    main()
