# Spécification de FixLoop

Développement piloté par la spécification (SDD), sur le modèle de Kiro : pour chaque partie du produit,
trois documents écrits **avant** le code, dans cet ordre.

1. `requirements.md` — **quoi** et **pourquoi** : récits utilisateur et critères d'acceptation testables (EARS).
2. `design.md` — **comment** : architecture, interfaces, modèles de données, erreurs, performances, tests.
3. `tasks.md` — **dans quel ordre** : tâches atomiques, chacune reliée aux exigences qu'elle satisfait.

Les documents de cadrage (`steering/`) valent pour toutes les parties : vision produit et règles du hackathon,
choix techniques, structure du dépôt. Un agent de code (Muse Code) lit `AGENTS.md`, puis le cadrage, puis la
partie sur laquelle il travaille.

## Sommaire

| Dossier | Partie | État au 30 oct. |
|---|---|---|
| `steering/product.md` | Vision, positionnement, règles du hackathon, grille de notation | cadrage |
| `steering/tech.md` | Modèles Meta, budgets mesurés, contraintes techniques | cadrage |
| `steering/structure.md` | Organisation du dépôt, conventions de code, de test et de commit | cadrage |
| `01-core-loop/` | Fiches de réparation, géométrie, vérificateur, machine à états | construit, à compléter |
| `02-perception/` | Client SAM 3.1 : mode image (direct) et mode vidéo (replay) | mesuré, à extraire en module |
| `03-agent-spark/` | Muse Spark : diagnostic, arbitrage sans validation, explication | construit, mesuré |
| `04-memory-voice/` | Muse Wonder (historique du vélo) et Muse Voice Transcribe (commandes vocales) | à faire |
| `05-session-server/` | Serveur FastAPI, protocole WebSocket, orchestration d'une session | à faire |
| `06-phone-app/` | Appli web mobile : caméra, surimpression, voix, écrans | à faire |
| `07-replay-mode/` | Démo publique sans clé API pour les juges | à faire |
| `08-evaluation/` | Jeu de 20 extraits, benchmark de 3 approches, rapport chiffré | à faire |
| `09-submission/` | README, vidéo de 3 min, conformité au règlement, dépôt du projet | à faire |
| `procedure_schema.json` | Schéma JSON d'une fiche (utilisé par le code) | en vigueur |

Ordre de construction et dépendances : voir `steering/product.md`, section « Planning ».

## Conventions

### Identifiants

- Exigence : `<PRÉFIXE>-R<n>`, critère : `<PRÉFIXE>-R<n>.<m>`. Préfixes : `CORE`, `PERC`, `AGT`, `MEM`, `VOX`,
  `SRV`, `APP`, `RPL`, `EVAL`, `SUB`. Exemple : `SRV-R3.2`.
- Décision de conception : `<PRÉFIXE>-D<n>`. Tâche : `<PRÉFIXE>-T<n>`.
- Chaque tâche cite les critères qu'elle satisfait (`Exigences : SRV-R3.1, SRV-R3.2`). Chaque critère est couvert
  par au moins une tâche ; un critère non couvert est un trou de la spec.

### Critères d'acceptation au format EARS (en français)

| Forme | Usage |
|---|---|
| `Le système DOIT …` | exigence permanente |
| `QUAND <événement>, le système DOIT …` | réaction à un événement |
| `PENDANT QUE <état>, le système DOIT …` | comportement dans un état |
| `SI <condition indésirable>, ALORS le système DOIT …` | erreur, cas limite |
| `OÙ <option activée>, le système DOIT …` | fonction optionnelle |

Un critère est **testable** : il nomme une valeur, un délai, un message ou un état observable. « Rapide »,
« robuste » ou « intuitif » sans chiffre ne sont pas des critères.

### Priorités (MoSCoW)

- **Must** : sans elle, pas de soumission valable ou pas de démo. Jamais coupée.
- **Should** : attendue par le jury, coupée seulement en cas de retard (ordre de coupe : `steering/product.md`).
- **Could** : bonus si le temps le permet.
- **Won't** : explicitement hors périmètre pour ce hackathon (écrit pour éviter les dérives).

### Statut des tâches

`[x]` fait et vérifié (preuve citée), `[ ]` à faire, `[~]` commencé. Une tâche n'est cochée que si sa condition
« Fait quand » est vraie et que `python -m pytest -q tests` passe.

### Chiffres

Tout chiffre de performance vient de `eval/` (mesuré sur le vélo de l'auteur) et cite sa source. Un objectif non
encore mesuré est écrit comme tel (« cible »), jamais comme un résultat.

### Contrôle automatique

`python scripts/check_spec.py` vérifie que chaque critère est couvert par une tâche (tableaux « Couverture » des
`tasks.md`) et que chaque identifiant cité existe. À lancer avant chaque commit qui touche `spec/`.

### Changer la spec

Si l'implémentation révèle une erreur de la spec (comme l'inversion du contact le 29 oct.), on corrige **d'abord**
la spec et on note la raison dans la section « Journal des décisions » du `design.md` concerné, puis le code.
