import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { createAudioSessionCoordinator, isLocalVoicePage, type RecognitionHandlers, type VoiceRecognitionAdapter } from "../voice";
import VoiceDictationControl from "./VoiceDictationControl.svelte";

function recognitionAdapterFake() {
  let handlers: RecognitionHandlers | undefined;
  const adapter: VoiceRecognitionAdapter & {
    interim(text: string): void;
    final(text: string): void;
    error(code: string): void;
  } = {
    supported: () => true,
    start: vi.fn((_language, nextHandlers) => { handlers = nextHandlers; }),
    stop: vi.fn(() => handlers?.end()),
    abort: vi.fn(() => handlers?.end()),
    interim: (text) => handlers?.interim(text),
    final: (text) => handlers?.final(text),
    error: (code) => handlers?.error(code),
  };
  return adapter;
}

it("does not start browser recognition when the local runtime is unavailable", async () => {
  const start = vi.fn();
  vi.stubGlobal("SpeechRecognition", class { start = start; });
  try {
    render(VoiceDictationControl, { draft: "draft", runtime: "unavailable", onchange: vi.fn() });
    expect(screen.getByRole("button", { name: "Dictate" })).toBeDisabled();
    expect(screen.getByText(/Models → Local/)).toBeInTheDocument();
    expect(start).not.toHaveBeenCalled();
  } finally {
    vi.unstubAllGlobals();
  }
});

it("does not record from a remotely served Raiker page", () => {
  // The locality decision is tested independently of microphone permission.
  expect(isLocalVoicePage("https://raiker.example.com")).toBe(false);
  expect(isLocalVoicePage("http://127.0.0.1:8765")).toBe(true);
});

it("keeps recognized words editable and never sends", async () => {
  const adapter = recognitionAdapterFake();
  const onchange = vi.fn();
  const onfinalized = vi.fn();
  render(VoiceDictationControl, {
    draft: "Review  today",
    selectionStart: 7,
    selectionEnd: 7,
    language: "en",
    adapter,
    onchange,
    onfinalized,
  });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  expect(adapter.start).toHaveBeenCalledWith("auto", expect.anything());
  adapter.final("the plan");
  expect(onchange).toHaveBeenLastCalledWith("Review the plan today", 15);
  expect(onfinalized).toHaveBeenCalledOnce();
  await fireEvent.click(screen.getByRole("button", { name: "Done dictating" }));
  expect(screen.getByRole("button", { name: "Dictate" })).toBeInTheDocument();
});

it("cancel restores the complete draft and selection snapshot", async () => {
  const adapter = recognitionAdapterFake();
  const onchange = vi.fn();
  render(VoiceDictationControl, {
    draft: "keep this",
    selectionStart: 4,
    selectionEnd: 4,
    language: "auto",
    adapter,
    onchange,
  });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  adapter.final("discarded");
  await fireEvent.click(screen.getByRole("button", { name: "Cancel dictation" }));
  expect(onchange).toHaveBeenLastCalledWith("keep this", 4);
});

it("inserts a completed transcript into the latest draft after typing", async () => {
  const adapter = recognitionAdapterFake();
  adapter.stop = vi.fn();
  const onchange = vi.fn();
  const view = render(VoiceDictationControl, {
    draft: "hello", selectionStart: 5, selectionEnd: 5, runtime: "local", adapter, onchange,
  });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  await fireEvent.click(screen.getByRole("button", { name: "Done dictating" }));
  await view.rerender({ draft: "hello new", selectionStart: 9, selectionEnd: 9 });
  adapter.final("words");
  expect(onchange).toHaveBeenLastCalledWith("hello new words", 15);
});

it("does not restore an old snapshot over edits made before cancellation", async () => {
  const adapter = recognitionAdapterFake();
  const onchange = vi.fn();
  const view = render(VoiceDictationControl, { draft: "hello", adapter, onchange });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  await view.rerender({ draft: "hello edited", selectionStart: 12, selectionEnd: 12 });
  await fireEvent.click(screen.getByRole("button", { name: "Cancel dictation" }));
  expect(onchange).not.toHaveBeenCalled();
});

it("uses a selection changed while transcription is pending", async () => {
  const adapter = recognitionAdapterFake();
  adapter.stop = vi.fn();
  const onchange = vi.fn();
  const view = render(VoiceDictationControl, {
    draft: "one two", selectionStart: 7, selectionEnd: 7, runtime: "local", adapter, onchange,
  });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  await fireEvent.click(screen.getByRole("button", { name: "Done dictating" }));
  await view.rerender({ selectionStart: 0, selectionEnd: 3 });
  adapter.final("new");
  expect(onchange).toHaveBeenLastCalledWith("new two", 3);
});

it("ignores a transcription callback received after cancellation", async () => {
  const adapter = recognitionAdapterFake();
  const onchange = vi.fn();
  render(VoiceDictationControl, { draft: "hello", adapter, onchange });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  await fireEvent.click(screen.getByRole("button", { name: "Cancel dictation" }));
  onchange.mockClear();
  adapter.final("late result");
  expect(onchange).not.toHaveBeenCalled();
});

