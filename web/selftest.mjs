// FixLoop : vérifications de lib.js, sans DOM (APP-T10).
// Même contenu que web/selftest.html : `node web/selftest.mjs` hors navigateur.
import { SCREENS, isScreen, errorMessage, wordCount, ERROR_MESSAGES, makeBikeId, isBikeId, codeRequired,
  CAMERA_MESSAGE, HISTORY_MESSAGE, VOICE_MESSAGE } from "./lib.js";

const checks = [];

function check(name, fn) {
  checks.push([name, fn]);
}

// --- APP-T1 : écrans et libellés ---
check("six écrans dans l'ordre", () => {
  const want = ["accueil", "cadrage", "session", "anomalie", "fin", "erreur"];
  if (JSON.stringify(SCREENS) !== JSON.stringify(want)) throw new Error(SCREENS.join(","));
});

check("écran inconnu refusé", () => {
  if (!isScreen("session") || isScreen("replay")) throw new Error("isScreen");
});

check("messages d'erreur connus", () => {
  if (errorMessage("access_denied") !== "Code incorrect") throw new Error("denied");
  if (!errorMessage("busy").includes("quelques minutes")) throw new Error("busy");
  if (!errorMessage("budget").includes("replay")) throw new Error("budget");
  if (errorMessage("api_key") !== "Problème du serveur.") throw new Error("api_key");
  if (errorMessage("code_inconnu") !== "Problème du serveur.") throw new Error("défaut");
});

check("textes utilisateur courts (≤ 20 mots)", () => {
  const texts = [...Object.values(ERROR_MESSAGES), CAMERA_MESSAGE, HISTORY_MESSAGE, VOICE_MESSAGE];
  for (const t of texts) {
    if (wordCount(t) > 20) throw new Error(`trop long : ${t}`);
  }
});

check("bike_id : format et validation (APP-R6)", () => {
  if (makeBikeId("1a2b3c4d") !== "b-1a2b3c4d") throw new Error("makeBikeId");
  if (!isBikeId("b-1a2b3c4d")) throw new Error("valide refusé");
  for (const bad of ["Vélo!", "ab", "b-xyz!", "", "c-1a2b3c4d"]) {
    if (isBikeId(bad)) throw new Error(`accepté : ${bad}`);
  }
});

check("champ de code selon la santé (APP-R1.5)", () => {
  if (!codeRequired({ access_code_required: true })) throw new Error("exigé");
  if (codeRequired({ access_code_required: false })) throw new Error("non exigé");
  if (codeRequired(null)) throw new Error("santé inconnue");
});

check("texte caméra exact (APP-R1.3)", () => {
  if (CAMERA_MESSAGE !== "FixLoop a besoin de la caméra pour vérifier ta réparation") {
    throw new Error(CAMERA_MESSAGE);
  }
});

export async function runAll() {
  const lines = [];
  let ok = 0;
  for (const [name, fn] of checks) {
    try {
      await fn();
      lines.push(`ok - ${name}`);
      ok += 1;
    } catch (e) {
      lines.push(`KO - ${name} : ${e.message}`);
    }
  }
  lines.push(`${ok}/${checks.length} vérifications passées`);
  return lines;
}

if (typeof process !== "undefined" && process.argv?.[1]?.endsWith("selftest.mjs")) {
  runAll().then((lines) => {
    console.log(lines.join("\n"));
    if (lines.some((l) => l.startsWith("KO"))) process.exit(1);
  });
}
