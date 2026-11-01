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

export function wordCount(text) {
  return String(text).trim().split(/\s+/).filter(Boolean).length;
}
