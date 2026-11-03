import { describe, expect, it, vi } from "vitest";
import { APPROVAL_LINE, Conversation, NOTHING_HEARD, type ConversationPorts, type TurnHandle } from "./conversation.svelte";
import type { AudioPort } from "./playbackQueue";
import { FRAME_SAMPLES } from "./vad";

function harness(options: Partial<{ handsFree: boolean; bargeIn: boolean }> = {}) {
  let onFrame: (frame: Float32Array, level: number) => void = () => {};
  const played: string[] = [];
  const stopped: string[] = [];
  let finishPlaying: (() => void) | null = null;
  const audio: AudioPort = {
    play(clip) {
      const label = (clip as unknown as { label: string }).label;
      played.push(label);
      const done = new Promise<void>((resolve) => (finishPlaying = resolve));
      return { done, stop: () => { stopped.push(label); finishPlaying?.(); } };
    },
  };
  let probability = 0;
  const turns: { text: string; resolve: (status: string) => void; cancelled: boolean; onText: (s: string) => void }[] = [];
  const ports: ConversationPorts = {
    startCapture: vi.fn(async (handler) => {
      onFrame = handler;
      return { stop: vi.fn() };
    }),
    loadVad: vi.fn(async () => ({ probability: async () => probability, reset: () => {} })),
    transcribe: vi.fn(async () => "what is on today"),
    send: vi.fn((text, onText): TurnHandle => {
      let resolve: (status: string) => void = () => {};
      const done = new Promise<{ status: string }>((r) => (resolve = (status) => r({ status })));
      const entry = { text, resolve, cancelled: false, onText };
      turns.push(entry);
      return { done, cancel: () => { entry.cancelled = true; } };
    }),
    synthesise: vi.fn(async (sentence: string) => ({ label: sentence }) as unknown as Blob),
    audio,
  };
  const conversation = new Conversation(ports, { handsFree: false, bargeIn: true, endSilenceMs: 300, ...options });
  return {
    conversation, ports, played, stopped, turns,
    frame: (p = probability) => { probability = p; onFrame(new Float32Array(FRAME_SAMPLES), 0.1); },
    setProbability: (p: number) => { probability = p; },
    finish: () => finishPlaying?.(),
  };
}

const settle = () => new Promise((r) => setTimeout(r, 0));

describe("conversation", () => {
  it("push to talk: hears while held, answers aloud sentence by sentence, then listens", async () => {
    const h = harness();
    await h.conversation.start();
    expect(h.conversation.state).toBe("listening");
    h.conversation.pressTalk();
    expect(h.conversation.state).toBe("hearing");
    for (let i = 0; i < 10; i += 1) h.frame(0);
    h.conversation.releaseTalk();
    await vi.waitFor(() => expect(h.turns).toHaveLength(1));
    expect(h.turns[0].text).toBe("what is on today");
    expect(h.conversation.captions[0]).toMatchObject({ who: "owner", text: "what is on today" });
    h.turns[0].onText("You have two meetings. The first");
    await vi.waitFor(() => expect(h.played).toEqual(["You have two meetings."]));
    expect(h.conversation.state).toBe("speaking");
    h.turns[0].onText("You have two meetings. The first is at ten.");
    h.turns[0].resolve("completed");
    h.finish();
    await vi.waitFor(() => expect(h.played).toEqual(["You have two meetings.", "The first is at ten."]));
    h.finish();
    await vi.waitFor(() => expect(h.conversation.state).toBe("listening"));
    expect(h.conversation.captions[1].text).toBe("You have two meetings. The first is at ten.");
  });

  it("barge-in: speaking over Raiker stops the audio and cancels the turn", async () => {
    const h = harness({ bargeIn: true });
    await h.conversation.start();
    h.conversation.pressTalk();
    for (let i = 0; i < 10; i += 1) h.frame(0);
    h.conversation.releaseTalk();
    await vi.waitFor(() => expect(h.turns).toHaveLength(1));
    h.turns[0].onText("A long answer begins here. It goes on.");
    await vi.waitFor(() => expect(h.conversation.state).toBe("speaking"));
    for (let i = 0; i < 5; i += 1) h.frame(0.9); // 160 ms of speech
    await vi.waitFor(() => expect(h.conversation.state).toBe("hearing"));
    expect(h.turns[0].cancelled).toBe(true);
    expect(h.stopped).toContain("A long answer begins here.");
  });

  it("an approval is asked for on screen, never by voice", async () => {
    const h = harness();
    await h.conversation.start();
    h.conversation.pressTalk();
    for (let i = 0; i < 10; i += 1) h.frame(0);
    h.conversation.releaseTalk();
    await vi.waitFor(() => expect(h.turns).toHaveLength(1));
    h.turns[0].resolve("needs_approval");
    await vi.waitFor(() => expect(h.played).toContain(APPROVAL_LINE));
    h.finish();
    await vi.waitFor(() => expect(h.conversation.state).toBe("paused"));
    h.conversation.resume();
    expect(h.conversation.state).toBe("listening");
  });

  it("says once that nothing was heard, and ends after three errors in a row", async () => {
    const h = harness();
    (h.ports.transcribe as ReturnType<typeof vi.fn>).mockResolvedValue("  ");
    await h.conversation.start();
    for (let attempt = 0; attempt < 3; attempt += 1) {
      h.conversation.pressTalk();
      for (let i = 0; i < 10; i += 1) h.frame(0);
      h.conversation.releaseTalk();
      await settle();
      await settle();
    }
    expect(h.conversation.error).toBe(NOTHING_HEARD);
    expect(h.conversation.state).toBe("idle");
    expect(h.ports.send).not.toHaveBeenCalled();
  });

  it("hands-free: the end of a sentence is found without a button", async () => {
    const h = harness({ handsFree: true });
    await h.conversation.start();
    for (let i = 0; i < 6; i += 1) h.frame(0.9);
    await vi.waitFor(() => expect(h.conversation.state).toBe("hearing"));
    for (let i = 0; i < 12; i += 1) h.frame(0.05);
    await vi.waitFor(() => expect(h.turns).toHaveLength(1));
  });

  it("a short tap is not an utterance, and End releases the microphone", async () => {
    const h = harness();
    await h.conversation.start();
    h.conversation.pressTalk();
    h.frame(0);
    h.conversation.releaseTalk();
    expect(h.conversation.state).toBe("listening");
    expect(h.ports.transcribe).not.toHaveBeenCalled();
    const capture = await (h.ports.startCapture as ReturnType<typeof vi.fn>).mock.results[0].value;
    h.conversation.end();
    expect(capture.stop).toHaveBeenCalled();
    expect(h.conversation.state).toBe("idle");
  });

  it("a refused microphone ends the conversation with one plain sentence", async () => {
    const h = harness();
    (h.ports.startCapture as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("NotAllowedError"));
    await h.conversation.start();
    expect(h.conversation.state).toBe("idle");
    expect(h.conversation.error).toMatch(/can't use the microphone/);
  });
});
