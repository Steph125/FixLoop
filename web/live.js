// FixLoop : appli téléphone en direct (spec/06-phone-app).
// Module ES, aucune dépendance (APP-R10.1). La logique pure vit dans lib.js.
import { isScreen, makeBikeId, isBikeId, codeRequired, HISTORY_MESSAGE } from "./lib.js";

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

function go(name) {
  return () => showScreen(name);
}

if (typeof document !== "undefined") {
  document.getElementById("btn-start")?.addEventListener("click", go("cadrage"));
  document.getElementById("btn-framed")?.addEventListener("click", go("session"));
  document.getElementById("btn-again")?.addEventListener("click", go("accueil"));
  document.getElementById("btn-retry")?.addEventListener("click", go("accueil"));
  const kept = loadBikeId().kept;
  showHistoryNote(kept);
  checkHealth();
}
