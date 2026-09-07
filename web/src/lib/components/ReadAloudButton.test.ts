import { fireEvent, render, screen } from "@testing-library/svelte";
import { expect, it, vi } from "vitest";
import { createAudioSessionCoordinator, type VoicePlayback } from "../voice";
import ReadAloudButton from "./ReadAloudButton.svelte";
import ReadAloudHarness from "./ReadAloudHarness.test.svelte";

type Handlers = { end(): void; error(): void; noLocalVoice?(language: string): void };

function playbackFake() {
  let handlers: Handlers | undefined;
  const playback: VoicePlayback & {
    end(): void;
    error(): void;
    noLocalVoice(language: string): void;
  } = {
    supported: () => true,
    speak: vi.fn((_id, _text, _language, next) => { handlers = next; }),
    stop: vi.fn(),
    end: () => handlers?.end(),
    error: () => handlers?.error(),
    noLocalVoice: (language: string) => handlers?.noLocalVoice?.(language),
  };
  return playback;
}

it("reads only cleaned visible answer text and toggles to Stop speaking", async () => {
  const playback = playbackFake();
  render(ReadAloudButton, {
    responseId: "turn-1",
    text: "**Ready** [s1]",
    language: "en",
    playback,
    coordinator: createAudioSessionCoordinator(),
  });
  await fireEvent.click(screen.getByRole("button", { name: "Read aloud" }));
  expect(playback.speak).toHaveBeenCalledWith("turn-1", "Ready", "en", expect.any(Object));
  expect(screen.getByRole("button", { name: "Stop speaking" })).toHaveAttribute("aria-pressed", "true");
  await fireEvent.click(screen.getByRole("button", { name: "Stop speaking" }));
  expect(playback.stop).toHaveBeenCalledOnce();
});

it("states playback failure and leaves text controls usable", async () => {
  const playback = playbackFake();
  render(ReadAloudButton, {
    responseId: "turn-1",
    text: "Answer",
    language: "auto",
    playback,
    coordinator: createAudioSessionCoordinator(),
  });
  await fireEvent.click(screen.getByRole("button", { name: "Read aloud" }));
  playback.error();
  expect(await screen.findByRole("status")).toHaveTextContent("This device could not play the response.");
  expect(screen.getByRole("button", { name: "Read aloud" })).toBeEnabled();
});

it("clears the previous response's pressed state when another response takes ownership", async () => {
  const playback = playbackFake();
  render(ReadAloudHarness, { coordinator: createAudioSessionCoordinator(), playback });
  const readButtons = screen.getAllByRole("button", { name: "Read aloud" });
  await fireEvent.click(readButtons[0]);
  expect(screen.getByRole("button", { name: "Stop speaking" })).toBeInTheDocument();
  await fireEvent.click(readButtons[1]);
  expect(await screen.findByRole("button", { name: "Stop speaking" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Read aloud" })).toHaveLength(1);
  expect(playback.stop).toHaveBeenCalledOnce();
});

// BUG-269 — playback either stays on this machine or says it could not. The
// message names the language because that is what is missing, not the feature.
it("says which language has no on-device voice, and reads nothing", async () => {
  const playback = playbackFake();
  render(ReadAloudButton, {
    responseId: "turn-1",
    text: "Answer",
    language: "ja",
    playback,
    coordinator: createAudioSessionCoordinator(),
  });
  await fireEvent.click(screen.getByRole("button", { name: "Read aloud" }));
  playback.noLocalVoice("ja");
  expect(await screen.findByRole("status")).toHaveTextContent(
    "No on-device voice for ja.",
  );
  // Back to the resting state, not stuck on "Stop speaking".
  expect(screen.getByRole("button", { name: "Read aloud" })).toBeEnabled();
});
