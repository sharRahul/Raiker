/**
 * Voice spec V2 — a spoken conversation, as a state machine.
 *
 * `idle → listening → hearing → thinking → speaking → listening`
 *
 * - **Push to talk** (ships): frames are collected while the owner holds the
 *   Talk button (or Space); releasing it ends the utterance.
 * - **Hands-free** (Preview, Settings › Voice): Silero VAD finds the end of a
 *   sentence by itself.
 * - **Barge-in**: while Raiker thinks or speaks, speech above threshold for
 *   150 ms stops playback at once, cancels the turn through the normal Stop
 *   path, and becomes the next utterance.
 * - **Approvals** are never given by voice: a turn that needs one stops
 *   speaking, says "I need your OK on screen", and pauses; the approval card
 *   is the ordinary one.
 * - **Errors** are said once and shown once; three in a row end the
 *   conversation.
 *
 * A spoken utterance becomes an ordinary governed turn (`input_mode: spoken`):
 * the transcript the owner sees is exactly what the model gets. Everything
 * reaches the outside through {@link ConversationPorts}, so the machine is
 * tested without a microphone, a model or a speaker.
 */
import { createPlaybackQueue, type AudioPort, type PlaybackQueue } from "./playbackQueue";
import { createSentenceStream } from "./sentences";
import { FRAME_MS, createSegmenter, type Segmenter, type SpeechProbability } from "./vad";

export type OrbState = "idle" | "listening" | "hearing" | "thinking" | "speaking" | "paused";

export const ORB_LABELS: Record<OrbState, string> = {
  idle: "Not listening",
  listening: "Listening",
  hearing: "Hearing you",
  thinking: "Thinking",
  speaking: "Speaking",
  paused: "Paused",
};

export interface Caption {
  id: number;
  who: "owner" | "raiker";
  text: string;
}

export interface TurnHandle {
  /** Resolves when the answer is complete, with its status (`completed`, `needs_approval`, …). */
  done: Promise<{ status: string }>;
  cancel(): void;
}

export interface ConversationPorts {
  startCapture(onFrame: (frame: Float32Array, level: number) => void): Promise<{ stop(): void }>;
  loadVad(): Promise<SpeechProbability>;
  transcribe(utterance: Float32Array): Promise<string>;
  /** Send `text` as a spoken turn; `onText` receives the answer so far as it streams. */
  send(text: string, onText: (answerSoFar: string) => void): TurnHandle;
  synthesise(sentence: string): Promise<Blob>;
  audio: AudioPort;
}

export interface ConversationOptions {
  handsFree: boolean;
  bargeIn: boolean;
  endSilenceMs: number;
}

const BARGE_IN_MS = 150;
const BARGE_IN_THRESHOLD = 0.5;
const MAX_ERRORS = 3;
export const APPROVAL_LINE = "I need your OK on screen.";
export const NOTHING_HEARD = "I couldn't hear anything. Check the microphone.";

export class Conversation {
  state = $state<OrbState>("idle");
  level = $state(0);
  captions = $state<Caption[]>([]);
  error = $state<string | null>(null);
  muted = $state(false);

  private capture: { stop(): void } | null = null;
  private vad: SpeechProbability | null = null;
  private segmenter: Segmenter;
  private queue: PlaybackQueue | null = null;
  private turn: TurnHandle | null = null;
  private pushFrames: Float32Array[] | null = null;
  private bargeFrames = 0;
  private bargeBuffer: Float32Array[] = [];
  private errors = 0;
  private nextCaption = 1;
  private generation = 0;
  private vadBusy: Promise<void> = Promise.resolve();

  constructor(private readonly ports: ConversationPorts, private readonly options: ConversationOptions) {
    this.segmenter = createSegmenter({ endSilenceMs: options.endSilenceMs });
  }

  get active(): boolean {
    return this.state !== "idle";
  }

  async start(): Promise<void> {
    if (this.active) return;
    this.error = null;
    this.errors = 0;
    try {
      if (this.options.handsFree || this.options.bargeIn) this.vad = await this.ports.loadVad();
      this.capture = await this.ports.startCapture((frame, level) => this.onFrame(frame, level));
    } catch {
      this.fail("I can't use the microphone. Allow it for Raiker and try again.", true);
      return;
    }
    this.state = "listening";
  }

  end(): void {
    this.generation += 1;
    this.queue?.stop();
    this.turn?.cancel();
    this.turn = null;
    this.capture?.stop();
    this.capture = null;
    this.pushFrames = null;
    this.segmenter.reset();
    this.vad?.reset();
    this.state = "idle";
    this.level = 0;
  }

  /** Stop Raiker talking without ending the conversation (Stop talking, any key). */
  stopTalking(): void {
    if (this.state !== "speaking" && this.state !== "thinking") return;
    this.generation += 1;
    this.queue?.stop();
    this.turn?.cancel();
    this.turn = null;
    this.state = "listening";
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    if (muted) {
      this.pushFrames = null;
      this.segmenter.reset();
      if (this.state === "hearing") this.state = "listening";
    }
  }

  // ── push to talk ───────────────────────────────────────────────────

