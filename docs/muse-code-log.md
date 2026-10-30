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
