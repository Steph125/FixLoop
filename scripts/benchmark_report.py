"""Rapport et graphique du benchmark (spec/08-evaluation, EVAL-T10).

Usage : python scripts/benchmark_report.py --results eval/benchmark/results.csv
       --clips eval/benchmark/clips.csv --labels eval/benchmark/labels.csv
       [--out eval/benchmark]

Lit `results.csv`, `clips.csv`, `labels.csv` ; écrit `report.md` (structure de
`design.md` section 6 : tableau principal sur les extraits `test`, réglage
`live` puis `replay`, matrice de classement, extraits ratés, limites,
commande pour reproduire, date, commit et seuils) et `chart.svg` (barres
groupées : fausses validations et appels Spark par approche, motifs en plus
des couleurs, valeurs écrites, SVG manuscrit sans dépendance lourde).
Les phrases d'analyse restent à l'auteur (marquées « À ÉCRIRE »).
"""

import argparse
import csv
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APPROACHES = ("spark", "rules", "fixloop")
SETTINGS = ("live", "replay")


def read_results(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_splits(clips_path):
    """clip -> split (`calib` ou `test`)."""
    out = {}
    with open(clips_path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out[row["clip"]] = row.get("split", "test")
    return out


def git_commit():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except Exception:
        return "inconnu"


def num(row, key):
    try:
        return float(row.get(key) or 0)
    except ValueError:
        return 0.0


def aggregate(rows):
    """Lignes (même approche, même réglage, extraits test) -> synthèse."""
    false = sum(int(num(r, "false_validations")) for r in rows)
    transition = sum(int(num(r, "transition_validations")) for r in rows)
    missed = sum(int(num(r, "missed_validations")) for r in rows)
    medians = [num(r, "delay_median_s") for r in rows if r.get("delay_median_s")]
    delay_med = round(statistics.median(medians), 2) if medians else "—"
    delay_max = round(max(num(r, "delay_max_s") for r in rows), 2) if rows else "—"
    recall_t = sum(int(num(r, "recall_total")) for r in rows)
    recall_s = sum(int(num(r, "recall_signaled")) for r in rows)
    recall = f"{recall_s}/{recall_t}" if recall_t else "—"
    spark = round(sum(num(r, "spark_calls") for r in rows) / len(rows), 1) if rows else "—"
    cost = round(sum(num(r, "cost_usd_est") for r in rows) / len(rows), 4) if rows else "—"
    return {"false": false, "transition": transition, "missed": missed,
            "delay_med": delay_med, "delay_max": delay_max, "recall": recall,
            "spark": spark, "cost": cost, "n": len(rows)}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description="Rapport et graphique du benchmark (EVAL-T10).")
    ap.add_argument("--results", required=True)
    ap.add_argument("--clips", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", default="eval/benchmark")
    args = ap.parse_args(argv)

    from fixloop.benchmark import OFF_MIN, ON_MAX
    on_fr = str(ON_MAX).replace(".", ",")  # affichage français, comme les mesures
    off_fr = str(OFF_MIN).replace(".", ",")
    rows = read_results(args.results)
    splits = read_splits(args.clips)
    test_rows = [r for r in rows if splits.get(r["clip"], "test") == "test"]
    test_clips = sorted({r["clip"] for r in test_rows})
    table = {(a, s): aggregate([r for r in test_rows
                                if r["approach"] == a and r["setting"] == s])
             for a in APPROACHES for s in SETTINGS}
    today, commit = date.today().isoformat(), git_commit()

    lines = []
    lines.append("# Benchmark FixLoop : rapport")
    lines.append("")
    lines.append("## Question")
    lines.append("")
    lines.append("Est-ce que la boucle FixLoop (SAM + règles + arbitrage Spark qui ne "
                 "valide jamais) se trompe moins qu'une approche simple ?")
    lines.append("À ÉCRIRE : réponse en 3 lignes après exécution (EVAL-T7).")
    lines.append("")
    lines.append("## Protocole")
    lines.append("")
    lines.append(f"- Extraits `test` : {len(test_clips)} ({', '.join(test_clips) or 'aucun'}), "
                 "étiquetés seconde par seconde avant exécution (EVAL-R1.3, R1.4).")
    lines.append("- Réglages : `live` (direct simulé, 1 image/s, anti-rebond 3) puis "
                 "`replay` (10 images/s, anti-rebond 4) (EVAL-R3.5).")
    lines.append("- Modèles : sam-3.1 (segmentation), muse-spark-1.3 (arbitrage et "
                 "Spark seul, `--model` dans EVAL-D5).")
    lines.append(f"- Seuils de contact : en place ≤ {on_fr}, tombée ≥ {off_fr}.")
    lines.append(f"- Date : {today}, commit : {commit} (EVAL-R5.3).")
    lines.append("- Diagnostic hors périmètre (une seule fiche, design 08 §3).")
    lines.append("")
    lines.append("## Tableau principal (extraits `test`)")
    lines.append("")
    for setting in SETTINGS:
        lines.append(f"### Réglage `{setting}`")
        lines.append("")
        lines.append("| Approche | Fausses validations | Validations manquées | "
                     "Délai médian (s) | Délai max (s) | Fausses remises | "
                     "Appels Spark / extrait | Coût / extrait ($) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for approach in APPROACHES:
            g = table[(approach, setting)]
            lines.append(f"| {approach} | {g['false']} | {g['missed']} | {g['delay_med']} | "
                         f"{g['delay_max']} | {g['recall']} | {g['spark']} | {g['cost']} |")
        lines.append("")
    lines.append("À ÉCRIRE : lecture du tableau (quelle approche, quel réglage, pourquoi).")
    lines.append("")
    lines.append("## Matrice de classement par image (règles SAM)")
    lines.append("")
    lines.append("Interprétation FixLoop de chaque image (`en place` ≤ "
                 f"{on_fr}, `tombée` ≥ {off_fr}, `incertain`, `non vu`) contre "
                 "l'étiquette, `transition` exclue (EVAL-R4.5).")
    lines.append("")
    lines.append("| Réglage | Fausses validations | Validations pendant transition | "
                 "Validations manquées |")
    lines.append("|---|---|---|---|")
    for setting in SETTINGS:
        g = table[("rules", setting)]
        lines.append(f"| {setting} | {g['false']} | {g['transition']} | {g['missed']} |")
    lines.append("")
    lines.append("À ÉCRIRE : matrice détaillée par image depuis les mesures "
                 "(`tests/test_benchmark.py::test_image_confusion_excludes_transition`).")
    lines.append("")
    lines.append("## Extraits ratés")
    lines.append("")
    failed = [c for c in test_clips
              if any(int(num(r, "false_validations")) > 0 or int(num(r, "missed_validations")) > 0
                     for r in test_rows if r["clip"] == c)]
    if not failed:
        lines.append("Aucun extrait raté sur les chiffres actuels.")
    for clip in failed:
        detail = "; ".join(f"{r['approach']}/{r['setting']} : "
                            f"{r['false_validations']} fausse(s), "
                            f"{r['missed_validations']} manquée(s)"
                            for r in test_rows if r["clip"] == clip)
        lines.append(f"### {clip}")
        lines.append("")
        lines.append(detail + ".")
        lines.append("À ÉCRIRE : image et explication.")
        lines.append("")
    lines.append("## Limites")
    lines.append("")
    lines.append("- Un seul vélo, un seul utilisateur, étiquettes posées par l'auteur "
                 "(EVAL-R7.4).")
    lines.append(f"- {len(test_clips)} extraits `test` : intervalle de confiance large, "
                 "aucun objectif chiffré publié sauf 0 fausse validation (EVAL-D4).")
    lines.append("- Seuils réglés sur `velo2` et au plus 4 extraits `calib` (EVAL-R2.1) ; "
                 "toute modification après les résultats `test` est dite ici (EVAL-R2.3).")
    lines.append("")
    lines.append("## Reproduire")
    lines.append("")
    lines.append("```")
    lines.append(f"python scripts/benchmark.py --clips {args.clips} --labels {args.labels} "
                 "--procedure chain_off_chainring --approaches spark,rules,fixloop "
                 "--settings replay,live --offline --yes")
    lines.append("```")
    lines.append("")
    lines.append(f"Commande du rapport : `python scripts/benchmark_report.py --results {args.results} "
                 f"--clips {args.clips} --labels {args.labels} --out {args.out}`.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "chart.svg").write_text(chart(table), encoding="utf-8")
    print(f"rapport -> {out / 'report.md'}, graphique -> {out / 'chart.svg'}")
    return {"report": out / "report.md", "chart": out / "chart.svg"}


def chart(table) -> str:
    """Barres groupées par approche (réglage `live`, extraits `test`).

    Deux séries (fausses validations, appels Spark / extrait), motifs en plus
    des couleurs et valeurs écrites : lisible en noir et blanc (EVAL-R7.2).
    """
    series = [("Fausses validations", "false", "url(#hach)", 1.0),
              ("Appels Spark / extrait", "spark", "url(#pois)", 1.0)]
    approaches = list(APPROACHES)
    width, height, left, bottom, top = 560, 300, 150, 60, 30
    plot_w, plot_h = width - left - 20, height - top - bottom
    peak = max(1.0, max(float(table[(a, "live")][key]) if isinstance(
        table[(a, "live")][key], (int, float)) else 0.0
        for a in approaches for _, key, _, _ in series))
    bar_h = min(22, (plot_h // (len(approaches) * len(series) + 1)))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             'role="img" aria-label="Fausses validations et appels Spark par approche">',
             "<defs>",
             '<pattern id="hach" width="8" height="8" patternUnits="userSpaceOnUse" '
             'patternTransform="rotate(45)"><rect width="8" height="8" fill="white"/>'
             '<line x1="0" y1="0" x2="0" y2="8" stroke="black" stroke-width="2"/></pattern>',
             '<pattern id="pois" width="10" height="10" patternUnits="userSpaceOnUse">'
             '<rect width="10" height="10" fill="white"/>'
             '<circle cx="3" cy="3" r="1.6" fill="black"/></pattern>',
             "</defs>"]
    y = top + 6
    for a in approaches:
        parts.append(f'<text x="8" y="{y + bar_h * len(series) // 2}" font-size="14">{a}</text>')
        for label, key, fill, _ in series:
            value = table[(a, "live")][key]
            number = float(value) if isinstance(value, (int, float)) else 0.0
            w = plot_w * number / peak if peak else 0
            parts.append(f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{bar_h}" '
                         f'fill="{fill}" stroke="black"/>')
            parts.append(f'<text x="{left + w + 6:.1f}" y="{y + bar_h - 5}" '
                         f'font-size="12">{value} ({label})</text>')
            y += bar_h + 2
        y += 6
    parts.append(f'<text x="{left}" y="{height - 12}" font-size="12">Réglage live, '
                 "extraits test ; motifs distincts, valeurs écrites.</text>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    main()
