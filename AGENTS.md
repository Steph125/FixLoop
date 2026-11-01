# FixLoop — instructions pour les agents de code (Muse Code)

FixLoop est un agent de réparation vélo qui vérifie ce que tu fais, construit pour le Meta Global AI Developer
Hackathon (rendu le 4 nov. 2026, 21 h ET). SAM 3.1 segmente les pièces, une machine à états vérifie chaque étape
par la géométrie des masques, Muse Spark diagnostique et explique sans jamais valider, Muse Wonder garde
l'historique du vélo, Muse Voice Transcribe capte les commandes vocales.

## Sources de vérité, dans cet ordre

1. `spec/README.md` : méthode (exigences → conception → tâches), conventions d'identifiants, format EARS.
2. `spec/steering/` : produit et règles du hackathon (`product.md`), choix techniques (`tech.md`), structure du
   dépôt et conventions de code, de test, de commit (`structure.md`).
3. La partie sur laquelle tu travailles : `spec/0N-<partie>/requirements.md`, puis `design.md`, puis `tasks.md`.
4. `eval/` : les mesures réelles. Aucun chiffre dans le code, le README ou les commentaires qui n'en vient pas.

Si le code et la spec divergent, **arrête-toi et signale-le** : la spec se corrige d'abord (journal des décisions
du `design.md` concerné), le code ensuite.

## Comment prendre une tâche

1. Choisis la première tâche `[ ]` de `tasks.md` dont les dépendances (« Dépend de ») sont faites.
2. Lis les critères qu'elle cite (`Exigences : …`) dans `requirements.md` et la section correspondante de
   `design.md`.
3. Écris d'abord les tests qui vérifient ces critères, puis le code.
4. Lance `python -m pytest -q tests` et `python scripts/check_spec.py` : les deux doivent passer.
5. Coche la tâche (`[x]`) avec sa preuve (nom du test ou fichier de `eval/`) seulement si « Fait quand » est vrai.
6. Commit : `type(scope): résumé [ID-T] (Muse Code)`, par exemple `feat(server): websocket session loop [SRV-T5]
   (Muse Code)`, et une ligne dans `docs/muse-code-log.md` (date, prompt, fichiers, corrections à la main).
7. Termine par : fichiers modifiés, commandes lancées et leur résultat, ce qui reste à faire.

Montre ton plan avant de modifier plus de 3 fichiers. Une tâche à la fois.

## Règles du projet (ne pas enfreindre)

1. **Muse Spark ne valide jamais une étape** (`AGT-R2`). Une réussite vient uniquement de la mesure SAM.
2. Sur la fiche `chain_off_chainring`, le contact est **inversé** : faible (≤ 0,18) = chaîne en place,
   élevé (≥ 0,26) = chaîne tombée. Pour le plateau, garder le plus gros objet (`select: largest`).
3. La logique (`geometry`, `verifier`, `state_machine`) reste pure, synchrone et sans réseau (`CORE-D1`).
4. Modèles Meta, identifiants exacts : `sam-3.1`, `muse-spark-1.3`, `muse-wonder-1.0`, `muse-voice-transcribe-1.0`.
   URL `https://api.meta.ai/v1`, clé dans la variable `MODEL_API_KEY` lue depuis `.env`, côté serveur uniquement.
5. Ne jamais lire, afficher, commiter ni copier le contenu de `.env`. Ne jamais ajouter `data/`, `probe_out*/`,
   `latency_out/`, `replay/build/` ni de vidéos au dépôt.
6. Aucun contenu tiers sans licence (pas de guides iFixit copiés). Les fiches de `procedures/` sont écrites à la main.
7. Textes destinés à l'utilisateur : en français, moins de 20 mots, deuxième personne. Code, noms et commits : en
   anglais.
8. Les appels réseau échouent parfois : relance, cache, et jamais de blocage de la session sur une erreur réseau.
9. Aucun test n'appelle l'API : faux clients (`tests/fakes.py`, `FakeClient`, `FakeSamClient`).
   Un test ne s'ignore (`pytest.skip`) que sur une cause précise et nommée (par exemple `PermissionError`
   WinError 10013), jamais sur `except OSError` ou `except Exception` : `TimeoutError` est une `OSError`, et un
   vrai échec deviendrait « ignoré » (constaté le 1er nov.).
10. Aucun appel payant (SAM, Spark, Wonder, Transcribe) sans afficher d'abord une estimation du coût.

## Environnement

- Windows, PowerShell 5.1 : **pas de `&&`**, une commande par ligne. Python 3.12 dans `.venv`.
- Dépendances : `requirements.txt`. N'ajoute une dépendance que si la spec en a besoin, et dis-le.

## Carte du code (état au 30 oct.)

| Chemin | Rôle | Spec |
|---|---|---|
| `fixloop/models.py` | Types partagés (`FrameMasks`, `Measures`, `Verdict`) | `01-core-loop` |
| `fixloop/procedures.py` | Chargement et validation des fiches (`spec/procedure_schema.json`) | `01-core-loop` |
| `fixloop/geometry.py` | Détection et taux de contact entre masques | `01-core-loop` |
| `fixloop/verifier.py` | Verdict d'une étape (0, 1, ?, eps) avec anti-rebond | `01-core-loop` |
| `fixloop/state_machine.py` | Machine à états d'une session | `01-core-loop` |
| `fixloop/agent.py` | Muse Spark : diagnostic, arbitrage (sans jamais valider), explication | `03-agent-spark` |
| `fixloop/sim.py` | Scène synthétique pour les tests | `01-core-loop` |
| `probe/` | Scripts de mesure SAM (mode vidéo par morceaux, mode image), preuves datées | `02-perception` |
| `scripts/` | Vérification de l'environnement, simulation, essai réel de Spark, contrôle de la spec | — |
| À créer | `perception.py`, `memory.py`, `voice.py`, `costs.py`, `cached_models.py`, `server/`, `web/`, `replay/` | `02` à `07` |
