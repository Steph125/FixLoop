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

## Question ouverte : temps réel ou par extraits

SAM 3.1 sur l'API fonctionne par requête, un concept par requête. Deux options, à trancher avec la latence
mesurée par la sonde :

1. **Images une à une** : 1 requête par pièce et par image, à 1–2 images/s. Simple, mais 3 à 6 requêtes par seconde.
2. **Extraits courts** : le client envoie des extraits de 3–5 s, segmentés en vidéo (suivi d'objets inclus).
   Moins de requêtes, mais 3–5 s de retard sur le verdict. Facturation minimale de 50 images par requête.

Le **mode replay** (vidéos pré-enregistrées pour les juges) segmente chaque vidéo une seule fois et met le résultat en cache.
Vérifier les tarifs exacts sur la page Pricing avant de choisir.
