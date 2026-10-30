# 06 — Appli téléphone : conception

Couvre `APP-R1` à `APP-R10`. Fichiers : `web/index.html`, `web/live.js`, `web/audio-worklet.js`, `web/style.css`.

## 1. Structure

```
index.html        un seul document, 6 <section data-screen="…">, une seule visible à la fois
live.js           module ES : état de l'appli, caméra, WebSocket, surimpression, voix, boutons
audio-worklet.js  AudioWorkletProcessor : rééchantillonnage vers 16 kHz, PCM16, blocs de 1 600 échantillons
style.css         variables de couleur, mise en page portrait, boutons
```

État de l'appli (objet unique `app`) : `screen`, `ws`, `stream`, `bikeId`, `sessionId`, `lastOverlayAt`,
`speaking`, `paused`, `reconnects`.

## 2. Caméra et capture

```js
stream = await navigator.mediaDevices.getUserMedia({
  video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
  audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
});
video.srcObject = stream;                       // affichage local, plein écran, object-fit: cover
setInterval(captureFrame, 1000);                // APP-R2.1
async function captureFrame() {
  if (!wsOpen() || app.paused) return;          // APP-R2.3 : pas de file
  const w = Math.min(848, video.videoWidth), h = Math.round(video.videoHeight * w / video.videoWidth);
  canvas.width = w; canvas.height = h; ctx.drawImage(video, 0, 0, w, h);
  const blob = await new Promise(r => canvas.toBlob(r, "image/jpeg", 0.7));
  ws.send(packBinary(0x02, Date.now(), await blob.arrayBuffer()));
}
function packBinary(kind, tMs, payload) {       // SRV-R3.2
  const buf = new Uint8Array(9 + payload.byteLength);
  buf[0] = kind; new DataView(buf.buffer).setBigUint64(1, BigInt(tMs), false);
  buf.set(new Uint8Array(payload), 9); return buf;
}
```

Si le micro est refusé, `getUserMedia` est relancé avec `audio: false` (`APP-R1.4`).

## 3. Surimpression

```html
<div class="stage">
  <video autoplay playsinline muted></video>
  <svg class="overlay" preserveAspectRatio="xMidYMid slice"></svg>   <!-- même règle que object-fit: cover -->
</div>
```

- `overlay` reçu : `svg.setAttribute("viewBox", `0 0 ${w} ${h}`)`, un `<path d=… class="part color-…">` par
  pièce, `stroke-width: 3` (vecteur non mis à l'échelle : `vector-effect: non-scaling-stroke`), remplissage 15 %.
- `highlight` reçu : couleur mémorisée par pièce jusqu'au prochain `highlight` ou à la validation.
- Toutes les 500 ms : si `now - lastOverlayAt > 3000`, classe `stale` (opacité 30 %) (`APP-R5.3`).
- Ligne de mesure : `contact 0,09 · en place`, à partir de `overlay.contact` et `overlay.label` calculés par le
  serveur avec les seuils de l'étape ; l'appli ne recalcule rien (`APP-D3`).

## 4. Voix

- Sortie : `const u = new SpeechSynthesisUtterance(text); u.lang = "fr-FR"; u.voice = voixFr;` ;
  `u.onstart` / `u.onend` → `send({type: "speaking", on, t_ms})`. Le premier `speak("")` est fait dans le geste
  « Commencer » (déblocage iOS).
- Entrée : `AudioContext` (fréquence native), `audioWorklet.addModule("audio-worklet.js")`, nœud qui poste des
  `Int16Array` de 1 600 échantillons (100 ms à 16 kHz) ; envoi `packBinary(0x01, Date.now(), pcm)`.
  Rééchantillonnage linéaire dans le worklet. Micro coupé pendant `pause`.

## 5. Écrans et transitions

```
Accueil ─Commencer─► (autorisations) ─► Cadrage ─C'est cadré─► Session ◄─► Anomalie
   ▲                                                              │
   └──────── Nouvelle session ◄── Fin ◄── closed ─────────────────┘
   └──────── Réessayer ◄── Erreur ◄── error / 3 reconnexions ratées
```

- Bandeau d'étape : `Étape k/K · <instruction>` depuis `state`.
- Anomalie : quand un `highlight` rouge arrive, bandeau rouge avec le dernier `say` ; retour au bandeau normal au
  prochain `state` avec `verdict` différent de `eps` ou au prochain `highlight` bleu.
- Erreurs : `access_denied` → « Code incorrect » ; `busy` → « FixLoop est déjà utilisé, réessaie dans quelques
  minutes » ; `budget` → « Démo en direct terminée pour aujourd'hui. Regarde le replay. » + lien ; `api_key`,
  `internal` → « Problème du serveur. ».

## 6. HTTPS pour le téléphone (`APP-D2`)

| Option | Commande (PowerShell, une par ligne) | Pour |
|---|---|---|
| Tunnel Cloudflare rapide | `cloudflared tunnel --url http://localhost:8000` | essais, démo en direct (URL changeante) |
| ngrok | `ngrok http 8000` | alternative si cloudflared est bloqué |
| Hébergement (Should) | serveur Python sur un hébergeur avec HTTPS | direct accessible au jury |

Le replay public (`07`) n'a pas besoin de serveur Python : hébergement statique HTTPS.

## 7. Tests

- Pas de framework de test JS (`APP-R10.1`) : `web/selftest.html` exécute dans le navigateur des vérifications de
  `packBinary`, du choix d'écran par message, du calcul de taille d'image ; résultat affiché.
- Test manuel sur téléphone : liste de contrôle `APP-T9` (chaque critère `APP-R*`, cases cochées avec la date et
  le modèle du téléphone dans `eval/day4/phone-checklist.md`).

## 8. Journal des décisions

- **APP-D1 (30 oct.)** — Appli web plutôt que native : pas de magasin d'applications, le jury l'ouvre d'un lien.
- **APP-D2 (30 oct.)** — HTTPS par tunnel pour les essais ; hébergement statique pour le replay.
- **APP-D3 (30 oct.)** — Le téléphone ne recalcule aucune mesure : une seule source de vérité, le serveur.
- **APP-D4 (30 oct.)** — Vidéo affichée en local, contours décalés d'environ 2 s : acceptable car la scène bouge
  peu (téléphone posé) et les contours s'estompent quand ils vieillissent.
