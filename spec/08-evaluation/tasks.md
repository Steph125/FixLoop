# 08 — Évaluation : tâches

## Fait

- [x] **EVAL-T0 — Première mesure sur une vidéo.** `velo2` : 0 image mal classée sur 285, seuils fixés.
  Exigences : base de `EVAL-R2.1` (`velo2` = `calib`). Preuve : `eval/day1/findings.md`.

## À faire

- [ ] **EVAL-T1 — Plan de tournage et tournage.** Remplir `clips.csv` (20 lignes au moins, matrice section 1,
  `split`) avant de filmer ; tourner ; copier dans `data/eval/` ; aucun visage ni document dans le champ.
  Exigences : `EVAL-R1.1`, `R1.2`, `R1.5`, `R2.1`, `R8.1`. Fait quand : chaque valeur de la matrice ≥ 3 fois.
- [ ] **EVAL-T2 — Étiquetage.** `labels.csv` seconde par seconde (outil `scripts/label_clip.py` facultatif) ;
  commit « labels » avant toute exécution.
  Exigences : `EVAL-R1.3`, `R1.4`.
- [ ] **EVAL-T3 — Calcul des mesures de comparaison.** Fonctions de la section 4 de `design.md`,
  `tests/test_benchmark.py` sur extraits synthétiques.
  Exigences : `EVAL-R4.1` à `R4.6`.
- [ ] **EVAL-T4 — Approches règles SAM et FixLoop.** `NoSparkAgent`, réglages `replay` et `live`
  (sous-échantillonnage, anti-rebond 3 / 4), `CachedAgent` partagé avec le replay.
  Exigences : `EVAL-R3.2` à `R3.5`. Dépend de : `CORE-T9`, `PERC-T5`, `RPL-T1`.
- [ ] **EVAL-T5 — Approche Spark seul.** Image toutes les 3 s et à chaque « c'est fait », machine minimale,
  cache des réponses.
  Exigences : `EVAL-R3.1`, `R3.4`. Dépend de : `AGT-T12`.
- [ ] **EVAL-T6 — Script `benchmark.py`.** Estimation et confirmation du coût, exécution en ligne puis hors
  ligne, `results.csv`, journal des coûts.
  Exigences : `EVAL-R5.1`, `R5.2`, `R6.1`, `R6.2`, `R7.3`.
- [ ] **EVAL-T7 — Exécution.** Passage en ligne, puis deux passages hors ligne identiques ; coût réel noté.
  Exigences : `EVAL-R2.2`, `R5.1`, `R6.2`, `R8.1`.
- [ ] **EVAL-T8 — Rapport et graphique.** `report.md` (structure section 6), `chart.svg`, limites, extraits
  ratés, versions et commit.
  Exigences : `EVAL-R2.3`, `R5.3`, `R7.1`, `R7.2`, `R7.4`.
- [ ] **EVAL-T9 — Gel des chiffres.** Mardi 3 nov. à midi : chiffres copiés dans le README et le script de la
  vidéo, chacun avec sa source.
  Exigences : `EVAL-R7.5`, `R8.1`. Utilisé par : `SUB-T3`, `SUB-T5`.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1, R1.2, R1.5 | T1 ; R1.3, R1.4 : T2 |
| R2.1 | T0, T1 ; R2.2 : T7 ; R2.3 : T8 |
| R3.1 | T5 ; R3.2, R3.3, R3.5 : T4 ; R3.4 : T4, T5 |
| R4.1–R4.6 | T3 |
| R5.1 | T6, T7 ; R5.2 : T6 ; R5.3 : T8 |
| R6.1 | T6 ; R6.2 : T6, T7 |
| R7.1, R7.2, R7.4 | T8 ; R7.3 : T6 ; R7.5 : T9 |
| R8.1 | T1, T7, T9 |
