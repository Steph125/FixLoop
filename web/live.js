// FixLoop : appli téléphone en direct (spec/06-phone-app).
// Module ES, aucune dépendance (APP-R10.1). La logique pure vit dans lib.js.
import { isScreen, makeBikeId, isBikeId, codeRequired, cameraConstraints, startMessage,
  helloMessage, userDoneMessage, commandMessage, pauseMessage, resumeMessage, stopMessage,
  packBinary, imageTargetSize, MSG_IMAGE, JPEG_QUALITY,
  partColor, formatMeasure, verdictLabel, stepLabel, staleOverlay, GREEN_MS, endSummaryText,
  pickFrenchVoice, shouldInterruptSay, VALIDATION_PHRASE,
  voiceStatusText, MSG_AUDIO,
  backoffDelay, screenFor, errorMessage, HISTORY_MESSAGE, CAMERA_MESSAGE } from "./lib.js";

export const app = {
  screen: "accueil",
  ws: null,
  stream: null,
  wakeLock: null,
  micDenied: false,
  bikeId: null,
  sessionId: null,
  started: false,
  lastOverlayAt: 0,
  speaking: false,
  paused: false,
  reconnects: 0,
  captureTimer: null,
  staleTimer: null,
  redParts: [],
  greenUntil: 0,
  stepIndex: 0,
  lastSay: "",
  speakingText: "",
  pendingSay: null,
  audioCtx: null,
  micNode: null,
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
  unlockSpeech(); // premier speak("") dans le geste : déblocage iOS
  showScreen("cadrage");
  connect();
}

// Écran allumé pendant la session (APP-R9.1) : demandé quand la session
// devient active, relâché à la fin ; sans échec si l'API manque.
export async function requestWakeLock() {
  try {
    if (!("wakeLock" in navigator) || !navigator.wakeLock?.request) return null;
    if (app.wakeLock) return app.wakeLock;
    app.wakeLock = await navigator.wakeLock.request("screen");
  } catch {
    app.wakeLock = null; // verrou indisponible : la session continue
  }
  return app.wakeLock;
}

export function releaseWakeLock() {
  const lock = app.wakeLock;
  app.wakeLock = null;
  if (!lock) return;
  try {
    const done = lock.release();
    if (done && typeof done.catch === "function") done.catch(() => {});
  } catch {
    // déjà relâché
  }
}

// Écran de cadrage : « C'est cadré » envoie start (APP-R3).
export function onFramedPressed() {
  if (!wsOpen()) connect();
  sendJson(startMessage());
  app.started = true;
  requestWakeLock();
  startCapture();
  startMic();
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
  startStaleTimer();
}

export function onServerMessage(msg) {
  if (msg.type === "hello_ack") {
    app.sessionId = msg.session_id;
    app.reconnects = 0; // nouvelle session acceptée : compteur remis à zéro
    return;
  }
  if (msg.type === "overlay") {
    drawOverlay(msg);
    return;
  }
  if (msg.type === "highlight") onHighlight(msg);
  if (msg.type === "say") onSay(msg.text);
  if (msg.type === "state") onState(msg);
  if (msg.type === "voice_status") onVoiceStatus(msg);
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
  stopCapture();
  stopStaleTimer();
  stopMic();
  releaseWakeLock();
  showScreen("erreur");
}

export function showEnd(msg) {
  const title = document.getElementById("end-title");
  if (title) title.textContent = msg.success ? "Réparation validée" : "Session arrêtée";
  const summary = document.getElementById("end-summary");
  if (summary) summary.textContent = endSummaryText(msg.success); // compteurs : au journal, pas à l'écran
  stopCapture();
  stopStaleTimer();
  stopMic();
  releaseWakeLock();
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
  if (app.audioCtx) { // micro coupé pendant pause (design 06, section 4)
    if (app.paused) app.audioCtx.suspend();
    else app.audioCtx.resume();
  }
  ev.currentTarget.textContent = app.paused ? "Reprendre" : "Pause";
}

export function onAgainPressed() {
  sendJson(stopMessage());
  app.started = false;
  app.reconnects = 0;
  showScreen("accueil");
  connect();
}


// Envoi des images : 1 image/s, 848 px, JPEG 0,7, binaire (APP-R2).
export async function captureFrame() {
  if (!wsOpen() || app.paused || !app.started) return; // APP-R2.3 : pas de file
  const video = document.getElementById("video-live");
  if (!video || !video.videoWidth) return;
  const { w, h } = imageTargetSize(video.videoWidth, video.videoHeight);
  const canvas = captureFrame.canvas || (captureFrame.canvas = document.createElement("canvas"));
  canvas.width = w; canvas.height = h;
  canvas.getContext("2d").drawImage(video, 0, 0, w, h);
  const blob = await new Promise((r) => canvas.toBlob(r, "image/jpeg", JPEG_QUALITY));
  if (!blob || !wsOpen()) return;
  const bytes = new Uint8Array(await blob.arrayBuffer());
  app.ws.send(packBinary(MSG_IMAGE, Date.now(), bytes));
}

export function startCapture() {
  stopCapture();
  app.captureTimer = setInterval(captureFrame, 1000); // APP-R2.1 : 1 image/s
}

export function stopCapture() {
  if (app.captureTimer) {
    clearInterval(app.captureTimer);
    app.captureTimer = null;
  }
}

