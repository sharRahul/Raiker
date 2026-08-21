import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { createAudioSessionCoordinator, type RecognitionHandlers, type VoiceRecognitionAdapter } from "../voice";
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

describe("recognition recovery", () => {
  it.each([
    ["not-allowed", /Allow microphone and speech-recognition access/],
    ["audio-capture", /No usable microphone was found/],
    ["no-speech", /No speech was recognized/],
    ["network", /browser speech service is unavailable/],
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

it("always exposes browser-processing disclosure and an honest unsupported state", () => {
  const adapter: VoiceRecognitionAdapter = {
    supported: () => false,
    start: vi.fn(),
    stop: vi.fn(),
    abort: vi.fn(),
  };
  render(VoiceDictationControl, { draft: "", language: "auto", adapter, onchange: vi.fn() });
  const disclosure = screen.getByText(/browser's speech service may process audio externally/);
  expect(disclosure).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Dictate" })).toBeDisabled();
  expect(screen.getByText(/You can keep typing/)).toBeInTheDocument();
});
