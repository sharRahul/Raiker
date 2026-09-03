import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createAudioSessionCoordinator,
  createLocalTranscriptionAdapter,
  createRecognitionAdapter,
  createVoicePlayback,
  encodeWav,
  inputModeForDraft,
  resample,
  resolveSpeechLanguage,
  speechText,
  toMono,
  TRANSCRIPTION_SAMPLE_RATE,
  type LocalTranscriptionPorts,
} from "./voice";

type ResultItem = { transcript: string; isFinal: boolean };

class FakeRecognition {
  static instance: FakeRecognition;
  continuous = false;
  interimResults = false;
  lang = "";
  onresult: ((event: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn();
  stop = vi.fn(() => this.onend?.());
  abort = vi.fn(() => this.onend?.());

  constructor() {
    FakeRecognition.instance = this;
  }

  emitResult(items: ResultItem[]) {
    const results = items.map((item) => Object.assign([{ transcript: item.transcript }], { isFinal: item.isFinal }));
    this.onresult?.({ resultIndex: 0, results });
  }
}

describe("voice recognition adapter", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("forwards interim and final segments without submitting anything", () => {
    const interim = vi.fn();
    const final = vi.fn();
    const adapter = createRecognitionAdapter(FakeRecognition);
    adapter.start("en", { interim, final, end: vi.fn(), error: vi.fn() });

    FakeRecognition.instance.emitResult([
      { transcript: "draft words", isFinal: false },
      { transcript: "final words", isFinal: true },
    ]);

    expect(interim).toHaveBeenCalledWith("draft words");
    expect(final).toHaveBeenCalledWith("final words");
    expect(FakeRecognition.instance.continuous).toBe(true);
    expect(FakeRecognition.instance.interimResults).toBe(true);
    expect(FakeRecognition.instance.lang).toBe("en");
  });

  it("stops playback and recognition owners bidirectionally", () => {
    const coordinator = createAudioSessionCoordinator();
    const recognitionStop = vi.fn();
    const playbackStop = vi.fn();
    const recognitionLost = vi.fn();
    const playbackLost = vi.fn();
    coordinator.subscribe("recognition", recognitionLost);
    coordinator.subscribe("playback", playbackLost);

    coordinator.startRecognition("recognition", vi.fn(), recognitionStop);
    coordinator.startPlayback("playback", vi.fn(), playbackStop);
    expect(recognitionStop).toHaveBeenCalledOnce();
    expect(recognitionLost).toHaveBeenCalledOnce();

    coordinator.startRecognition("recognition", vi.fn(), recognitionStop);
    expect(playbackStop).toHaveBeenCalledOnce();
    expect(playbackLost).toHaveBeenCalledOnce();
  });

  it.each(["submit", "route", "sign-out", "handoff"] as const)(
    "releases the active owner on %s cleanup",
    (reason) => {
      const coordinator = createAudioSessionCoordinator();
      const stop = vi.fn();
      const lost = vi.fn();
      coordinator.subscribe("composer", lost);
      coordinator.startRecognition("composer", vi.fn(), stop);
      coordinator.stopAll(reason);
      expect(stop).toHaveBeenCalledOnce();
      expect(lost).toHaveBeenCalledOnce();
    },
  );
});

it("coordinates browser playback and exposes failure callbacks", () => {
  const synth = { speak: vi.fn(), cancel: vi.fn() };
  const playback = createVoicePlayback(synth);
  const end = vi.fn();
  const error = vi.fn();
  playback.speak("turn-1", "Answer", "en", { end, error });
  const utterance = synth.speak.mock.calls[0][0];
  expect(utterance.text).toBe("Answer");
  expect(utterance.lang).toBe("en");
  utterance.onerror?.();
  expect(error).toHaveBeenCalledOnce();
});

it("resolves Auto to a valid device language with an English fallback", () => {
  expect(resolveSpeechLanguage("auto", "en-GB")).toBe("en-GB");
  expect(resolveSpeechLanguage("auto", "")).toBe("en");
  expect(resolveSpeechLanguage("ja", "en-GB")).toBe("ja");
});

it("classifies the submitted draft from actual dictation contribution", () => {
  expect(inputModeForDraft({ dictated: false, typedBefore: false, editedAfter: false })).toBe("typed");
  expect(inputModeForDraft({ dictated: true, typedBefore: false, editedAfter: false })).toBe("dictated");
  expect(inputModeForDraft({ dictated: true, typedBefore: true, editedAfter: false })).toBe("mixed");
  expect(inputModeForDraft({ dictated: true, typedBefore: false, editedAfter: true })).toBe("mixed");
});

it("speaks answer text without markdown syntax, raw URLs, citations or code bodies", () => {
  expect(speechText("See [the guide](https://example.test) [s1].\n```ts\nconst secret = 1\n```"))
    .toBe("See the guide. Code block.");
});

// ── BUG-256 — dictation that runs on this machine ────────────────────────────

describe("on-device transcription", () => {
  function ports(overrides: Partial<LocalTranscriptionPorts> = {}) {
    let stopRecording: ((clip: Blob) => void) | null = null;
    const cancel = vi.fn();
    const base: LocalTranscriptionPorts = {
      supported: () => true,
      record: async () => ({
        stop: () => new Promise<Blob>((resolve) => { stopRecording = resolve; }),
        cancel,
      }),
      toWav: async (clip) => clip,
      transcribe: async () => "the words that were said",
      ...overrides,
    };
    return { base, cancel, finishRecording: (clip: Blob) => stopRecording?.(clip) };
  }

  it("hands the recording to the runtime and reports the transcript once", async () => {
    const { base, finishRecording } = ports();
    const adapter = createLocalTranscriptionAdapter(base);
    const final = vi.fn();
    const end = vi.fn();
    const phase = vi.fn();
    adapter.start("auto", { interim: vi.fn(), final, end, error: vi.fn(), phase });
    await vi.waitFor(() => expect(phase).toHaveBeenCalledWith("listening"));
    adapter.stop();
    expect(phase).toHaveBeenCalledWith("transcribing");
    finishRecording(new Blob(["audio"]));
    await vi.waitFor(() => expect(end).toHaveBeenCalled());
    expect(final).toHaveBeenCalledExactlyOnceWith("the words that were said");
  });

  it("reports a refusal from the runtime with the code the control can explain", async () => {
    const failure = Object.assign(new Error("refused"), {
      reasonCode: "speech_runtime_unreachable",
    });
    const { base, finishRecording } = ports({ transcribe: async () => { throw failure; } });
    const adapter = createLocalTranscriptionAdapter(base);
    const error = vi.fn();
    adapter.start("auto", { interim: vi.fn(), final: vi.fn(), end: vi.fn(), error });
    await vi.waitFor(() => expect(true).toBe(true));
    adapter.stop();
    finishRecording(new Blob(["audio"]));
    await vi.waitFor(() => expect(error).toHaveBeenCalledWith("speech_runtime_unreachable"));
  });

  it("maps a refused microphone onto the same code the browser adapter reports", async () => {
    const denied = Object.assign(new Error("denied"), { name: "NotAllowedError" });
    const { base } = ports({ record: async () => { throw denied; } });
    const adapter = createLocalTranscriptionAdapter(base);
    const error = vi.fn();
    adapter.start("auto", { interim: vi.fn(), final: vi.fn(), end: vi.fn(), error });
    await vi.waitFor(() => expect(error).toHaveBeenCalledWith("not-allowed"));
  });

  it("throws the recording away and transcribes nothing when the turn is cancelled", async () => {
    const transcribe = vi.fn();
    const { base, cancel } = ports({ transcribe });
    const adapter = createLocalTranscriptionAdapter(base);
    adapter.start("auto", { interim: vi.fn(), final: vi.fn(), end: vi.fn(), error: vi.fn() });
    await vi.waitFor(() => expect(true).toBe(true));
    adapter.abort();
    expect(cancel).toHaveBeenCalled();
    expect(transcribe).not.toHaveBeenCalled();
  });
});

describe("the WAV a local runtime can read", () => {
  it("writes a 16 kHz mono PCM header", () => {
    const wav = encodeWav(new Float32Array([0, 0.5, -0.5]), TRANSCRIPTION_SAMPLE_RATE);
    expect(wav.type).toBe("audio/wav");
    expect(wav.size).toBe(44 + 3 * 2);
  });

  it("down-mixes every channel rather than dropping all but the first", () => {
    const mono = toMono([new Float32Array([1, 0]), new Float32Array([0, 1])]);
    expect(Array.from(mono)).toEqual([0.5, 0.5]);
  });

  it("resamples to the rate the runtime expects", () => {
    const halved = resample(new Float32Array([0, 1, 2, 3]), 32_000, 16_000);
    expect(halved.length).toBe(2);
    expect(resample(new Float32Array([1, 2]), 16_000, 16_000).length).toBe(2);
  });
});
