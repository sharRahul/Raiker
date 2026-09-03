export type VoiceInputMode = "typed" | "dictated" | "mixed";
export type SpeechLanguage =
  | "auto"
  | "en"
  | "fr"
  | "de"
  | "hi"
  | "it"
  | "ja"
  | "ko"
  | "pt"
  | "ru"
  | "es"
  | "tr"
  | "uk";

export const speechLanguages: readonly SpeechLanguage[] = [
  "auto", "en", "fr", "de", "hi", "it", "ja", "ko", "pt", "ru", "es", "tr", "uk",
];

export function speechLanguagePreference(value: unknown): SpeechLanguage {
  return typeof value === "string" && (speechLanguages as readonly string[]).includes(value)
    ? value as SpeechLanguage
    : "auto";
}

export interface RecognitionHandlers {
  interim(text: string): void;
  final(text: string): void;
  end(): void;
  error(code: string): void;
  /**
   * Optional, because only the on-device runtime has a second phase to report
   * (BUG-256). The browser streams words as they are heard; a local runtime
   * hears the whole clip and then transcribes it, and a control that still says
   * "Listening…" through that wait is lying about what is happening.
   */
  phase?(phase: RecognitionPhase): void;
}

export type RecognitionPhase = "listening" | "transcribing";

export interface VoiceRecognitionAdapter {
  supported(): boolean;
  start(language: SpeechLanguage, handlers: RecognitionHandlers): void;
  stop(): void;
  abort(): void;
}

type RecognitionResult = ArrayLike<{ transcript: string }> & { isFinal: boolean };
type RecognitionEvent = { resultIndex: number; results: ArrayLike<RecognitionResult> };
type RecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
};
type RecognitionConstructor = new () => RecognitionInstance;

type AudioKind = "recognition" | "playback";
type CleanupReason = "submit" | "route" | "sign-out" | "handoff";

export interface AudioSessionCoordinator {
  startRecognition(ownerId: string, start: () => void, stop: () => void): void;
  startPlayback(ownerId: string, start: () => void, stop: () => void): void;
  release(ownerId: string): void;
  stopAll(reason: CleanupReason): void;
  subscribe(ownerId: string, onOwnershipLost: () => void): () => void;
}

export function createAudioSessionCoordinator(): AudioSessionCoordinator {
  let active: { ownerId: string; kind: AudioKind; stop: () => void } | null = null;
  const subscribers = new Map<string, Set<() => void>>();

  const notify = (ownerId: string) => {
    for (const callback of subscribers.get(ownerId) ?? []) callback();
  };

  const displace = () => {
    const previous = active;
    active = null;
    if (!previous) return;
    previous.stop();
    notify(previous.ownerId);
  };

  const start = (kind: AudioKind, ownerId: string, begin: () => void, stop: () => void) => {
    displace();
    active = { ownerId, kind, stop };
    try {
      begin();
    } catch (error) {
      active = null;
      throw error;
    }
  };

  return {
    startRecognition: (ownerId, begin, stop) => start("recognition", ownerId, begin, stop),
    startPlayback: (ownerId, begin, stop) => start("playback", ownerId, begin, stop),
    release(ownerId) {
      if (active?.ownerId !== ownerId) return;
      const previous = active;
      active = null;
      previous.stop();
    },
    stopAll() {
      displace();
    },
    subscribe(ownerId, callback) {
      const ownerSubscribers = subscribers.get(ownerId) ?? new Set<() => void>();
      ownerSubscribers.add(callback);
      subscribers.set(ownerId, ownerSubscribers);
      return () => {
        ownerSubscribers.delete(callback);
        if (ownerSubscribers.size === 0) subscribers.delete(ownerId);
      };
    },
  };
}

export const audioSessionCoordinator = createAudioSessionCoordinator();

export function resolveSpeechLanguage(preference: SpeechLanguage, deviceLanguage: string): string {
  if (preference !== "auto") return preference;
  return deviceLanguage.trim() || "en";
}

export function createRecognitionAdapter(Recognition: RecognitionConstructor | undefined): VoiceRecognitionAdapter {
  let current: RecognitionInstance | null = null;
  return {
    supported: () => Recognition !== undefined,
    start(language, handlers) {
      if (!Recognition) throw new Error("speech_recognition_unavailable");
      current?.abort();
      const recognition = new Recognition();
      current = recognition;
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = resolveSpeechLanguage(language, globalThis.navigator?.language ?? "");
      recognition.onresult = (event) => {
        const interim: string[] = [];
        const final: string[] = [];
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index];
          const transcript = result?.[0]?.transcript?.trim();
          if (!transcript) continue;
          (result.isFinal ? final : interim).push(transcript);
        }
        if (interim.length) handlers.interim(interim.join(" "));
        if (final.length) handlers.final(final.join(" "));
      };
      recognition.onerror = (event) => handlers.error(event.error);
      recognition.onend = () => {
        if (current === recognition) current = null;
        handlers.end();
      };
      recognition.start();
    },
    stop() {
      current?.stop();
    },
    abort() {
      current?.abort();
    },
  };
}

