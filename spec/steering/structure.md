# Cadrage : structure et conventions

## 1. Arborescence cible (au rendu)

```
fixloop/
├── AGENTS.md                  # règles pour les agents de code (Muse Code)
├── README.md                  # présentation pour le jury (09-submission)
├── LICENSE, NOTICE.md         # MIT ; composants tiers et licences
├── requirements.txt
├── .env.example               # MODEL_API_KEY=… (jamais .env)
├── spec/                      # cette spécification
├── fixloop/                   # bibliothèque : logique pure + clients des modèles
│   ├── models.py              # FrameMasks, Measures, Verdict
│   ├── procedures.py          # chargement et validation des fiches
│   ├── geometry.py            # détection, taux de contact
│   ├── verifier.py            # verdict d'une étape
│   ├── state_machine.py       # machine à états (logique pure, synchrone)
│   ├── perception.py          # client SAM 3.1 : image et vidéo (02-perception)
│   ├── agent.py               # Muse Spark (03-agent-spark)
│   ├── memory.py              # Muse Wonder + historique local (04-memory-voice)
│   ├── voice.py               # Muse Voice Transcribe, détection des commandes (04-memory-voice)
│   ├── costs.py               # journal des appels et des coûts estimés (05-session-server)
│   ├── cached_models.py       # réponses des modèles en cache, pour replay et benchmark (07, 08)
│   └── sim.py                 # scène synthétique pour les tests
├── server/                    # 05-session-server
│   ├── app.py                 # FastAPI : routes HTTP, WebSocket, fichiers statiques
│   ├── session.py             # orchestration asynchrone d'une session
│   └── protocol.py            # messages WebSocket (validation)
├── web/                       # 06-phone-app et 07-replay-mode (statique)
│   ├── index.html, live.js    # appli en direct
│   ├── audio-worklet.js       # micro → PCM16 16 kHz
│   ├── replay.html, replay.js # lecteur de replay
│   ├── selftest.html          # auto-tests dans le navigateur
│   └── style.css
├── replay/                    # 07-replay-mode
│   ├── build_replay.py, deploy_check.py
│   ├── sessions/*.json        # description des sessions (commité)
│   ├── cache/*.models.json    # réponses réelles des modèles (commité, sans image)
│   └── build/                 # sortie déployée (ignorée par git)
├── docs/muse-code-log.md      # journal d'usage de Muse Code (09-submission)
├── procedures/                # fiches de réparation (JSON, écrites à la main)
├── probe/                     # scripts de mesure SAM, Wonder, Transcribe (conservés comme preuves)
├── scripts/                   # check_setup, check_spec, simulate_session, try_agent, ws_client, seed_history, benchmark
├── eval/                      # mesures et rapports (day1, day2, benchmark)
├── tests/                     # pytest, faux clients
└── data/                      # vidéos brutes, historiques locaux (ignoré par git)
```

## 2. Dépendances entre couches

`fixloop/` ne dépend ni de `server/` ni de `web/`. La logique (`geometry`, `verifier`, `state_machine`) ne fait
**aucun appel réseau** : les modèles sont injectés par interfaces (`Agent`, `Memory`, `Output`, `Perception`).
`server/` assemble les pièces. `web/` ne parle qu'au serveur (jamais directement à l'API Meta).

## 3. Conventions de code

- Python : annotations de type, docstrings courtes en français, noms en anglais. Fonctions pures quand c'est
  possible. Pas de variable globale mutable hors configuration.
- Configuration : constantes en tête de module, surchargées par variables d'environnement `FIXLOOP_*` quand utile.
- Textes lus ou affichés à l'utilisateur : français, deuxième personne, moins de 20 mots.
- JavaScript : modules ES, pas de dépendance externe sauf nécessité argumentée dans la spec.
- Erreurs réseau : jamais d'exception non rattrapée qui interrompt une session ; journaliser et dégrader.

## 4. Tests

- `python -m pytest -q tests` doit passer avant chaque commit.
- Aucun test n'appelle l'API : faux clients (`tests/fakes.py`, `FakeClient` de `test_agent.py`).
- Chaque critère d'acceptation « Must » a au moins un test automatique ou une preuve dans `eval/` citée par sa tâche.
- Les scénarios de bout en bout utilisent `fixloop/sim.py` ou des sorties SAM enregistrées (`raw_*.txt`).

## 5. Git

- Branche unique `main`. Un commit par tâche terminée, message en anglais au format
  `type(scope): résumé` (`feat`, `fix`, `test`, `docs`, `chore`), avec l'identifiant de tâche :
  `feat(server): websocket session loop [SRV-T4]`.
- Code produit avec Muse Code : mention `(Muse Code)` dans le message et prompt consigné dans
  `docs/muse-code-log.md`.
- `git push` après chaque commit (preuve de date, sauvegarde).
