import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import { createManagedPlayback } from "./managedPlayback";
import { createPlaybackQueue, type AudioPort } from "./playbackQueue";
import { MAX_SENTENCE_CHARS, createSentenceStream, splitSentences, takeSentences } from "./sentences";

describe("sentences", () => {
  it("cuts at sentence ends but not after abbreviations, initials or decimals", () => {
    expect(splitSentences("Dr. Smith arrives at 3.5 pm. J. R. R. Tolkien wrote it! Is that right? Yes")).toEqual([
      "Dr. Smith arrives at 3.5 pm.",
      "J. R. R. Tolkien wrote it!",
      "Is that right?",
      "Yes",
    ]);
  });

  it("cuts a long sentence at a comma, never past the limit", () => {
    const long = `${"word ".repeat(30)}, ${"more ".repeat(40)}end.`;
    const parts = splitSentences(long);
    expect(parts.length).toBeGreaterThan(1);
    for (const part of parts) expect(part.length).toBeLessThanOrEqual(MAX_SENTENCE_CHARS);
  });

  it("drops code blocks and tables before speaking", () => {
    expect(splitSentences("Run this:\n\n```\nrm -rf /tmp/x\n```\n\nDone.")).not.toContain("rm -rf /tmp/x");
  });

  it("yields sentences as a streamed answer completes them", () => {
    const stream = createSentenceStream();
    expect(stream.push("Hello the")).toEqual([]);
    expect(stream.push("Hello there. How are")).toEqual(["Hello there."]);
    expect(stream.push("Hello there. How are you? I")).toEqual(["How are you?"]);
    expect(stream.finish()).toEqual(["I"]);
    expect(takeSentences("No end yet").rest).toBe("No end yet");
  });
});

function fakePort(log: string[]): AudioPort & { finish(): void } {
  let resolveCurrent: (() => void) | null = null;
  return {
    play(clip) {
      log.push(`play:${(clip as unknown as { label: string }).label}`);
      const done = new Promise<void>((resolve) => (resolveCurrent = resolve));
      return { done, stop: () => { log.push("stop"); resolveCurrent?.(); } };
    },
    finish() {
      resolveCurrent?.();
    },
  };
}

const clip = (label: string) => ({ label }) as unknown as Blob;

describe("playback queue", () => {
  it("synthesises ahead and plays in order", async () => {
    const log: string[] = [];
    const port = fakePort(log);
    const synth = vi.fn(async (s: string) => clip(s));
    const queue = createPlaybackQueue(synth, port);
    queue.enqueue("one");
    queue.enqueue("two");
    expect(synth).toHaveBeenCalledTimes(2); // both requested before either plays
    await vi.waitFor(() => expect(log).toEqual(["play:one"]));
    port.finish();
    await vi.waitFor(() => expect(log).toEqual(["play:one", "play:two"]));
    port.finish();
    await queue.drained();
    expect(queue.speaking).toBe(false);
  });

  it("stops at once and drops what was queued (barge-in)", async () => {
    const log: string[] = [];
    const port = fakePort(log);
    const queue = createPlaybackQueue(async (s) => clip(s), port);
    queue.enqueue("one");
    queue.enqueue("two");
    await vi.waitFor(() => expect(log).toEqual(["play:one"]));
    queue.stop();
    await queue.drained();
    expect(log).toEqual(["play:one", "stop"]);
  });
});

describe("managed read-aloud", () => {
  const fallback = () => ({ supported: () => true, speak: vi.fn(), stop: vi.fn() });

  it("speaks on the installed engine", async () => {
    const log: string[] = [];
    const port = fakePort(log);
    const end = vi.fn();
    const playback = createManagedPlayback(fallback(), async (s) => clip(s), port);
    playback.speak("r1", "First. Second.", "auto", { end, error: vi.fn() });
    await vi.waitFor(() => expect(log).toEqual(["play:First."]));
    port.finish();
    await vi.waitFor(() => expect(log).toEqual(["play:First.", "play:Second."]));
    port.finish();
    await vi.waitFor(() => expect(end).toHaveBeenCalledOnce());
  });

  it("falls back to the system voice when no engine is installed, and remembers", async () => {
    const system = fallback();
    let now = 0;
    const synth = vi.fn(async () => {
      throw new ApiError(409, "voice_speaking_not_installed", "refused");
    });
    const playback = createManagedPlayback(system, synth, fakePort([]), () => now);
    playback.speak("r1", "Hello there.", "auto", { end: vi.fn(), error: vi.fn() });
    await vi.waitFor(() => expect(system.speak).toHaveBeenCalledOnce());
    playback.speak("r2", "Again.", "auto", { end: vi.fn(), error: vi.fn() });
    expect(system.speak).toHaveBeenCalledTimes(2);
    expect(synth).toHaveBeenCalledOnce();
    now = 61_000;
    playback.speak("r3", "Later.", "auto", { end: vi.fn(), error: vi.fn() });
    await vi.waitFor(() => expect(synth).toHaveBeenCalledTimes(2));
  });
});
