// FixLoop : lecteur de replay (spec/07-replay-mode, RPL-T5).
// Modules ES, aucune dépendance (APP-R10.1, RPL-R1.4). La logique pure est
// testée sans DOM dans `web/selftest.mjs` (miroir `web/selftest.html`).

// État affiché à l'instant t : rejeu des événements (design 07, section 4).
// Miroir de `state_at` (`replay/build_replay.py`), testé à l'identique.
export function stateAt(events, t) {
  const out = { step: null, say: null, highlight: {} };
  for (const e of events) {
    if ((e.t || 0) > t + 1e-9) break;
    if (e.event === "step") out.step = e.step;
    else if (e.event === "say") out.say = e.text;
    else if (e.event === "highlight") {
      for (const part of e.parts || []) out.highlight[part] = e.color || "blue";
    }
  }
  return out;
}

// Image d'overlay la plus proche de t (recherche dichotomique).
export function nearestFrame(frames, t) {
  let lo = 0;
  let hi = frames.length - 1;
  if (hi < 0) return null;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid].t <= t + 1e-9) lo = mid;
    else hi = mid - 1;
  }
  if (lo + 1 < frames.length) {
    const a = Math.abs(frames[lo].t - t);
    const b = Math.abs(frames[lo + 1].t - t);
    if (b < a - 1e-9) return frames[lo + 1];
  }
  return frames[lo];
}

// Interprétation d'un contact (mêmes seuils que le direct, RPL-R4.4).
export function contactLabel(contact, onMax = 0.18, offMin = 0.26) {
  if (typeof contact !== "number" || !Number.isFinite(contact)) return "non vu";
  if (contact <= onMax) return "en place";
  if (contact >= offMin) return "tombée";
  return "incertain";
}

// Validation récente : contours verts pendant 1 s (comme l'appli).
export function validatedFlash(events, t) {
  return events.some((e) => e.event === "validated" && e.t <= t + 1e-9 && e.t > t - 1);
}

// Vitesses : ×0,5 / ×1 / ×2 (RPL-R4.5).
export const SPEEDS = [0.5, 1, 2];

export function nextSpeed(s) {
  return SPEEDS[(SPEEDS.indexOf(s) + 1) % SPEEDS.length] || 1;
}

export const app = {
  index: [],
  meta: null,
  events: [],
  frames: [],
  current: -1,
  speed: 1,
  sound: false,
  spokenUntil: -1,
  video: null,
  svg: null,
};

export function stepBanner(meta, stepId) {
  const steps = (meta && meta.steps) || [];
  const k = steps.findIndex((s) => s.id === stepId);
  if (k < 0) return "";
  return `Étape ${k + 1}/${steps.length} · ${steps[k].instruction}`;
}

export async function loadSession(name, fetchFn = fetch) {
  const get = async (p) => (await fetchFn(p)).json();
  const meta = await get(`build/${name}/meta.json`);
  const events = await get(`build/${name}/events.json`);
  const overlays = await get(`build/${name}/overlays.json`);
  app.meta = meta;
  app.events = events;
  app.frames = overlays.frames || [];
  app.current = -1;
  app.spokenUntil = -1;
  return meta;
}

export async function loadIndex(fetchFn = fetch) {
  app.index = await (await fetchFn("build/index.json")).json();
  return app.index;
}

// Rendu pour currentTime : contours, bandeau, sous-titre, mesure (RPL-R4.1).
export function render(t) {
  const frame = nearestFrame(app.frames, t);
  const st = stateAt(app.events, t);
  const svg = app.svg;
  if (svg && frame) {
    const colors = {};
    for (const [part, color] of Object.entries(st.highlight)) colors[part] = color;
    if (validatedFlash(app.events, t)) {
      for (const part of Object.keys(frame.parts || {})) colors[part] = "green";
    }
    const w = frame.w || 400;
    const h = frame.h || 400;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.innerHTML = Object.entries(frame.parts || {})
      .map(([part, d]) => `<path d="${d}" fill="none" stroke="${colors[part] || "blue"}" stroke-width="4"/>`)
      .join("");
  }
  const banner = document.getElementById("step-banner");
  if (banner) banner.textContent = stepBanner(app.meta, st.step);
  const subtitle = document.getElementById("subtitle");
  if (subtitle) subtitle.textContent = st.say || "";
  const measure = document.getElementById("measure-line");
  if (measure && frame) {
    const label = frame.label || contactLabel(frame.contact);
    const c = typeof frame.contact === "number" ? frame.contact.toFixed(2).replace(".", ",") : "–";
    measure.textContent = `contact ${c} · ${label}`;
  }
  speakUntil(t);
  moveCursor(t);
  return { frame, state: st };
}

