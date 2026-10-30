# 04 — Mémoire et voix : tâches

Toutes à faire. Ordre conseillé : les tâches sans réseau d'abord (T1, T2, T5), puis les sondes, puis les ponts.

## Mémoire

- [ ] **MEM-T1 — Historique local.** `WonderMemory` sans Wonder d'abord : lecture, validation de `bike_id`,
  écriture atomique, `repeated()`, repli texte brut. `FakeMemory` reste pour les tests de session.
  Fichiers : `fixloop/memory.py`, `tests/test_memory.py`.
  Exigences : `MEM-R1.1`, `R1.5`, `R1.6`, `R2.1`, `R2.3`, `R2.4`, `R3.1`, `R3.2`.
- [ ] **MEM-T2 — Rapport enrichi.** `Session._close` fournit étapes validées, anomalies (étape, instant, message)
  et durée ; adapter `test_happy_path_to_closure`.
  Fichiers : `state_machine.py`. Exigences : `MEM-R2.1`. Touche `01-core-loop`.
- [ ] **MEM-T3 — Sonde Wonder.** `probe/wonder_probe.py` : une synthèse sur un historique de 5 entrées ; noter
  durée et réponse dans `eval/day3/findings.md`. Coût : quelques centimes.
  Exigences : `MEM-R1.2`. Fait quand : durée notée, réponse < 60 mots.
- [ ] **MEM-T4 — Synthèse et rapport par Wonder.** Appels de `load` et `save` (délai 20 s, journal `calls`,
  coûts). Si la sonde montre plus de 5 s : synthèse lancée en parallèle du diagnostic (`MEM-D3`).
  Exigences : `MEM-R1.2`, `R1.3`, `R2.2`. Dépend de : T1, T3, `SRV-T2`.
- [ ] **MEM-T5 — Phrase de panne répétée.** Après le diagnostic, si `repeated() ≥ 2`, la session dit la phrase de
  `design.md` 1.2. Exigences : `MEM-R1.4`. Touche `01-core-loop`.
- [ ] **MEM-T6 — Historique de démo.** `scripts/seed_history.py`, entrées `demo: true`.
  Exigences : `MEM-R4.1` ; `MEM-R4.2` couvert par `SUB-T3`, `SUB-T6`.

## Voix

- [ ] **VOX-T1 — Lire la doc et sonder Transcribe.** `probe/transcribe_probe.py` : ouvrir la WebSocket, envoyer un
  fichier WAV de test (« c'est fait », enregistré par l'auteur), afficher les événements reçus. Noter dans
  `design.md` section 2.1 : configuration, encodage audio, noms des événements, délai mesuré.
  Exigences : `VOX-R1.2`, `R1.4`. Fait quand : transcription finale reçue et délai noté dans `eval/day3/`.
- [ ] **VOX-T2 — Détecteur de commandes.** `normalize`, `CommandDetector` et `tests/test_voice.py`.
  Exigences : `VOX-R2.1` à `R2.4`. Aucun réseau.
- [ ] **VOX-T3 — Pont Transcribe.** `VoiceBridge` (connexion, envoi PCM16, réception, 3 reconnexions, arrêt) ;
  test avec faux serveur WebSocket.
  Exigences : `VOX-R1.1`, `R1.3`, `R3.2`, `R4.1`. Dépend de : T1.
- [ ] **VOX-T4 — Branchement à la session.** Commande → `on_user_done` / `on_command` ; journal `command` avec texte
  normalisé ; durée audio dans les coûts.
  Exigences : `VOX-R2.5`, `R4.2`. Dépend de : T2, T3, `SRV-T6`, `CORE-T15`.
- [ ] **VOX-T5 — Repli bouton.** Côté serveur : message `voice_status` (`on`, `off`, `error`) ; côté appli : texte
  « Commande vocale indisponible ». Exigences : `VOX-R3.1`, `R3.2`. Dépend de : `APP-T5`.

## Couverture

| Critère | Tâches |
|---|---|
| MEM-R1.1, R1.5, R1.6 | MEM-T1 |
| MEM-R1.2, R1.3 | MEM-T3, MEM-T4 |
| MEM-R1.4 | MEM-T5 |
| MEM-R2.1 | MEM-T1, MEM-T2 ; R2.2 : MEM-T4 ; R2.3, R2.4 : MEM-T1 |
| MEM-R3.1, R3.2 | MEM-T1 |
| MEM-R4.1 | MEM-T6 ; R4.2 : `SUB-T3`, `SUB-T6` |
| VOX-R1.1, R1.3 | VOX-T3 ; R1.2, R1.4 : VOX-T1 |
| VOX-R2.1–R2.4 | VOX-T2 ; R2.5 : VOX-T4 |
| VOX-R3.1 | VOX-T5, `APP-T4` ; R3.2 : VOX-T3, VOX-T5 |
| VOX-R4.1 | VOX-T3 ; R4.2 : VOX-T4 |