it("ignores duplicate local transcription results", async () => {
  const adapter = recognitionAdapterFake();
  adapter.stop = vi.fn();
  const onchange = vi.fn();
  render(VoiceDictationControl, { draft: "", runtime: "local", adapter, onchange });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  await fireEvent.click(screen.getByRole("button", { name: "Done dictating" }));
  adapter.final("words");
  adapter.final("words");
  expect(onchange).toHaveBeenCalledOnce();
  expect(onchange).toHaveBeenLastCalledWith("words", 5);
});

describe("recognition recovery", () => {
  it.each([
    ["not-allowed", /Allow microphone and speech-recognition access/],
    ["audio-capture", /No usable microphone was found/],
    ["no-speech", /No speech was recognized/],
    ["network", /speech runtime on this machine could not be reached/],
  ])("maps %s to exact recovery guidance", async (code, message) => {
    const adapter = recognitionAdapterFake();
    render(VoiceDictationControl, { draft: "", language: "auto", adapter, onchange: vi.fn() });
    await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
    adapter.error(code);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it.each(["not-allowed", "audio-capture", "no-speech"])(
    "%s restores the original draft and selection",
    async (code) => {
      const adapter = recognitionAdapterFake();
      const onchange = vi.fn();
      render(VoiceDictationControl, {
        draft: "keep this",
        selectionStart: 4,
        selectionEnd: 4,
        language: "auto",
        adapter,
        onchange,
      });
      await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
      adapter.final("discarded");
      adapter.error(code);
      expect(onchange).toHaveBeenLastCalledWith("keep this", 4);
    },
  );
});

it("keeps finalized text but discards interim text on service failure or ownership loss", async () => {
  const adapter = recognitionAdapterFake();
  const coordinator = createAudioSessionCoordinator();
  const onchange = vi.fn();
  render(VoiceDictationControl, { draft: "", language: "en", adapter, coordinator, onchange });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  adapter.final("keep finalized");
  adapter.interim("discard interim");
  adapter.error("network");
  await waitFor(() => expect(onchange).toHaveBeenLastCalledWith("keep finalized", 14));

  await fireEvent.click(await screen.findByRole("button", { name: "Dictate" }));
  adapter.interim("also discard");
  coordinator.stopAll("route");
  expect(await screen.findByRole("button", { name: "Dictate" })).toBeInTheDocument();
});

it("exposes local-processing disclosure and an honest unsupported state", () => {
  const adapter: VoiceRecognitionAdapter = {
    supported: () => false,
    start: vi.fn(),
    stop: vi.fn(),
    abort: vi.fn(),
  };
  render(VoiceDictationControl, { draft: "", language: "auto", adapter, onchange: vi.fn() });
  const disclosure = screen.getByText(/transcribed by the speech runtime on this machine/);
  expect(disclosure).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Dictate" })).toBeDisabled();
  expect(screen.getByText(/You can keep typing/)).toBeInTheDocument();
});

// ── BUG-256 — the disclosure has to match the runtime that is actually in use ──

describe("on-device dictation", () => {
  it("says the audio stays here when the local runtime is the one in use", async () => {
    render(VoiceDictationControl, {
      draft: "",
      runtime: "local",
      adapter: recognitionAdapterFake(),
      onchange: vi.fn(),
    });
    await fireEvent.click(screen.getByLabelText("About dictation privacy"));
    expect(
      screen.getByText(/transcribed by the speech runtime on this machine/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/browser's speech service may process audio externally/),
    ).not.toBeInTheDocument();
  });

  it("never advertises browser processing when a test adapter is supplied", async () => {
    render(VoiceDictationControl, {
      draft: "",
      runtime: "unavailable",
      adapter: recognitionAdapterFake(),
      onchange: vi.fn(),
    });
    await fireEvent.click(screen.getByLabelText("About dictation privacy"));
    expect(
      screen.queryByText(/browser's speech service may process audio externally/),
    ).not.toBeInTheDocument();
  });

  it("says it is transcribing rather than still listening", async () => {
    // An on-device turn does not end when recording does: the clip still has to
    // be transcribed, which is exactly the wait this label exists to describe.
    const adapter = recognitionAdapterFake();
    adapter.stop = vi.fn();
    render(VoiceDictationControl, {
      draft: "",
      runtime: "local",
      adapter,
      onchange: vi.fn(),
    });
    await fireEvent.click(screen.getByLabelText("Dictate"));
    expect(screen.getByText("Listening…")).toBeInTheDocument();
    await fireEvent.click(screen.getByLabelText("Done dictating"));
    expect(await screen.findByText("Transcribing…")).toBeInTheDocument();
    // The recording stopped; the words arrive afterwards.
    expect(adapter.stop).toHaveBeenCalled();
  });

  it("names the thing to change when the runtime does not answer", async () => {
    const adapter = recognitionAdapterFake();
    render(VoiceDictationControl, {
      draft: "",
      runtime: "local",
      adapter,
      onchange: vi.fn(),
    });
    await fireEvent.click(screen.getByLabelText("Dictate"));
    adapter.error("speech_runtime_unreachable");
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/did not answer. Check that it is running/),
    );
  });
});
