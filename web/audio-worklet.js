// FixLoop : micro → PCM16 mono 24 kHz, trames de 1 920 échantillons (80 ms).
// (APP-R7.4, VOX-R1.2 : fréquence native de Transcribe, pas de rééchantillonnage côté Meta.)
// Testé pour de vrai : `node web/selftest.mjs` importe ce module avec des
// bouchons (AudioWorkletProcessor, registerProcessor) et rejouent process().

export const OUT_RATE = 24000;
export const FRAME_SAMPLES = 1920; // 80 ms à 24 kHz

// Rééchantillonnage linéaire Float32 [-1, 1] -> PCM16.
export function resampleFrame(input, inRate, outRate = OUT_RATE) {
  const ratio = inRate / outRate;
  const outLen = Math.floor(input.length / ratio);
  const out = new Int16Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const pos = i * ratio;
    const i0 = Math.floor(pos);
    const frac = pos - i0;
    const a = input[i0] || 0;
    const b = input[Math.min(i0 + 1, input.length - 1)] || 0;
    const v = Math.max(-1, Math.min(1, a + (b - a) * frac));
    out[i] = Math.round(v * 32767);
  }
  return out;
}

export function concatInt16(a, b) {
  const out = new Int16Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

class FixLoopCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.kept = new Int16Array(0);
  }

  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input || input.length === 0) return true;
    this.kept = concatInt16(this.kept, resampleFrame(input, sampleRate));
    while (this.kept.length >= FRAME_SAMPLES) {
      const frame = this.kept.slice(0, FRAME_SAMPLES);
      this.kept = this.kept.slice(FRAME_SAMPLES);
      this.port.postMessage(frame, [frame.buffer]);
    }
    return true;
  }
}

export { FixLoopCapture as CaptureProcessor };

if (typeof registerProcessor !== "undefined") {
  registerProcessor("fixloop-capture", FixLoopCapture);
}
