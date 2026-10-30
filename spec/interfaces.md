# Spec 3 — Interfaces entre modules

Statut : brouillon du 28 oct. Chaque module se teste seul, avec des entrées enregistrées (pas d'appel API dans les tests unitaires).

## Modules

| Module | Fichier | Responsabilité |
|---|---|---|
| Perception | `fixloop/perception.py` | Appelle `sam-3.1`, renvoie des masques plein cadre par pièce et par image |
| Géométrie | `fixloop/geometry.py` | Calcule les mesures (détection, taux de contact) à partir des masques |
| Vérificateur | `fixloop/verifier.py` | Applique les règles d'une étape sur une fenêtre de mesures, renvoie `V` |
| Machine à états | `fixloop/state_machine.py` | Enchaîne les états de la spec 1, journalise chaque transition |
| Agent | `fixloop/agent.py` | Muse Spark avec outils : diagnostic, arbitrage, explication d'anomalie |
| Mémoire | `fixloop/memory.py` | Muse Wonder : lit l'historique en début de session, écrit le rapport à la fin |
| Voix | `fixloop/voice.py` | Muse Voice Transcribe en temps réel, détecte « c'est fait » / « aide-moi » |
| Serveur | `server/app.py` | FastAPI + WebSocket entre le téléphone et les modules |
| Client | `web/` | Caméra, surimpression des masques, synthèse vocale du navigateur |

## Types partagés

```python
@dataclass
class FrameMasks:
    frame_index: int
    t: float                       # secondes depuis le début de la session
    masks: dict[str, np.ndarray]   # clé de pièce -> masque booléen plein cadre (H, W)
    confidence: dict[str, float]   # clé de pièce -> meilleure confiance SAM

@dataclass
class Measures:
    frame_index: int
    detected: dict[str, bool]
    contact: dict[tuple[str, str], float]   # (a, b) -> taux de contact, NaN si une pièce manque

@dataclass
class Verdict:
    value: Literal["0", "1", "?", "eps"]
    rule: dict | None              # règle qui a décidé
    evidence: dict                 # mesures utilisées (chiffres affichés dans la démo)
    message: str | None            # explication si anomalie
```

## Fonctions

| Fonction | Entrée | Sortie |
|---|---|---|
| `perception.segment_clip(path, parts)` | vidéo locale, `{clé: prompt}` | `list[FrameMasks]` |
| `geometry.measure(frame_masks, procedure)` | `FrameMasks`, fiche | `Measures` |
| `verifier.verify(step, window, user_done)` | étape, `N` dernières `Measures`, booléen | `Verdict` |
| `agent.diagnose(images, procedures)` | 1–3 images, fiches disponibles | id de fiche + justification |
| `agent.arbitrate(step, keyframes, measures)` | étape, 2–3 images, mesures | `Verdict` (`1` ou `eps`) |
| `agent.explain(step, verdict, keyframes)` | étape, anomalie, images | phrase courte à lire + pièce à surligner |
| `memory.load(bike_id)` / `memory.save(bike_id, report)` | id du vélo | texte d'historique / rien |

Outils exposés à Muse Spark (tool calling) : `get_measures`, `get_keyframes`, `highlight(part, color)`,
`speak(text)`, `set_verdict(value, reason)`.

## Messages WebSocket

| Sens | Type | Contenu |
|---|---|---|
| client → serveur | `frame` | image JPEG base64, horodatage |
| client → serveur | `audio` | morceau audio pour Transcribe |
| serveur → client | `overlay` | contours des pièces (chemins SVG), couleur par pièce |
| serveur → client | `say` | texte à lire avec la synthèse vocale du navigateur |
| serveur → client | `state` | état courant, étape `k / K`, dernières mesures |

## Décision : direct en mode image, replay en mode vidéo (30 oct.)

Mesuré dans `eval/day1/findings.md` : verdict par image en 1,9 s (médiane), 4,4 s au 90e centile, 10 états corrects sur 10.

1. **Direct** : 1 image par seconde, 1 requête `sam-3.1` par pièce et par image, requêtes qui se chevauchent ;
   anti-rebond de 3 images en direct (4 en replay).
2. **Replay** (juges) : vidéo segmentée une seule fois en morceaux de 10 s, résultat mis en cache.
3. Coût : vérifier sur la page Usage après une session de démo avant de multiplier les essais en direct.
