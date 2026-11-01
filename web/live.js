// FixLoop : appli téléphone en direct (spec/06-phone-app).
// Module ES, aucune dépendance (APP-R10.1). La logique pure vit dans lib.js.
import { isScreen } from "./lib.js";

export const app = {
  screen: "accueil",
  ws: null,
  stream: null,
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

function go(name) {
  return () => showScreen(name);
}

if (typeof document !== "undefined") {
  document.getElementById("btn-start")?.addEventListener("click", go("cadrage"));
  document.getElementById("btn-framed")?.addEventListener("click", go("session"));
  document.getElementById("btn-again")?.addEventListener("click", go("accueil"));
  document.getElementById("btn-retry")?.addEventListener("click", go("accueil"));
}
