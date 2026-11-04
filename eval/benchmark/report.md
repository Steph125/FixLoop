# Benchmark FixLoop : rapport

## Question

Est-ce que la boucle FixLoop (SAM + règles + arbitrage Spark qui ne valide jamais) se trompe moins qu'une approche simple ?
Oui pour la mesure, pas encore pour la cible. Sur ces 8 extraits, la géométrie sépare nettement la chaîne sur le disque de la chaîne dans les dents : aucune image `off` n'est classée « en place ». Mais FixLoop n'atteint pas la cible de 0 fausse validation : 6 en réglage `replay`, 1 en `live`, toutes pendant qu'une main est marquée `hidden`. Trois d'entre elles sont un effet d'étiquette à la seconde ; celles de B1 sont une vraie faiblesse. Spark seul ne fait aucune fausse validation, mais ne valide qu'une fois sur 8 extraits et répond « impossible à dire » à 21 images sur 37 : il ne peut pas conduire une réparation seul.

## Protocole

- Extraits `test` : 8 (A1, B1, L1, L2, L3, L4, S1, S3), étiquetés seconde par seconde avant exécution (EVAL-R1.3, R1.4).
- Réglages : `live` (direct simulé, 1 image/s, anti-rebond 3) puis `replay` (10 images/s, anti-rebond 4) (EVAL-R3.5).
- Modèles : sam-3.1 (segmentation), muse-spark-1.3 (arbitrage et Spark seul, `--model` dans EVAL-D5).
- Seuils de contact : en place ≤ 0,18, tombée ≥ 0,26.
- Date : 2026-11-04, commit : 643244b (EVAL-R5.3).
- Diagnostic hors périmètre (une seule fiche, design 08 §3).

## Tableau principal (extraits `test`)

### Réglage `live`

| Approche | Fausses validations | Validations manquées | Délai médian (s) | Délai max (s) | Fausses remises | Appels Spark / extrait | Coût / extrait ($) |
|---|---|---|---|---|---|---|---|
| spark | 0 | 1 | — | 0.0 | — | 4.6 | 0.0462 |
| rules | 1 | 0 | 1.0 | 4.0 | — | 0.0 | 0.01 |
| fixloop | 1 | 0 | 1.0 | 4.0 | — | 1.8 | 0.0275 |

### Réglage `replay`

| Approche | Fausses validations | Validations manquées | Délai médian (s) | Délai max (s) | Fausses remises | Appels Spark / extrait | Coût / extrait ($) |
|---|---|---|---|---|---|---|---|
| spark | 0 | 1 | — | 0.0 | — | 4.6 | 0.0462 |
| rules | 6 | 1 | 1.2 | 2.4 | — | 0.0 | 0.0342 |
| fixloop | 6 | 1 | 1.2 | 2.4 | — | 1.1 | 0.0455 |

### Par extrait (réglage `live`, fausses validations / validations manquées)

| Extrait | spark | rules | fixloop |
|---|---|---|---|
| A1 | 0 / 1 | 0 / 0 | 0 / 0 |
| B1 | 0 / 0 | 1 / 0 | 1 / 0 |
| L1 | 0 / 0 | 0 / 0 | 0 / 0 |
| L2 | 0 / 0 | 0 / 0 | 0 / 0 |
| L3 | 0 / 0 | 0 / 0 | 0 / 0 |
| L4 | 0 / 0 | 0 / 0 | 0 / 0 |
| S1 | 0 / 0 | 0 / 0 | 0 / 0 |
| S3 | 0 / 0 | 0 / 0 | 0 / 0 |

Règles SAM et FixLoop valident aux mêmes instants en `replay` : l'arbitrage de Spark ne valide jamais, il ajoute des refus et des explications. En `live`, il refuse le « c'est bon » de A1 à 13 s et le « c'est fait » de B1 à 10 s ; sur A1, ce refus retarde la validation d'une seconde (16 s au lieu de 15 s), car la chaîne venait d'être remise. Le réglage `live` valide plus tard et fait moins de fausses validations que `replay`, parce qu'il regarde moins d'images. Quatre extraits ne montrent presque rien de la boucle : SAM ne voit jamais la chaîne sur L2 (0 image sur 110), jamais le plateau sur L4 (0 sur 122), la chaîne sur un tiers de L3 (34 sur 109) et sur la moitié de S3 (50 sur 101). Le tableau les compte à 0 fausse validation et 0 validation manquée, car aucun « c'est fait » n'y est dit : ce 0 ne prouve donc rien pour eux.

