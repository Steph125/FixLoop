// FixLoop : vérifications de lib.js, sans DOM (APP-T10).
// Même contenu que web/selftest.html : `node web/selftest.mjs` hors navigateur.
import { SCREENS, isScreen, errorMessage, wordCount, ERROR_MESSAGES, makeBikeId, isBikeId, codeRequired, cameraConstraints, startMessage, helloMessage, userDoneMessage, commandMessage, speakingMessage, pauseMessage, resumeMessage, stopMessage, backoffDelay, screenFor, packBinary, imageTargetSize, MSG_AUDIO, MSG_IMAGE, MAX_SEND_WIDTH, JPEG_QUALITY, STALE_MS, GREEN_MS, partColor, formatMeasure, verdictLabel, stepLabel, stateAt, staleOverlay, pickFrenchVoice, shouldInterruptSay, VALIDATION_PHRASE, voiceStatusText,
  CAMERA_MESSAGE, HISTORY_MESSAGE, VOICE_MESSAGE } from "./lib.js";
import { frameSize, stateAt as replayStateAt, nearestFrame, contactLabel, validatedFlash, nextSpeed, stepBanner, timelineItems, eventDetail, curveGeometry, cursorX, honestyText, linksFor, relabelFrames, filmedDate, loadLinks, REPO_URL } from "./replay.js";

const checks = [];

function check(name, fn) {
  checks.push([name, fn]);
}

check("replay : taille de la vidéo lue dans overlays.json", () => {
  const got = frameSize({ w: 848, h: 464, frames: [{ t: 0 }] });
  if (got.w !== 848 || got.h !== 464) throw new Error(JSON.stringify(got));
  const repli = frameSize(null);
  if (repli.w !== 400 || repli.h !== 400) throw new Error(JSON.stringify(repli));
});

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
  const pcm = new Int16Array([256, -1]); // sortie du worklet
  const buf2 = packBinary(MSG_AUDIO, 80, pcm);
  if (buf2[0] !== 0x01 || buf2.length !== 13) throw new Error("marqueur audio");
  const view = new DataView(buf2.buffer, buf2.byteOffset + 9, 4);
  if (view.getInt16(0, true) !== 256 || view.getInt16(2, true) !== -1) {
    throw new Error("octets petit-boutistes");
  }
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

check("surimpression : couleurs et mesure (APP-R5)", () => {
  if (partColor("chain", ["chain"], 0, 1000) !== "red") throw new Error("rouge");
  if (partColor("chain", [], 2000, 1000) !== "green") throw new Error("vert");
  if (partColor("chain", [], 500, 1000) !== "blue") throw new Error("bleu");
  if (formatMeasure(0.09, "en place") !== "contact 0,09 · en place") throw new Error("mesure");
  if (formatMeasure(NaN, "non vu") !== "non vu") throw new Error("non vu");
  if (formatMeasure(null, "non vu") !== "non vu") throw new Error("nul");
  if (verdictLabel("1") !== "validée" || verdictLabel("eps") !== "anomalie") throw new Error("verdict");
  if (verdictLabel("?") !== "incertain" || verdictLabel("0") !== "en cours") throw new Error("verdict");
  if (stepLabel({ step: { index: 2, count: 4, instruction: "Pose la chaîne." } }) !== "Étape 2/4 · Pose la chaîne.") {
    throw new Error("bandeau");
  }
  if (stepLabel({}) !== "") throw new Error("sans étape");
  if (stateAt({ t: 31.5 }) !== 31.5 || stateAt({}) !== 0) throw new Error("instant");
  if (!staleOverlay(4000, 500) || staleOverlay(2500, 500)) throw new Error("estompage");
  if (STALE_MS !== 3000 || GREEN_MS !== 1000) throw new Error("constantes");
});

check("voix en sortie (APP-R7)", () => {
  const voices = [{ lang: "en-US", name: "Alex" }, { lang: "fr-FR", name: "Marie" }];
  if (pickFrenchVoice(voices)?.name !== "Marie") throw new Error("fr-FR");
  if (pickFrenchVoice([{ lang: "fr-CA", name: "Jo" }])?.name !== "Jo") throw new Error("fr");
  if (pickFrenchVoice([]) !== null) throw new Error("aucune");
  if (shouldInterruptSay("Tu poses ta chaîne sur le bord noir.")) {
    // interrompt : ok
  } else {
    throw new Error("interruption");
  }
  if (shouldInterruptSay("C'est bon.")) throw new Error("validation coupée");
  if (VALIDATION_PHRASE !== "C'est bon.") throw new Error("validation");
  if (voiceStatusText("on") !== null) throw new Error("micro actif");
  if (voiceStatusText("off") !== "Commande vocale indisponible") throw new Error("repli");
  if (voiceStatusText("error") !== "Commande vocale indisponible") throw new Error("erreur");
});

