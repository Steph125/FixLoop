# 05 — Serveur de session : conception

Couvre `SRV-R1` à `SRV-R10`. Fichiers : `server/app.py`, `server/session.py`, `server/protocol.py`,
`fixloop/costs.py`, `scripts/ws_client.py`, `tests/test_server.py`.

## 1. Architecture d'une session

```
WebSocket ─► receive_loop ──JSON──► control (hello, start, user_done, command, speaking, pause, stop)
                │
                ├─binaire 0x02─► LivePerception.try_submit ──(≤3 en cours)──► SAM 3.1 (x2 pièces, parallèle)
                │                                                        │
                │                                   résultat ◄───────────┘
                │                       filtre (> 5 s ou désordre) ──► measure() ──► send overlay
                │                                                        │
                │                                          pending (dernière mesure seulement)
                │                                                        ▼
                │                               sm_worker : await to_thread(Session.on_measures, m, keyframe)
                │                                 │  (Spark, Wonder appelés depuis ce fil)
                │                                 └─ QueueOutput.say/highlight/state ─► out_queue (thread-safe)
                │                                                                          │
                └─binaire 0x01─► VoiceBridge ─► Transcribe ─► CommandDetector ─► sm_worker │
                                                                                           ▼
                                                                         send_loop ─► WebSocket
```

Une instance `LiveSession` (`server/session.py`) par connexion ; tâches asyncio : `receive_loop`, `send_loop`,
`sm_worker`, tâches de perception, `VoiceBridge`. Annulées ensemble à la fermeture (`SRV-R7.4`).

## 2. Composants

```python
class QueueOutput:                         # implémente Output (01-core-loop)
    def __init__(self, loop, queue): ...
    def say(self, text): self._put({"type": "say", "text": text})
    def highlight(self, parts, color): self._put({"type": "highlight", "parts": parts, "color": color})
    def state(self, snapshot): self._put({"type": "state", **snapshot})
    def _put(self, msg): self.loop.call_soon_threadsafe(self.queue.put_nowait, msg)

class LiveSession:
    def __init__(self, ws, procedures, models: Models, costs: CostLog, limits: Limits): ...
    async def run(self) -> None
    # état interne : session_id, t0_client_ms, startup_frames, last_applied_frame, pending, counters
```

`Models` regroupe `LivePerception`, `SparkAgent`, `WonderMemory`, `VoiceBridge` ; `FIXLOOP_FAKE_MODELS=1` les
remplace par des faux (perception rejouée depuis `raw_*.txt` ou la scène synthétique), pour `SRV-R10.2`.

File de la machine à états : `sm_queue` d'éléments `("measure", m, kf)`, `("done",)`, `("command", c)`.
`sm_worker` les consomme un par un. Pour les mesures, `pending` remplace l'élément mesure non encore consommé
(`SRV-R5.3`) ; `done` et `command` ne sont jamais écartés.

## 3. Protocole WebSocket `/ws/session`

### 3.1 Client → serveur (JSON)

| `type` | Champs | Effet |
|---|---|---|
| `hello` | `bike_id`, `access_code`, `client` (`{ua, w, h}`) | ouverture, contrôle d'accès |
| `start` | — | démarrage : les 3 images suivantes servent au diagnostic |
| `user_done` | `t_ms` | « c'est fait » (bouton) |
| `command` | `cmd` (`repeat` / `help`), `t_ms` | bouton d'aide ou de répétition |
| `speaking` | `on` (bool), `t_ms` | synthèse vocale en cours (pour `VOX-R2.4`) |
| `pause` / `resume` | — | suspend images et audio |
| `stop` | — | clôture demandée (rapport avec `success: false`) |

### 3.2 Client → serveur (binaire)

```
octet 0     : 0x01 audio PCM16 mono 16 kHz | 0x02 image JPEG
octets 1–8  : horodatage client, ms, uint64 gros-boutiste
octets 9–   : données (JPEG ≤ 200 ko ; audio 100 ms = 3 200 octets)
```

### 3.3 Serveur → client (JSON)

| `type` | Champs |
|---|---|
| `hello_ack` | `session_id`, `limits` (`{max_minutes, max_cost_usd, fps: 1}`), `procedures` |
| `state` | instantané `CORE` (`design.md` 6.5 de 01) |
| `say` | `text` |
| `highlight` | `parts`, `color` (`blue` / `red` / `green`) |
| `overlay` | `frame_index`, `t_ms`, `w`, `h`, `parts: {pièce: {path, color}}`, `contact`, `label` (`en place` / `tombée` / `incertain` / `non vu`, d'après les seuils de l'étape), `verdict`, `latency_ms` |
| `voice_status` | `status` (`on` / `off` / `error`), `reason` |
| `error` | `code` (`access_denied`, `busy`, `api_key`, `budget`, `bad_message`, `internal`), `message` |
| `closed` | `success`, `summary` |

Validation (`server/protocol.py`) : un dictionnaire `type → champs requis et types`, fonction
`parse_client_message(raw) -> dict | None`. Aucune dépendance externe.