// Voix : lit les phrases franchies, à ×1, coupée par défaut (RPL-R4.5).
export function speakUntil(t) {
  if (!app.sound) return;
  const synth = window.speechSynthesis;
  if (!synth) return;
  const news = app.events.filter((e) => e.event === "say" && e.t <= t + 1e-9 && e.t > app.spokenUntil);
  for (const e of news) {
    const u = new SpeechSynthesisUtterance(e.text);
    u.lang = "fr-FR";
    u.rate = 1.0;
    synth.speak(u);
  }
  if (news.length) app.spokenUntil = t;
}

export function tick() {
  const video = app.video;
  if (!video || video.paused) return;
  render(video.currentTime);
  if (window.requestVideoFrameCallback) video.requestVideoFrameCallback(tick);
  else window.requestAnimationFrame(tick);
}

const TIMELINE_LABELS = {
  diagnose: "Diagnostic",
  step: "Étape",
  user_done: "« c'est fait »",
  command: "Commande",
  anomaly: "Anomalie",
  arbitrate: "Arbitrage",
  validated: "Validée",
  dynamic_start: "Test de rotation",
  closed: "Clôture",
};

// Frise des événements : diagnostic, étapes, « c'est fait », anomalies,
// arbitrages, validations, clôture — chaque point saute à son instant (RPL-R4.2).
export function timelineItems(events) {
  return events
    .filter((e) => Object.hasOwn(TIMELINE_LABELS, e.event))
    .map((e) => {
      let label = TIMELINE_LABELS[e.event];
      if ((e.event === "step" || e.event === "validated" || e.event === "anomaly") && e.step) {
        label = `${label} : ${e.step}`;
      }
      if (e.event === "command" && e.cmd) label = `${label} : ${e.cmd}`;
      if (e.event === "closed") label = e.success ? "Clôture : réussie" : "Clôture : arrêtée";
      return { t: e.t || 0, kind: e.event, label, ref: e };
    });
}

const MODEL_NAMES = {
  "sam-3.1": "SAM 3.1",
  "muse-spark-1.3": "Muse Spark",
  "muse-wonder-1.0": "Muse Wonder",
  "muse-voice-transcribe-1.0": "Muse Voice Transcribe",
};

function contactLine(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const label = contactLabel(value);
  return `contact ${value.toFixed(3).replace(".", ",")} · ${label}`;
}

// Détail d'un événement : modèle Meta concerné et preuve (RPL-R4.3).
export function eventDetail(e) {
  const items = timelineItems([e]);
  const title = items.length ? items[0].label : String(e.event || "événement");
  const model = MODEL_NAMES[e.model] || "Mesure FixLoop";
  const lines = [];
  if (e.step) lines.push(`Étape : ${e.step}`);
  if (e.message) lines.push(e.message);
  const evidence = e.evidence || {};
  for (const [pair, value] of Object.entries(evidence.contact || {})) {
    const line = contactLine(value);
    if (line) lines.push(`${pair} : ${line}`);
  }
  if (typeof evidence.confiance === "number") {
    lines.push(`confiance ${String(evidence.confiance).replace(".", ",")}`);
  }
  if (evidence.verdict_brut) lines.push(`réponse brute : ${evidence.verdict_brut}`);
  if (e.event === "diagnose" && e.procedure) lines.push(`Fiche : ${e.procedure}`);
  if (e.event === "closed") lines.push(e.success ? "Réparation validée." : "Session arrêtée.");
  return { title, model, lines };
}

// Courbe du contact dans le temps, seuils 0,18 / 0,26, curseur (RPL-R4.4).
export function curveGeometry(frames, width, height, duration, onMax = 0.18, offMin = 0.26) {
  const maxC = 0.5;
  const y = (c) => height - Math.min(c, maxC) / maxC * height;
  const x = (t) => (duration > 0 ? t / duration : 0) * width;
  const points = frames
    .filter((f) => typeof f.contact === "number" && Number.isFinite(f.contact))
    .map((f) => ({ x: x(f.t), y: y(f.contact), t: f.t }));
  return {
    points,
    d: points.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" "),
    onY: y(onMax),
    offY: y(offMin),
  };
}

