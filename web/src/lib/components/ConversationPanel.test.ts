import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import ConversationPanel from "./ConversationPanel.svelte";
import type { ConversationPorts } from "../speech/conversation.svelte";

function ports(): ConversationPorts & { stopped: () => boolean } {
  let stopped = false;
  return {
    startCapture: vi.fn(async () => ({ stop: () => { stopped = true; } })),
    loadVad: vi.fn(async () => ({ probability: async () => 0, reset: () => {} })),
    transcribe: vi.fn(async () => "hello"),
    send: vi.fn(() => ({ done: Promise.resolve({ status: "completed" }), cancel: vi.fn() })),
    synthesise: vi.fn(async () => new Blob()),
    audio: { play: () => ({ done: Promise.resolve(), stop: () => {} }) },
    stopped: () => stopped,
  };
}

describe("ConversationPanel", () => {
  it("opens the microphone, announces its state, and releases it on End", async () => {
    const fake = ports();
    const onClose = vi.fn();
    render(ConversationPanel, { ports: fake, privacyLine: "On this device · Whisper small · Kokoro", onClose });
    expect(await screen.findByText("Listening")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText("On this device · Whisper small · Kokoro")).toBeInTheDocument();
    expect(screen.getByText("Preview")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "End" }));
    expect(onClose).toHaveBeenCalled();
    expect(fake.stopped()).toBe(true);
  });

  it("offers hold-to-talk only in push-to-talk mode", async () => {
    render(ConversationPanel, { ports: ports(), privacyLine: "x" });
    expect(await screen.findByRole("button", { name: /Hold to talk/ })).toBeInTheDocument();
  });

  it("does not offer a talk button when hands-free", async () => {
    render(ConversationPanel, { ports: ports(), privacyLine: "x", handsFree: true });
    await waitFor(() => expect(screen.getByText("Listening")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /Hold to talk/ })).toBeNull();
  });

  it("says plainly when the microphone is refused", async () => {
    const fake = ports();
    (fake.startCapture as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("NotAllowedError"));
    render(ConversationPanel, { ports: fake, privacyLine: "x" });
    expect(await screen.findByRole("alert")).toHaveTextContent("can't use the microphone");
  });
});
