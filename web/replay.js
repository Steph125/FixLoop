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