## Matrice de classement par image (règles SAM)

Interprétation FixLoop de chaque image (`en place` ≤ 0,18, `tombée` ≥ 0,26, `incertain`, `non vu`) contre l'étiquette, `transition` exclue (EVAL-R4.5).

| Réglage | Fausses validations | Validations pendant transition | Validations manquées |
|---|---|---|---|
| live | 1 | 0 | 0 |
| replay | 6 | 1 | 1 |

Images, réglage `live` :

| Étiquette | en place | tombée | incertain | non vu |
|---|---|---|---|---|
| off | 0 | 21 | 1 | 6 |
| on | 40 | 0 | 8 | 42 |
| hidden | 6 | 7 | 0 | 7 |

Images, réglage `replay` :

| Étiquette | en place | tombée | incertain | non vu |
|---|---|---|---|---|
| off | 0 | 235 | 9 | 36 |
| on | 435 | 5 | 45 | 388 |
| hidden | 92 | 45 | 3 | 60 |

Sur ces 8 extraits, aucune image `off` n'est classée « en place » : c'est le résultat le plus solide de ce benchmark, avec une limite sur les copies transformées (section « Robustesse »). Le contact vaut environ 0,25 à 0,41 chaîne sur le disque et 0,05 à 0,21 chaîne dans les dents (médianes par seconde). La colonne « non vu » de la ligne `on` vient surtout de L2, L3, L4 et S3. La ligne `hidden` montre le risque : une main peut faire chuter le contact sans que la chaîne soit remise. Sur S3, à 8 s, l'objet pris pour le plateau est la cassette arrière (masque vérifié sur cette image).

## Extraits ratés

### A1

rules/replay : 1 fausse(s), 1 manquée(s); fixloop/replay : 1 fausse(s), 1 manquée(s); spark/replay : 0 fausse(s), 1 manquée(s); rules/live : 0 fausse(s), 0 manquée(s); fixloop/live : 0 fausse(s), 0 manquée(s); spark/live : 0 fausse(s), 1 manquée(s).
Validation de la remise à 12,4 s, dans une seconde marquée `hidden` : la main se retire, le contact vaut déjà environ 0,07 et la seconde suivante est marquée `on`. C'est un effet de la résolution à la seconde, pas une chaîne mal posée. La validation manquée en `replay` est un artefact : le premier « c'est bon » (13,1 s) valide l'étape de rotation et la session se ferme à 16,2 s, avant le second (32,9 s), après lequel la mesure attend encore une validation. Limite réelle : la rotation filmée entre 25 et 45 s n'a pas servi, car FixLoop ne mesure pas que le pédalier tourne.

### B1

rules/replay : 3 fausse(s), 0 manquée(s); fixloop/replay : 3 fausse(s), 0 manquée(s); spark/replay : 0 fausse(s), 0 manquée(s); rules/live : 1 fausse(s), 0 manquée(s); fixloop/live : 1 fausse(s), 0 manquée(s); spark/live : 0 fausse(s), 0 manquée(s).
Vraie faiblesse. Jusqu'à 8 s, la chaîne est sur le disque (contact 0,35). À 9,2 s, la main saisit la chaîne et le contact chute à environ 0,15 : la remise est validée à 9,5 s alors que la chaîne est tenue par la main, et on entend encore « vas-y remets-le » à 20 s. Puis la rotation est validée à 16,1 s et la session se ferme à 19,2 s, toujours avec la main. Un contact faible ne prouve pas que la chaîne est dans les dents si une main la soulève. Le système ne détecte pas les mains ; rien n'a été changé après ce résultat.

### L1

rules/replay : 1 fausse(s), 0 manquée(s); fixloop/replay : 1 fausse(s), 0 manquée(s); spark/replay : 0 fausse(s), 0 manquée(s); rules/live : 0 fausse(s), 0 manquée(s); fixloop/live : 0 fausse(s), 0 manquée(s); spark/live : 0 fausse(s), 0 manquée(s).
Validation de la remise à 5,3 s, dans une seconde marquée `hidden` : le contact vaut déjà environ 0,05 et la seconde suivante est marquée `on`. Effet de la résolution à la seconde.

### S1

