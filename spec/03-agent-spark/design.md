# 03 — Agent Muse Spark : conception

Couvre `AGT-R1` à `AGT-R8`. Fichier : `fixloop/agent.py` (classe `SparkAgent`, protocole `Agent` de
`01-core-loop`). Script de mesure : `scripts/try_agent.py`.

## 1. Rôle de chaque appel

| Appel | Quand | Entrées | Sortie | Effort | Peut valider ? |
|---|---|---|---|---|---|
| `diagnose` | `DEMARRAGE` | 1–3 images entières, historique, catalogue | id de fiche, raison | `low` | — |
| `arbitrate` | `V = ?`, au plus 1 fois / 10 s | 2–3 gros plans, consigne, `visual_cues`, `notes`, 4 mesures | `Verdict("eps")` ou `Verdict("0")` | `medium` | **non** |
| `explain` | `V = ε` | gros plans, consigne, message, mesures | phrase, pièce | `low` | non |
| `help` | « aide-moi » | gros plans, consigne, `visual_cues` | phrase | `low` | non |

## 2. Appel commun

```python
r = client.responses.create(
    model="muse-spark-1.3",
    reasoning={"effort": EFFORT[kind]},            # "low" | "medium"
    instructions=SYSTEM,                           # rôle, JSON seul, français, < 20 mots, 2e personne
    input=[{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": "data:image/jpeg;base64,…"},   # 0 à 3
    ]}],
    timeout=20,
)
data = extract_json(r.output_text)                 # None si illisible
```

Le client est synchrone aujourd'hui ; le serveur l'appelle dans un fil (`asyncio.to_thread`) pour ne pas bloquer
la boucle (`SRV-D3`). Jetons : lus dans `r.usage` s'il existe (`input_tokens`, `output_tokens`).

## 3. Prompts (texte exact, à garder synchronisé avec le code)

**Système** : « Tu es FixLoop, un mécanicien vélo qui guide un débutant à la voix. Tu regardes des images de la
transmission prises par son téléphone. Réponds uniquement avec un objet JSON valide, sans texte autour. Les phrases
destinées à l'utilisateur sont en français, courtes (moins de 20 mots), à la deuxième personne. »

**Diagnostic** : historique, catalogue JSON, puis « Regarde les images et choisis la fiche qui correspond au
problème visible. Réponds : {"procedure": "<id>", "raison": "<ce que tu vois, une phrase>"} ».

**Arbitrage** : consigne ; `visual_cues` ou `GENERIC_CUES` ; « Comment lire les mesures automatiques : <notes> » ;
dernières mesures JSON ; « Les images sont des gros plans du plateau. L'étape est-elle réussie ? Si tu ne vois pas
clairement la chaîne et le plateau, réponds impossible_a_dire. » ; format JSON de `AGT-R3.4`.

**Explication** : consigne ; problème détecté ; mesures ; « dis à l'utilisateur, en une phrase, ce qui ne va pas
et quoi faire. Indique la pièce à surligner parmi <parts>. » ; `{"phrase", "piece"}`.

**Aide** (à écrire) : consigne ; `visual_cues` ; « Donne une seule indication concrète pour réussir cette étape,
moins de 25 mots. » ; `{"phrase"}`.

## 4. Décision de l'arbitrage (table de vérité)

| `verdict` rendu | `confiance` | Résultat | Message | Preuve ajoutée |
|---|---|---|---|---|
| `ratee` | ≥ 0,6 | `eps` | `raison` | `source`, `confiance`, `verdict_brut` |
| `ratee` | < 0,6 | `0` | `conseil` ou défaut | idem |
| `reussie` | toute | `0` | `conseil` ou défaut | idem + `ignore` |
| `impossible_a_dire` | toute | `0` | `conseil` ou défaut | idem |
| absent, illisible, erreur | — | `0` | défaut | `source`, `confiance: 0` |

Message par défaut (dans la session) : « Je ne vois pas bien. Montre-moi le plateau de face, mains hors du champ. »

## 5. Images envoyées

- Diagnostic : images entières réduites à 768 px de large au plus.
- Arbitrage, explication, aide : gros plan `crop_around(img, box_plateau, margin=0.6)` ; la boîte vient de la
  perception (`PartResult.box`, `PERC-R6.3`) ; sans boîte, image entière.
- Jamais d'agrandissement : la vidéo de test fait 848×464, agrandir n'ajoute aucun détail (`eval/day2`).
- Les images ne contiennent ni visage ni document : l'appli demande de cadrer la transmission (`APP-R3`).

## 6. Garde-fous de sortie

- Phrase > 20 mots : on garde la première phrase si elle fait ≤ 20 mots, sinon le message de la règle.
- Pièce hors `parts` : `None`.
- Toute exception dans `_ask` : journalisée (`error`), `None` rendu.
- Délai de 20 s dépassé : traité comme une erreur.

## 7. Tests (`tests/test_agent.py`, `FakeClient`)

| Test | Critères |
|---|---|
| `test_extract_json_tolerates_fences_and_text` | R6.3 |
| `test_diagnose_picks_known_procedure_and_sends_images` | R1.1, R1.2 |
| `test_diagnose_falls_back_on_unknown_id` | R1.3 |
| `test_arbitrate_never_validates_but_confirms_failures` | R2.1–R2.3 |
| `test_unsure_answer_returns_filming_advice` | R2.4 |
| `test_network_error_never_blocks` | R6.1 |
| `test_explain_returns_phrase_and_valid_part` | R4.2, R4.3 |
| `test_small_crop_is_not_upscaled` | R6.4 |
| `test_reasoning_effort_is_sent` | R1.1, R3.3 |
| `test_crop_around_box` | R3.2 |
| À écrire : confiance 0,59 → `0` ; phrase trop longue ; délai ; `help` ; raison du diagnostic ; jetons journalisés | R2.4, R4.5, R6.2, R5, R1.4, R7.1 |

## 8. Journal des décisions

- **AGT-D1 (30 oct.) — Spark ne valide jamais.** Mesure : essais 1 et 2, Spark juge « réussie » une chaîne tombée
  (0,82 à l'essai 2). Cause : disque noir de protection, la chaîne tombée posée sur son bord ressemble à une
  chaîne en place. Essai 3, avec les repères du disque : 2 verdicts justes sur 2, mais 2 cas ne suffisent pas.
  Décision : seule la mesure SAM valide ; Spark peut confirmer un échec ou conseiller.
- **AGT-D2 (30 oct.) — Repères visuels par vélo (`visual_cues`)** dans la fiche, plutôt qu'une description
  générique de la chaîne.
- **AGT-D3 (30 oct.) — Effort `low` pour diagnostic et explication, `medium` pour l'arbitrage.** Durées mesurées :
  2,7 à 8,3 s par appel (essai 3).
- **AGT-D4 (30 oct.) — Pas d'agrandissement** des gros plans.
- **AGT-D5 (30 oct.) — Réponses JSON plutôt qu'appel d'outils** (`CORE-D7`).
- **AGT-D6 (30 oct.) — Confiance minimale de 0,6** pour accepter un échec : en dessous, on préfère demander un
  meilleur cadrage qu'interrompre l'utilisateur à tort.
