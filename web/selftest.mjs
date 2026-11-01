// FixLoop : vérifications de lib.js, sans DOM (APP-T10).
// Même contenu que web/selftest.html : `node web/selftest.mjs` hors navigateur.
import { SCREENS, isScreen, errorMessage, wordCount, ERROR_MESSAGES, makeBikeId, isBikeId, codeRequired, cameraConstraints, startMessage, helloMessage, userDoneMessage, commandMessage, speakingMessage, pauseMessage, resumeMessage, stopMessage, backoffDelay, screenFor, packBinary, imageTargetSize, MSG_IMAGE, MAX_SEND_WIDTH, JPEG_QUALITY,
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

check("contraintes caméra (APP-R1.2, R1.4)", () => {
  const full = cameraConstraints(true);
  if (full.video.facingMode.ideal !== "environment") throw new Error("arrière");
  if (full.audio.channelCount !== 1) throw new Error("micro");
  const muted = cameraConstraints(false);
  if (muted.audio !== false) throw new Error("relance sans micro");
});

check("messages de contrôle (APP-T4)", () => {
  const hello = helloMessage("b-1234abcd", null, null);
  if (hello.type !== "hello" || hello.bike_id !== "b-1234abcd") throw new Error("hello");
  if ("access_code" in hello) throw new Error("code vide");
  const helloCode = helloMessage("b-1234abcd", "sésame", { ua: "t" });
  if (helloCode.access_code !== "sésame") throw new Error("code");
  if (userDoneMessage(11500).t_ms !== 11500) throw new Error("user_done");
  const cmd = commandMessage("help", 12000);
  if (cmd.cmd !== "help" || cmd.t_ms !== 12000) throw new Error("command");
  if (speakingMessage(true, 1).on !== true) throw new Error("speaking");
  if (pauseMessage().type !== "pause" || resumeMessage().type !== "resume") throw new Error("pause");
  if (stopMessage().type !== "stop") throw new Error("stop");
});

check("reconnexions 1 s, 2 s, 4 s (APP-R9.3)", () => {
  if (backoffDelay(0) !== 1000 || backoffDelay(1) !== 2000) throw new Error("délais");
  if (backoffDelay(2) !== 4000 || backoffDelay(9) !== 4000) throw new Error("plafond");
});

check("choix d'écran par message (APP-R8)", () => {
  if (screenFor({ type: "closed" }, "session") !== "fin") throw new Error("closed");
  if (screenFor({ type: "error" }, "session") !== "erreur") throw new Error("error");
  if (screenFor({ type: "highlight", color: "red" }, "session") !== "anomalie") throw new Error("rouge");
  if (screenFor({ type: "highlight", color: "blue" }, "anomalie") !== "session") throw new Error("bleu");
  if (screenFor({ type: "state" }, "session") !== null) throw new Error("state");
  if (screenFor({ type: "say" }, "cadrage") !== "session") throw new Error("say");
  if (screenFor(null, "session") !== null) throw new Error("invalide");
});

check("packBinary : en-tête SRV-R3.2 (APP-R2.2)", () => {
  const payload = new Uint8Array([10, 20, 30]);
  const buf = packBinary(MSG_IMAGE, 11500, payload);
  if (buf.length !== 12) throw new Error("longueur");
  if (buf[0] !== 0x02) throw new Error("marqueur");
  const t = new DataView(buf.buffer).getBigUint64(1, false);
  if (t !== 11500n) throw new Error("horodatage");
  if (buf[9] !== 10 || buf[11] !== 30) throw new Error("données");
});

check("taille d'image 848 px (APP-R2.2)", () => {
  const big = imageTargetSize(1920, 1080);
  if (big.w !== 848 || big.h !== 477) throw new Error(`paysage : ${big.w}x${big.h}`);
  const small = imageTargetSize(400, 300);
  if (small.w !== 400 || small.h !== 300) throw new Error("petite gardée");
  const tall = imageTargetSize(1080, 1920);
  if (tall.w !== 848 || tall.h !== Math.round(1920 * 848 / 1080)) throw new Error("portrait");
  if (JPEG_QUALITY !== 0.7 || MAX_SEND_WIDTH !== 848) throw new Error("constantes");
});

check("message start (APP-R3.2)", () => {
  if (startMessage().type !== "start") throw new Error("start");
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
