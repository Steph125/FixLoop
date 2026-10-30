# 01 — Boucle de vérification : tâches

Ordre d'exécution de haut en bas. Chaque tâche : statut, fichiers touchés, exigences couvertes, condition
« Fait quand », preuve. `python -m pytest -q tests` doit passer après chaque tâche.

## Fait (27 – 30 oct.)

- [x] **CORE-T1 — Types partagés.** `FrameMasks`, `Measures`, `Verdict` dans `fixloop/models.py`.
  Exigences : `CORE-R2.1`, `R2.2`. Preuve : commit du 28 oct., importés par tous les modules.
- [x] **CORE-T2 — Schéma et chargement des fiches.** `spec/procedure_schema.json` ; `load_procedure` valide par
  jsonschema et contrôle que chaque pièce citée existe ; `load_all()`.
  Exigences : `CORE-R1.1`, `R1.2`, `R1.3`. Preuve : `scripts/simulate_session.py` charge la fiche.
- [x] **CORE-T3 — Champs `select`, `notes`, `visual_cues`, `when`, `requires_done`.** Ajoutés au schéma.
  Exigences : `CORE-R1.4`, `R1.5`, `R3.5`, `R3.3`. Preuve : fiche `chain_off_chainring` validée au chargement.
- [x] **CORE-T4 — Géométrie.** `outer_edge`, `contact_ratio` (NaN si pièce absente), `contact_pairs`, `measure`.
  Exigences : `CORE-R2.1` à `R2.3`. Preuve : `test_contact_ratio_separates_on_and_off`, `test_missing_part_gives_nan`.
- [x] **CORE-T5 — Vérificateur.** `eval_rule`, `verify` (priorité eps > 1 > ? > 0), `holds`.
  Exigences : `CORE-R3.1` à `R3.7`. Preuve : 7 tests de `test_geometry_verifier.py`.
- [x] **CORE-T6 — Machine à états.** `Session` : démarrage, étapes, validation, anomalie avec anti-répétition,
  arbitrage limité à 1 fois / 10 s, test dynamique, clôture, journal.
  Exigences : `CORE-R4`, `R5`, `R6.1` à `R6.3`, `R7`, `R8.1`. Preuve : 6 tests de `test_state_machine.py`.
- [x] **CORE-T7 — Fiche `chain_off_chainring` calibrée.** Seuils 0,18 / 0,26, `after_done`, `requires_done`.
  Exigences : `CORE-R1.6`. Preuve : `eval/day1/findings.md` (0 image mal classée sur 285).
- [x] **CORE-T8 — Scène synthétique et simulation.** `fixloop/sim.py` (en place ≈ 0,07, tombée ≈ 0,54, cachée),
  `scripts/simulate_session.py`. Exigences : tests de bout en bout (`structure.md` section 4).

## À faire

- [x] **CORE-T9 — Anti-rebond de session.** Ajouter `debounce_frames` au constructeur de `Session` (défaut 4) ;
  le passer à `verify(step, window, user_done, n)` (la valeur de l'étape l'emporte si elle existe), à la fenêtre
  d'arbitrage et au compteur d'échecs du test dynamique ; supprimer les usages directs de `DEFAULT_DEBOUNCE`
  dans `state_machine.py`.
  Fichiers : `verifier.py`, `state_machine.py`, tests. Exigences : `CORE-R3.8`, `R9.1`.
  Fait quand : `test_session_debounce_3_validates_after_3_frames` passe.
  Preuve : `tests/test_state_machine.py::test_session_debounce_3_validates_after_3_frames`.
- [x] **CORE-T10 — Tests manquants du vérificateur.** Succès et anomalie vrais en même temps → `eps` ; NaN sur
  une règle `contact_ratio_max` → jamais `1`.
  Fichiers : `tests/test_geometry_verifier.py`. Exigences : `CORE-R3.4`, `R3.7`.
  Preuve : `test_anomaly_wins_when_both_true`, `test_nan_never_validates_contact_ratio_max`.