check("worklet : rééchantillonnage 24 kHz (APP-T8)", async () => {
  if (typeof globalThis.AudioWorkletProcessor === "undefined") {
    globalThis.AudioWorkletProcessor = class {
      constructor() { this.port = { postMessage() {} }; }
    };
  }
  if (typeof globalThis.registerProcessor === "undefined") {
    globalThis.registerProcessor = () => {};
  }
  const worklet = await import("./audio-worklet.js");
  if (worklet.OUT_RATE !== 24000 || worklet.FRAME_SAMPLES !== 1920) {
    throw new Error("constantes");
  }
  const half = worklet.resampleFrame(new Float32Array(480).fill(0.5), 48000);
  if (half.length !== 240) throw new Error("longueur");
  if (Math.abs(half[0] - 16384) > 2) throw new Error("amplitude");
  if (worklet.resampleFrame(new Float32Array(0), 48000).length !== 0) throw new Error("vide");
  const posted = [];
  const node = new worklet.CaptureProcessor();
  node.port = { postMessage: (frame) => posted.push(frame) };
  globalThis.sampleRate = 48000;
  try {
    for (let i = 0; i < 30; i++) node.process([[new Float32Array(128).fill(0.25)]]);
  } finally {
    delete globalThis.sampleRate;
  }
  if (posted.length !== 1 || posted[0].length !== 1920) {
    throw new Error(`trames : ${posted.length}`);
  }
  if (Math.abs(posted[0][0] - 8192) > 2) throw new Error("contenu");
});

check("texte caméra exact (APP-R1.3)", () => {
  if (CAMERA_MESSAGE !== "FixLoop a besoin de la caméra pour vérifier ta réparation") {
    throw new Error(CAMERA_MESSAGE);
  }
});

check("replay : état rejoué (RPL-T5)", () => {
  const events = [
    { t: 0, event: "step", step: "frame_view" },
    { t: 1, event: "say", text: "Place le téléphone." },
    { t: 2, event: "highlight", parts: ["chain"], color: "red" },
    { t: 3, event: "step", step: "engage_top_teeth" },
  ];
  const a = replayStateAt(events, 0.5);
  if (a.step !== "frame_view" || a.say !== null) throw new Error("début");
  const b = replayStateAt(events, 2.5);
  if (b.say !== "Place le téléphone.") throw new Error("sous-titre");
  if (b.highlight.chain !== "red") throw new Error("couleur");
  if (replayStateAt(events, 3).step !== "engage_top_teeth") throw new Error("étape");
});

check("replay : image la plus proche (RPL-T5)", () => {
  const frames = [{ t: 0 }, { t: 0.2 }, { t: 0.4 }];
  if (nearestFrame(frames, 0.29).t !== 0.2) throw new Error("0.29");
  if (nearestFrame(frames, 9).t !== 0.4) throw new Error("fin");
  if (nearestFrame([], 1) !== null) throw new Error("vide");
});

check("replay : seuils de contact (RPL-T5)", () => {
  if (contactLabel(0.18) !== "en place") throw new Error("0,18");
  if (contactLabel(0.26) !== "tombée") throw new Error("0,26");
  if (contactLabel(0.22) !== "incertain") throw new Error("0,22");
  if (contactLabel(NaN) !== "non vu") throw new Error("NaN");
});

check("replay : validation et vitesses (RPL-T5)", () => {
  const events = [{ t: 2, event: "validated" }];
  if (!validatedFlash(events, 2.5)) throw new Error("vert");
  if (validatedFlash(events, 3.5)) throw new Error("éteint");
  if (nextSpeed(1) !== 2 || nextSpeed(2) !== 0.5 || nextSpeed(0.5) !== 1) {
    throw new Error("vitesses");
  }
  const meta = { steps: [{ id: "a", instruction: "Cadre." }, { id: "b", instruction: "Pose." }] };
  if (stepBanner(meta, "b") !== "Étape 2/2 · Pose.") throw new Error("bandeau");
  if (stepBanner(meta, "z") !== "") throw new Error("inconnu");
});