rules/replay : 1 fausse(s), 0 manquée(s); fixloop/replay : 1 fausse(s), 0 manquée(s); spark/replay : 0 fausse(s), 0 manquée(s); rules/live : 0 fausse(s), 0 manquée(s); fixloop/live : 0 fausse(s), 0 manquée(s); spark/live : 0 fausse(s), 0 manquée(s).
Validation de la remise à 6,9 s, dans une seconde marquée `hidden` : le contact chute à ce moment-là et les secondes suivantes sont marquées `transition` puis `on`. Effet de la résolution à la seconde. La validation pendant `transition` à 7,3 s suit le « c'est fait » (fin de phrase à 7,8 s, placé à 7 s par l'étiquette).

## Robustesse (copies transformées, à part)

Copies transformées des 8 extraits filmés (A1, B1, L1, L2, L3, L4, S1, S3) : mêmes étiquettes que l'original, masques et mesures recalculés par SAM 3.1 sur chaque copie. Elles ne s'ajoutent pas aux extraits du tableau principal (EVAL-R9.4, EVAL-D7).

### Réglage `live` (fausses validations / validations manquées)

| Copie | Transformation | rules | fixloop |
|---|---|---|---|
| original | aucune | 1 / 0 | 1 / 0 |
| zoom13 | recadrage 1/1,3 autour du plateau | 2 / 0 | 2 / 0 |
| shift | recadrage 90 % décalé vers un coin | 1 / 0 | 1 / 0 |
| dark | sous-exposition (gamma 0,75) | 0 / 0 | 0 / 0 |
| bright | surexposition (gamma 1,25, contraste 0,85) | 0 / 0 | 0 / 0 |
| blur_noise | flou 1,5 px et bruit à graine fixe | 1 / 0 | 1 / 0 |
| lowq | demi-résolution et compression forte | 0 / 1 | 0 / 1 |
| rotate4 | rotation de 4°, coins noirs recadrés | 0 / 0 | 0 / 0 |

### Remise validée ou non (règles SAM, réglage `live`)

Tous les extraits finissent chaîne en place : une remise jamais validée est un échec, que le tableau ci-dessus ne compte pas. Une validation pendant `transition` compte comme chaîne en place. Source : `eval/benchmark/robust/detail.csv` (`scripts/robust_detail.py`, totaux contrôlés contre `results.csv` et `confusion.csv`).

| Copie | Remise validée, chaîne en place | Remise validée à tort | SAM muet | Chaîne vue | Plateau vu | Images `off` lues « en place » | Images `on` lues « tombée » |
|---|---|---|---|---|---|---|---|
| original | 3 / 8 | 1 | 0 | 98 / 141 | 128 / 141 | 0 | 0 |
| zoom13 | 5 / 8 | 2 | 0 | 110 / 141 | 137 / 141 | 0 | 0 |
| shift | 4 / 8 | 1 | 0 | 103 / 141 | 127 / 141 | 3 | 0 |
| dark | 1 / 8 | 0 | 1 | 64 / 130 | 116 / 130 | 0 | 0 |
| bright | 4 / 8 | 0 | 0 | 74 / 141 | 136 / 141 | 0 | 0 |
| blur_noise | 2 / 8 | 1 | 0 | 41 / 141 | 136 / 141 | 0 | 0 |
| lowq | 0 / 8 | 0 | 3 | 0 / 99 | 99 / 99 | 0 | 0 |
| rotate4 | 5 / 8 | 0 | 0 | 85 / 141 | 140 / 141 | 1 | 1 |

FixLoop et les règles SAM font les mêmes erreurs sur chaque transformation. Il faut lire le second tableau : un 0 dans le premier veut souvent dire que rien n'a été validé, pas que le système a bien jugé. La logique, les seuils et les étiquettes n'ont pas changé après ces résultats.

