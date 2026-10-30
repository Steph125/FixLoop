# 02 — Perception SAM 3.1 : conception

Couvre `PERC-R1` à `PERC-R9`. Fichier créé : `fixloop/perception.py`. Fichiers source à reprendre :
`probe/sam_image_latency.py` (mode image), `probe/sam_api_probe.py` (mode vidéo, découpage, cache).

## 1. Appel SAM 3.1 (forme commune)

```python
stream = await client.responses.create(
    model="sam-3.1",
    input=[{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": prompt},                      # un seul concept : "bicycle chain"
        {"type": "input_image", "image_url": data_url},              # direct
        # ou {"type": "input_video", "file_id": file_id},            # replay
    ]}],
    metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
    stream=True,
)
result = await parse_responses_stream(stream, image_segmentation_format()).final_result()
# vidéo : video_segmentation_format()
```

Sortie brute : une ligne par objet et par image, `<Nf>id<|box…|><|mask…;data=H,W,enc…|>`. Les records décodés
portent `kind` (`"mask"`), `object_id`, `frame.frame_index` (vidéo), `bounds.left/top`, `mask.width/height`,
`confidence`. `decode_mask_to_raster(rec.mask)` rend `width × height` octets 0/1 couvrant **la boîte**.

Client : `AsyncOpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"], timeout=60)`,
créé une fois par processus, fermé à l'arrêt (`await client.close()`).

## 2. API du module

```python
CONF_THR = 0.4            # FIXLOOP_SAM_CONF
LIVE_WIDTH = 848          # FIXLOOP_SAM_WIDTH, largeur envoyée en direct (pas d'agrandissement)
MAX_IN_FLIGHT = 3         # FIXLOOP_SAM_INFLIGHT
CHUNK_SECONDS = 10.0      # FIXLOOP_SAM_CHUNK_S
VIDEO_FPS = 10.0
RETRYABLE = (APIConnectionError, ResponsesStreamError, ConnectionError, TimeoutError)

@dataclass
class PartResult:
    mask: np.ndarray | None          # plein cadre, None si rien retenu
    confidence: float
    box: tuple[int, int, int, int] | None    # x0, y0, x1, y1
    svg_path: str | None             # coordonnées image
    n_objects: int

@dataclass
class ImageResult:
    frame_index: int
    t: float
    parts: dict[str, PartResult]
    timing: dict                     # {"total_s", "first_byte_s", "attempts": {pièce: n}}
    error: str | None = None
    def to_frame_masks(self) -> FrameMasks

class LivePerception:
    def __init__(self, procedure: dict, client: AsyncOpenAI | None = None, costs: CostLog | None = None): ...
    def try_submit(self, jpeg: bytes, frame_index: int, t: float) -> asyncio.Task | None
        # None si MAX_IN_FLIGHT images déjà en cours (image abandonnée, compteur dropped += 1)
    async def segment_image(self, jpeg: bytes, frame_index: int, t: float) -> ImageResult
    in_flight: int; dropped: int

async def segment_video(video: Path, procedure: dict, out_dir: Path, *, client=None, costs=None,
                        chunk_seconds=CHUNK_SECONDS, fps=VIDEO_FPS, width=960,
                        confirm: Callable[[int], bool] | None = None) -> list[FrameMasks]

def parse_raw(text: str, video: bool = True) -> SegmentationResult
def lines_for(text: str, frames: set[int] | None) -> str
def masks_from_records(records, h, w, conf_thr, largest) -> dict[int, PartResult]   # vidéo : par image
def mask_to_svg_path(mask: np.ndarray, tol: float = 1.5) -> str
```

Le module ne connaît pas la machine à états : il rend des `FrameMasks` ; `geometry.measure` fait le reste.

## 3. Mode image (direct)

1. Le JPEG reçu du téléphone (≤ 848 px de large, `APP-R2`) est envoyé tel quel en data URL : pas de
   redimensionnement côté serveur, sauf s'il dépasse `LIVE_WIDTH` (réduction seulement).
2. `segment_image` lance `asyncio.gather` d'une tâche par pièce. Chaque tâche : `responses.create` en flux,
   mesure du premier octet (premier événement `response.output_text.delta`, que l'événement soit un dict ou un
   objet), décodage, `stream.close()` dans un `finally`.
3. Pour chaque pièce : records `kind == "mask"`, filtre `confidence ≥ CONF_THR` (confiance absente = 1,0),
   placement plein cadre, sélection `largest` ou union, boîte englobante, chemin SVG.
4. Erreur après 3 tentatives sur une pièce : `ImageResult.error = "<pièce>: <type d'erreur>"`, pièce absente.
   Erreur non réseau : pas de relance, même traitement.
5. `try_submit` : si `in_flight >= MAX_IN_FLIGHT`, rend `None` et incrémente `dropped` ; sinon crée la tâche et
   décrémente `in_flight` à sa fin (callback `add_done_callback`).

Différence avec `probe/sam_image_latency.py` : la sonde ne filtrait pas la confiance en mode image. Le filtre à
0,4 est appliqué partout pour un comportement identique entre direct et replay ; `PERC-T3` vérifie que les
10 états mesurés le 30 oct. restent corrects.

