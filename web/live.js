// FixLoop : appli téléphone en direct (spec/06-phone-app).
// Module ES, aucune dépendance (APP-R10.1). La logique pure vit dans lib.js.
import { isScreen, makeBikeId, isBikeId, codeRequired, cameraConstraints, startMessage,
  helloMessage, userDoneMessage, commandMessage, pauseMessage, resumeMessage, stopMessage,
  backoffDelay, screenFor, errorMessage, HISTORY_MESSAGE, CAMERA_MESSAGE } from "./lib.js";

export const app = {
  screen: "accueil",
  ws: null,
  stream: null,
  micDenied: false,
  bikeId: null,
  sessionId: null,
  started: false,
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
  connect();
}

// Écran de cadrage : « C'est cadré » envoie start (APP-R3).
export function onFramedPressed() {
  if (!wsOpen()) connect();
  sendJson(startMessage());
  app.started = true;
  showScreen("session");
}

// WebSocket et reconnexions (APP-T4, APP-R9.3).
export function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/session`;
}

export function connect() {
  if (app.ws) {
    try {
      app.ws.close();
    } catch {
      // déjà fermée
    }
  }
  const ws = new WebSocket(wsUrl());
  app.ws = ws;
  ws.onopen = () => {
    const code = document.getElementById("code")?.value || null;
    sendJson(helloMessage(app.bikeId, code,
      { ua: navigator.userAgent, w: window.innerWidth, h: window.innerHeight }));
  };
  ws.onmessage = (ev) => onServerMessage(JSON.parse(ev.data));
  ws.onclose = () => onClose();
}

export function onServerMessage(msg) {
  if (msg.type === "hello_ack") {
    app.sessionId = msg.session_id;
    app.reconnects = 0; // nouvelle session acceptée : compteur remis à zéro
    return;
  }
  const target = screenFor(msg, app.screen);
  if (msg.type === "error") showError(msg.code);
  if (msg.type === "closed") showEnd(msg);
  if (target) showScreen(target);
}

export function onClose() {
  app.ws = null;
  if (app.screen === "fin" || app.screen === "erreur") return; // fermeture voulue
  if (app.reconnects >= 3) {
    showError("internal"); // APP-R9.3 : 3 reconnexions ratées, écran d'erreur
    return;
  }
  const delay = backoffDelay(app.reconnects); // 1 s, 2 s, 4 s
  app.reconnects += 1;
  setTimeout(connect, delay); // une reconnexion ouvre une nouvelle session
}

export function showError(code) {
  const el = document.getElementById("error-text");
  if (el) el.textContent = errorMessage(code);
  showScreen("erreur");
}

export function showEnd(msg) {
  const title = document.getElementById("end-title");
  if (title) title.textContent = msg.success ? "Réparation validée" : "Session arrêtée";
  const summary = document.getElementById("end-summary");
  if (summary && msg.summary) summary.textContent = JSON.stringify(msg.summary);
  showScreen("fin");
}

// Boutons : vibration + retour visuel en moins de 100 ms (APP-R4.3).
export function pressFeedback(btn) {
  try {
    navigator.vibrate?.(30);
  } catch {
    // pas de vibration disponible
  }
  btn.classList.add("pressed");
  setTimeout(() => btn.classList.remove("pressed"), 100);
}

export function onDonePressed(ev) {
  pressFeedback(ev.currentTarget);
  sendJson(userDoneMessage(Date.now())); // APP-R4.1, VOX-R3.1 : bouton « C'est fait »
}

export function onCommandPressed(cmd) {
  return (ev) => {
    pressFeedback(ev.currentTarget);
    sendJson(commandMessage(cmd, Date.now())); // APP-R4.2 : aide, répète
  };
}

export function onPausePressed(ev) {
  pressFeedback(ev.currentTarget);
  app.paused = !app.paused;
  sendJson(app.paused ? pauseMessage() : resumeMessage()); // APP-R4.2
  ev.currentTarget.textContent = app.paused ? "Reprendre" : "Pause";
}

export function onAgainPressed() {
  sendJson(stopMessage());
  app.started = false;
  app.reconnects = 0;
  showScreen("accueil");
  connect();
}

function go(name) {
  return () => showScreen(name);
}

if (typeof document !== "undefined") {
  document.getElementById("btn-start")?.addEventListener("click", onStartPressed);
  document.getElementById("btn-framed")?.addEventListener("click", onFramedPressed);
  for (const id of ["btn-done", "btn-done2"]) {
    document.getElementById(id)?.addEventListener("click", onDonePressed);
  }
  document.getElementById("btn-help")?.addEventListener("click", onCommandPressed("help"));
  document.getElementById("btn-help2")?.addEventListener("click", onCommandPressed("help"));
  document.getElementById("btn-repeat")?.addEventListener("click", onCommandPressed("repeat"));
  document.getElementById("btn-repeat2")?.addEventListener("click", onCommandPressed("repeat"));
  for (const id of ["btn-pause", "btn-pause2"]) {
    document.getElementById(id)?.addEventListener("click", onPausePressed);
  }
  document.getElementById("btn-again")?.addEventListener("click", onAgainPressed);
  document.getElementById("btn-retry")?.addEventListener("click", go("accueil"));
  const kept = loadBikeId().kept;
  showHistoryNote(kept);
  checkHealth();
}
