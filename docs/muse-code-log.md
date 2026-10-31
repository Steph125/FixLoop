# Journal d'usage de Muse Code

Tenu par Muse Code à chaque tâche terminée (date, prompt, fichiers, corrections à la main).
Les entrées « BLOQUÉ » notent les tâches abandonnées après 3 essais et la raison.

## 2026-10-31 (sans interaction, choix prudent noté sans question)

- MEM-T7 (commit du reste de la veille) : le code et les tests dataient du 30 oct. au soir
  mais n'étaient pas committés (arbre sale) ; vérifié `tests/test_memory.py` 7 passed,
  `test_voice.py` + `test_state_machine.py` 29 passed, `check_spec.py` OK
  (82 exigences, 299 critères, 46 décisions, 104 tâches), puis commit nominatif.
  Choix prudent : `git add` nominatif (pas `-A`) pour ne pas embarquer `latency_out/`,
  `prompt_serie2.md`, `pytest-of-nguen/`, `tmp*/` (fichiers de l'utilisateur et résidus).
  VOX-T6 et CORE-T18 déjà committés le 30 oct., vérifiés sans changement.
  Fichiers : `fixloop/memory.py`, `tests/test_memory.py`, `spec/04-memory-voice/tasks.md`.
- AGT-T5 (délai de 20 s) : `timeout=20` ajouté à `responses.create` dans `_ask`
  (délai déjà traité comme absence de réponse par l'exception existante).
  Difficile : 1er essai raté, `httpx` absent du `.venv` — `APITimeoutError(request=None)`
  suffit (seul le nom du type est journalisé). Passé au 2e essai.
  Preuve : `test_spark_calls_send_timeout_20_and_timeout_is_logged`,
  `pytest` 83 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `fixloop/agent.py`, `tests/test_agent.py`, `spec/03-agent-spark/tasks.md`.

## 2026-10-30 (soir, sans interaction)

- VOX-T6 (négation et formes corrigées) : listes `COMMANDS` alignées sur `design.md` 2.2
  (« fini »/« quoi » seuls retirés, « c est fini »/« c est termine »/« repeter » ajoutés),
  règle VOX-R2.6 (négation dans les 3 mots avant ou « pas » après → aucune commande).
  Difficile : `muse.edit_file` refuse les blocs multilignes sur fichiers CRLF — fichier
  réécrit puis reconverti en CRLF ; 1 test existant adapté (`fini` seul, exigé par la spec).
  Choix prudent : `git add` nominatif (pas `-A`) pour ne pas embarquer `latency_out/`,
  `prompt_serie2.md` (fichiers de l'utilisateur).
  Preuve : `test_negated_forms_trigger_nothing`, `test_corrected_forms_detected`,
  `pytest` 79 passed + 9 skipped (async PERC-T4, sandbox), `check_spec.py` OK.
  Fichiers : `fixloop/voice.py`, `tests/test_voice.py`, `spec/04-memory-voice/tasks.md`.
- CORE-T18 (robustesse mémoire) : `_safe_load` (repli « aucun » + `memory_error`)
  et `_safe_save` (clôture sans rapport + `memory_error`), compteur `wonder` incrémenté
  seulement en cas de succès ; `RaisingMemory` dans `tests/fakes.py`, paramètre `memory`
  ajouté au `Runner` (aucun test existant modifié).
  Preuve : `test_raising_memory_falls_back_and_closes`.
  Fichiers : `fixloop/state_machine.py`, `tests/fakes.py`, `tests/test_state_machine.py`,
  `spec/01-core-loop/tasks.md`.
- MEM-T7 (historique illisible) : `_read` attrape JSON invalide/illisible et forme non-dict,
  renomme en `<id>.corrupt-<date>.json` (suffixe si doublon) via `_quarantine`, repart vide
  sans lever. Passé du 1er coup.
  Preuve : `test_corrupt_history_renamed_and_empty`, `test_non_dict_history_renamed_and_empty`.
  Fichiers : `fixloop/memory.py`, `tests/test_memory.py`, `spec/04-memory-voice/tasks.md`.

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
- CORE-T9 (anti-rebond de session) : `debounce_frames` au constructeur de `Session` (défaut 4),
  passé à `verify` (nouveau paramètre `n`, la valeur de l'étape l'emporte), à la fenêtre d'arbitrage
  et au compteur d'échecs du test dynamique ; plus aucun usage de `DEFAULT_DEBOUNCE` dans
  `state_machine.py`. Test passé du 1er coup.
  Preuve : `test_session_debounce_3_validates_after_3_frames`, `pytest` 42 passed + 9 skipped,
  `check_spec.py` OK. Fichiers : `fixloop/verifier.py`, `fixloop/state_machine.py`,
  `tests/test_state_machine.py`, `spec/01-core-loop/tasks.md`.
- CORE-T10 (tests vérificateur) : tâche de tests uniquement, `eps` > `1` et NaN jamais `1`.
  Passés du 1er coup. Preuve : `test_anomaly_wins_when_both_true`,
  `test_nan_never_validates_contact_ratio_max`, `pytest` 44 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `tests/test_geometry_verifier.py`, `spec/01-core-loop/tasks.md`.
- CORE-T11 (robustesse agent) : replis `diagnose` (1re fiche), `arbitrate` (`_safe_arbitration` : seul
  `eps`/`0` passe, jamais `1`), `explain` (message de la règle) ; mesures hors ordre ignorées ;
  `on_measures` ignoré en `CLOTURE`. `RaisingAgent` + `UnknownAgent` dans `tests/fakes.py`.
  Difficile : 2 essais ratés sur mes propres assertions (appartenance à une liste au lieu de
  sous-chaîne, point final absent de la phrase de repli) — code bon dès le 1er essai, vérifié par
  une sonde d'exécution. Preuve : `test_raising_agent_still_reaches_closure` et 3 autres,
  `pytest` 48 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `fixloop/state_machine.py`, `tests/fakes.py`, `tests/test_state_machine.py`,
  `spec/01-core-loop/tasks.md`.
- CORE-T12 (chronomètre dynamique) : tâche de tests uniquement, code déjà conforme.
  Passé du 1er coup. Preuve : `test_single_bad_frame_resets_dynamic_timer_without_anomaly`,
  `pytest` 49 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `tests/test_state_machine.py`, `spec/01-core-loop/tasks.md`.
- CORE-T13 (perte du cadrage) : `last_seen` à chaque mesure, `_check_framing` sur verdict discret
  uniquement (pas de parole double avec anomalie/arbitrage), message avec nom français de la pièce,
  rappel après 10 s. Passé du 1er coup.
  Preuve : `test_framing_lost_after_timeout`, `test_no_framing_when_parts_visible`,
  `pytest` 51 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `fixloop/state_machine.py`, `tests/test_state_machine.py`, `spec/01-core-loop/tasks.md`.
- CORE-T14 (instantané et Output.state) : `snapshot()` au format 6.5, `verdict` suivi, `last_contact`
  gardé après vidage de fenêtre, `_maybe_emit_state` sur changement d'état/étape/verdict, `state()`
  ajouté au protocole `Output` et à `FakeOutput` (demandé par la tâche).
  Difficile : 1er essai raté, contact vide après validation — `last_contact` ajouté, justifié par
  R11.1 (« dernière mesure »). Preuve : `test_snapshot_and_state_notifications`,
  `pytest` 52 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `fixloop/state_machine.py`, `tests/fakes.py`, `tests/test_state_machine.py`,
  `spec/01-core-loop/tasks.md`.
- CORE-T16 (source + export JSONL) : `source` sur `anomaly` (`rule` géométrie/dynamique,
  `muse-spark` arbitrage confirmé), `export_jsonl` avec `_sanitize` (numpy → listes, octets
  nommés, NaN → None). Passé du 1er coup. Note : R8.2 cite « design.md section 6 » mais le
  schéma des événements est en section 7 — simple renvoi, export aligné sur la section 7.
  Preuve : `test_anomaly_events_carry_source`, `test_export_jsonl_has_no_binary_or_key`,
  `pytest` 54 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `fixloop/state_machine.py`, `tests/test_state_machine.py`, `spec/01-core-loop/tasks.md`.
- SRV-T2 (journal des coûts) : `PRICES` (table tech §3), `CostLog` (`add` → coût estimé, `session_total`,
  `day_total`, `by_model`, JSONL par jour relu au démarrage), vidéo facturée min 50, modèle inconnu → 0
  sans lever, `estimated` marqué pour les jetons. Appel compatible avec le crochet posé en PERC-T4.
  Difficile : 1er essai raté sur mes égalités float (0.36*2.5) — `pytest.approx` partout.
  Preuve : `tests/test_costs.py` (5 tests), `pytest` 59 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `fixloop/costs.py`, `tests/test_costs.py`, `spec/05-session-server/tasks.md`.
- SRV-T3 (protocole) : `parse_client_message` (table type → champs requis, `cmd` restreint, bool
  exclu des entiers, champs en plus permis), `parse_binary` (0x01/0x02, t_ms gros-boutiste,
  `too_big` au-delà de 200 ko). Aucune dépendance externe. Passé du 1er coup.
  Choix prudent : tests dans `tests/test_protocol.py` plutôt que `test_server.py` (FastAPI absent,
  SRV-T1/T5 le rempliront). Preuve : 4 tests, `pytest` 63 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `server/protocol.py`, `server/__init__.py`, `tests/test_protocol.py`,
  `spec/05-session-server/tasks.md`.
- VOX-T2 (détecteur de commandes) : `normalize` (minuscules, NFD, ponctuation en espaces),
  `CommandDetector` (mot entier, priorité done > help > repeat, anti-répétition 2 s, silence
  synthèse + 500 ms, `history` pour VOX-T4), méthode nommée `speaking` comme le design.
  Passé du 1er coup. Preuve : `tests/test_voice.py` (8 tests), `pytest` 71 passed + 9 skipped,
  `check_spec.py` OK. Fichiers : `fixloop/voice.py`, `tests/test_voice.py`,
  `spec/04-memory-voice/tasks.md`.
- MEM-T1 (historique local) : `WonderMemory` sans Wonder (`load` → « aucun » ou 5 dernières lignes,
  `repeated`, `save` atomique par allowlist, `date` surchargeable pour MEM-T6, client stocké pour
  MEM-T4). Passé du 1er coup. Preuve : `tests/test_memory.py` (5 tests),
  `pytest` 76 passed + 9 skipped, `check_spec.py` OK.
  Fichiers : `fixloop/memory.py`, `tests/test_memory.py`, `spec/04-memory-voice/tasks.md`.

## Résumé final (30 oct. 2026)

Tâches faites (14/14) : PERC-T3, PERC-T4, PERC-T6, CORE-T9, CORE-T10, CORE-T11, CORE-T12,
CORE-T13, CORE-T14, CORE-T16, SRV-T2, SRV-T3, VOX-T2, MEM-T1. Chacune cochée `[x]` dans son
`tasks.md` avec sa preuve, journalisée ci-dessus et committée séparément.

Tâches bloquées : aucune. Écarts assumés et notés en cours de route : tests async de PERC-T4
ignorés proprement là où `listen()` est bloqué (vérifiés 10/10 sur boucle réelle sans socket
dans un script jetable supprimé après) ; `tests/test_protocol.py` au lieu de `test_server.py`
(FastAPI absent, SRV-T1/T5 le rempliront) ; renvoi R8.2 « section 6 » visant le schéma de la
section 7. Crochets posés pour la suite : `LivePerception._cost` → PERC-T7, `CommandDetector.history`
→ VOX-T4, `WonderMemory.client` et `report["date"]`/`title` → MEM-T4/MEM-T6.

Résultat final : `python -m pytest -q tests` → 76 passed + 9 skipped (les 9 = tests async PERC-T4,
ignorés dans cette sandbox) ; `python scripts/check_spec.py` → 82 exigences, 297 critères,
46 décisions, 101 tâches, OK. Interdits respectés : `.env` ni lu ni committé, aucun appel API,
aucun lancement de `probe/` ou `try_agent.py`, aucun `push`/`merge`/changement de branche,
aucune dépendance ajoutée, aucune suppression hors scripts jetables créés puis supprimés.
