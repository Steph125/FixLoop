# 05 — Serveur de session : tâches

Toutes à faire. Jalon (`steering/product.md`, samedi 31) : session de bout en bout en local avec `ws_client.py`.

- [~] **SRV-T1 — Squelette FastAPI.** `server/app.py` : fichiers statiques, `/api/health`, `/api/procedures`,
  chargement des fiches au démarrage, lecture de `.env`. Ajouter `fastapi`, `uvicorn[standard]`, `websockets` à
  `requirements.txt`.
  Exigences : `SRV-R1.1` à `R1.4`. Fait quand : `curl http://127.0.0.1:8000/api/health` rend `ok`.
  À vérifier hors sandbox : PyPI injoignable ici (3 tentatives pip sans réponse), `fastapi`/`httpx`
  absents donc `tests/test_server.py` ignoré ici et le `curl` local impossible (sockets interdits).
  Preuve partielle : `py_compile` OK, `pytest` 97 passed + 13 skipped, `check_spec.py` OK.
- [x] **SRV-T2 — Journal des coûts.** `fixloop/costs.py` (`PRICES`, `CostLog`, persistance par jour, estimation
  des jetons manquants), `tests/test_costs.py`.
  Exigences : `SRV-R8.1`, `R8.5`. Bloque : `PERC-T7`, `AGT-T9`, `MEM-T4`.
  Preuve : `tests/test_costs.py` (5 tests : 360 images → 0,90 $, vidéo min 50, persistance).
- [x] **SRV-T3 — Protocole.** `server/protocol.py` : validation des messages JSON, en-tête binaire, taille max.
  Exigences : `SRV-R3.1` à `R3.4`.
  Preuve : `tests/test_protocol.py` (4 tests, sans dépendance externe).
- [ ] **SRV-T4 — Ouverture et contrôle d'accès.** `hello` / `hello_ack`, code d'accès, 2 sessions max, blocage
  après 5 refus par IP.
  Exigences : `SRV-R2.1` à `R2.4`.
- [ ] **SRV-T5 — Boucle de session.** `LiveSession` : images de démarrage, `Session.start` dans un fil, soumission
  à la perception, filtre âge et ordre, mesures, `overlay`, `sm_worker` avec `pending`, `QueueOutput`,
  `send_loop`, `debounce_frames = 3`, temps client, image clé recadrée.
  Exigences : `SRV-R4.1` à `R4.5`, `R5.1` à `R5.3`, `R6.1`, `R6.2`, `CORE-R9.2`.
  Dépend de : T1, T3, `PERC-T4`. Fait quand : tests de session complète, d'âge, d'ordre et de `pending` passent.
- [ ] **SRV-T6 — Commandes et voix.** `user_done`, `command`, `speaking`, `pause` / `resume`, `stop` ; audio
  binaire vers `VoiceBridge` ; `voice_status`.
  Exigences : `SRV-R5.4`. Dépend de : T5, `VOX-T3`.
- [ ] **SRV-T7 — Clôture et erreurs.** `closed` puis fermeture après 2 s ; 401, 402 / 429, budget, lenteur 15 s,
  exceptions (3 de suite → arrêt), déconnexion.
  Exigences : `SRV-R6.3`, `R7.1` à `R7.4`.
- [ ] **SRV-T8 — Limites de coût et de durée.** Arrêt à 1,50 $ ou 10 min ; refus au-delà du budget du jour ;
  `/api/costs` protégé.
  Exigences : `SRV-R8.2` à `R8.4`. Dépend de : T2.
- [ ] **SRV-T9 — Journal et enregistrement.** `data/sessions/<id>.jsonl` ; option `FIXLOOP_RECORD=1` (images
  reçues + sorties SAM brutes dans `data/recordings/<id>/`).
  Exigences : `SRV-R9.1` à `R9.3`. Utilisé par : `RPL-T2`, `EVAL-T2`, `AGT-T11`.
- [ ] **SRV-T10 — Client de test et faux modèles.** `scripts/ws_client.py --video … --done 18,30` ;
  `FIXLOOP_FAKE_MODELS=1` (perception depuis la scène synthétique ou des `raw_*.txt`, faux Spark, faux Wonder).
  Exigences : `SRV-R10.1`, `R10.2`. Fait quand : session `velo2` jouée sans réseau jusqu'à `closed`.
- [ ] **SRV-T11 — Première session réelle en local.** `ws_client.py` sur `velo2` avec les vrais modèles ;
  noter dans `eval/day3/findings.md` : délai du verdict après le geste, `dropped`, résultats écartés, appels Spark,
  coût estimé, puis comparer au coût affiché sur la page Usage.
  Exigences : `SRV-R8.5`, indicateurs de `steering/product.md` section 9. Coût prévu : 57 images × 2 pièces ≈ 0,29 $ de SAM, plus quelques centimes de Spark et Wonder.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1–R1.4 | T1 |
| R2.1–R2.4 | T4 |
| R3.1–R3.4 | T3 |
| R4.1–R4.5 | T5 |
| R5.1–R5.3 | T5 ; R5.4 : T6 |
| R6.1, R6.2 | T5 ; R6.3 : T7 |
| R7.1–R7.4 | T7 |
| R8.1, R8.5 | T2, T11 ; R8.2–R8.4 : T8 |
| R9.1–R9.3 | T9 |
| R10.1, R10.2 | T10 |