  pressTalk(): void {
    if (!this.active || this.muted) return;
    if (this.state === "speaking" || this.state === "thinking") this.stopTalking();
    this.pushFrames = [];
    this.state = "hearing";
  }

  releaseTalk(): void {
    const frames = this.pushFrames;
    this.pushFrames = null;
    if (frames === null) return;
    if (frames.length * FRAME_MS < 200) {
      this.state = "listening";
      return;
    }
    void this.utterance(join(frames));
  }

  // ── frames ─────────────────────────────────────────────────────────

  private onFrame(frame: Float32Array, level: number): void {
    if (this.muted) return;
    this.level = level;
    if (this.pushFrames !== null) {
      this.pushFrames.push(frame);
      return;
    }
    const vad = this.vad;
    if (vad === null) return;
    // Frames are scored one at a time, in order: the model is recurrent.
    this.vadBusy = this.vadBusy.then(async () => {
      const probability = await vad.probability(frame);
      this.scored(frame, probability);
    });
  }

  private scored(frame: Float32Array, probability: number): void {
    if (!this.active || this.muted) return;
    if (this.state === "speaking" || this.state === "thinking") {
      if (!this.options.bargeIn) return;
      this.bargeBuffer.push(frame);
      if (this.bargeBuffer.length > 12) this.bargeBuffer.shift();
      this.bargeFrames = probability >= BARGE_IN_THRESHOLD ? this.bargeFrames + 1 : 0;
      if (this.bargeFrames * FRAME_MS >= BARGE_IN_MS) {
        this.bargeFrames = 0;
        this.stopTalking();
        // The words that interrupted are the start of the next utterance.
        this.segmenter.reset();
        for (const held of this.bargeBuffer) this.segmenter.push(held, 1);
        this.bargeBuffer = [];
        this.state = "hearing";
      }
      return;
    }
    if (!this.options.handsFree) return;
    const step = this.segmenter.push(frame, probability);
    if (step.started) this.state = "hearing";
    if (step.utterance) void this.utterance(step.utterance);
  }

  // ── one exchange ───────────────────────────────────────────────────

  private async utterance(samples: Float32Array): Promise<void> {
    const turn = ++this.generation;
    this.state = "thinking";
    let text: string;
    try {
      text = (await this.ports.transcribe(samples)).trim();
    } catch {
      if (turn === this.generation) this.fail("I couldn't turn that into words. Try again.");
      return;
    }
    if (turn !== this.generation) return;
    if (!text) {
      this.fail(NOTHING_HEARD);
      return;
    }
    this.errors = 0;
    this.caption("owner", text);
    const answer = this.caption("raiker", "");
    const sentences = createSentenceStream();
    const queue = createPlaybackQueue((sentence) => this.ports.synthesise(sentence), this.ports.audio, {
      onSentence: () => {
        if (turn === this.generation) this.state = "speaking";
      },
      onError: () => {
        if (turn === this.generation) this.fail("I couldn't speak the answer. It is on screen.");
      },
    });
    this.queue = queue;
    let handle: TurnHandle;
    try {
      handle = this.ports.send(text, (soFar) => {
        if (turn !== this.generation) return;
        answer.text = soFar;
        for (const sentence of sentences.push(soFar)) queue.enqueue(sentence);
      });
    } catch {
      this.fail("Raiker could not start that turn.");
      return;
    }
    this.turn = handle;
    let status = "failed";
    try {
      status = (await handle.done).status;
    } catch {
      status = "failed";
    }
    if (turn !== this.generation) return;
    this.turn = null;
    if (status === "needs_approval") {
      // Never approved by voice (spec §8.2, §9): stop, say so, and wait.
      queue.stop();
      const notice = createPlaybackQueue((s) => this.ports.synthesise(s), this.ports.audio);
      this.queue = notice;
      notice.enqueue(APPROVAL_LINE);
      this.caption("raiker", APPROVAL_LINE);
      await notice.drained();
      if (turn === this.generation) this.state = "paused";
      return;
    }
    for (const sentence of sentences.finish()) queue.enqueue(sentence);
    await queue.drained();
    if (turn === this.generation && this.active) this.state = "listening";
  }

  /** After an approval was decided on screen, carry on listening. */
  resume(): void {
    if (this.state === "paused") this.state = "listening";
  }

  private caption(who: Caption["who"], text: string): Caption {
    this.captions.push({ id: this.nextCaption++, who, text });
    return this.captions[this.captions.length - 1];
  }

  private fail(message: string, fatal = false): void {
    this.error = message;
    this.errors += 1;
    if (fatal || this.errors >= MAX_ERRORS) {
      this.end();
      return;
    }
    // Said once, shown once, and the conversation goes on listening.
    const said = createPlaybackQueue((s) => this.ports.synthesise(s), this.ports.audio);
    said.enqueue(message);
    this.state = "listening";
  }
}

function join(frames: Float32Array[]): Float32Array {
  const size = frames.reduce((total, frame) => total + frame.length, 0);
  const out = new Float32Array(size);
  let at = 0;
  for (const frame of frames) {
    out.set(frame, at);
    at += frame.length;
  }
  return out;
}
