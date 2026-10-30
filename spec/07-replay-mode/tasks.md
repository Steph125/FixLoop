# 07 — Mode replay : tâches

Toutes à faire. Jalon (lundi 2 nov.) : replay public déployé, 2 sessions.

- [ ] **RPL-T1 — Cache des modèles.** `fixloop/cached_models.py` (`CachedAgent`, `CachedMemory`, clé sha256,
  date d'obtention, mode hors ligne strict) et tests.
  Exigences : `RPL-R2.1`, `R2.3`, `R2.4`.
- [ ] **RPL-T2 — Construction d'une session.** `replay/build_replay.py` : fichier de session, source `video`
  (`segment_video`) ou `recording`, rejeu par `Session` avec `RecordingOutput`, écriture de `video.mp4`
  (ffmpeg, `-preset veryfast`, faststart), `overlays.json` (5 fps), `events.json`, `meta.json`, `index.json`.
  Exigences : `RPL-R2.2`, `R2.3`, `R5.2`, `R7.1`. Dépend de : T1, `PERC-T5`, `PERC-T6`.
  Fait quand : la session synthétique se construit deux fois à l'identique.
- [ ] **RPL-T3 — Tourner les vidéos A et B.** Vélo de l'auteur, téléphone posé, son activé (« c'est fait » dit à
  voix haute) ; A : chaîne tombée → posée sur le disque → « c'est fait » → correction → rotation arrière → test
  dynamique ; B : mains devant le plateau, angle de 30°, pour provoquer un arbitrage. Noter les instants de
  « c'est fait » dans `replay/sessions/A.json`, `B.json`. Aucun visage ni document dans le champ.
  Exigences : `RPL-R3.1`. Peut se faire avec le tournage du benchmark (`EVAL-T1`).
- [ ] **RPL-T4 — Construire A et B avec les vrais modèles.** 1re construction en ligne (coût : environ 1 200
  images vidéo ≈ 0,25 $, plus quelques appels Spark et Wonder), puis `--offline` pour vérifier l'identité.
  Commiter `replay/cache/*.models.json` et `replay/sessions/*.json`.
  Exigences : `RPL-R2.1`, `R2.3`, `R2.4`, `R3.1`.
- [ ] **RPL-T5 — Lecteur : vidéo, contours, bandeau, sous-titres.** `web/replay.html`, `replay.js`, `stateAt`,
  synchronisation ± 100 ms, commandes de lecture, son.
  Exigences : `RPL-R4.1`, `R4.5`, `R1.3`, `R1.4`.
- [ ] **RPL-T6 — Frise, détail des événements, courbe.** Événements cliquables, modèle et preuve, réponse brute et
  confiance, courbe du contact avec seuils et curseur.
  Exigences : `RPL-R4.2` à `R4.4`.
- [ ] **RPL-T7 — Honnêteté et liens.** Bandeau permanent, mode de calcul, mention de l'historique de démo, liens.
  Exigences : `RPL-R5.1` à `R5.3`, `R7.2`.
- [ ] **RPL-T8 — Session enregistrée en direct (Should).** Une session réelle avec `FIXLOOP_RECORD=1`, construite
  en source `recording`. Exigences : `RPL-R3.2`. Dépend de : `SRV-T9`, `APP-T9`.
- [ ] **RPL-T9 — Déploiement et vérification.** `replay/deploy_check.py` ; déploiement statique ; vérification en
  navigation privée, sur téléphone en 4G, Chrome, Firefox, Safari ; temps d'affichage de la 1re image noté dans
  `eval/day5/replay-check.md`.
  Exigences : `RPL-R1.1` à `R1.3`, `R8.1`, `R8.2`.
- [ ] **RPL-T10 — Explorer les seuils (Could).** Curseurs, recalcul des `label`, mention « simulation ».
  Exigences : `RPL-R6.1`, `R6.2`.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1–R1.3 | T9 ; R1.3, R1.4 : T5 |
| R2.1 | T1, T4 ; R2.2 : T2 ; R2.3 : T1, T2, T4 ; R2.4 : T1, T4 |
| R3.1 | T3, T4 ; R3.2 : T8 |
| R4.1, R4.5 | T5 ; R4.2–R4.4 : T6 |
| R5.1–R5.3 | T7 ; R5.2 : T2 |
| R6.1, R6.2 | T10 |
| R7.1 | T2, T9 ; R7.2 : T7 |
| R8.1, R8.2 | T9 |
