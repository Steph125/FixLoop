# 04 — Mémoire et voix : conception

Couvre `MEM-R1` à `MEM-R4`, `VOX-R1` à `VOX-R4`. Fichiers : `fixloop/memory.py`, `fixloop/voice.py`,
`scripts/seed_history.py`, `probe/transcribe_probe.py`, tests.

## 1. Mémoire

### 1.1 Fichier d'historique `data/bikes/<bike_id>.json`

```json
{"bike_id": "b-7f3c", "created": "2026-10-31T10:12:00+01:00", "demo": false,
 "entries": [
   {"date": "2026-11-01T18:40:12+01:00", "procedure": "chain_off_chainring", "success": true,
    "duration_s": 142, "steps_validated": ["frame_view", "engage_top_teeth", "turn_backward"],
    "anomalies": [{"step": "engage_top_teeth", "t": 31.5, "message": "Tu as dit que c'était fait, mais…"}],
    "model_calls": {"spark": 3, "wonder": 2, "sam_images": 290},
    "summary": "Chaîne remise après une tentative sur le disque de protection ; test de rotation réussi."}
 ]}
```

`bike_id` : `^[a-z0-9-]{4,32}$`, sinon refus.

### 1.2 Classe `WonderMemory` (protocole `Memory`)

```python
class WonderMemory:
    def __init__(self, root: Path = Path("data/bikes"), client=None, model="muse-wonder-1.0"): ...
    def load(self, bike_id: str) -> str            # synthèse (< 60 mots), "aucun", ou texte brut de repli
    def save(self, bike_id: str, report: dict) -> None
    def repeated(self, bike_id: str, procedure: str, days: int = 30) -> int   # nb d'occurrences
    calls: list[dict]
```

- `load` : 0 entrée → `"aucun"` sans appel. Sinon appel Wonder (`responses.create`, mode Standard, sans
  paramètre de mode « profond »), prompt : « Voici l'historique de réparation d'un vélo (JSON). Résume en moins de
  60 mots, en français : réparations passées, pannes qui reviennent, un conseil s'il y a lieu. Réponds en texte
  simple. » + les 20 dernières entrées. Délai 20 s. Erreur → 5 dernières entrées sous la forme
  `"<date> : <title>, réussie|échouée"`.
- `save` : construit l'entrée depuis `report` (fourni par `Session._close`, enrichi : étapes validées, anomalies,
  durée) ; appel Wonder pour `summary` (« Résume cette réparation en une phrase de moins de 30 mots. ») ; écrit
  `<id>.json.tmp` puis `os.replace`.
- Phrase de panne répétée (`MEM-R1.4`) : calculée **localement** par `repeated()` (pas par Wonder), dite par la
  session après le diagnostic : « C'est la <n>e fois en un mois que ta chaîne tombe. On vérifiera son usure à la
  fin. » Wonder ne fait que la synthèse lisible.

