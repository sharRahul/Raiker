/**
 * Voice spec §5.1 — is anyone speaking? Silero VAD v5, in the page.
 *
 * The model is the MIT-licensed Silero VAD v5 ONNX file shipped with Raiker
 * (`public/voice/silero_vad.onnx`, its digest checked by a backend test), run
 * with onnxruntime-web's WebAssembly backend on one thread. Silence never
 * leaves the page: only the utterances it finds are sent anywhere.
 *
 * Two parts:
 * - {@link SileroVad} turns one 32 ms frame (512 samples at 16 kHz) into a
 *   speech probability, carrying the model's recurrent state and 64-sample
 *   context between frames exactly as upstream's `OnnxWrapper` does.
 * - {@link createSegmenter} turns probabilities into utterances: speech starts
 *   after 64 ms above 0.5, ends after the owner's end-of-speech silence, keeps
 *   300 ms of pre-roll so first syllables are not cut, and caps an utterance.
 */
export const SAMPLE_RATE = 16_000;
export const FRAME_SAMPLES = 512;
export const FRAME_MS = (FRAME_SAMPLES / SAMPLE_RATE) * 1000;
const CONTEXT_SAMPLES = 64;

type Ort = typeof import("onnxruntime-web");

export interface SpeechProbability {
  probability(frame: Float32Array): Promise<number>;
  reset(): void;
}

export class SileroVad implements SpeechProbability {
  private state: Float32Array = new Float32Array(2 * 128);
  private context: Float32Array = new Float32Array(CONTEXT_SAMPLES);

  private constructor(
    private readonly ort: Ort,
    private readonly session: import("onnxruntime-web").InferenceSession,
  ) {}

  /** Load the bundled model. `wasmPaths` points onnxruntime at Raiker's own copy of its WebAssembly. */
  static async load(
    modelUrl: string,
    options: { ort?: Ort; wasmPaths?: Record<string, string> } = {},
  ): Promise<SileroVad> {
    const ort = options.ort ?? (await import("onnxruntime-web/wasm"));
    ort.env.wasm.numThreads = 1;
    if (options.wasmPaths) ort.env.wasm.wasmPaths = options.wasmPaths;
    const model = await (await fetch(modelUrl)).arrayBuffer();
    const session = await ort.InferenceSession.create(new Uint8Array(model), { executionProviders: ["wasm"] });
    return new SileroVad(ort, session);
  }

  /** For a model already in memory (tests, Node). */
  static async fromBytes(ort: Ort, model: Uint8Array): Promise<SileroVad> {
    ort.env.wasm.numThreads = 1;
    const session = await ort.InferenceSession.create(model, { executionProviders: ["wasm"] });
    return new SileroVad(ort, session);
  }

  reset(): void {
    this.state = new Float32Array(2 * 128);
    this.context = new Float32Array(CONTEXT_SAMPLES);
  }

  async probability(frame: Float32Array): Promise<number> {
    if (frame.length !== FRAME_SAMPLES) throw new Error("vad_frame_size");
    const input = new Float32Array(CONTEXT_SAMPLES + FRAME_SAMPLES);
    input.set(this.context, 0);
    input.set(frame, CONTEXT_SAMPLES);
    const feeds = {
      input: new this.ort.Tensor("float32", input, [1, input.length]),
      state: new this.ort.Tensor("float32", this.state, [2, 1, 128]),
      sr: new this.ort.Tensor("int64", BigInt64Array.from([BigInt(SAMPLE_RATE)]), []),
    };
    const out = await this.session.run(feeds);
    const names = this.session.outputNames;
    const probability = (out[names[0]].data as Float32Array)[0];
    this.state = Float32Array.from(out[names[1]].data as Float32Array);
    this.context = input.slice(input.length - CONTEXT_SAMPLES);
    return probability;
  }
}

export interface SegmenterOptions {
  /** End of speech after this much silence (spec: 500 ms default, 250–1500). */
  endSilenceMs?: number;
  startThreshold?: number;
  endThreshold?: number;
  /** Speech must last this long before it counts (64 ms). */
  minSpeechMs?: number;
  preRollMs?: number;
  /** An utterance is cut here (30 s in conversation). */
  maxUtteranceMs?: number;
}

export interface Segmenter {
  /** Feed one frame and its probability; returns what happened. */
  push(frame: Float32Array, probability: number): { started: boolean; utterance: Float32Array | null };
  readonly speaking: boolean;
  reset(): void;
}

export function createSegmenter(options: SegmenterOptions = {}): Segmenter {
  const startThreshold = options.startThreshold ?? 0.5;
  const endThreshold = options.endThreshold ?? 0.35;
  const startFrames = Math.max(1, Math.round((options.minSpeechMs ?? 64) / FRAME_MS));
  const endFrames = Math.max(1, Math.round((options.endSilenceMs ?? 500) / FRAME_MS));
  const preRollFrames = Math.round((options.preRollMs ?? 300) / FRAME_MS);
  const maxFrames = Math.round((options.maxUtteranceMs ?? 30_000) / FRAME_MS);

  let preRoll: Float32Array[] = [];
  let collected: Float32Array[] = [];
  let speaking = false;
  let above = 0;
  let below = 0;

  const join = (frames: Float32Array[]) => {
    const out = new Float32Array(frames.length * FRAME_SAMPLES);
    frames.forEach((frame, i) => out.set(frame, i * FRAME_SAMPLES));
    return out;
  };

  return {
    get speaking() {
      return speaking;
    },
    reset() {
      preRoll = [];
      collected = [];
      speaking = false;
      above = 0;
      below = 0;
    },
    push(frame, probability) {
      if (!speaking) {
        preRoll.push(frame);
        if (preRoll.length > preRollFrames + startFrames) preRoll.shift();
        above = probability >= startThreshold ? above + 1 : 0;
        if (above >= startFrames) {
          speaking = true;
          collected = preRoll;
          preRoll = [];
          below = 0;
          return { started: true, utterance: null };
        }
        return { started: false, utterance: null };
      }
      collected.push(frame);
      below = probability < endThreshold ? below + 1 : 0;
      if (below >= endFrames || collected.length >= maxFrames) {
        const utterance = join(collected);
        speaking = false;
        collected = [];
        above = 0;
        below = 0;
        return { started: false, utterance };
      }
      return { started: false, utterance: null };
    },
  };
}
