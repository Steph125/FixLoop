# 03 — Agent Muse Spark : tâches

## Fait (30 oct.)

- [x] **AGT-T1 — `SparkAgent` : diagnostic, arbitrage, explication.** Appel commun `_ask`, `extract_json`,
  `image_to_data_url` (réduction seulement), `crop_around`, journal `calls`.
  Exigences : `AGT-R1.1` à `R1.3`, `R3.1`, `R3.3`, `R3.4`, `R4.1` à `R4.4`, `R6.1`, `R6.3` à `R6.5`, `R7.1`.
  Preuve : 10 tests de `tests/test_agent.py`.
- [x] **AGT-T2 — Règle « Spark ne valide jamais ».** `arbitrate` rend `eps` ou `0` ; « réussie » ignorée.
  Exigences : `AGT-R2.1` à `R2.4`. Preuve : `test_arbitrate_never_validates_but_confirms_failures`,
  `test_uncertain_asks_spark_once_then_geometry_decides` (machine à états).
- [x] **AGT-T3 — Essais réels 1 à 3.** `scripts/try_agent.py` : images de `velo2`, gros plans d'après les boîtes
  SAM, vraies mesures. Exigences : `AGT-R8.2`. Preuve : `eval/day2/findings.md`,
  `try_agent_v1_image_entiere.json`, `try_agent_v3_reperes_disque.json`.
- [x] **AGT-T4 — Repères visuels du disque noir.** `visual_cues` et `notes` dans la fiche, transmis à l'arbitrage.
  Exigences : `AGT-R3.1`. Preuve : essai 3, 2 verdicts justes.

## À faire

- [x] **AGT-T5 — Délai de 20 s.** Passer `timeout=20` à chaque appel ; test avec un faux client qui lève
  `APITimeoutError` → `None`, journal `error`.
  Fichiers : `agent.py`, `tests/test_agent.py`. Exigences : `AGT-R6.2`.
  Preuve : `tests/test_agent.py::test_spark_calls_send_timeout_20_and_timeout_is_logged`,
  `pytest` 83 passed + 9 skipped (async PERC-T4, sandbox), `check_spec.py` OK.
- [ ] **AGT-T6 — Diagnostic avec raison.** `diagnose` rend `(id, raison)` ; adapter le protocole `Agent`,
  `FakeAgent` et `Session.start` (dire « Je vois : <titre>. ») ; journaliser le repli.
  Exigences : `AGT-R1.3`, `R1.4`. Dépend de : rien. Touche `01-core-loop` (`CORE-R4.1`).
- [ ] **AGT-T7 — Garde-fous de sortie.** Phrase > 20 mots tronquée ou remplacée ; test confiance 0,59 → `0`.
  Exigences : `AGT-R2.4`, `R4.5`.
- [ ] **AGT-T8 — `help(step, keyframes)`.** Prompt de `design.md` section 3 ; repli sur la consigne.
  Exigences : `AGT-R5.1`, `R5.2`. Bloque : `CORE-T15`.
- [ ] **AGT-T9 — Jetons et coûts.** Lire `r.usage` ; ajouter `input_tokens`, `output_tokens` au journal ; reporter
  dans `CostLog` (`model="muse-spark-1.3"`).
  Exigences : `AGT-R7.1`, `R7.2`. Dépend de : `SRV-T2`.
- [ ] **AGT-T10 — Gros plans depuis la perception.** Le serveur transmet comme image clé le gros plan découpé avec
  `PartResult.box` du plateau (image entière à défaut).
  Exigences : `AGT-R3.2`. Dépend de : `PERC-T4`, `SRV-T5`.
- [ ] **AGT-T11 — Compter les appels par session.** Mesurer sur 3 sessions de démo enregistrées ; noter le nombre
  d'appels Spark dans `eval/benchmark/report.md`.
  Exigences : `AGT-R7.3`. Dépend de : `SRV-T9`.
- [ ] **AGT-T12 — Spark seul dans le benchmark.** Fournir au benchmark une fonction `spark_only_verdict(images,
  step)` qui pose la question de l'arbitrage **sans** la règle de sécurité (pour mesurer ce qu'elle évite).
  Exigences : `AGT-R8.1`. Utilisée par : `EVAL-T5`.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1–R1.3 | T1 ; R1.3, R1.4 : T6 |
| R2.1–R2.4 | T2 ; R2.4 : T7 |
| R2.5 | T2 (revue : aucun autre chemin ne rend `1`) |
| R3.1, R3.3, R3.4 | T1, T4 ; R3.2 : T1, T10 |
| R4.1–R4.4 | T1 ; R4.5 : T7 |
| R5.1, R5.2 | T8 |
| R6.1, R6.3–R6.5 | T1 ; R6.2 : T5 |
| R7.1 | T1, T9 ; R7.2 : T9 ; R7.3 : T11 |
| R8.1 | T12 ; R8.2 : T3 |
