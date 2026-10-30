# Journal d'usage de Muse Code

Tenu par Muse Code à chaque tâche terminée (date, prompt, fichiers, corrections à la main).
Les entrées « BLOQUÉ » notent les tâches abandonnées après 3 essais et la raison.

## 2026-10-30

- PERC-T3 (partie commune perception) : aucun code à écrire, `fixloop/perception.py`
  et `tests/test_perception.py` couvraient déjà placement plein cadre, `largest`/union,
  filtre 0,4, pièce absente, `parse_raw`, `lines_for`, `shift_frames`, `plan_chunks`.
  Choix prudent : pas de test ajouté pour les surcharges `FIXLOOP_*` (couvert par PERC-T10).
  Preuve : `tests/test_perception.py`, `pytest` 37 passed, `check_spec.py` OK.
  Fichiers : `spec/02-perception/tasks.md` (case cochée). Aucune correction à la main.
- PERC-T4 (mode image) : `live_parts`, `LivePerception` (`segment_image` en `asyncio.gather`
  par pièce, `try_submit` ≤ 3 en cours, relances 5 s × tentative, pas de relance hors réseau
  ni sur refus, `stream.close()` en `finally`, chronométrage, `to_frame_masks`), `FakeSamClient`
  dans `tests/fakes.py`, `tests/test_perception_live.py` (10 tests).
  Difficile : la sandbox bloque `listen()`, donc aucune boucle asyncio ; vérification par
  une boucle sans socket dans un script jetable (10/10, script supprimé après), puis `pytest`
  38 passed + 9 skipped et `check_spec.py` OK. Corrigé en cours : import manquant de
  `parse_responses_stream`, refus SAM exclu des relances (sous-classe de `ResponsesStreamError`).
  Fichiers : `fixloop/perception.py`, `tests/fakes.py`, `tests/test_perception_live.py`,
  `spec/02-perception/tasks.md`.
- PERC-T6 (contours SVG) : `mask_to_svg_path` (OpenCV simplifié, tol 1,5, seuil 40 px²),
  `svg_path` rempli dans `masks_from_records`, comparaison sur 20 masques enregistrés :
  303 o médians contre 9 344 o pour `decode_mask_to_svg_path` (rejeté, > 4 ko), décision
  `PERC-D6` dans `spec/02-perception/design.md`.
  Difficile : 1er essai raté, mon rectangle de test (12 px²) sous le seuil de 40 px² de la
  spec — test adapté (100 px²), spec inchangée. Preuve : `test_recorded_masks_svg_median_under_4k`,
  `pytest` 41 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `fixloop/perception.py`, `tests/test_perception.py`, `spec/02-perception/design.md`,
  `spec/02-perception/tasks.md`.