// Surimpression : contours SVG mis à l'échelle de l'affichage (APP-R5.1).
export function drawOverlay(msg) {
  app.lastOverlayAt = Date.now();
  const now = Date.now();
  for (const id of ["overlay", "overlay-anomaly"]) {
    const svg = document.getElementById(id);
    if (!svg) continue;
    svg.setAttribute("viewBox", `0 0 ${msg.w} ${msg.h}`);
    svg.innerHTML = Object.entries(msg.parts || {})
      .map(([part, info]) => `<path d="${info.path}" class="part color-${
        info.color || partColor(part, app.redParts, app.greenUntil, now)}"/>`)
      .join("");
    svg.classList.remove("stale");
  }
  const measure = document.getElementById("measure"); // APP-R5.4 : preuve visible
  if (measure) measure.textContent = `${formatMeasure(msg.contact, msg.label)} · ${verdictLabel(msg.verdict)}`;
}

export function onHighlight(msg) {
  if (msg.color === "red") {
    app.redParts = [...msg.parts];
    const banner = document.getElementById("anomaly-banner");
    if (banner && app.lastSay) banner.textContent = app.lastSay;
  }
  else app.redParts = app.redParts.filter((part) => !msg.parts.includes(part));
}

export function onState(msg) {
  const label = stepLabel(msg);
  const banner = document.getElementById("step-banner");
  if (banner && label) banner.textContent = label;
  const idx = msg.step ? msg.step.index : 0;
  if (app.stepIndex !== 0 && idx !== app.stepIndex) {
    app.greenUntil = Date.now() + GREEN_MS; // APP-R5.2 : vert pendant 1 s
  }
  app.stepIndex = idx;
}

export function startStaleTimer() {
  stopStaleTimer();
  app.staleTimer = setInterval(() => { // APP-R5.3 : estompe après 3 s
    const stale = staleOverlay(Date.now(), app.lastOverlayAt);
    for (const id of ["overlay", "overlay-anomaly"]) {
      document.getElementById(id)?.classList.toggle("stale", stale);
    }
  }, 500);
}

export function stopStaleTimer() {
  if (app.staleTimer) {
    clearInterval(app.staleTimer);
    app.staleTimer = null;
  }
}

// Voix en sortie : lecture fr-FR + sous-titres, interruption, speaking (APP-R7).
export function showSubtitle(text) {
  for (const id of ["subtitle", "subtitle-anomaly"]) {
    const el = document.getElementById(id);
    if (el) el.textContent = text; // affiché jusqu'au message suivant
  }
}

export function unlockSpeech() {
  try {
    if ("speechSynthesis" in window) window.speechSynthesis.speak(new SpeechSynthesisUtterance(""));
  } catch {
    // synthèse indisponible : sous-titres seuls
  }
}

export function onSay(text) {
  app.lastSay = text;
  showSubtitle(text);
  if (!("speechSynthesis" in window)) return;
  const synth = window.speechSynthesis;
  if (synth.speaking && !shouldInterruptSay(app.speakingText)) {
    app.pendingSay = text; // APP-R7.2 : la validation « C'est bon. » va au bout
    return;
  }
  synth.cancel(); // APP-R7.2 : un nouveau say interrompt la lecture en cours
  speak(text);
}

export function speak(text) {
  const synth = window.speechSynthesis;
  app.speakingText = text;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "fr-FR";
  u.rate = 1.0;
  const voice = pickFrenchVoice(synth.getVoices());
  if (voice) u.voice = voice;
  u.onstart = () => {
    app.speaking = true;
    sendJson(speakingMessage(true, Date.now())); // APP-R7.3, VOX-R2.4
  };
  u.onend = () => {
    app.speaking = false;
    sendJson(speakingMessage(false, Date.now()));
    if (app.pendingSay) {
      const next = app.pendingSay;
      app.pendingSay = null;
      speak(next);
    }
  };
  synth.speak(u);
}

// Statut voix : indicateur micro, ou repli bouton seul (VOX-T5, APP-R7.4).
export function onVoiceStatus(msg) {
  const el = document.getElementById("mic-indicator");
  if (!el) return;
  const text = voiceStatusText(msg.status);
  el.textContent = text === null ? "Micro actif" : text;
  el.hidden = false;
}

// Voix en entrée : micro -> PCM16 24 kHz, trames de 80 ms (APP-R7.4).
export async function startMic() {
  if (!app.stream || app.micDenied) return false; // APP-R1.4 : boutons seuls
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return false;
  try {
    app.audioCtx = new AC();
    await app.audioCtx.audioWorklet.addModule("audio-worklet.js");
    const node = new AudioWorkletNode(app.audioCtx, "fixloop-capture");
    node.port.onmessage = (ev) => {
      if (!wsOpen() || app.paused || !app.started) return; // pas de file
      app.ws.send(packBinary(MSG_AUDIO, Date.now(), ev.data));
    };
    app.audioCtx.createMediaStreamSource(app.stream).connect(node);
    app.micNode = node;
    return true;
  } catch {
    stopMic();
    return false;
  }
}

export function stopMic() {
  if (app.audioCtx) {
    app.audioCtx.close().catch(() => {});
    app.audioCtx = null;
    app.micNode = null;
  }
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
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && app.started) requestWakeLock(); // APP-R9.1 : réaffiché
  });
  const kept = loadBikeId().kept;
  showHistoryNote(kept);
  checkHealth();
}
