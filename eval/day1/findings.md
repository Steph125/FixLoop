# Jour 1 : la chaîne est-elle mesurable avec SAM 3.1 ?

Vidéo `velo2` (29 oct., 57 s, filmée par l'auteur), segmentée par `sam-3.1` via la Meta Model API,
10 images/s, 848×464, en 6 morceaux de 10 s. Prompts : `bicycle chain`, `chainring`, `rear derailleur`.

Déroulé indiqué par l'auteur : chaîne tombée de 0 à 16 s, remise en place puis pédalier tourné de 16 à 43 s,
vélo immobile puis incliné après 43 s.

## Détection

| Pièce | Images détectées | Confiance moyenne |
|---|---|---|
| Chaîne | 94 % | 0,73 |
| Plateau | 100 % | 0,88 |
| Dérailleur arrière | 100 % | 0,79 |

« Plateau » renvoie deux objets (plateau avant et pignons arrière) : on garde le plus gros.
« Dérailleur arrière » attrape aussi la manivelle et le plateau : non utilisé par la fiche.

## Mesure : part du bord du plateau couverte par la chaîne (plateau avant seul)

| Phase | Médiane | 10e – 90e centile |
|---|---|---|
| Chaîne tombée (0–15 s) | 0,344 | 0,315 – 0,355 |
| En place, pédalier qui tourne (17–42 s) | 0,090 | 0,059 – 0,110 |
| En place, vélo immobile puis incliné (44–57 s) | 0,085 | 0,053 – 0,118 |

Le sens est l'inverse de l'intuition : quand la chaîne est sur les dents, SAM la fond dans le plateau et elle ne
touche son bord qu'aux deux points d'entrée et de sortie. Quand elle est tombée, elle repose le long du plateau.

## Seuils retenus

En place si contact ≤ 0,18 ; tombée si contact ≥ 0,26 ; entre les deux ou pièce non détectée = incertain.

Sur les 285 images analysées (une sur deux), avec ces seuils :

| Phase | Tombée | En place | Incertain |
|---|---|---|---|
| 0–15 s (tombée) | 78 | 0 | 0 |
| 16–17 s (transition) | 3 | 4 | 0 |
| 17–42 s (en place, rotation) | 0 | 114 | 11 |
| 43–57 s (immobile, incliné) | 0 | 68 | 7 |

Aucune image classée dans le mauvais état. Avec l'anti-rebond de 4 images, « en place » est validé à 16,8 s.

## Limites

- Une seule vidéo, un seul vélo, un seul angle : les seuils sont à confirmer sur le jeu d'évaluation.
- Durée de segmentation : 529 s pour 57 s de vidéo (3 pièces en série). Le mode vidéo convient au replay,
  pas au guidage en direct : tester ensuite le mode image par image.

## Mode image par image (30 oct.)

10 images de `velo2` (848×464), 2 requêtes `sam-3.1` par image (chaîne et plateau) lancées en parallèle.

| Mesure | Valeur |
|---|---|
| Verdict par image, médiane | 1,9 s |
| Verdict par image, 90e centile | 4,4 s (premières requêtes, plus lentes) |
| Premier octet, médiane | 1,2 s |
| Relances réseau | 0 |
| États corrects selon le déroulé de l'auteur | 10 / 10 |
| Accord avec le mode vidéo | 8 / 10 (les 2 écarts : mode vidéo « incertain », mode image « en place », ce qui est juste) |

Contacts mesurés : chaîne tombée 0,29 – 0,32 ; chaîne en place 0,07 – 0,15. L'image à 30 s (0,145) est la plus
proche du seuil de 0,18.

Décision : le guidage en direct passe par le mode image. L'appli envoie une image par seconde sans attendre la
réponse précédente (requêtes qui se chevauchent), avec un anti-rebond de 3 images : verdict environ 4 à 5 s après
le geste. Le mode vidéo reste utilisé pour le replay des juges, calculé une fois et mis en cache.
