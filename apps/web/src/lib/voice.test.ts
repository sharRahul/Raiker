import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createAudioSessionCoordinator,
  createRecognitionAdapter,
  createVoicePlayback,
  inputModeForDraft,
  resolveSpeechLanguage,
  speechText,
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