Pourquoi Wonder et pas Spark pour la mémoire : Wonder a un contexte d'un million de jetons, pensé pour les longs
historiques ; ici l'historique est court, l'intérêt est de **montrer** l'usage d'un 4e modèle Meta à sa place
naturelle (tenue d'un dossier), avec un repli sans lui. Si Wonder ajoute plus de 5 s au démarrage, la synthèse est
lancée en parallèle du diagnostic et transmise au premier appel suivant (`MEM-D3`).

### 1.3 Historique de démonstration

`scripts/seed_history.py --bike demo-velo` : 2 entrées `chain_off_chainring` (J-6, J-2), `demo: true`. Le
README et la vidéo le signalent.

## 2. Voix

### 2.1 Chaîne audio

```
téléphone : getUserMedia(audio) → AudioWorklet (rééchantillonnage 24 kHz, PCM16 LE mono, trames de 80 ms)
         → WebSocket FixLoop, message binaire préfixé 0x01 (05-session-server)
serveur  : VoiceBridge ── WebSocket ──► wss://api.meta.ai/v1/asr/realtime (clé côté serveur)
         ◄── speechStart / transcript / speechEnd / speechComplete / error
         → CommandDetector (sur speechComplete) → Session.on_user_done() / on_command("help" | "repeat")
```

Protocole (doc Meta « Speech to text », lue le 1er nov. ; sonde `probe/transcribe_probe.py`, `VOX-T1`) :

1. Ouverture de `wss://api.meta.ai/v1/asr/realtime` ; l'en-tête HTTP `Authorization` est **ignoré** sur la
   WebSocket : la clé va dans la première trame texte, envoyée dans les 10 s :

   ```json
   {"authorization": {"accessToken": "Bearer <clé>"}, "model": "muse-voice-transcribe-1.0",
    "audioEncoding": "PCM_24KHZ", "mode": "ENDPOINTING", "partialMode": "CUMULATIVE",
    "emitAudioProgress": false, "languageBias": ["French"],
    "keywords": ["c'est fait", "aide-moi", "répète", "plateau", "chaîne"]}
   ```

2. Accusé de réception sans champ `type` : `{"sessionId": "…"}`. Aucun audio avant.
3. Audio : trames binaires PCM16 LE mono 24 kHz, 80 ms (3 840 octets), au rythme réel, jamais plus de 5 s en avance.
4. Événements serveur (JSON, champ `type`) : `speechStart` (`turnId`), `transcript` (`transcript`, `final`),
   `speechEnd` (`turnId`), `speechComplete` (`turnId`, `transcript`) — **c'est celui qu'on utilise**, `audioProgress`,
   `error` (`message`). Types inconnus ignorés.
5. Fin : `{"type": "endStream"}`, puis lecture jusqu'à la fermeture (code 1000). Refus de charge : code 1013.
6. Limites : session de 60 min au plus ; flux fermé par le serveur s'il ne reçoit plus d'audio sans `endStream`.

La sonde mesure aussi le délai `speechComplete` − fin de la phrase, et passe chaque transcription au
`CommandDetector`. Repli de test sans WebSocket : `POST https://api.meta.ai/v1/asr/transcribe` (fichier WAV,
en-tête `Authorization` classique, même tarif).

### 2.2 `fixloop/voice.py`

```python
COMMANDS = {
    "done":   ["c est fait", "j ai fini", "c est fini", "j ai termine", "c est termine", "c est bon"],
    "help":   ["aide moi", "aide", "je n y arrive pas", "au secours"],
    "repeat": ["repete", "repeter", "redis", "pardon"],
}

def normalize(text: str) -> str      # minuscules, NFD sans accents, apostrophes et ponctuation -> espace, espaces réduits

class CommandDetector:
    def __init__(self, cooldown_s=2.0, mute_tail_s=0.5): ...
    def speaking(self, on: bool, t: float) -> None     # signalé par l'appli (début / fin de synthèse)
    def feed(self, final_text: str, t: float) -> str | None   # "done" | "help" | "repeat" | None

class VoiceBridge:                    # une instance par session
    async def start(self) -> None
    async def push_audio(self, pcm16_24k: bytes) -> None   # trames de 80 ms
    async def stop(self) -> None
    on_final: Callable[[str, float], None]
    seconds_sent: float; failures: int
```

Règles de `feed` :
- correspondance par **mot entier** dans le texte normalisé (`" aide "` ne correspond pas à « aider ») ;
- si plusieurs commandes, priorité `done` > `help` > `repeat` ;
- **négation** (`VOX-R2.6`) : forme ignorée si l'un des 3 mots qui la précèdent est `pas`, `n`, `ne`, `jamais`,
  ou si le mot qui la suit est `pas` ; « fini » et « quoi » seuls sont retirés (trop de faux positifs :
  « c'est quoi ce bruit », « pas fini ») ;
- ignoré si `speaking` ou moins de `mute_tail_s` après la fin de la synthèse ;
- ignoré si la même commande a été rendue il y a moins de `cooldown_s`.

Attention à l'écho : la session dit « Tu as dit que c'était fait… » ; normalisé, cela donne « c etait fait », qui
ne correspond pas à « c est fait ». Le silence pendant la synthèse protège en plus des autres phrases.

### 2.3 Erreurs

| Cas | Comportement |
|---|---|
| Micro refusé | Appli : message « Commande vocale indisponible », bouton seul |
| Connexion Transcribe refusée ou coupée | 3 reconnexions (1 s, 2 s, 4 s), puis abandon de la voix pour la session |
| Session > 10 min | `stop()` |
| Budget voix atteint (`SRV-R8`) | `stop()`, message |

## 3. Tests

- `test_voice.py` : normalisation (accents, apostrophes), chaque forme de chaque commande, mot entier, priorité,
  anti-répétition, silence pendant la synthèse, phrase d'écho « Tu as dit que c'était fait » → `None`.
- `test_memory.py` : historique vide sans appel ; repli texte brut sur erreur ; écriture atomique ; `repeated` ;
  `bike_id` invalide refusé ; aucune clé `image`, `audio`, `transcript` dans le fichier.
- `VoiceBridge` : testé avec un faux serveur WebSocket local (`websockets.serve`) qui renvoie une transcription
  finale.

## 4. Journal des décisions

- **MEM-D1 (30 oct.)** — Historique en JSON local, Wonder pour la synthèse et le rapport seulement. Raison :
  l'historique doit survivre sans le modèle (preview) et sans compte utilisateur.
- **MEM-D2 (30 oct.)** — Calcul des pannes répétées en local, pas par le modèle : chiffre exact, testable.
- **MEM-D3 (30 oct., conditionnel)** — Si Wonder ajoute plus de 5 s au démarrage, sa synthèse est calculée en
  parallèle du diagnostic ; Spark diagnostique alors sans historique et la phrase de panne répétée (locale) reste.
- **VOX-D1 (30 oct.)** — Audio relayé par le serveur : la clé API ne quitte jamais le serveur (`steering/tech.md`
  section 6).
- **VOX-D2 (30 oct.)** — Bouton « C'est fait » toujours visible : la voix est un confort, pas une dépendance.
- **VOX-D4 (1er nov.)** — Mode `ENDPOINTING` et 24 kHz, d'après la doc : `PUSH_TO_TALK` exigerait un bouton,
  `DIARIZATION` n'est pas réglé pour la faible latence ; 24 kHz évite un rééchantillonnage côté Meta.
- **VOX-D3 (30 oct.)** — Synthèse vocale par le navigateur (`speechSynthesis`) : Transcribe ne fait que la
  reconnaissance (`steering/tech.md`).
