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