- [x] **CORE-T11 — Robustesse face à l'agent.** Envelopper `diagnose`, `arbitrate`, `explain` dans la session :
  exception ou valeur invalide → repli de `design.md` section 8. Ignorer les mesures dont `t` est inférieur à la
  dernière. Ignorer `on_measures` en `CLOTURE`.
  Fichiers : `state_machine.py`, `tests/fakes.py` (`RaisingAgent`). Exigences : `CORE-R5.4`, `R7.4`.
  Fait quand : une session avec `RaisingAgent` arrive à la clôture sur la scène synthétique.
  Preuve : `test_raising_agent_still_reaches_closure`, `test_out_of_order_measures_are_ignored`,
  `test_measures_ignored_after_closure`, `test_unknown_procedure_falls_back_to_first`.
- [x] **CORE-T12 — Chronomètre du test dynamique.** Test : une image fausse isolée remet le chronomètre à zéro sans
  anomalie ; `N` images fausses déclenchent l'anomalie.
  Fichiers : `tests/test_state_machine.py`. Exigences : `CORE-R6.2`, `R6.4`.
  Preuve : `test_single_bad_frame_resets_dynamic_timer_without_anomaly`.
- [x] **CORE-T13 — Perte du cadrage.** `last_seen[pièce]` mis à jour à chaque mesure ; si une pièce requise n'a
  pas été vue depuis `framing_timeout_s`, dire le message, journaliser `framing_lost`, ne pas répéter avant 10 s.
  Fichiers : `state_machine.py`, tests. Exigences : `CORE-R10.1`, `R10.2`, `R9.1`.
  Preuve : `test_framing_lost_after_timeout`, `test_no_framing_when_parts_visible`.
- [x] **CORE-T14 — Instantané et `Output.state`.** `Session.snapshot()` au format `design.md` 6.5 ; appel de
  `out.state(...)` à chaque changement d'état, d'étape ou de verdict (pas à chaque image si rien ne change).
  Mettre à jour `FakeOutput`. Fichiers : `state_machine.py`, `tests/fakes.py`. Exigences : `CORE-R11.1`, `R11.2`.
  Preuve : `test_snapshot_and_state_notifications`.
- [ ] **CORE-T15 — Commandes « répète » et « aide-moi ».** `Session.on_command("repeat" | "help")` ; ajouter
  `Agent.help(step, keyframes) -> str` au protocole et à `FakeAgent` ; journaliser `command`.
  Fichiers : `state_machine.py`, `tests/fakes.py`. Exigences : `CORE-R12.1`, `R12.2`, `R12.3`.
  Dépend de : `AGT-T8` pour l'implémentation réelle de `help`.
- [ ] **CORE-T16 — Champ `source` des anomalies et export JSONL.** `source: "rule" | "muse-spark"` sur
  l'événement `anomaly` ; fonction `export_jsonl(log, path)` ; test qu'aucune entrée ne contient de tableau numpy,
  d'octets ou la chaîne `MODEL_API_KEY`.
  Fichiers : `state_machine.py`, tests. Exigences : `CORE-R8.1`, `R8.2`, `R8.3`.
- [ ] **CORE-T17 — Performance de la géométrie.** Mesurer `measure()` sur 100 images 848×464 enregistrées ;
  noter la médiane dans `eval/day1/findings.md` (section ajoutée).
  Exigences : `CORE-R2.4`. Fait quand : médiane notée, cible < 50 ms atteinte ou écart expliqué.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1–R1.3 | T2 |
| R1.4, R1.5 | T3 |
| R1.6 | T7 |
| R2.1–R2.3 | T1, T4 |
| R2.4 | T17 |
| R3.1–R3.3, R3.5, R3.6 | T5 |
| R3.4, R3.7 | T5, T10 |
| R3.8 | T9 |
| R4.1–R4.6 | T6 |
| R5.1–R5.3 | T6 |
| R5.4 | T11 |
| R6.1–R6.3 | T6 ; R6.2, R6.4 : T12 |
| R7.1–R7.3, R7.5 | T6 ; R7.4 : T6, T11 |
| R8.1–R8.3 | T6, T16 |
| R9.1, R9.2 | T9, T13 ; R9.2 côté serveur : `SRV-T5` |
| R10.1, R10.2 | T13 |
| R11.1, R11.2 | T14 |
| R12.1–R12.3 | T15 ; détection vocale : `VOX-T4` |
