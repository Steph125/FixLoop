# Jour 3 : première session en direct avec les vrais modèles (SRV-T11)

1er nov. 2026. Serveur local (`uvicorn`), client `scripts/ws_client.py` qui rejoue `velo2` (848×464) à 1 image/s,
comme le téléphone ; « c'est fait » envoyé à 30 s. Modèles réels : `sam-3.1` (mode image, chaîne et plateau),
`muse-spark-1.3` (diagnostic). Journal : `data/sessions/5ad14f4241454c79.jsonl` (non commité, ni image ni clé).

## Déroulé

| Instant (s) | Événement | Contact chaîne/plateau |
|---|---|---|
| 0 | Diagnostic Spark : « chaîne tombée du plateau », raison dite à l'utilisateur | — |
| 14 | Étape 1 (cadrage) validée | 0,328 (tombée) |
| 19 | Étape 2 (chaîne sur les dents) validée, 3 s après la remise réelle (≈ 16 s) | 0,081 |
| 27 | « c'est fait » reçu | — |
| 28 | Étape 3 (demi-tour arrière) validée | 0,128 |
| 28 – 32 | Test dynamique réussi, clôture `success: true` | ≤ 0,18 |

Appels Spark : 1 (aucun arbitrage ni anomalie dans ce déroulé). Session close sans erreur.

## Mesures

| Mesure | Valeur |
|---|---|
| Délai d'un résultat SAM (17 résultats appliqués) | médiane 2,7 s, minimum 1,8 s, maximum 4,0 s |
| Images envoyées jusqu'à la clôture | 37 (3 pour le diagnostic) |
| Abandonnées (déjà 3 en cours) | 10 |
| Périmées (plus de 5 s) | 6 |
| Arrivée dans le désordre | 1 |
| Coût estimé de la journée au moment de la clôture (journal local) | 0,125 $ |

## Constats et décisions

1. **Trop d'images perdues avec 3 en cours** : à 1 image/s et 2,7 s de délai médian, il y a en moyenne
   2,7 images en cours. Limite portée à 5 (`PERC-D7`). L'étape 1 aurait dû être validée dans les premières
   secondes ; elle l'a été à 14 s.
2. **Coût par session à 0 $** dans le journal : les appels n'étaient pas rattachés à la session, donc la limite
   de 1,50 $ par session (`SRV-R8.2`) ne pouvait pas jouer. Corrigé (`SessionCosts`, test
   `test_costs_are_attributed_to_the_session`).
3. Le délai médian est plus long que le 30 oct. (1,9 s, `eval/day1`) : à remesurer après la correction 1.
4. Reste à faire : comparer le coût de la journée avec la page Usage de la console Meta (`SRV-R8.5`).

# Sonde Muse Voice Transcribe (VOX-T1)

1er nov. 2026. `probe/transcribe_probe.py`, enregistrement de l'auteur au téléphone (21,2 s, 6 phrases séparées
par des silences), converti en PCM16 mono 24 kHz. Voie temps réel : WebSocket, mode `ENDPOINTING`,
`languageBias: ["French"]`, trames de 80 ms au rythme réel. Résultats : `eval/day3/transcribe_probe.json`.

| Phrase dite | Transcription (`speechComplete`) | Commande détectée | Délai après la fin de phrase |
|---|---|---|---|
| c'est fait | « c'est fait. » | `done` | 0,61 s |
| aide-moi | « aidemoi. » | aucune → **`help` après correction** | 0,69 s |
| je n'ai pas fini | « je n'ai pas fini. » | aucune (négation, `VOX-R2.6`) | 0,64 s |
| répète | « répète. » | `repeat` | 0,64 s |
| c'est quoi ce bruit | « c'est quoi ce bruit? » | aucune | 0,64 s |
| c'est bon | « c'est bon. » | `done` | 0,65 s |

- Délai médian 0,64 s, maximum 0,69 s : bien sous la cible de 2 s (`VOX-R1.4`).
- Transcribe colle « aide-moi » en « aidemoi » : forme ajoutée à `COMMANDS` et à `VOX-R2.1`, test
  `test_real_transcriptions_from_probe` (les 6 transcriptions réelles donnent la bonne commande).
- Voie fichier (`POST /v1/asr/transcribe`) : « 400 Malformed request » avec tous les réglages du temps réel ;
  requête réduite au strict nécessaire dans la sonde, à réessayer. Sans conséquence : FixLoop n'utilise que le
  temps réel.
- Coût estimé : 0,002 $ pour les deux voies.
