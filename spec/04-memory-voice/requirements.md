# 04 — Mémoire (Muse Wonder) et voix (Muse Voice Transcribe) : exigences

Deux préfixes : `MEM` (historique du vélo) et `VOX` (commandes vocales). Les deux sont **Should** dans le
périmètre produit, mais leurs interfaces sont **Must** : la session (`01-core-loop`) en dépend, et chacune a un
repli qui marche sans le modèle (historique JSON relu tel quel, bouton « C'est fait »).

---

## MEM-R1 — Lire l'historique au démarrage (Should)

**Récit** : en tant que cycliste, je veux que FixLoop se souvienne de mes réparations précédentes, pour qu'il me
dise par exemple « c'est la 3e fois que ta chaîne tombe ce mois-ci ».

1. Le système DOIT conserver un historique par vélo dans `data/bikes/<bike_id>.json` (ignoré par git).
   SI ce fichier est illisible (JSON invalide), ALORS le système DOIT le renommer en `<bike_id>.corrupt-<date>.json`
   et repartir d'un historique vide, sans lever d'exception.
2. QUAND une session démarre, le système DOIT lire l'historique et demander à `muse-wonder-1.0` (mode Standard)
   une synthèse de moins de 60 mots : réparations passées, pannes répétées, conseil éventuel.
3. La synthèse DOIT être transmise au diagnostic (`AGT-R1.1`).
4. SI la synthèse mentionne une panne répétée (même fiche au moins 2 fois dans les 30 derniers jours), ALORS le
   système DOIT la dire à l'utilisateur en une phrase après le diagnostic.
5. SI l'historique est vide, ALORS le système NE DOIT PAS appeler Wonder et DOIT rendre « aucun ».
6. SI Wonder est injoignable, ALORS le système DOIT rendre les 5 dernières entrées de l'historique en texte brut.

## MEM-R2 — Écrire le rapport à la clôture (Should)

1. QUAND une session est clôturée, le système DOIT ajouter à l'historique une entrée : date ISO, fiche, succès,
   étapes validées, anomalies (message, étape, instant), durée, appels aux modèles.
2. Le système DOIT demander à Wonder une phrase de rapport (moins de 30 mots) stockée dans l'entrée (`summary`).
3. SI Wonder est injoignable, ALORS l'entrée DOIT être écrite sans `summary`.
4. L'écriture DOIT être atomique (fichier temporaire puis renommage) : un arrêt brutal ne corrompt pas l'historique.

## MEM-R3 — Confidentialité (Must)

1. L'historique NE DOIT contenir ni image, ni audio, ni transcription brute, ni donnée personnelle (nom, lieu).
2. `bike_id` DOIT être un identifiant opaque choisi par l'appli (`APP-R6`), jamais un nom.

## MEM-R4 — Démo de la mémoire (Should)

1. Le système DOIT fournir `scripts/seed_history.py` qui crée un historique de démonstration (2 chutes de chaîne
   les jours précédents), **marqué `demo: true`**, pour montrer la mémoire dans la vidéo.
2. La vidéo et le README DOIVENT dire que cet historique est préparé (`SUB-R2`).

---

## VOX-R1 — Transcription en temps réel (Should)

**Récit** : en tant qu'utilisateur aux mains pleines de graisse, je veux dire « c'est fait » au lieu de toucher
l'écran.

1. PENDANT QU'une session est active et que le micro est autorisé, le système DOIT transmettre l'audio du
   téléphone à `muse-voice-transcribe-1.0` par WebSocket (`wss://api.meta.ai/v1/asr/realtime`), **via le serveur**
   (la clé ne va jamais au navigateur).
2. Le format audio DOIT être celui exigé par la doc de Transcribe, vérifié par une sonde (`VOX-T1`) ; défaut
   prévu : PCM 16 bits, mono, 16 kHz, morceaux de 100 ms.
3. Le système DOIT utiliser les transcriptions finales (pas les partielles) pour détecter les commandes.
4. Le délai entre la fin de la phrase et la commande reçue par la session DOIT être ≤ 2 s (cible).

## VOX-R2 — Détection des commandes (Must pour l'interface, Should pour la voix)

1. Le système DOIT reconnaître, après normalisation (minuscules, sans accents, sans ponctuation) :

   | Commande | Formes reconnues |
   |---|---|
   | `done` | « c'est fait », « c est fait », « j'ai fini », « c'est fini », « j'ai terminé », « c'est bon » |
   | `help` | « aide-moi », « aide moi », « aide », « je n'y arrive pas », « au secours » |
   | `repeat` | « répète », « repete », « redis », « tu peux répéter », « pardon » |

2. Une transcription qui ne contient aucune de ces formes NE DOIT déclencher aucune commande.
3. Une même commande NE DOIT pas être déclenchée deux fois en moins de 2 s.
4. PENDANT QUE le téléphone parle (synthèse vocale) et 500 ms après, le système NE DOIT PAS déclencher de
   commande (éviter que FixLoop s'entende lui-même).
5. Le système DOIT journaliser chaque commande détectée avec la transcription normalisée (pas l'audio).
6. SI la forme reconnue est niée (« pas », « n' », « ne », « jamais » dans les 3 mots qui la précèdent, ou « pas »
   juste après : « je n'ai pas fini », « c'est pas fait », « ce n'est pas bon »), ALORS le système NE DOIT
   déclencher aucune commande. Trouvé à la relecture du 30 oct. : « je n'ai pas fini » déclenchait `done`.

## VOX-R3 — Repli sans voix (Must)

1. L'appli DOIT toujours afficher un gros bouton « C'est fait » (`APP-R4`), qui envoie `user_done`.
2. SI le micro est refusé, la connexion Transcribe échoue 3 fois ou le budget voix est atteint, ALORS le système
   DOIT continuer la session avec le bouton seul et afficher « Commande vocale indisponible ».

## VOX-R4 — Coût et durée (Must)

1. Le système DOIT couper le flux audio à la clôture de la session, après 10 min de session ou sur
   « Pause » de l'appli.
2. La durée audio transmise DOIT être journalisée dans les coûts (`SRV-R8`).
