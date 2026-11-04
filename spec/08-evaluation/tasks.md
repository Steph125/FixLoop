# 08 — Évaluation : tâches

## Fait

- [x] **EVAL-T0 — Première mesure sur une vidéo.** `velo2` : 0 image mal classée sur 285, seuils fixés.
  Exigences : base de `EVAL-R2.1` (`velo2` = `calib`). Preuve : `eval/day1/findings.md`.

## À faire

- [ ] **EVAL-T1 — Plan de tournage et tournage.** Remplir `clips.csv` (20 lignes au moins, matrice section 1,
  `split`) avant de filmer ; tourner ; copier dans `data/eval/` ; aucun visage ni document dans le champ.
  Exigences : `EVAL-R1.1`, `R1.2`, `R1.5`, `R2.1`, `R8.1`. Fait quand : chaque valeur de la matrice ≥ 3 fois.
  `EVAL-D6` (2 nov.) : 2 éclairages (lampe, soir) ; nombre d'extraits = ceux filmés, limite dite dans le rapport.
  État au 3 nov. : 8 extraits. Lampe 6, soir 2 ; face 6, plongée 2, aucun à 30° de côté ; 50 cm 6, 30 cm 2 ; S2 3,
  S3 2, S5 1, S6 2, aucun S1 ni S4. « Fait quand » n'est pas atteint : à dire dans les limites du rapport.
  Décision de l'auteur (4 nov.) : pas de nouveau tournage, le jeu reste à ces 8 extraits.
- [x] **EVAL-T2 — Étiquetage.** `labels.csv` seconde par seconde (outil `scripts/label_clip.py` facultatif) ;
  commit « labels » avant toute exécution.
  Exigences : `EVAL-R1.3`, `R1.4`.
  Preuve (3 nov.) : `eval/benchmark/labels.csv`, 8 extraits (`EVAL-D8`), commit avant la première exécution.
- [x] **EVAL-T3 — Calcul des mesures de comparaison.** Fonctions de la section 4 de `design.md`,
  `tests/test_benchmark.py` sur extraits synthétiques.
  Exigences : `EVAL-R4.1` à `R4.6`.
  Preuve : `fixloop/benchmark.py` + `tests/test_benchmark.py` 12 passed (fausse validation off/hidden,
  clôture dynamique, validation manquée, délai depuis `done`, rappel des fausses remises, confusion
  par image hors transition, lecture `labels.csv` / `clips.csv`).
