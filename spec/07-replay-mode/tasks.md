# 07 — Mode replay : tâches

Toutes à faire. Jalon (lundi 2 nov.) : replay public déployé, 2 sessions.

- [x] **RPL-T1 — Cache des modèles.** `fixloop/cached_models.py` (`CachedAgent`, `CachedMemory`, clé sha256,
  date d'obtention, mode hors ligne strict) et tests.
  Exigences : `RPL-R2.1`, `R2.3`, `R2.4`.
  Preuve : `tests/test_replay.py` 4 passed (enregistrement, rejeu hors ligne à l'identique,
  `OfflineError` sur clé absente ou historique modifié, date d'obtention).
- [~] **RPL-T2 — Construction d'une session.** `replay/build_replay.py` : fichier de session, source `video`
  (`segment_video`) ou `recording`, rejeu par `Session` avec `RecordingOutput`, écriture de `video.mp4`
  (ffmpeg, `-preset veryfast`, faststart), `overlays.json` (5 fps), `events.json`, `meta.json`, `index.json`.
  Exigences : `RPL-R2.2`, `R2.3`, `R5.2`, `R7.1`. Dépend de : T1 ([x]), `PERC-T5` ([~]), `PERC-T6` ([x]).
  Fait quand : la session synthétique se construit deux fois à l'identique — fait (octet par octet
  pour `events.json` et `overlays.json`).
  Choix : source `synthetic` ajoutée pour le code seul (vidéos réelles en RPL-T4) ; `state_at` et
  `nearest_overlay` (référence Python du lecteur) ; `.gitignore` couvre `replay/build/`.
  Preuve : `tests/test_replay.py` (déterminisme, 60 s sous 2 Mo, `state_at`, refus `video` sans modèles).
  **Relecture du 1er nov. : rouverte.** Pour RPL-T2 : seule la source `synthetic` existe ; `source: video` lève une
  erreur. Il manque le chemin réel : `segment_video` (cache), mesures, `CachedAgent(SparkAgent)`, images clés
  recadrées depuis la vidéo, vidéo réencodée par ffmpeg (H.264, ≤ 960 px, `+faststart`), `meta.source = "video"`
  et mode « vidéo 10 images/s, anti-rebond 4 » ; plus la source `recording` (images 1 fps + sorties SAM du direct).
  Fait quand : une session `video` se construit avec un faux client SAM et un faux Spark, deux fois à l'identique,
  puis `--offline` depuis le cache sans aucun appel.
- [ ] **RPL-T3 — Tourner les vidéos A et B.** Vélo de l'auteur, téléphone posé, son activé (« c'est fait » dit à
  voix haute) ; A : chaîne tombée → posée sur le disque → « c'est fait » → correction → rotation arrière → test
  dynamique ; B : mains devant le plateau, angle de 30°, pour provoquer un arbitrage. Noter les instants de
  « c'est fait » dans `replay/sessions/A.json`, `B.json`. Aucun visage ni document dans le champ.
  Exigences : `RPL-R3.1`. Peut se faire avec le tournage du benchmark (`EVAL-T1`).
- [ ] **RPL-T4 — Construire A et B avec les vrais modèles.** 1re construction en ligne (coût : environ 1 200
  images vidéo ≈ 0,25 $, plus quelques appels Spark et Wonder), puis `--offline` pour vérifier l'identité.
  Commiter `replay/cache/*.models.json` et `replay/sessions/*.json`.
  Exigences : `RPL-R2.1`, `R2.3`, `R2.4`, `R3.1`.
- [x] **RPL-T5 — Lecteur : vidéo, contours, bandeau, sous-titres.** `web/replay.html`, `replay.js`, `stateAt`,
  synchronisation ± 100 ms, commandes de lecture, son.
  Exigences : `RPL-R4.1`, `R4.5`, `R1.3`, `R1.4`.
  Preuve : `tests/test_phone_app.py` (fichiers + câblage synchro/son), `node web/selftest.mjs`
  21/21 (miroir Python de `state_at`, overlay le plus proche, seuils, vitesses).
- [x] **RPL-T6 — Frise, détail des événements, courbe.** Événements cliquables, modèle et preuve, réponse brute et
  confiance, courbe du contact avec seuils et curseur.
  Exigences : `RPL-R4.2` à `R4.4`.
  Preuve : `tests/test_phone_app.py::test_replay_timeline_detail_curve`, `node web/selftest.mjs`
  23/23 (`timelineItems`, `eventDetail` avec modèle et preuve, `curveGeometry` + seuils 0,18/0,26).
