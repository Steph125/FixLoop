// FixLoop : logique pure partagée entre live.js et web/selftest.html (APP-T10).
// Modules ES, aucune dépendance (APP-R10.1). Aucune mesure recalculée ici :
// les libellés viennent du serveur (APP-D3).

export const SCREENS = ["accueil", "cadrage", "session", "anomalie", "fin", "erreur"];

export function isScreen(name) {
  return SCREENS.includes(name);
}

// Messages d'erreur du serveur (design 06, section 5), APP-R1.5, VOX-R3.1.
export const ERROR_MESSAGES = {
  access_denied: "Code incorrect",
  busy: "FixLoop est déjà utilisé, réessaie dans quelques minutes",
  budget: "Démo en direct terminée pour aujourd'hui. Regarde le replay.",
  api_key: "Problème du serveur.",
  internal: "Problème du serveur.",
  bad_message: "Problème du serveur.",
};

export function errorMessage(code) {
  return ERROR_MESSAGES[code] || "Problème du serveur.";
}

export const CAMERA_MESSAGE = "FixLoop a besoin de la caméra pour vérifier ta réparation";
export const HISTORY_MESSAGE = "Historique non conservé sur ce navigateur";
export const VOICE_MESSAGE = "Commande vocale indisponible";

export function makeBikeId(hex8) {
  return `b-${hex8}`;
}

export function isBikeId(s) {
  return typeof s === "string" && /^[a-z0-9-]{4,32}$/.test(s) && s.startsWith("b-");
}

export function wordCount(text) {
  return String(text).trim().split(/\s+/).filter(Boolean).length;
}

// Santé du serveur : le champ de code ne s’affiche que si exigé (APP-R1.5).
export function codeRequired(health) {
  return !!(health && health.access_code_required);
}

// Caméra : arrière idéale + micro, relance sans micro si refusé (APP-R1.2, R1.4).
export function cameraConstraints(withMic) {
  return {
    video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: withMic
      ? { channelCount: 1, echoCancellation: true, noiseSuppression: true }
      : false,
  };
}

// Message de démarrage : les 3 images suivantes servent au diagnostic (APP-R3.2).
export function startMessage() {
  return { type: "start" };
}

// Messages de contrôle vers le serveur (design 05, section 3.1).
export function helloMessage(bikeId, accessCode, client) {
  const msg = { type: "hello", bike_id: bikeId };
  if (accessCode) msg.access_code = accessCode;
  if (client) msg.client = client;
  return msg;
}

export function userDoneMessage(tMs) {
  return { type: "user_done", t_ms: tMs };
}

export function commandMessage(cmd, tMs) {
  return { type: "command", cmd, t_ms: tMs };
}

export function speakingMessage(on, tMs) {
  return { type: "speaking", on, t_ms: tMs };
}

export function pauseMessage() {
  return { type: "pause" };
}

export function resumeMessage() {
  return { type: "resume" };
}

export function stopMessage() {
  return { type: "stop" };
}

// Reconnexions : 1 s, 2 s, 4 s puis écran d’erreur (APP-R9.3).
export function backoffDelay(attempt) {
  return [1000, 2000, 4000][Math.min(attempt, 2)];
}

// Choix d’écran par message serveur (APP-R8) : rend l’écran cible ou null (rester).
export function screenFor(msg, current) {
  if (!msg || typeof msg.type !== "string") return null;
  if (msg.type === "closed") return "fin";
  if (msg.type === "error") return "erreur";
  if (msg.type === "highlight") return msg.color === "red" ? "anomalie" : "session";
  if (msg.type === "say" && current === "cadrage") return "session";
  return null;
}

// Images : réduction à 848 px au plus, JPEG 0,7, en-tête binaire SRV-R3.2.
export const MAX_SEND_WIDTH = 848;
export const JPEG_QUALITY = 0.7;
export const MSG_AUDIO = 0x01; // PCM16 mono 24 kHz, 80 ms (VOX-R1.2)
export const MSG_IMAGE = 0x02;

export function imageTargetSize(videoW, videoH, maxW = MAX_SEND_WIDTH) {
  const w = Math.min(maxW, videoW);
  return { w, h: Math.round((videoH * w) / videoW) };
}

// 1 octet de type, 8 octets d’horodatage gros-boutiste, puis les données.
export function packBinary(kind, tMs, payload) {
  const bytes = ArrayBuffer.isView(payload)
    ? new Uint8Array(payload.buffer, payload.byteOffset, payload.byteLength)
    : new Uint8Array(payload); // Int16Array du worklet comprise
  const buf = new Uint8Array(9 + bytes.byteLength);
  buf[0] = kind;
  new DataView(buf.buffer).setBigUint64(1, BigInt(tMs), false);
  buf.set(bytes, 9);
  return buf;
}

// Surimpression : couleurs et libellés (APP-R5). Le téléphone ne recalcule rien (APP-D3).
export const STALE_MS = 3000; // sans overlay depuis 3 s : contours estompés
export const GREEN_MS = 1000; // vert pendant 1 s après une validation

export function partColor(part, redParts, greenUntil, now) {
  if (redParts && redParts.includes(part)) return "red"; // anomalie
  if (greenUntil && now < greenUntil) return "green"; // validation récente
  return "blue"; // pièce de l’étape
}

export function formatMeasure(contact, label) {
  if (typeof contact !== "number" || !Number.isFinite(contact)) return label;
  return `contact ${contact.toFixed(2).replace(".", ",")} · ${label}`;
}

export function verdictLabel(verdict) {
  return { 1: "validée", 0: "en cours", eps: "anomalie", "?": "incertain" }[verdict] || "en cours";
}

// Bandeau d’étape : "Étape k/K · consigne" (APP-R8, écran Session).
export function stepLabel(snapshot) {
  const step = snapshot && snapshot.step;
  if (!step) return "";
  return `Étape ${step.index}/${step.count} · ${step.instruction}`;
}

// Instant de l’instantané (temps session, en secondes).
export function stateAt(snapshot) {
  return (snapshot && snapshot.t) || 0;
}

export function staleOverlay(nowMs, lastOverlayAt) {
  return nowMs - lastOverlayAt > STALE_MS;
}

// Voix en sortie : lecture fr-FR, débit 1,0 (APP-R7.1).
export const VALIDATION_PHRASE = "C'est bon.";

export function pickFrenchVoice(voices) {
  const list = [...(voices || [])];
  return list.find((v) => v.lang === "fr-FR") || list.find((v) => (v.lang || "").startsWith("fr")) || null;
}

// Statut voix du serveur : texte affiché, ou null si tout va bien (VOX-R3.2).
export function voiceStatusText(status) {
  if (status === "on") return null;
  return VOICE_MESSAGE;
}

// Un nouveau `say` interrompt la lecture en cours, sauf la validation (APP-R7.2).
export function shouldInterruptSay(currentText) {
  return currentText !== VALIDATION_PHRASE;
}
