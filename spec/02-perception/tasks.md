# 02 — Perception SAM 3.1 : tâches

## Fait (28 – 30 oct.)

- [x] **PERC-T1 — Sonde vidéo.** `probe/sam_api_probe.py` : préparation ffmpeg, morceaux de 10 s, cache,
  relances, `largest`, mesures, vidéo annotée, `metrics.csv`, états.
  Exigences : `PERC-R3.1` à `R3.6`, `R4.1`, `R4.2`. Preuve : `eval/day1/findings.md` (18 morceaux, 529 s).
- [x] **PERC-T2 — Sonde image.** `probe/sam_image_latency.py` : 2 requêtes en parallèle par image, premier octet,
  relances, fermeture des flux. Exigences : `PERC-R1.1` à `R1.3`, `R1.5`, `R1.7`, `R1.8`, `R4.5`.
  Preuve : `eval/day1/findings.md`, section mode image (1,9 s, 10/10).

## À faire

- [x] **PERC-T3 — Extraire `fixloop/perception.py`, partie commune.** Constantes, `RETRYABLE`, placement plein
  cadre, `masks_from_records` (filtre de confiance, `largest` / union, boîte), `parse_raw`, `lines_for` (repris de
  `scripts/try_agent.py`), `shift_frames`, `plan_chunks`.
  Exigences : `PERC-R1.3` à `R1.6`, `R3.2`, `R3.4`, `R5.1`, `R5.2`, `R8.2`.
  Fait quand : tests unitaires de placement, sélection, filtre et découpage passent.
  Preuve : `tests/test_perception.py` (12 tests, `pytest` 37 passed le 30 oct.).
- [x] **PERC-T4 — Mode image dans le module.** `LivePerception.segment_image`, `try_submit` (au plus 3 en cours),
  relances (5 s × tentative), pas de relance hors réseau, résultat `error`, chronométrage, `live_parts`
  (seulement les pièces citées par une règle).
  Exigences : `PERC-R1.1`, `R1.2`, `R1.8`, `R1.9`, `R2.1` à `R2.3`, `R4.1` à `R4.5`.
  Fait quand : tests avec `FakeSamClient` (relance, 401, 4e image refusée) passent.
  Preuve : `tests/test_perception_live.py` (10 tests, exécutés 10/10 sur boucle réelle
  sans socket le 30 oct. ; ignorés proprement là où `listen()` est bloqué).
- [~] **PERC-T5 — Mode vidéo dans le module.** `segment_video` (préparation, morceaux, Files API, cache par
  empreinte, confirmation du nombre d'images facturées). `probe/sam_api_probe.py` reste inchangé (preuve datée).
  Exigences : `PERC-R3.1` à `R3.6`, `R4.2`. Fait quand : test du cache (2e passage sans requête) passe.
  À vérifier hors sandbox : `test_video_cache_skips_second_pass` ignoré ici (sockets interdits).
  Preuve partielle : `test_assemble_frames_merges_shifted_chunks`, `test_chunk_key_stable_and_content_bound`
  (passent ici), `pytest` 96 passed + 12 skipped, `check_spec.py` OK.
- [x] **PERC-T6 — Contours SVG et boîtes.** `mask_to_svg_path` ; comparer avec `decode_mask_to_svg_path` sur
  20 masques enregistrés (taille, rendu) ; noter le choix dans `design.md` section 9.
  Exigences : `PERC-R6.1` à `R6.3`. Fait quand : taille médiane < 4 ko notée.
  Preuve : `test_recorded_masks_svg_median_under_4k` (médiane 303 o, max 410 o) ; décision `PERC-D6`.
- [~] **PERC-T7 — Journal des coûts.** Appeler `CostLog.add(model="sam-3.1", mode, part, images, seconds,
  attempts, ok)` à chaque requête ; facturation vidéo max(images, 50).
  Exigences : `PERC-R7.1`, `R7.2`. Dépend de : `SRV-T2` (`fixloop/costs.py`).
  À vérifier hors sandbox : les 2 tests async bout-en-bout sont ignorés ici (sockets interdits).
  Preuve partielle : `tests/test_perception.py::test_cost_log_called_per_request` (mapping vérifié),
  `test_image_requests_are_logged_to_costs`, `test_failed_request_is_logged_not_ok` (ignorés ici),
  `pytest` 94 passed + 11 skipped, `check_spec.py` OK. Aucun code à écrire (`_cost` couvrait déjà
  les 4 chemins de `_segment_part`) ; le mode vidéo sera couvert par PERC-T5.
- [x] **PERC-T8 — Équivalence avec `eval/day1`.** Test `recorded` : rejouer `probe_out2/raw_*.txt` avec le module,
  comparer les médianes par phase (± 0,005) et le classement des 285 images (0 erreur).
  Exigences : `PERC-R9.1`, `R9.2`.
  Preuve : `tests/test_perception.py::test_recorded_equivalence_day1`
  (médianes 0,3437 / 0,0903 / 0,0896 contre 0,344 / 0,090 / 0,085 ; 0 mal classée),
  `pytest` 97 passed + 12 skipped, `check_spec.py` OK.
- [ ] **PERC-T9 — Vérification en direct, filtre de confiance.** Relancer `probe/sam_image_latency.py --times
  5,10,25,35` en important le module ; confirmer les 4 états. Coût : 8 images, environ 0,02 $.
  Exigences : `PERC-R1.4`, `R1.7`. Preuve à noter : `eval/day1/findings.md`.
- [ ] **PERC-T10 — Configuration.** Surcharges `FIXLOOP_SAM_*` ; vérification que la clé n'apparaît dans aucun
  journal (test qui cherche la valeur de `MODEL_API_KEY` dans les sorties).
  Exigences : `PERC-R8.1`, `R8.2`.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1–R1.3, R1.5, R1.8 | T2, T3, T4 |
| R1.4, R1.6 | T3, T9 |
| R1.7 | T2, T9 |
| R1.9 | T4 |
| R2.1–R2.3 | T4 |
| R3.1–R3.6 | T1, T5 |
| R4.1–R4.5 | T1, T2, T4 |
| R5.1, R5.2 | T3 |
| R6.1–R6.3 | T6 |
| R7.1, R7.2 | T7 |
| R8.1, R8.2 | T10 |
| R9.1, R9.2 | T8 |
