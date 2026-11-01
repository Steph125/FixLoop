# 02 — Perception SAM 3.1 : exigences

Préfixe `PERC`. Transformer des images (direct) ou une vidéo (replay) en masques plein cadre par pièce
(`FrameMasks`), avec SAM 3.1 via la Meta Model API. Aujourd'hui, ce code existe dans deux scripts de mesure
(`probe/sam_api_probe.py`, `probe/sam_image_latency.py`) ; il doit devenir un module réutilisable,
`fixloop/perception.py`, sans changer les résultats mesurés.

## PERC-R1 — Segmentation d'une image (Must, direct)

**Récit** : en tant que session en direct, je veux les masques de chaque pièce d'une image en moins de 5 s, pour
donner un verdict pendant que l'utilisateur répare.

1. QUAND une image JPEG et une fiche sont fournies, le système DOIT lancer une requête `sam-3.1` par pièce de
   `parts`, **en parallèle**, avec `input_image` et le prompt de la pièce.
2. Chaque requête DOIT demander `include_confidence: "true"` et `mask_encoding: "one_bit"`, en flux
   (`stream=True`), et être décodée par `meta-sam-parser` (`image_segmentation_format`).
3. Le système DOIT rendre un `FrameMasks` dont chaque masque est **plein cadre** (H × W de l'image), le masque
   de boîte étant replacé à `bounds.left`, `bounds.top` et tronqué au cadre.
4. Le système DOIT ignorer les objets de confiance < 0,4 (valeur de `eval/day1`).
5. OÙ la fiche déclare `select: largest` pour une pièce, le système DOIT ne garder que l'objet ayant le plus de
   pixels ; sinon il DOIT fusionner tous les objets (union).
6. SI aucun objet n'est retenu pour une pièce, ALORS la pièce DOIT être absente de `masks` (pas de masque vide).
7. Le délai entre l'envoi et le `FrameMasks` DOIT rester ≤ 5 s au 90e centile sur le Wi-Fi de l'auteur (mesuré :
   1,9 s en médiane, 4,4 s au 90e centile, `eval/day1`).
8. Le système DOIT mesurer et rendre, pour chaque image : durée totale, premier octet, nombre de tentatives.
9. En direct, le système NE DOIT segmenter que les pièces citées par une règle de la fiche (succès, anomalie,
   `must_hold`) : pour `chain_off_chainring`, chaîne et plateau, pas le dérailleur. Raison : coût
   (`steering/tech.md` section 3, environ 0,90 $ pour 3 min avec 2 pièces, 1,35 $ avec 3).

## PERC-R2 — Débit en direct (Must)

**Récit** : en tant que session en direct, je veux analyser une image par seconde même si une requête met 4 s.

1. Le système DOIT accepter une nouvelle image sans attendre la fin des précédentes (requêtes qui se chevauchent).
2. Le système DOIT limiter à 3 le nombre d'images en cours d'analyse ; au-delà, la nouvelle image DOIT être
   abandonnée (et comptée), jamais mise en file.
3. Le système DOIT rendre chaque résultat avec son `frame_index` et son instant `t` d'origine, pour que l'appelant
   écarte les résultats arrivés dans le désordre ou trop vieux (`SRV-R4`).

## PERC-R3 — Segmentation d'une vidéo (Must, replay et évaluation)

**Récit** : en tant que constructeur du replay et du benchmark, je veux segmenter une vidéo entière de façon
fiable malgré les coupures réseau, sans payer deux fois la même chose.

1. Le système DOIT préparer la vidéo avec ffmpeg : 10 images/s, largeur ≤ 960 px, sans son, H.264.
2. Le système DOIT découper la vidéo en morceaux de 10 s (`plan_chunks`), fusionner un dernier morceau de moins
   de 50 images au précédent, et extraire chaque morceau à l'image près.
3. Le système DOIT téléverser chaque morceau par la Files API (`purpose="user_data"`) et lancer une requête
   `input_video` par morceau et par pièce citée par une règle de la fiche (`live_parts`, comme `PERC-R1.9`) ;
   OÙ l'appelant passe `parts=[…]`, le système DOIT segmenter ces pièces à la place.
4. Le système DOIT recoller les sorties des morceaux en décalant les numéros d'image (`<Nf>`) de l'indice de début
   du morceau, et produire un `FrameMasks` par image de la vidéo entière.
5. Le système DOIT enregistrer la sortie brute de chaque morceau (`raw_<pièce>_NN.txt`) avec une clé d'empreinte
   (sha256 du morceau + prompt + modèle) ; QUAND la clé existe et correspond, le système NE DOIT PAS rappeler l'API.
6. Le système DOIT afficher l'estimation du nombre d'images facturées (au moins 50 par requête) et demander une
   confirmation, sauf option `--yes`.

## PERC-R4 — Relances (Must)

1. SI une requête échoue sur une erreur réseau (`APIConnectionError`, `ResponsesStreamError`, `ConnectionError`,
   `TimeoutError`), ALORS le système DOIT la relancer au plus 2 fois (3 tentatives au total).
2. Délai avant relance : 5 s × tentative en mode image ; 10 s × tentative en mode vidéo.
3. SI une erreur n'est pas réseau (400, 401, 402, 429…), ALORS le système NE DOIT PAS relancer et DOIT la remonter
   avec son code.
4. SI la dernière tentative échoue en direct, ALORS le système DOIT rendre un résultat vide marqué `error` (la
   session continue sans cette image).
5. Le flux DOIT toujours être fermé (`stream.close()`), y compris après une erreur.

## PERC-R5 — Relecture sans appel API (Must)

**Récit** : en tant que développeur, je veux recalculer les mesures et les tests à partir de sorties SAM
enregistrées, sans dépenser de crédit.

1. Le système DOIT relire une sortie brute enregistrée (`parse_raw`) et produire les mêmes `FrameMasks` qu'au
   moment de l'appel.
2. Le système DOIT permettre de ne décoder que certaines images (filtre sur les lignes `<Nf>`), pour éviter de
   décoder tous les masques d'une vidéo.

## PERC-R6 — Contours pour la surimpression (Must)

**Récit** : en tant qu'appli téléphone, je veux dessiner le contour des pièces sur l'image vidéo, léger à
transmettre.

1. Pour chaque pièce d'un `FrameMasks`, le système DOIT produire un chemin SVG en coordonnées de l'image
   (`decode_mask_to_svg_path` décalé de la boîte, ou contour OpenCV simplifié).
2. Un chemin DOIT peser moins de 4 ko par pièce et par image (simplification `approxPolyDP`, tolérance 1,5 px).
3. Le système DOIT rendre aussi la boîte englobante de chaque pièce (pour les gros plans de `03-agent-spark`).

## PERC-R7 — Coûts et journal (Must)

1. Le système DOIT journaliser chaque requête SAM : mode (image / vidéo), pièce, nombre d'images, durée,
   tentatives, succès, dans le journal des coûts (`costs.py`, `SRV-R8`).
2. Le nombre d'images facturées d'une requête vidéo DOIT être compté max(images, 50).

## PERC-R8 — Configuration (Should)

1. La clé DOIT être lue depuis `MODEL_API_KEY` (`.env`), jamais passée en argument ni journalisée.
2. Le seuil de confiance, la largeur d'envoi, la durée des morceaux et le nombre maximal d'images en cours
   DOIVENT être des constantes du module surchargeables par variable `FIXLOOP_*`.

## PERC-R9 — Équivalence avec les mesures du 29 – 30 oct. (Must)

1. Rejouée sur `probe_out2/raw_*.txt` (vidéo `velo2`), la chaîne perception → géométrie DOIT redonner les médianes
   de `eval/day1/findings.md` à ± 0,005 près et 0 image mal classée.
2. Les scripts `probe/*.py` DOIVENT continuer de fonctionner (ils importent le module ou restent tels quels comme
   preuves datées).