- [~] **RPL-T7 — Honnêteté et liens.** Bandeau permanent, mode de calcul, mention de l'historique de démo, liens.
  Exigences : `RPL-R5.1` à `R5.3`, `R7.2`.
  Choix : lien rapport vers `eval/benchmark/report.md` (chemin du dépôt ; ajusté au déploiement RPL-T9).
  Preuve : `tests/test_phone_app.py::test_replay_honesty_and_links`, `node web/selftest.mjs`
  24/24 (`honestyText`, `linksFor` sans la session courante).
  **Relecture du 1er nov. : rouverte.** Pour RPL-T7 : le bandeau dit « Rejoué le <date de construction> », pas la
  phrase de RPL-R5.1 (« Replay d'une session réelle, filmée le <date>. Les décisions ont été calculées par FixLoop
  sur cette vidéo ; les réponses des modèles Meta sont celles obtenues ce jour-là. »), et pour une session
  synthétique il doit dire « Session synthétique de test » au lieu de « réelle ». Les liens ne pointent pas vers le
  dépôt, la vidéo ni le direct, et « ../eval/benchmark/report.md » sera cassé sur GitHub Pages : lire
  `build/links.json` (`repo`, `benchmark`, `video`, `live`, tous facultatifs sauf `repo`), lien absent = non affiché.
- [ ] **RPL-T8 — Session enregistrée en direct (Should).** Une session réelle avec `FIXLOOP_RECORD=1`, construite
  en source `recording`. Exigences : `RPL-R3.2`. Dépend de : `SRV-T9`, `APP-T9`.
- [ ] **RPL-T9 — Déploiement et vérification.** `replay/deploy_check.py` ; déploiement statique ; vérification en
  navigation privée, sur téléphone en 4G, Chrome, Firefox, Safari ; temps d'affichage de la 1re image noté dans
  `eval/day5/replay-check.md`.
  Exigences : `RPL-R1.1` à `R1.3`, `R8.1`, `R8.2`.
- [x] **RPL-T10 — Explorer les seuils (Could).** Curseurs, recalcul des `label`, mention « simulation ».
  Exigences : `RPL-R6.1`, `R6.2`.
  Preuve : `tests/test_phone_app.py::test_replay_threshold_simulation`, `node web/selftest.mjs`
  25/25 (`relabelFrames` sans mutation, seuils croisés ignorés).

- [ ] **RPL-T11 — Publication sur GitHub Pages (préparation).** Ajouté à la relecture du 1er nov. `replay/build/`
  est ignoré par git : le workflow ne peut pas le publier. Créer `replay/publish.py <sessions…> [--video URL]
  [--live URL]` qui copie les sessions choisies de `replay/build/` vers `replay/published/` (suivi par git), écrit
  `index.json` (ces sessions seulement) et `links.json` (`repo` = https://github.com/Steph125/FixLoop, `benchmark` =
  lien GitHub vers `eval/benchmark/report.md`). `.gitignore` : `!replay/published/*/video.mp4`. `pages.yml` publie
  `replay/published/` comme `build/` et copie `replay.html` aussi en `index.html`. `deploy_check.py` : accepte
  `index.html` et les liens `href="https://…"`, refuse tout `fetch`/`src`/`import` externe, tout fichier `.env`,
  `.jsonl` ou contenant `MODEL_API_KEY`, toute vidéo de plus de 15 Mo.
  Exigences : `RPL-R1.1`, `R1.4`, `R7.1`, `R7.2`, `R8.2`. Fait quand : tests de `publish.py` et de `deploy_check.py`
  sur un site synthétique, sans déclencher le workflow.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1–R1.3 | T9 ; R1.3, R1.4 : T5 |
| R2.1 | T1, T4 ; R2.2 : T2 ; R2.3 : T1, T2, T4 ; R2.4 : T1, T4 |
| R3.1 | T3, T4 ; R3.2 : T8 |
| R4.1, R4.5 | T5 ; R4.2–R4.4 : T6 |
| R5.1–R5.3 | T7 ; R5.2 : T2 |
| R6.1, R6.2 | T10 |
| R7.1 | T2, T9, T11 ; R7.2 : T7, T11 |
| R8.1, R8.2 | T9 |