export function cursorX(t, width, duration) {
  return (duration > 0 ? t / duration : 0) * width;
}

export function renderTimeline() {
  const el = document.getElementById("timeline");
  if (!el) return;
  el.innerHTML = "";
  for (const item of timelineItems(app.events)) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = item.label;
    b.setAttribute("role", "listitem");
    b.addEventListener("click", () => {
      seekTo(item.t);
      renderDetail(item.ref);
    });
    el.appendChild(b);
  }
}

export function renderDetail(e) {
  const el = document.getElementById("event-detail");
  if (!el) return;
  const detail = eventDetail(e);
  el.innerHTML = "";
  const h = document.createElement("h3");
  h.textContent = detail.title;
  el.appendChild(h);
  const model = document.createElement("p");
  model.textContent = detail.model;
  el.appendChild(model);
  for (const line of detail.lines) {
    const p = document.createElement("p");
    p.textContent = line;
    el.appendChild(p);
  }
}

export function renderCurve() {
  const el = document.getElementById("curve");
  if (!el || !app.frames.length) return;
  const width = 300;
  const height = 80;
  const duration = Math.max(...app.frames.map((f) => f.t), 0.01);
  const g = curveGeometry(app.frames, width, height, duration);
  el.setAttribute("viewBox", `0 0 ${width} ${height}`);
  el.innerHTML =
    `<line x1="0" y1="${g.onY}" x2="${width}" y2="${g.onY}" stroke="green"/>` +
    `<line x1="0" y1="${g.offY}" x2="${width}" y2="${g.offY}" stroke="red"/>` +
    `<path d="${g.d}" fill="none" stroke="black"/>` +
    `<line id="cursor" x1="0" y1="0" x2="0" y2="${height}" stroke="black"/>`;
  app.curve = { width, duration };
}

export function moveCursor(t) {
  const cursor = document.getElementById("cursor");
  if (cursor && app.curve) {
    const x = cursorX(t, app.curve.width, app.curve.duration);
    cursor.setAttribute("x1", x);
    cursor.setAttribute("x2", x);
  }
}

export function seekTo(t) {
  if (app.video) app.video.currentTime = t;
  render(t);
}

export function onPlayPressed(ev) {
  const video = app.video;
  if (!video) return;
  if (video.paused) {
    video.playbackRate = app.speed;
    video.play();
  } else {
    video.pause();
  }
  if (ev && ev.currentTarget) ev.currentTarget.textContent = video.paused ? "Lecture" : "Pause";
}

export function onSpeedPressed(ev) {
  app.speed = nextSpeed(app.speed);
  if (app.video) app.video.playbackRate = app.speed;
  if (ev && ev.currentTarget) ev.currentTarget.textContent = `×${app.speed}`;
}

export function onSoundPressed(ev) {
  app.sound = !app.sound;
  if (!app.sound && window.speechSynthesis) window.speechSynthesis.cancel();
  else unlockSpeech();
  if (ev && ev.currentTarget) ev.currentTarget.textContent = app.sound ? "Son : oui" : "Son : non";
}

export function unlockSpeech() {
  try {
    const synth = window.speechSynthesis;
    if (!synth) return;
    const u = new SpeechSynthesisUtterance(" ");
    u.volume = 0;
    synth.speak(u);
  } catch {
    // voix indisponible : les sous-titres restent (RPL-R4.5)
  }
}

export async function selectSession(name) {
  await loadSession(name);
  if (app.video) {
    app.video.src = `build/${name}/video.mp4`;
    app.video.playbackRate = app.speed;
  }
  app.spokenUntil = -1;
  renderTimeline();
  renderCurve();
  render(0);
}

export function wire(video, svg) {
  app.video = video;
  app.svg = svg;
  video.addEventListener("play", () => tick());
  video.addEventListener("seeked", () => render(video.currentTime));
  video.addEventListener("timeupdate", () => {
    if (!window.requestVideoFrameCallback) render(video.currentTime);
  });
}