## 4. Temps et ordre

- `t0_client_ms` = horodatage de la première image après `start`. `t` d'une mesure =
  `(t_ms_image - t0_client_ms) / 1000`. `user_done` porte aussi `t_ms`.
- Âge d'un résultat SAM = `monotonic()` à l'arrivée − `monotonic()` à la réception de l'image ; > 5 s → écarté
  (`stale += 1`).
- `frame_index` attribué par le serveur à la réception (compteur), donc croissant ; un résultat d'index inférieur
  au dernier appliqué est écarté (`out_of_order += 1`).

## 5. Coûts (`fixloop/costs.py`)

```python
PRICES = {   # steering/tech.md section 3 — à vérifier sur la page Pricing avant le 2 nov.
    ("sam-3.1", "image"): 2.50 / 1000,          # par image
    ("sam-3.1", "video"): 0.20 / 1000,          # par image, minimum 50 par requête
    ("muse-spark-1.3", "in"): 1.25 / 1e6, ("muse-spark-1.3", "out"): 4.25 / 1e6,
    ("muse-wonder-1.0", "in"): 4.00 / 1e6, ("muse-wonder-1.0", "out"): 20.0 / 1e6,
    ("muse-voice-transcribe-1.0", "second"): 0.18 / 3600,
}
class CostLog:
    def add(self, model, kind, units, seconds, ok, session_id=None, **extra) -> float   # coût estimé
    def session_total(self, session_id) -> float
    def day_total(self) -> float
    def by_model(self, day=None) -> dict
# persistance : data/costs/<AAAA-MM-JJ>.jsonl (une ligne par appel), relue au démarrage pour day_total
```

Jetons Spark inconnus (API sans `usage`) : estimation de 1 500 jetons d'entrée par image et 200 de sortie,
marquée `estimated: true`.

## 6. Hébergement et HTTPS

- Développement : `uvicorn server.app:app --host 127.0.0.1 --port 8000`, téléphone via tunnel HTTPS (`APP-D2`).
- Démo en ligne du replay : statique, sans serveur Python (`07-replay-mode`).
- Direct pour le jury (Should) : même serveur derrière le tunnel ou un hébergement, `FIXLOOP_ACCESS_CODE` défini,
  `FIXLOOP_DAILY_BUDGET=10`.

## 7. Erreurs

| Cas | Traitement |
|---|---|
| Exception dans `Session.on_measures` | journalisée avec trace, `error: internal` envoyé, session continue avec la mesure suivante ; 3 exceptions de suite → arrêt |
| `try_submit` refuse (3 en cours) | `dropped += 1` |
| Aucun résultat SAM depuis 15 s | `say` lent (au plus 1 / min) |
| 401 | `error: api_key`, arrêt |
| 402 / 429 / budget | `error: budget`, `say`, arrêt |
| Client déconnecté | annulation de toutes les tâches, `VoiceBridge.stop()`, journal écrit, `Memory.save` non appelé si pas clôturé |

## 8. Tests (`tests/test_server.py`, `fastapi.testclient`)

- `hello` sans code alors que le code est défini → `access_denied` ; 3e session → `busy`.
- Message JSON invalide ignoré ; image > 200 ko ignorée ; en-tête binaire décodé (type, `t_ms`).
- Session complète avec `FIXLOOP_FAKE_MODELS=1` et la scène synthétique : `hello_ack`, `state`, `say` des 3
  consignes, `closed` avec `success: true`.
- Résultat SAM vieux de 6 s écarté ; résultat dans le désordre écarté.
- `pending` : 5 mesures pendant un faux appel Spark de 2 s → 1 seule appliquée ensuite.
- Coûts : 360 images → 0,90 $ ; dépassement de 1,50 $ → `error: budget`.
- Journal : aucune clé `image`, aucune valeur de `MODEL_API_KEY`.

## 9. Journal des décisions

- **SRV-D1 (30 oct.)** — Binaire pour images et audio (pas de base64) : un tiers de données en moins sur le Wi-Fi
  du téléphone.
- **SRV-D2 (30 oct.)** — 1 image/s, au plus 3 en cours, résultats de plus de 5 s écartés (`PERC-D3`).
- **SRV-D3 (30 oct.)** — Machine à états synchrone exécutée dans un fil, un appel à la fois : on garde la logique
  pure et testée de `01-core-loop`, sans réécriture asynchrone.
- **SRV-D4 (30 oct.)** — Pendant un appel Spark, seule la mesure la plus récente attend : l'utilisateur a pu
  bouger pendant 8 s, les anciennes mesures ne décrivent plus la scène.
- **SRV-D5 (30 oct.)** — Temps de la machine à états = horloge du téléphone, pour que l'anti-rebond ne dépende pas
  de la latence du réseau.
- **SRV-D6 (30 oct.)** — Limites : 2 sessions en direct, 10 min, 1,50 $ par session, 10 $ par jour. Raison :
  crédit total de 150 $ (`steering/tech.md`).