- **La chaîne est ce que SAM perd en premier ; le plateau reste presque toujours vu.** En `lowq`, la chaîne n'est vue sur aucune des 5 copies segmentées et SAM ne rend rien sur les 3 autres (L2, L4, S3) : aucune remise n'est validée. En `dark`, une seule l'est (A1), et SAM ne rend rien sur S3. Sur `blur_noise`, deux le sont (L4, A1, cette dernière à 35 s au lieu de 15 s). Les 0 fausse validation de `dark` et de `lowq` viennent de là, pas d'une meilleure lecture. Le mode d'échec reste prudent : la session attend au lieu de valider, mais l'utilisateur n'obtient rien.
- **La distance compte.** Avec `zoom13`, la remise est aussi validée sur L3, L4 et S3 ; une partie des échecs de ces extraits vient donc du cadrage de loin. C'est aussi la seule copie de A1 dont la session se ferme (39 s). Aucune copie de L2 ne montre la chaîne.
- **La faiblesse de B1 n'est pas un hasard d'image.** La fausse validation, main dans le champ, reste sur `zoom13`, `shift` et `blur_noise`. Sur `dark`, `bright` et `lowq`, la remise n'y est pas validée du tout. Seule `rotate4` la valide chaîne en place (23 s), et une seule copie ne prouve rien. `S1-zoom13` ajoute une fausse validation à 6 s, dans la même seconde `hidden` que l'original en `replay` (6,9 s).
- **Le meilleur résultat a une limite.** Sur les copies, 4 images `off` sur 196 sont lues « en place » (S1-shift à 2 et 3 s, S1-rotate4 à 3 s, A1-shift à 10 s ; contact de 0,001 à 0,108), contre 0 sur les extraits d'origine. Aucune n'a conduit à une validation. Une image `on` est lue « tombée » (L3-rotate4, 4 s).
- **Mauvaise pièce.** S3-shift valide la remise à 8 s alors que SAM prend la cassette arrière pour le plateau (masque vérifié sur cette image). La chaîne est bien en place, mais cette validation ne le prouve pas, et elle est comptée dans le second tableau. FixLoop ne détecte pas cette confusion. Sur S3-zoom13 à 9 s, le masque est bien sur le plateau (vérifié), près du bord du cadre.

## Limites

- Un seul vélo, un seul utilisateur (EVAL-R7.4). États posés par l'auteur, avec des corrections proposées par un assistant IA et validées par l'auteur ; instants « c'est fait » issus de muse-voice-transcribe-1.0 (EVAL-D8).
- 8 extraits `test` : intervalle de confiance large, aucun objectif chiffré publié sauf 0 fausse validation (EVAL-D4).
- 8 extraits filmés au lieu des 20 visés, éclairage lampe et soir seulement, pas de lumière du jour (EVAL-R1.1 révisé, EVAL-D6) : chiffres donnés par extrait, aucun pourcentage global présenté comme une précision.
- Les copies transformées viennent des mêmes extraits : elles mesurent la robustesse, pas la diversité (EVAL-D7).
- Seuils réglés sur `velo2` et au plus 4 extraits `calib` (EVAL-R2.1) ; toute modification après les résultats `test` est dite ici (EVAL-R2.3).
- FixLoop ne mesure pas que le pédalier tourne : l'étape de rotation et le test dynamique vérifient seulement que la chaîne reste en place.
- Aucun « c'est fait » n'est dit pendant que la chaîne est visible sur le disque (EVAL-D8, RPL-D6) : le rappel des fausses remises n'a pas de donnée (0/0) sur ce jeu.
- Scénarios absents : S1 et S4 (la chaîne qui retombe pendant la rotation) ; angle à 30° absent. La chute pendant la rotation n'est donc pas testée.
- Spark seul passe par `muse-spark-1.3-contributor`, l'arbitrage de FixLoop par `muse-spark-1.3` (EVAL-D5).
- Pendant la vraie rotation de A1, le contact remonte à environ 0,12-0,20, autour du seuil de 0,18 : au réglage `live`, le test dynamique de 3 s ne se termine pas sur cette vidéo (aucune clôture, aucune anomalie).
- Le rapport compte les validations à la seconde : une validation à la fin d'une seconde `hidden` compte comme fausse, même si la chaîne vient d'être remise. Les étiquettes n'ont pas été modifiées après ces résultats (EVAL-R1.4).
- SAM peut prendre une autre pièce pour le plateau : sur S3, la cassette arrière (masque vérifié à 8 s). FixLoop ne le détecte pas, et S3-shift valide la remise sur cette cassette.

## Reproduire

```
python scripts/benchmark.py --clips eval/benchmark/clips.csv --labels eval/benchmark/labels.csv --procedure chain_off_chainring --approaches spark,rules,fixloop --settings replay,live --offline --yes
```

Commande du rapport : `python scripts/benchmark_report.py --results eval/benchmark/results.csv --clips eval/benchmark/clips.csv --labels eval/benchmark/labels.csv --out eval/benchmark --robust eval/benchmark/robust/results.csv --notes eval/benchmark/notes.json`.
