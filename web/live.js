// FixLoop : appli téléphone en direct (spec/06-phone-app).
// Module ES, aucune dépendance (APP-R10.1). La logique pure vit dans lib.js.
import { isScreen, makeBikeId, isBikeId, codeRequired, cameraConstraints, startMessage,
  HISTORY_MESSAGE, CAMERA_MESSAGE } from "./lib.js";

export const app = {
  screen: "accueil",
  ws: null,
  stream: null,
  micDenied: false,
  bikeId: null,
  sessionId: null,
  lastOverlayAt: 0,
  speaking: false,
  paused: false,
  reconnects: 0,
};

export function showScreen(name) {
  if (!isScreen(name)) return false;
  app.screen = name;
  for (const section of document.querySelectorAll("[data-screen]")) {
    section.hidden = section.dataset.screen !== name;
  }
  return true;
}

export function wsOpen() {
  return !!app.ws && app.ws.readyState === 1;
}

export function sendJson(msg) {
  if (wsOpen()) app.ws.send(JSON.stringify(msg));
}

// Identité du vélo (APP-R6) : "b-" + 8 hex, localStorage protégé par try/catch.
export function randomHex8() {
  const bytes = new Uint8Array(4);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function loadBikeId() {
  try {
    const saved = localStorage.getItem("fixloop.bike_id");
    if (isBikeId(saved)) {
      app.bikeId = saved;
      return { id: saved, kept: true };
    }
    const fresh = makeBikeId(randomHex8());
    try {
      localStorage.setItem("fixloop.bike_id", fresh);
    } catch {
      return { id: fresh, kept: false };
    }
    app.bikeId = fresh;
    return { id: fresh, kept: true };
  } catch {
    const fallback = makeBikeId(randomHex8());
    app.bikeId = fallback;
    return { id: fallback, kept: false }; // APP-R6.2 : id de session
  }
}

export function showHistoryNote(kept) {
  const note = document.getElementById("history-note");
  if (!note) return;
  if (!kept) {
    note.textContent = HISTORY_MESSAGE;
    note.hidden = false;
  } else {
    note.hidden = true;
  }
}

// Code d'accès : affiché seulement si le serveur l'exige (APP-R1.5).
export async function checkHealth() {
  let health = null;
  try {
    const r = await fetch("/api/health");
    health = await r.json();
  } catch {
    return false;
  }
  const needed = codeRequired(health);
  const label = document.getElementById("code-label");
  if (label) label.hidden = !needed;
  return needed;
}

// Caméra + micro demandés dans le geste « Commencer » (APP-R1.2).
export async function requestCamera() {
  try {
    app.stream = await navigator.mediaDevices.getUserMedia(cameraConstraints(true));
    app.micDenied = false;
  } catch {
    try {
      app.stream = await navigator.mediaDevices.getUserMedia(cameraConstraints(false));
      app.micDenied = true; // APP-R1.4 : on continue avec les boutons seuls
    } catch {
      return false; // APP-R1.3 : caméra refusée
    }
  }
  for (const id of ["video", "video-live", "video-anomaly"]) {
    const el = document.getElementById(id);
    if (el) el.srcObject = app.stream; // APP-R2.4 : vidéo locale, sans délai
  }
  return true;
}

export async function onStartPressed() {
  const ok = await requestCamera();
  if (!ok) {
    const err = document.getElementById("home-error");
    if (err) {
      err.textContent = `${CAMERA_MESSAGE} Touchez « Réessayer ».`;
      err.hidden = false;
    }
    const btn = document.getElementById("btn-start");
    if (btn) btn.textContent = "Réessayer";
    return;
  }
  showScreen("cadrage");
}

// Écran de cadrage : « C'est cadré » envoie start (APP-R3).
export function onFramedPressed() {
  sendJson(startMessage());
  showScreen("session");
}

function go(name) {
  return () => showScreen(name);
}

if (typeof document !== "undefined") {
  document.getElementById("btn-start")?.addEventListener("click", onStartPressed);
  document.getElementById("btn-framed")?.addEventListener("click", onFramedPressed);
  document.getElementById("btn-again")?.addEventListener("click", go("accueil"));
  document.getElementById("btn-retry")?.addEventListener("click", go("accueil"));
  const kept = loadBikeId().kept;
  showHistoryNote(kept);
  checkHealth();
}
