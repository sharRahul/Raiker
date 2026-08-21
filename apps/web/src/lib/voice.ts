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
}

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