function browserRecognitionConstructor(): RecognitionConstructor | undefined {
  if (typeof window === "undefined") return undefined;
  const speechWindow = window as typeof window & {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
}

let activeBrowserRecognition: VoiceRecognitionAdapter | null = null;

export const browserRecognitionAdapter: VoiceRecognitionAdapter = {
  supported: () => browserRecognitionConstructor() !== undefined,
  start(language, handlers) {
    activeBrowserRecognition?.abort();
    activeBrowserRecognition = createRecognitionAdapter(browserRecognitionConstructor());
    activeBrowserRecognition.start(language, handlers);
  },
  stop() {
    activeBrowserRecognition?.stop();
  },
  abort() {
    activeBrowserRecognition?.abort();
  },
};

type PlaybackHandlers = { end(): void; error(): void };
type SpeechUtterance = {
  text: string;
  lang: string;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};
type SpeechSynth = { speak(utterance: SpeechUtterance): void; cancel(): void };

export interface VoicePlayback {
  supported(): boolean;
  speak(ownerId: string, text: string, language: SpeechLanguage, handlers: PlaybackHandlers): void;
  stop(): void;
}

function makeUtterance(text: string): SpeechUtterance {
  if (typeof SpeechSynthesisUtterance !== "undefined") {
    return new SpeechSynthesisUtterance(text) as SpeechUtterance;
  }
  return { text, lang: "", onend: null, onerror: null };
}

export function createVoicePlayback(synth: SpeechSynth | undefined): VoicePlayback {
  return {
    supported: () => synth !== undefined,
    speak(_ownerId, text, language, handlers) {
      if (!synth) throw new Error("speech_synthesis_unavailable");
      synth.cancel();
      const utterance = makeUtterance(text);
      utterance.lang = resolveSpeechLanguage(language, globalThis.navigator?.language ?? "");
      utterance.onend = handlers.end;
      utterance.onerror = handlers.error;
      synth.speak(utterance);
    },
    stop() {
      synth?.cancel();
    },
  };
}

export const voicePlayback = createVoicePlayback(
  typeof window === "undefined" ? undefined : window.speechSynthesis as unknown as SpeechSynth,
);

export function inputModeForDraft(state: {
  dictated: boolean;
  typedBefore: boolean;
  editedAfter: boolean;
}): VoiceInputMode {
  if (!state.dictated) return "typed";
  return state.typedBefore || state.editedAfter ? "mixed" : "dictated";
}

export function speechText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " Code block. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\[(?:s|source|citation)\s*\d+\]/gi, "")
    .replace(/^\s{0,3}(?:#{1,6}|>|[-+*]|\d+\.)\s+/gm, "")
    .replace(/[*_~]/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+([.,!?;:])/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

// ── On-device dictation (BUG-256) ────────────────────────────────────────────
//
// Everything else in Raiker can be run entirely on this machine. Dictation was
// the exception: the browser's `SpeechRecognition` sends audio to a speech
// service off the device on Chrome, behind a button that looks local. The
// adapter below records instead, and hands the clip to the owner's own
// transcription runtime through the host.
//
// The clip is converted here rather than sent as-is. `MediaRecorder` produces
// WebM/Opus, and the reference runtime — a plain `whisper-server` built without
// ffmpeg — reads 16 kHz mono WAV and nothing else. Decoding in the page means an
// owner who installed the ordinary build gets a working microphone rather than a
// refusal they would have to diagnose.

/** Interleaved samples down-mixed to one channel. */
export function toMono(channels: Float32Array[]): Float32Array {
  if (channels.length === 0) return new Float32Array(0);
  if (channels.length === 1) return channels[0];
  const mono = new Float32Array(channels[0].length);
  for (let index = 0; index < mono.length; index += 1) {
    let sum = 0;
    for (const channel of channels) sum += channel[index] ?? 0;
    mono[index] = sum / channels.length;
  }
  return mono;
}

/**
 * Linear resampling to `target` Hz.
 *
 * Linear rather than windowed-sinc on purpose: this feeds a speech model, not a
 * listener, and the difference is inaudible to one while the cost is a page
 * that stays responsive on a long dictation.
 */
export function resample(samples: Float32Array, from: number, target: number): Float32Array {
  if (from === target || samples.length === 0) return samples;
  const ratio = from / target;
  const out = new Float32Array(Math.max(1, Math.floor(samples.length / ratio)));
  for (let index = 0; index < out.length; index += 1) {
    const position = index * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, samples.length - 1);
    const weight = position - left;
    out[index] = samples[left] * (1 - weight) + samples[right] * weight;
  }
  return out;
}

/** A 16-bit PCM WAV file, which is the one format every runtime here accepts. */
export function encodeWav(samples: Float32Array, rate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const ascii = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(offset + index, text.charCodeAt(index));
    }
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  ascii(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export const TRANSCRIPTION_SAMPLE_RATE = 16_000;

/** What the on-device adapter needs from the page, so it can be tested without one. */
export interface LocalTranscriptionPorts {
  supported(): boolean;
  /** Opens the microphone. Rejects when the owner refuses or none is present. */
  record(): Promise<LocalRecording>;
  /** Converts a recorded clip into the WAV the runtime reads. */
  toWav(clip: Blob): Promise<Blob>;
  /** Hands the clip to the host, which hands it to the owner's runtime. */
  transcribe(wav: Blob, language: SpeechLanguage): Promise<string>;
}

export interface LocalRecording {
  /** Resolves with the recorded audio once `stop` has been called. */
  stop(): Promise<Blob>;
  /** Throw the recording away and release the microphone. */
  cancel(): void;
}

/** Map a failure to the same codes the browser adapter reports, so one handler serves both. */
function localErrorCode(error: unknown): string {
  const name = (error as { name?: string })?.name ?? "";
  if (name === "NotAllowedError" || name === "SecurityError") return "not-allowed";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "audio-capture";
  const reason = (error as { reasonCode?: string | null })?.reasonCode;
  if (typeof reason === "string" && reason) return reason;
  return "network";
}

export function createLocalTranscriptionAdapter(
  ports: LocalTranscriptionPorts,
): VoiceRecognitionAdapter {
  let recording: LocalRecording | null = null;
  let handlers: RecognitionHandlers | null = null;
  let language: SpeechLanguage = "auto";
  let cancelled = false;

  const finish = () => {
    recording = null;
    handlers = null;
  };

  return {
    supported: () => ports.supported(),
    start(chosenLanguage, chosenHandlers) {
      cancelled = false;
      language = chosenLanguage;
      handlers = chosenHandlers;
      chosenHandlers.phase?.("listening");
      void (async () => {
        try {
          const opened = await ports.record();
          if (cancelled) {
            opened.cancel();
            return;
          }
          recording = opened;
        } catch (error) {
          const report = handlers;
          finish();
          report?.error(localErrorCode(error));
        }
      })();
    },
    stop() {
      const active = recording;
      const report = handlers;
      recording = null;
      if (!active) {
        // Stopped before the microphone finished opening. There is nothing to
        // transcribe, and the control has to be told the turn is over or it
        // would sit on "Listening…" for ever.
        cancelled = true;
        finish();
        report?.end();
        return;
      }
      report?.phase?.("transcribing");
      void (async () => {
        try {
          const wav = await ports.toWav(await active.stop());
          const text = await ports.transcribe(wav, language);
          if (cancelled) return;
          if (text) report?.final(text);
          report?.end();
        } catch (error) {
          if (cancelled) return;
          report?.error(localErrorCode(error));
        } finally {
          finish();
        }
      })();
    },
    abort() {
      cancelled = true;
      recording?.cancel();
      finish();
    },
  };
}

/** The real page's implementation of those ports. */
export function browserTranscriptionPorts(
  transcribe: (wav: Blob, language: SpeechLanguage) => Promise<string>,
): LocalTranscriptionPorts {
  return {
    supported() {
      return (
        typeof window !== "undefined" &&
        typeof MediaRecorder !== "undefined" &&
        typeof navigator !== "undefined" &&
        navigator.mediaDevices?.getUserMedia !== undefined
      );
    },
    async record() {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      // Releasing the tracks is what turns the browser's recording indicator
      // off. Leaving them open is how a microphone stays live behind a closed
      // composer, which is the defect ConversationAudioLifecycle guards against.
      const release = () => {
        for (const track of stream.getTracks()) track.stop();
      };
      recorder.start();
      return {
        stop: () =>
          new Promise<Blob>((resolve) => {
            recorder.onstop = () => {
              release();
              resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
            };
            if (recorder.state === "inactive") recorder.onstop?.(new Event("stop"));
            else recorder.stop();
          }),
        cancel() {
          if (recorder.state !== "inactive") recorder.stop();
          release();
        },
      };
    },
    async toWav(clip) {
      const AudioCtx =
        window.AudioContext ??
        (window as typeof window & { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!AudioCtx) return clip;
      const context = new AudioCtx();
      try {
        const decoded = await context.decodeAudioData(await clip.arrayBuffer());
        const channels: Float32Array[] = [];
        for (let index = 0; index < decoded.numberOfChannels; index += 1) {
          channels.push(decoded.getChannelData(index));
        }
        const mono = resample(toMono(channels), decoded.sampleRate, TRANSCRIPTION_SAMPLE_RATE);
        return encodeWav(mono, TRANSCRIPTION_SAMPLE_RATE);
      } finally {
        void context.close();
      }
    },
    transcribe,
  };
}
