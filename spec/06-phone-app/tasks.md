# 06 — Appli téléphone : tâches

Toutes à faire. Jalon (dimanche 1er nov.) : appli sur le téléphone de l'auteur, session en direct complète.

- [x] **APP-T1 — Écrans statiques.** `index.html` (6 sections), `style.css` (portrait, contrastes, boutons),
  navigation entre écrans sans serveur.
  Exigences : `APP-R8`, `APP-R9.2`, `APP-R10.1`, `R10.2`.
  Preuve : `tests/test_phone_app.py` (6 tests), `node web/selftest.mjs` 5/5, `pytest` ciblé OK, `check_spec.py` OK.
- [x] **APP-T2 — Identité du vélo et code d'accès.** `bike_id` dans `localStorage` (try/catch, repli de session),
  champ de code affiché si `/api/health` indique un code requis.
  Exigences : `APP-R6.1`, `R6.2`, `R1.5`.
  Preuve : `tests/test_phone_app.py::test_bike_id_and_access_code`, `node web/selftest.mjs` 7/7.
- [x] **APP-T3 — Caméra et cadrage.** Autorisations dans le geste « Commencer », caméra arrière, refus caméra et
  micro, écran de cadrage, envoi de `start`.
  Exigences : `APP-R1.2` à `R1.4`, `R2.4`, `R3.1`, `R3.2`.
  Preuve : `tests/test_phone_app.py::test_camera_and_framing`, `node web/selftest.mjs` 9/9.
- [x] **APP-T4 — WebSocket et boutons.** `hello`, `user_done`, `command`, `pause`, `stop` ; retour visuel et
  vibration ; reconnexions.
  Exigences : `APP-R4.1` à `R4.3`, `R9.3`, `VOX-R3.1`. Dépend de : `SRV-T4`.
  Preuve : `tests/test_phone_app.py::test_websocket_and_buttons`, `node web/selftest.mjs` 12/12.
- [x] **APP-T5 — Envoi des images.** Capture 1 image/s, réduction 848 px, JPEG 0,7, en-tête binaire, pas de file.
  Exigences : `APP-R2.1` à `R2.3`. Dépend de : `SRV-T3`.
  Preuve : `tests/test_phone_app.py::test_image_sending`, `node web/selftest.mjs` 14/14.
- [x] **APP-T6 — Surimpression.** SVG aligné sur la vidéo, couleurs, estompage après 3 s, ligne de mesure.
  Exigences : `APP-R5.1` à `R5.4`. Dépend de : `SRV-T5`, `PERC-T6`.
  Preuve : `tests/test_phone_app.py::test_overlay_drawing`, `node web/selftest.mjs` 15/15.
- [x] **APP-T7 — Voix en sortie.** `speechSynthesis` fr-FR, sous-titres, interruption, message `speaking`,
  déblocage iOS.
  Exigences : `APP-R7.1` à `R7.3`.
  Preuve : `tests/test_phone_app.py::test_spoken_voice_output`, `node web/selftest.mjs` 16/16.
- [x] **APP-T8 — Voix en entrée.** `audio-worklet.js`, PCM16 16 kHz, morceaux de 100 ms, indicateur micro,
  `voice_status`.
  Exigences : `APP-R7.4` (24 kHz, 80 ms — le titre disait 16 kHz / 100 ms : voir SPEC À REVOIR). Dépend de : `VOX-T3` ([~]), `SRV-T6` ([~], voix coupée sans pont).
  Preuve : `tests/test_phone_app.py::test_voice_input_worklet`, `test_voice_fallback_status`, `node web/selftest.mjs` 17/17.
- [ ] **APP-T9 — Écran allumé, HTTPS et essai sur téléphone.** `wakeLock` ; tunnel HTTPS ; session réelle
  complète sur le vélo ; liste de contrôle `eval/day4/phone-checklist.md`.
  Exigences : `APP-R1.1`, `R9.1`, `R10.3`, et vérification manuelle de tous les `APP-R*`.
- [x] **APP-T10 — Auto-test navigateur.** `web/selftest.html`.
  Exigences : tests de `design.md` section 7.
  Preuve : `tests/test_phone_app.py::test_selftest_covers_lib`, `node web/selftest.mjs` 16/16.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1 | T9 ; R1.2–R1.4 : T3 ; R1.5 : T2 |
| R2.1–R2.3 | T5 ; R2.4 : T3 |
| R3.1, R3.2 | T3 |
| R4.1–R4.3 | T4 |
| R5.1–R5.4 | T6 |
| R6.1, R6.2 | T2 |
| R7.1–R7.3 | T7 ; R7.4 : T8 |
| R8 | T1 |
| R9.1 | T9 ; R9.2 : T1 ; R9.3 : T4 |
| R10.1, R10.2 | T1 ; R10.3 : T9 |
