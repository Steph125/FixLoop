# 08 — Évaluation : exigences

Préfixe `EVAL`. Le benchmark répond à la question du jury « est-ce que ça marche, et pourquoi cette
architecture ? » : il compare FixLoop à deux approches plus simples, sur des extraits filmés par l'auteur et
étiquetés à la main, avec des chiffres reproductibles. C'est aussi ce qui distingue FixLoop d'un « analyseur
d'images » : on mesure une **boucle de décision**, pas une réponse sur une image.

## EVAL-R1 — Jeu d'extraits (Must)

1. Le jeu DOIT contenir au moins 20 extraits de 10 à 20 s, filmés par l'auteur sur son vélo (droits : `SUB-R6`).
2. Le jeu DOIT couvrir la matrice de `design.md` section 1 : au moins 3 éclairages, 3 angles, 2 distances, et les
   6 scénarios (dont la fausse remise sur le disque et la chute pendant la rotation).
3. Chaque extrait DOIT être étiqueté seconde par seconde : `off` (tombée), `on` (en place), `transition`,
   `hidden` (plateau ou chaîne masqué), et porter les instants où l'auteur a dit « c'est fait ».
4. Les étiquettes DOIVENT être écrites avant de lancer le benchmark et ne plus être modifiées après (commit daté).
5. Les vidéos NE DOIVENT PAS être commitées (`data/eval/`) ; `labels.csv` et la matrice le sont.

## EVAL-R2 — Séparation calibration / test (Must)

1. Les extraits utilisés pour régler les seuils (`velo2` et au plus 4 autres) DOIVENT être marqués `calib`.
2. Les chiffres principaux du rapport DOIVENT être calculés sur les extraits `test` uniquement (au moins 15).
3. SI les seuils sont modifiés après avoir vu les résultats `test`, ALORS le rapport DOIT le dire et donner les
   chiffres avant et après.

## EVAL-R3 — Trois approches (Must)

1. **Spark seul** : une image toutes les 3 s envoyée à `muse-spark-1.3` avec le prompt d'arbitrage, les
   `visual_cues` et sans mesures ; l'étape est validée quand Spark répond « réussie » (sans la règle `AGT-R2`).
2. **Règles SAM seules** : vérificateur de `01-core-loop` sur les mesures SAM, sans aucun appel Spark (`?` reste
   sans décision).
3. **FixLoop** : machine à états complète (SAM + règles + arbitrage Spark qui ne valide jamais).
4. Les trois approches DOIVENT recevoir les mêmes extraits, les mêmes instants « c'est fait » et la même fiche.
5. FixLoop et les règles SAM DOIVENT être évalués dans deux réglages : « replay » (10 fps, anti-rebond 4) et
   « direct simulé » (1 image/s sous-échantillonnée, anti-rebond 3).

## EVAL-R4 — Mesures (Must)

Pour chaque approche et chaque réglage, le système DOIT calculer :

1. **Fausses validations** : nombre d'étapes validées alors que l'étiquette est `off` ou `hidden` à cet instant
   (indicateur principal de sécurité, cible 0).
2. **Validations manquées** : extraits où la chaîne est `on` stable pendant au moins 5 s sans validation.
3. **Délai de validation** : secondes entre le début d'un `on` stable et la validation (médiane, maximum).
4. **Rappel des anomalies** : part des « fausses remises » (« c'est fait » dit alors que `off`) signalées comme
   anomalie.
5. **Classement par image** (règles SAM et FixLoop) : matrice `on` / `off` / incertain contre étiquette.
6. **Appels aux modèles** : appels Spark et images SAM par extrait ; **coût estimé** par extrait.

## EVAL-R5 — Reproductibilité (Must)

1. Le benchmark DOIT se relancer hors ligne à partir des caches (sorties SAM brutes, réponses Spark), en une
   commande, et redonner les mêmes chiffres.
2. Les réponses brutes de Spark DOIVENT être conservées (`eval/benchmark/cache/`, commitées, sans image).
3. Le rapport DOIT donner la date, les versions des modèles, le commit du code et les seuils.

## EVAL-R6 — Budget (Must)

1. Le système DOIT estimer le coût avant de lancer le benchmark en ligne et demander confirmation.
2. Le coût total du benchmark DOIT rester sous 30 $ (`steering/tech.md`, répartition du budget).

## EVAL-R7 — Rapport (Must)

1. Le système DOIT produire `eval/benchmark/report.md` : tableau des mesures `EVAL-R4` par approche, limites,
   extraits ratés avec explication.
2. Le système DOIT produire un graphique (`eval/benchmark/chart.svg`) : fausses validations et appels Spark par
   approche, lisible en noir et blanc.
3. Le système DOIT produire `eval/benchmark/results.csv` (une ligne par extrait et par approche).
4. Le rapport DOIT écrire les limites : un seul vélo, un seul utilisateur, nombre d'extraits, étiquettes par
   l'auteur.
5. Aucun chiffre du README ni de la vidéo NE DOIT venir d'ailleurs que de ce rapport ou de `eval/day*`
   (`SUB-R8.3`).

## EVAL-R8 — Calendrier (Must)

1. Tournage et étiquetage : dimanche 1er nov. Exécution et rapport : lundi 2 nov. Chiffres gelés : mardi 3 nov. à
   midi.
