"""Générateur du rapport et du graphique (spec/08-evaluation, EVAL-T10).

`scripts/benchmark_report.py` lit `results.csv`, `clips.csv`, `labels.csv` et
écrit `report.md` (structure de `design.md` section 6) et `chart.svg` (barres
groupées, sans dépendance lourde). Les phrases d'analyse restent à l'auteur
(marquées « À ÉCRIRE »). Aucun réseau.
"""

import csv
from pathlib import Path


def write_inputs(work):
    clips = work / "clips.csv"
    with clips.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "file", "duration_s", "lighting", "angle",
                    "distance", "scenario", "split"])
        w.writerow(["t1", "t1.mp4", "10", "jour", "face", "30cm", "S1", "test"])
        w.writerow(["t2", "t2.mp4", "10", "jour", "face", "30cm", "S2", "test"])
        w.writerow(["c1", "c1.mp4", "10", "jour", "face", "30cm", "S1", "calib"])
    labels = work / "labels.csv"
    with labels.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "t", "state", "done"])
        for clip in ("t1", "t2", "c1"):
            for t in range(10):
                w.writerow([clip, str(t), "off" if t < 4 else "on",
                            "1" if t == 5 else "0"])
    results = work / "results.csv"
    with results.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "approach", "setting", "false_validations",
                    "transition_validations", "missed_validations",
                    "delay_median_s", "delay_max_s", "recall_total",
                    "recall_signaled", "spark_calls", "sam_images", "cost_usd_est"])
        for clip in ("t1", "t2", "c1"):
            for setting in ("live", "replay"):
                w.writerow([clip, "spark", setting, "1", "0", "0",
                            "2.0", "2.0", "1", "0", "5", "0", "0.05"])
                w.writerow([clip, "rules", setting, "0", "0", "0",
                            "1.5", "2.5", "1", "1", "0", "100", "0.02"])
                w.writerow([clip, "fixloop", setting, "0", "0", "1",
                            "1.0", "1.0", "1", "1", "2", "100", "0.04"])
    return clips, labels, results


def test_report_and_chart_sections(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import benchmark_report as rep
    clips, labels, results = write_inputs(tmp_path)
    out = tmp_path / "bench"
    rep.main(["--results", str(results), "--clips", str(clips),
              "--labels", str(labels), "--out", str(out)])
    md = (out / "report.md").read_text(encoding="utf-8")
    for section in ("Question", "Protocole", "Tableau principal", "Matrice",
                    "Extraits ratés", "Limites", "Reproduire"):
        assert section in md, f"section manquante : {section}"  # design 08, §6
    assert "À ÉCRIRE" in md  # analyses à l'auteur, marquées
    assert "c1" not in md.split("Tableau principal")[1].split("Matrice")[0]  # test seuls
    for token in ("live", "replay", "spark", "rules", "fixloop",
                  "0,18", "0,26", "muse-spark-1.3", "sam-3.1"):
        assert token in md, f"mention manquante : {token}"  # seuils, versions, réglages
    svg = (out / "chart.svg").read_text(encoding="utf-8")
    assert "<svg" in svg
    for token in ("spark", "rules", "fixloop"):
        assert token in svg  # une série par approche, motifs + valeurs