- [x] **EVAL-T4 — Approches règles SAM et FixLoop.** `NoSparkAgent`, réglages `replay` et `live`
  (sous-échantillonnage, anti-rebond 3 / 4), `CachedAgent` partagé avec le replay.
  Exigences : `EVAL-R3.2` à `R3.5`. Dépend de : `CORE-T9` ([x]), `PERC-T5` ([x]), `RPL-T1` ([x]).
  Preuve : `tests/test_benchmark.py` (NoSparkAgent, réglages 10 fps/4 et 1 fps/3, clôture synthétique
  sans fausse validation, arbitrage sur `hidden` rejoué à l'identique hors ligne).
  Choix : `false_validations` exclut le cadrage (`frame_view`, visibilité seule) — sinon la cible 0
  du design serait inatteignable → SPEC À REVOIR (design 08, section 4).
- [x] **EVAL-T5 — Approche Spark seul.** Image toutes les 3 s et à chaque « c'est fait », machine minimale,
  cache des réponses.
  Exigences : `EVAL-R3.1`, `R3.4`. Dépend de : `AGT-T12` ([x]).
  Preuve : `run_spark_only` (requêtes 3 s + `done`, arrêt au 1er terminal) + `CachedAgent.spark_only` ;
  `tests/test_benchmark.py` (fausse validation construite sur `off`, anomalie après `done`, cache rejoué).
- [x] **EVAL-T6 — Script `benchmark.py`.** Estimation et confirmation du coût, exécution en ligne puis hors
  ligne, `results.csv`, journal des coûts.
  Exigences : `EVAL-R5.1`, `R5.2`, `R6.1`, `R6.2`, `R7.3`.
  Preuve : `scripts/benchmark.py` tourne en `--offline --fake` sur 2 extraits synthétiques
  (12 lignes `results.csv`, journal des coûts) ; `eval/benchmark/labels_template.csv` (en-tête seul) ;
  `scripts/label_clip.py` (fonctions pures testées, servira EVAL-T2).
  Fait quand (série 4) : le script tourne en `--offline` sur les extraits synthétiques — fait ;
  l'exécution réelle (EVAL-T7) n'est pas pour cette série.
  **Relecture du 1er nov. : rouverte.** Pour EVAL-T6 : seul `--fake` fonctionne ; le chemin en ligne s'arrête
  (« pas pour cette série ») et `--offline` exige `--fake`. Il manque : pour chaque extrait de `clips.csv`,
  `segment_video` (chaîne et plateau, cache `data/eval/sam/<clip>/`), mesures, réglages `replay` et `live`,
  `CachedAgent(SparkAgent)` pour FixLoop et Spark seul (cache `eval/benchmark/cache/`), images clés lues dans la
  vidéo ; `--offline` relit ces caches sans aucun appel et s'arrête si une réponse manque ; option
  `--model muse-spark-1.3-contributor` pour Spark seul (`EVAL-D5`). Fait quand : 2 extraits vidéo synthétiques
  (écrits avec OpenCV) passent en ligne avec un faux client SAM et un faux Spark, puis en `--offline` avec des
  `results.csv` identiques.
  Preuve (1er nov.) : `tests/test_benchmark_real.py` 2 passed (2 extraits vidéo OpenCV en ligne
  avec faux SAM + faux Spark, puis `--offline`, `results.csv` identiques ; `--offline` sans cache
  refusé) ; `scripts/benchmark.py --model` (EVAL-D5), `--sam-cache`, `--spark-cache`.
  Correction du 2 nov. : `benchmark.py` charge `.env` avant le passage en ligne (sinon `KeyError` sur
  `MODEL_API_KEY` juste après la confirmation du coût).
- [x] **EVAL-T7 — Exécution.** Passage en ligne, puis deux passages hors ligne identiques ; coût réel noté.
  Exigences : `EVAL-R2.2`, `R5.1`, `R6.2`, `R8.1`.
  Preuve (4 nov.) : `eval/benchmark/results.csv`, 8 extraits en ligne, puis deux passages `--offline` identiques
  octet par octet. Coût estimé au journal : 1,68 $ (la page Usage reste à comparer par l'auteur).
- [x] **EVAL-T8 — Rapport et graphique.** `report.md` (structure section 6), `chart.svg`, limites, extraits
  ratés, versions et commit.
  Exigences : `EVAL-R2.3`, `R5.3`, `R7.1`, `R7.2`, `R7.4`.
  Preuve (4 nov.) : `eval/benchmark/report.md` et `chart.svg`, régénérés avec `--notes` et `--robust`, aucun
  « À ÉCRIRE » restant.
- [x] **EVAL-T9 — Gel des chiffres.** Mardi 3 nov. à midi : chiffres copiés dans le README et le script de la
  vidéo, chacun avec sa source.
  Exigences : `EVAL-R7.5`, `R8.1`. Utilisé par : `SUB-T3`, `SUB-T5`.
  Preuve (4 nov.) : README (`Results`, `Stress test`) et `docs/video-plan.md`, chiffres repris de `report.md`,
  `results.csv`, `confusion.csv` et `robust/detail.csv`. Gel le 4 nov. et non le 3 : le tournage a pris du retard.

- [x] **EVAL-T10 — Générateur du rapport et du graphique.** Ajouté à la relecture du 1er nov.
  `scripts/benchmark_report.py` lit `results.csv`, `clips.csv` et `labels.csv` et écrit `report.md` (structure de
  `design.md` section 6 : tableau principal sur les extraits `test`, réglage `live` puis `replay`, matrice de
  classement, extraits ratés, limites, commande pour reproduire, date, commit et seuils) et `chart.svg` (barres
  groupées, motifs en plus des couleurs, valeurs écrites, sans dépendance lourde). Les phrases d'analyse restent à
  écrire par l'auteur (marquées « À ÉCRIRE »). Exigences : `EVAL-R5.3`, `R7.1` à `R7.4`.
  Fait quand : rapport et graphique produits depuis un `results.csv` synthétique, test qui vérifie les sections.
  Preuve (1er nov.) : `tests/test_benchmark_report.py` 1 passed (7 sections, « À ÉCRIRE », extraits
  `test` seuls, seuils, versions, `chart.svg` avec motifs et valeurs).

- [x] **EVAL-T11 — Copies transformées et section Robustesse.** Ajouté le 3 nov. (`EVAL-D7`).
  `scripts/augment_clips.py` : variantes de `design.md` section 9, mêmes paramètres pour tout l'extrait, contrôle
  de la durée, de la cadence et de la taille, `robust/clips.csv` (`split = robust`, `source`, `transform`) et
  `robust/labels.csv` copiées de l'original. `benchmark_report.py --robust` : section « Robustesse »,
  transformation par transformation face à l'original, et tableau par extrait (`EVAL-R1.1` révisé).
  Exigences : `EVAL-R9.1` à `R9.4`, `R1.1`. Fait quand : copies produites sur 2 extraits synthétiques, durées et
  étiquettes identiques, rapport avec la section à part, sans appel réseau.
  Preuve (3 nov.) : `tests/test_augment_clips.py` 6 passed (ffmpeg réel : 7 variantes sur 2 extraits, mêmes
  images, cadence et taille, étiquettes copiées, `calib` exclu, copie identique octet par octet au 2e passage),
  `tests/test_benchmark_report.py::test_report_per_clip_and_robustness_apart` ; essai local sur `L1` (7 copies de
  321 images, plateau dans le cadre) ; suite complète 268 passed, 0 skipped.

- [x] **EVAL-T12 — Détail par copie.** Ajouté le 4 nov. (`EVAL-D9`). `scripts/robust_detail.py` écrit
  `robust/detail.csv` ; `benchmark_report.py` en tire le tableau « Remise validée ou non ».
  Exigences : `EVAL-R9.5`. Fait quand : ligne correcte sur scène simulée et sur SAM muet, refus d'écrire si les totaux
  diffèrent du benchmark, tableau du rapport testé.
  Preuve (4 nov.) : `tests/test_robust_detail.py`,
  `tests/test_benchmark_report.py::test_report_per_clip_and_robustness_apart` ; sur les vraies données, 64 lignes,
  aucun écart avec `results.csv` et `confusion.csv`, aucun appel.

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
| R9.1–R9.4 | T11 ; R9.5 : T12 |
