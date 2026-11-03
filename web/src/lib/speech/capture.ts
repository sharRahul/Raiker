/**
 * Voice spec §5.1, §9 — the microphone, open only while it is shown to be.
 *
 * Echo cancellation and noise suppression are asked for, so Raiker's own voice
 * is not heard as the owner interrupting. Frames arrive at 16 kHz in 512-sample
 * blocks from `public/voice/capture-worklet.js`. `stop()` releases the
 * microphone and closes the audio graph; nothing is recorded to keep.
 */
export interface Capture {
  stop(): void;
}

export interface CaptureHandlers {
  onFrame(frame: Float32Array, level: number): void;
}

export async function startCapture(handlers: CaptureHandlers, workletUrl = assetUrl("voice/capture-worklet.js")): Promise<Capture> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const context = new AudioContext();
  try {
    await context.audioWorklet.addModule(workletUrl);
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    await context.close();
    throw error;
  }
  const source = context.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(context, "raiker-capture");
  node.port.onmessage = (event: MessageEvent<{ frame: Float32Array; level: number }>) =>
    handlers.onFrame(event.data.frame, event.data.level);
  source.connect(node);
  return {
    stop() {
      node.port.onmessage = null;
      source.disconnect();
      node.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      void context.close();
    },
  };
}

/** A file under `public/`, relative to where the app is served (instances included). */
export function assetUrl(path: string): string {
  return new URL(path, document.baseURI).toString();
}

/** 16 kHz mono float samples as a 16-bit WAV clip, for the transcription engine. */
export function wavFromSamples(samples: Float32Array, rate = 16_000): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
