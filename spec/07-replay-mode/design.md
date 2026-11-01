# 07 — Mode replay : conception

Couvre `RPL-R1` à `RPL-R8`. Fichiers : `replay/build_replay.py`, `replay/sessions/<nom>.json`,
`fixloop/cached_models.py`, `web/replay.html`, `web/replay.js`, sortie `replay/build/` (ignorée par git).

## 1. Chaîne de construction

```
replay/sessions/A.json  ──►  build_replay.py
  (vidéo, instants « c'est fait », images de diagnostic,
   bike_id de démo, source: video | recording)
        │
        ├─ source video : perception.segment_video (cache raw_*.txt, pièces de live_parts, 10 fps)
        ├─ source recording : data/recordings/<id>/ (images 1 fps + sorties SAM brutes)
        │
        ├─ pour chaque image : FrameMasks → geometry.measure → Session.on_measures (même code que le direct)
        │      user_done injecté aux instants du fichier de session
        │      Agent = CachedAgent(SparkAgent)   Memory = CachedMemory(WonderMemory)
        │
        └─► replay/build/<nom>/
               video.mp4       H.264, ≤ 960 px, faststart, son d'origine si présent
               overlays.json   contours par image (5 images/s), contact, label
               events.json     journal de la session (CORE-R8) + texte dit + modèle concerné
               meta.json       date de tournage, mode, anti-rebond, versions, modèles, coûts réels de construction
        └─► replay/build/index.json   liste des sessions
```

Fichier de session :

```json
{"name": "A", "title": "Erreur corrigée", "video": "data/velo3.mp4", "filmed": "2026-10-31",
 "source": "video", "debounce_frames": 4, "bike_id": "demo-velo", "demo_history": true,
 "diagnose_at": [0.5, 1.5, 2.5], "user_done": [12.0, 24.5, 33.0]}
```

`user_done` : instants où l'auteur a dit « c'est fait » pendant le tournage (lus sur la piste son, notés à la main
une fois). En `source: recording`, ils viennent du journal de la session en direct.

## 2. Cache des modèles (`fixloop/cached_models.py`)

```python
class CachedAgent:      # enveloppe un Agent ; clé = sha256(type d'appel + prompt + images JPEG)
    def __init__(self, inner: Agent | None, path: Path): ...   # inner=None : cache seul, erreur si absent
class CachedMemory:     # idem pour load/save
```

Fichier `replay/cache/<nom>.models.json` (commité : réponses brutes des modèles, sans image ni clé) :
`{clé: {"kind", "response", "obtained": "2026-10-31T…", "model": "muse-spark-1.3"}}`.

1re construction : `inner` réel, réponses enregistrées. Suivantes : `--offline`, `inner=None`. Comme les prompts et
images sont déterministes, les clés retombent identiques (`RPL-R2.3`) ; une clé manquante arrête la construction
avec un message (jamais de réponse inventée, `RPL-R2.4`).

## 3. Formats

`overlays.json` :

```json
{"fps": 5, "w": 848, "h": 464,
 "frames": [{"t": 0.0, "parts": {"chain": "M 412,233 L …Z", "chainring": "M …Z"},
             "contact": 0.344, "label": "tombée", "verdict": "0"}, …]}
```

Coordonnées entières, une image sur deux de la vidéo à 10 fps (5 fps suffisent à l'œil). Couleur non stockée :
recalculée depuis les événements `highlight`.

`events.json` : les entrées du journal (`CORE` design 7) plus `say` (texte dit), `highlight` (`parts`, `color`) et
`model` (`sam-3.1`, `muse-spark-1.3`, `muse-wonder-1.0`, `muse-voice-transcribe-1.0`, ou `null`). Les sorties
`Output` sont journalisées par une `RecordingOutput` pendant la construction.

## 4. Lecteur (`web/replay.html`, `web/replay.js`)

```
┌──────────────────────────────────────────────┐
│ bandeau honnêteté (RPL-R5)                   │
│ [A Erreur corrigée] [B Cas difficile]        │  sélecteur de session (index.json)
├──────────────────────────────────────────────┤
│ <video> + <svg> contours  │ Étape 2/3        │
│                           │ consigne         │
│  sous-titre               │ contact 0,31 ·   │
│                           │ tombée           │
├──────────────────────────────────────────────┤
│ courbe du contact (SVG), seuils, curseur     │
│ frise : ● diagnostic (Spark) ● étape ● fait  │
│         ● anomalie (SAM + Spark) ● validée   │
├──────────────────────────────────────────────┤
│ détail de l'événement : preuve, modèle, réponse brute, confiance │
└──────────────────────────────────────────────┘
```

- Synchronisation : `requestVideoFrameCallback` si disponible, sinon `timeupdate` + `requestAnimationFrame` ;
  image d'overlay = la plus proche de `video.currentTime` (recherche dichotomique).
- État affiché (étape, consigne, couleurs) = rejeu des événements jusqu'à `currentTime` (fonction pure
  `stateAt(events, t)`), pour qu'un saut dans la frise donne immédiatement le bon état.
- Son : `speechSynthesis` des `say` franchis pendant la lecture à ×1, désactivé par défaut.
- Courbe : SVG tracé une fois, curseur vertical déplacé.
- Seuils (Could) : curseurs qui recalculent les `label` de la courbe à partir de `contact` ; mention « simulation ».
- Aucune bibliothèque externe ; même `style.css` que l'appli.

## 5. Hébergement

| Moment | Hébergement | Raison |
|---|---|---|
| Dès le 2 nov. | GitHub Pages depuis le dépôt (public depuis le 31 oct.), dossier publié par une action ou une branche `gh-pages` contenant uniquement les fichiers de la liste ci-dessous | Gratuit, même compte, URL stable |
| Repli | Cloudflare Pages ou Netlify (téléversement direct du même dossier) | Si GitHub Pages pose problème |

Contenu déployé : `web/replay.html`, `web/replay.js`, `web/style.css`, `replay/build/**`. Script
`replay/deploy_check.py` : liste les fichiers, vérifie l'absence de `.env`, `.jsonl`, `MODEL_API_KEY`, la taille
par session (`RPL-R7.1`).

## 6. Tests

- `tests/test_replay.py` : construction de la session synthétique deux fois → `events.json` identiques ; clé de
  cache absente en `--offline` → erreur ; `overlays.json` sous 2 Mo pour 60 s ; `stateAt` (portage Python de
  référence) donne l'étape attendue à des instants choisis.
- `web/selftest.html` : `stateAt`, recherche de l'overlay le plus proche.
- Vérification manuelle `RPL-T9` : navigation privée sur ordinateur, téléphone en 4G, trois navigateurs.

## 7. Journal des décisions

- **RPL-D1 (30 oct.)** — Replay = vraie exécution du code sur une vraie vidéo, réponses des modèles en cache.
  Raison : le règlement demande de ne montrer que ce qui a été construit ; un replay « scripté à la main » serait
  une démo truquée.
- **RPL-D2 (30 oct., révisé le 1er nov.)** — Dépôt public depuis le 31 oct. : GitHub Pages, avec seulement les
  fichiers du replay publiés ; l'URL ne change plus après la soumission.
- **RPL-D3 (30 oct.)** — Mode vidéo (10 fps, anti-rebond 4) pour les sessions tournées exprès ; mode
  « enregistrement » (1 fps, anti-rebond 3) pour une session du direct. Le mode est affiché (`RPL-R5.2`).
- **RPL-D4 (30 oct.)** — Contours à 5 images/s pour tenir le poids de 2 Mo.
