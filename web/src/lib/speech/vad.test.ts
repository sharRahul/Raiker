// @vitest-environment node
/**
 * Silero VAD v5, the real model, on a real speech clip: half a second of
 * silence, about 2.9 s of speech (Kokoro reading a sentence), half a second of
 * silence. The segmenter must find exactly one utterance covering the speech.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import * as ort from "onnxruntime-web";
import { FRAME_SAMPLES, SileroVad, createSegmenter } from "./vad";

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

function samples(): Float32Array {
  const bytes = readFileSync(here("./fixtures/speech-16k.wav"));
  const pcm = new Int16Array(bytes.buffer, bytes.byteOffset + 44, (bytes.length - 44) / 2);
  return Float32Array.from(pcm, (v) => v / 32768);
}

function frames(audio: Float32Array): Float32Array[] {
  const out: Float32Array[] = [];
  for (let i = 0; i + FRAME_SAMPLES <= audio.length; i += FRAME_SAMPLES) out.push(audio.slice(i, i + FRAME_SAMPLES));
  return out;
}

describe("Silero VAD v5", () => {
  it("hears the speech and not the silence around it", async () => {
    const vad = await SileroVad.fromBytes(ort, readFileSync(here("../../../public/voice/silero_vad.onnx")));
    const probabilities: number[] = [];
    for (const frame of frames(samples())) probabilities.push(await vad.probability(frame));
    const leading = probabilities.slice(0, 12);
    const middle = probabilities.slice(30, 80);
    expect(Math.max(...leading)).toBeLessThan(0.3);
    expect(middle.filter((p) => p > 0.5).length).toBeGreaterThan(middle.length * 0.6);

    const segmenter = createSegmenter({ endSilenceMs: 400 });
    const utterances: Float32Array[] = [];
    let starts = 0;
    frames(samples()).forEach((frame, i) => {
      const step = segmenter.push(frame, probabilities[i]);
      if (step.started) starts += 1;
      if (step.utterance) utterances.push(step.utterance);
    });
    expect(starts).toBe(1);
    expect(utterances).toHaveLength(1);
    const seconds = utterances[0].length / 16_000;
    expect(seconds).toBeGreaterThan(2.3);
    expect(seconds).toBeLessThan(3.8);
  }, 30_000);
});

describe("segmenter", () => {
  const frame = () => new Float32Array(FRAME_SAMPLES);

  it("needs 64 ms of speech to start, keeps pre-roll, and ends after the silence", () => {
    const s = createSegmenter({ endSilenceMs: 96, preRollMs: 64, minSpeechMs: 64 });
    expect(s.push(frame(), 0.1).started).toBe(false);
    expect(s.push(frame(), 0.9).started).toBe(false); // one frame is a click, not speech
    expect(s.push(frame(), 0.2).started).toBe(false);
    expect(s.push(frame(), 0.9).started).toBe(false);
    expect(s.push(frame(), 0.9).started).toBe(true);
    expect(s.speaking).toBe(true);
    s.push(frame(), 0.9);
    s.push(frame(), 0.1);
    s.push(frame(), 0.1);
    const end = s.push(frame(), 0.1);
    expect(end.utterance).not.toBeNull();
    // pre-roll (2 frames + 2 start frames, capped) + the speech and silence after it
    expect(end.utterance!.length / FRAME_SAMPLES).toBeGreaterThanOrEqual(5);
    expect(s.speaking).toBe(false);
  });

  it("cuts an utterance at the cap", () => {
    const s = createSegmenter({ maxUtteranceMs: 320, minSpeechMs: 32 });
    s.push(frame(), 0.9);
    let cut: Float32Array | null = null;
    for (let i = 0; i < 20 && cut === null; i += 1) cut = s.push(frame(), 0.9).utterance;
    expect(cut).not.toBeNull();
  });
});
