/* global AudioWorkletProcessor, sampleRate, registerProcessor */
// Voice spec §5.1 — microphone capture at 16 kHz mono, in 32 ms frames.
//
// Runs on the audio thread. Each input block is mixed to mono and resampled
// (linear) to 16 kHz, and every 512 samples are posted to the page as one
// frame with its level. Nothing is kept: a frame is handed over and dropped.
const TARGET_RATE = 16000;
const FRAME = 512;

class RaikerCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / TARGET_RATE;
    this.position = 0;
    this.frame = new Float32Array(FRAME);
    this.filled = 0;
    this.previous = 0;
  }

  process(inputs) {
    const channels = inputs[0];
    if (!channels || channels.length === 0 || channels[0].length === 0) return true;
    const length = channels[0].length;
    const mono = new Float32Array(length);
    for (const channel of channels) for (let i = 0; i < length; i += 1) mono[i] += channel[i] / channels.length;
    // Linear resampling from the context rate to 16 kHz.
    while (this.position < length) {
      const index = Math.floor(this.position);
      const fraction = this.position - index;
      const a = index === 0 ? this.previous : mono[index - 1];
      const b = mono[index];
      this.frame[this.filled++] = a + (b - a) * fraction;
      if (this.filled === FRAME) {
        let sum = 0;
        for (let i = 0; i < FRAME; i += 1) sum += this.frame[i] * this.frame[i];
        this.port.postMessage({ frame: this.frame, level: Math.sqrt(sum / FRAME) });
        this.frame = new Float32Array(FRAME);
        this.filled = 0;
      }
      this.position += this.ratio;
    }
    this.position -= length;
    this.previous = mono[length - 1];
    return true;
  }
}

registerProcessor("raiker-capture", RaikerCapture);