## 4. Mode vidéo (replay, évaluation)

```
vidéo source ─ffmpeg─► prepared.mp4 (10 fps, ≤960 px, H.264, sans son)
             ─plan_chunks(n, 100 images, min 50)─► [(0,100), (100,200), … , (400,570)]
             ─extract_chunk (select=between(n\,a\,b-1), setpts)─► chunk_NN.mp4
pour chaque morceau et chaque pièce (pièces en parallèle, morceaux en série) :
    clé = sha256(chunk_NN.mp4) + prompt + "sam-3.1"
    si raw_<pièce>_NN.txt et .key correspondent → relire
    sinon → Files API (purpose="user_data") → responses.create(input_video) → enregistrer brut + clé
    shift_frames(brut, a) → concaténer dans raw_<pièce>.txt
parse_raw(raw_<pièce>.txt) → masks_from_records → FrameMasks par image
```

- Les morceaux sont traités en série pour limiter les coupures (constaté le 29 oct. : les requêtes de plus de
  60 s environ sont coupées par le serveur) ; les pièces d'un même morceau partent en parallèle.
- Confirmation : `confirm(n_images_facturées)` avec `n = Σ max(images du morceau, 50) × nombre de pièces`.
- Le fichier `.key` contient l'empreinte ; une vidéo modifiée invalide son cache.
- `out_dir` est ignoré par git (`probe_out*/`, `replay/build/`).

## 5. Contours SVG

`mask_to_svg_path(mask)` : `cv2.findContours(RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)`, `approxPolyDP(tol=1,5)`,
contours de moins de 40 px² ignorés, chaîne `"M x,y L x,y … Z"` par contour, coordonnées entières. Alternative :
`decode_mask_to_svg_path` de `meta-sam-parser` décalé de `bounds` ; retenue seulement si plus légère à qualité
égale (`PERC-T6` mesure les deux).

## 6. Erreurs

| Cas | Mode image | Mode vidéo |
|---|---|---|
| Coupure réseau | 3 tentatives, attente 5 s puis 10 s | 3 tentatives, attente 10 s puis 20 s |
| 401 clé invalide | erreur remontée, la session prévient l'utilisateur (`SRV-R7`) | arrêt du script avec message |
| 402 / 429 crédit ou quota | erreur remontée, plus d'appel SAM pour la session | arrêt, cache conservé |
| Réponse refusée (`ResponsesStreamRefusalError`) | pièce absente pour cette image | morceau marqué en échec, autres morceaux continués |
| Masque illisible (`InvalidSegmentationMaskError`) | objet ignoré | objet ignoré |

## 7. Performances (référence `eval/day1`)

| Mesure | Mesuré | Cible |
|---|---|---|
| Image, durée totale, médiane | 1,9 s | ≤ 3 s |
| Image, 90e centile | 4,4 s | ≤ 5 s |
| Vidéo, 57 s, 3 pièces | 529 s | non critique (calcul unique) |
| Chemin SVG par pièce | non mesuré | < 4 ko |

## 8. Tests (sans réseau)

- `FakeSamClient` : `responses.create` rend un flux d'événements rejoués depuis un fichier brut enregistré
  (`tests/data/sam_image_chain.txt`, `sam_image_chainring.txt`, quelques lignes extraites de `probe_out2`).
- Tests : placement plein cadre (boîte décalée), `largest` contre union, filtre de confiance, pièce absente,
  relance après `APIConnectionError` puis succès, pas de relance sur 401, `try_submit` refuse la 4e image,
  `shift_frames`, `plan_chunks` (dernier morceau court fusionné), cache (2e appel sans requête), SVG < 4 ko.
- Test d'équivalence (`PERC-R9`) : marqué `@pytest.mark.recorded`, sauté si `probe_out2/` est absent.

## 9. Journal des décisions

- **PERC-D1 (29 oct.)** — Vidéo par morceaux de 10 s avec cache, après des coupures répétées sur la vidéo entière
  (WinError 10054). Résultat : 18 requêtes (6 morceaux × 3 pièces), 529 s, aucune perte.
- **PERC-D2 (30 oct.)** — Direct en mode image (1 image/s, requêtes qui se chevauchent), replay en mode vidéo
  calculé une fois. Raison : 1,9 s par image en mode image contre 529 s pour 57 s en mode vidéo.
- **PERC-D3 (30 oct.)** — Au plus 3 images en cours ; au-delà, abandon. Raison : à 1 image/s et 4,4 s au
  90e centile, une file grossirait sans fin et les verdicts arriveraient trop tard.
- **PERC-D4 (29 oct.)** — `select: largest` pour le plateau : le prompt `chainring` renvoie aussi les pignons
  arrière (`eval/day1`).
- **PERC-D5 (29 oct., précisé le 30)** — Le dérailleur n'est pas utilisé par la fiche : son prompt attrape la
  manivelle et le plateau. Il reste dans `parts` (segmenté en replay pour la surimpression) mais n'est pas
  demandé en direct (`PERC-R1.9`) : `live_parts(procedure)` = pièces citées par une règle.