check("replay : frise et détail (RPL-T6)", () => {
  const events = [
    { t: 0, event: "diagnose", procedure: "chain_off_chainring", model: "muse-spark-1.3" },
    { t: 1, event: "user_done" },
    { t: 2, event: "anomaly", step: "engage_top_teeth", message: "Tu poses mal.",
      source: "rule", evidence: { contact: { "chain/chainring": 0.344 } }, model: "sam-3.1" },
    { t: 3, event: "validated", step: "engage_top_teeth", model: "sam-3.1" },
    { t: 4, event: "say", text: "C'est bon." },
  ];
  const items = timelineItems(events);
  if (items.length !== 4) throw new Error(`frise : ${items.length}`);
  if (!items[0].label.includes("Diagnostic")) throw new Error("diagnostic");
  if (!items[1].label.includes("c'est fait")) throw new Error("done");
  const detail = eventDetail(events[2]);
  if (detail.model !== "SAM 3.1") throw new Error("modèle");
  if (!detail.lines.some((l) => l.includes("0,344"))) throw new Error("preuve");
  const closed = eventDetail({ t: 5, event: "closed", success: true });
  if (!closed.title.includes("Clôture")) throw new Error("clôture");
});

check("replay : courbe du contact (RPL-T6)", () => {
  const frames = [{ t: 0, contact: 0.34 }, { t: 1, contact: 0.09 }, { t: 2, contact: null }];
  const g = curveGeometry(frames, 300, 80, 2);
  if (g.points.length !== 2) throw new Error("points");
  if (!(g.onY > g.offY)) throw new Error("seuils"); // 0,18 en bas, 0,26 en haut
  if (cursorX(1, 300, 2) !== 150) throw new Error("curseur");
  if (g.d === "") throw new Error("tracé");
});

check("replay : honnêteté et liens (RPL-T7)", async () => {
  const meta = { filmed: "2026-10-31", source: "video",
    mode: "vidéo 10 images/s, anti-rebond 4 (RPL-R5.2)",
    bike_id: "demo-velo", demo_history: false, name: "vid-A" };
  const banner = honestyText(meta);
  if (!banner.includes("Replay d'une session réelle, filmée le")) throw new Error("RPL-R5.1");
  if (!banner.includes("31 octobre 2026")) throw new Error(`date : ${banner}`);
  if (!banner.includes("calculées par FixLoop")) throw new Error("calcul");
  if (!banner.includes("celles obtenues le ")) throw new Error("modèles");
  if (!banner.includes("10 images/s")) throw new Error("mode RPL-R5.2");
  const syn = honestyText({ source: "synthetic", mode: meta.mode, demo_history: true });
  if (!syn.includes("Session synthétique de test")) throw new Error("synthétique");
  if (!syn.includes("démonstration")) throw new Error("historique RPL-R5.3");
  if (filmedDate(null) !== "date inconnue") throw new Error("date inconnue");
  const index = [{ name: "vid-A", title: "A" }, { name: "vid-B", title: "B" }];
  const full = linksFor(meta, index,
    { repo: REPO_URL, benchmark: "https://example.invalid/rapport", video: "https://example.invalid/video" });
  if (!full.some((l) => l.text === "Dépôt GitHub" && l.href === REPO_URL)) throw new Error("dépôt");
  if (!full.some((l) => l.text === "Rapport du benchmark")) throw new Error("rapport");
  if (!full.some((l) => l.text === "Vidéo de démonstration")) throw new Error("vidéo");
  if (full.some((l) => l.text === "Direct")) throw new Error("direct absent affiché");
  if (!full.some((l) => l.href.includes("?session=vid-B"))) throw new Error("brève B");
  if (full.some((l) => l.href.includes("?session=vid-A"))) throw new Error("soi-même");
  const bare = linksFor(meta, index, {});
  if (!bare.some((l) => l.href === REPO_URL)) throw new Error("repli dépôt");
  if (bare.some((l) => l.text === "Rapport du benchmark")) throw new Error("rapport absent affiché");
  const got = await loadLinks(async (p) => {
    if (p === "build/links.json") return { json: async () => ({ repo: REPO_URL }) };
    throw new Error(`chemin inattendu : ${p}`);
  });
  if (got.repo !== REPO_URL) throw new Error("links.json");
  const missing = await loadLinks(async () => { throw new Error("404"); });
  if (Object.keys(missing).length !== 0) throw new Error("repli sans liens");
});

check("replay : seuils simulés (RPL-T10)", () => {
  const frames = [{ t: 0, contact: 0.22 }, { t: 1, contact: 0.3 }];
  const relabeled = relabelFrames(frames, 0.25, 0.26);
  if (relabeled[0].label !== "en place") throw new Error("0,22 < 0,25");
  if (relabeled[1].label !== "tombée") throw new Error("0,3 >= 0,26");
  if (frames[0].label !== undefined) throw new Error("copie, pas mutation");
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
