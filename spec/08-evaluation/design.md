# 08 — Évaluation : conception

Couvre `EVAL-R1` à `EVAL-R8`. Fichiers : `eval/benchmark/labels.csv`, `eval/benchmark/clips.csv`,
`scripts/benchmark.py`, `eval/benchmark/report.md`, `chart.svg`, `results.csv`, `cache/`.

## 1. Matrice de diversité

Chaque extrait combine une valeur par ligne. 20 extraits au minimum ; chaque valeur apparaît au moins 3 fois
(scénarios : au moins 3 fois chacun pour S1 à S4, 2 fois pour S5, S6).

| Dimension | Valeurs |
|---|---|
| Éclairage | jour (dehors ou fenêtre), intérieur lampe, faible (soir) |
| Angle | face au plateau, 30° de côté, en plongée |
| Distance | 30 cm, 50 cm |
| Scénario | S1 tombée → remise correcte ; S2 fausse remise sur le disque → correction ; S3 en place, rotation, reste en place ; S4 en place → retombe pendant la rotation ; S5 mains devant le plateau ; S6 en place immobile, aucun geste |

`clips.csv` : `clip,file,duration_s,lighting,angle,distance,scenario,split` (`split` = `calib` ou `test`).

## 2. Étiquettes

`labels.csv`, une ligne par seconde et par extrait :

```
clip,t,state,done
c01,0,off,0
c01,1,off,0
…
c01,7,transition,0
c01,8,on,1
```

- `state` ∈ {`off`, `on`, `transition`, `hidden`}, `done = 1` si « c'est fait » est dit dans cette seconde.
- Étiquetage par l'auteur en regardant l'extrait image par image (`ffplay` ou lecteur avec pas à pas) ; outil
  facultatif `scripts/label_clip.py` (touches o / f / t / h, enregistrement CSV).
- Commit « labels » daté **avant** la première exécution (`EVAL-R1.4`).

## 3. Exécution

```
python scripts/benchmark.py --clips eval/benchmark/clips.csv --labels eval/benchmark/labels.csv \
       --procedure chain_off_chainring --approaches spark,rules,fixloop --settings replay,live \
       [--offline] [--yes]
```

Étapes :

1. **SAM** : `perception.segment_video` par extrait (10 fps, chaîne et plateau), cache `data/eval/sam/<clip>/`.
2. **Mesures** : `geometry.measure` pour chaque image → `measures.parquet` ou `.csv` par extrait.
3. **Réglage** `replay` : toutes les images, anti-rebond 4. Réglage `live` : une image par seconde (la plus proche
   de chaque seconde pleine), anti-rebond 3.
4. **Règles SAM** : `Session` avec un `NoSparkAgent` (diagnostic = fiche donnée, arbitrage = `0` sans appel,
   explication = message de la règle).
5. **FixLoop** : `Session` avec `CachedAgent(SparkAgent)` (`07-replay-mode`), même cache que le replay.
6. **Spark seul** : `AGT-T12` `spark_only_verdict` sur une image toutes les 3 s (et à chaque « c'est fait ») ;
   machine minimale : étape validée au premier « réussie », anomalie au premier « ratée » après « c'est fait ».
   Réponses en cache `eval/benchmark/cache/spark_only.json`.
7. **Comparaison aux étiquettes** : section 4 ; écriture de `results.csv`, `report.md`, `chart.svg`.

Le diagnostic n'est pas évalué ici (une seule fiche) : il est noté « hors périmètre du benchmark » dans le rapport.

## 4. Définition exacte des mesures

Soit `L(t)` l'étiquette à la seconde `floor(t)`.

| Mesure | Définition |
|---|---|
| Fausse validation | événement `validated` (ou clôture du test dynamique) à l'instant `t` avec `L(t) ∈ {off, hidden}` ; `transition` compte à part (« validation pendant transition ») |
| Validation manquée | segment `on` de ≥ 5 s consécutives (après le dernier `done` si l'étape exige « c'est fait ») sans `validated` pendant le segment |
| Délai de validation | `t_validated − t_début_du_segment_on` (et, si l'étape exige « c'est fait », depuis `max(début, done)`) |
| Fausse remise | seconde avec `done = 1` et `L = off` ; signalée si un événement `anomaly` arrive dans les 10 s |
| Classement par image | label FixLoop de l'image (`en place` ≤ 0,18, `tombée` ≥ 0,26, `incertain`, `non vu`) contre `L` ; `transition` exclue |
| Coût | `CostLog` (prix de `steering/tech.md`), par extrait |

## 5. Estimation du coût

| Poste | Calcul | Estimation |
|---|---|---|
| SAM vidéo | 20 extraits × 15 s × 10 fps × 2 pièces = 6 000 images × 0,20 $ / 1 000 | 1,20 $ |
| Spark seul | 20 × (15 s / 3 s + 2 « c'est fait ») ≈ 140 appels × environ 0,01 $ | 1,40 $ |
| FixLoop (arbitrages, explications) | ≈ 60 appels × 0,01 $ | 0,60 $ |
| Marge (relances, deuxième passage si erreur de code) | × 2 | ≈ 6 $ au total |

Le coût par appel Spark (environ 0,01 $ avec 3 images) est une estimation à confirmer par `AGT-T9`.

## 6. Rapport

Structure de `report.md` :

1. Question et réponse en 3 lignes.
2. Protocole : extraits, matrice, étiquetage, séparation calibration / test, versions, commit, date.
3. Tableau principal (extraits `test`, réglage `live`, puis `replay`) :

   | Approche | Fausses validations | Validations manquées | Délai médian | Rappel des fausses remises | Appels Spark / extrait | Coût / extrait |
   |---|---|---|---|---|---|---|

4. Matrice de classement par image (règles SAM).
5. Extraits ratés : un paragraphe par extrait, avec image et explication.
6. Limites.
7. Reproduire : commande hors ligne.

Graphique : deux barres groupées par approche (fausses validations, appels Spark par extrait), motifs différents
en plus des couleurs, étiquettes de valeur sur les barres, SVG généré en Python sans dépendance lourde
(ou matplotlib si déjà installé).

## 7. Tests

- `tests/test_benchmark.py` : sur 2 extraits synthétiques (`sim.py`) avec étiquettes connues, chaque mesure de la
  section 4 donne la valeur attendue (fausse validation construite exprès, validation manquée, délai).
- Le benchmark en `--offline` est relancé deux fois en CI locale : `results.csv` identiques.

## 8. Journal des décisions

- **EVAL-D1 (30 oct.)** — Indicateur principal = fausses validations : c'est l'erreur qui envoie le cycliste sur
  la route avec une chaîne mal posée.
- **EVAL-D2 (30 oct.)** — Spark seul reçoit les `visual_cues` : comparaison loyale, on mesure l'architecture, pas
  un prompt affaibli.
- **EVAL-D3 (30 oct.)** — Réglage « direct simulé » en plus du replay : le direct est ce que le jury verra dans la
  vidéo, il doit être mesuré.
- **EVAL-D4 (30 oct.)** — Pas d'objectif chiffré publié avant la mesure, sauf la cible de 0 fausse validation.
