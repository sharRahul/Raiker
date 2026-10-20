// C17 — recall is ambient, so it leaves no citation to click. The strip is the
// only place the transcript can say what Raiker remembered, and the only place
// a wrong memory can be corrected at the moment it did damage.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import RecallStrip from "./RecallStrip.svelte";

const MEMORIES = [
  {
    memory_id: "mem_1",
    turn_id: "turn_1",
    text: "Backups go to the encrypted NAS.",
    scope: "project:alpha",
    pinned: false,
  },
];

const DISCLOSURE = {
  turn_id: "turn_1",
  recall_mode: "search_when_relevant" as const,
  effective_mode: "search_when_relevant" as const,
  incognito: false,
  retrieval_backend: "memory-brief-v1 + sqlite-fts5 + raiker-local-hash-v1",
  brief_version: "memory-brief-v1",
  brief_count: 1,
  brief_omitted: 2,
  recall_count: 0,
};

describe("RecallStrip", () => {
  // MEM-MODE-02 — the turn says which recall mode and backend it ran under.
  it("names the mode beside the count and the backend when opened", async () => {
    render(RecallStrip, {
      props: { memories: MEMORIES, disclosure: DISCLOSURE, onforget: vi.fn(), oncorrect: vi.fn() },
    });
    const toggle = screen.getByRole("button", { name: "Remembered 1 · Brief + search" });
    await fireEvent.click(toggle);
    expect(
      screen.getByText(
        "Recall mode: Search when relevant · searched sqlite-fts5 + raiker-local-hash-v1 · 2 approved memories left out of the brief by its budget",
      ),
    ).toBeInTheDocument();
  });

  it("says memory was off, or that Incognito held it back, when nothing was recalled", () => {
    const { rerender } = render(RecallStrip, {
      props: {
        memories: [],
        disclosure: { ...DISCLOSURE, effective_mode: "off" as const, incognito: true, retrieval_backend: "none" },
        onforget: vi.fn(),
        oncorrect: vi.fn(),
      },
    });
    expect(screen.getByText("Memory not used: Incognito is on")).toBeInTheDocument();
    rerender({
      memories: [],
      disclosure: { ...DISCLOSURE, brief_omitted: 0 },
      onforget: vi.fn(),
      oncorrect: vi.fn(),
    });
    expect(
      screen.getByText("Memory: Brief + search · nothing recalled · searched sqlite-fts5 + raiker-local-hash-v1"),
    ).toBeInTheDocument();
  });

  it("renders nothing when the turn recalled nothing", () => {
    const { container } = render(RecallStrip, {
      props: { memories: [], onforget: vi.fn(), oncorrect: vi.fn() },
    });
    expect(container.querySelector("section")).toBeNull();
  });

  it("stays collapsed until asked, so recall never owns the turn", async () => {
    render(RecallStrip, { props: { memories: MEMORIES, onforget: vi.fn(), oncorrect: vi.fn() } });
    expect(screen.getByRole("button", { name: /remembered 1/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText(MEMORIES[0].text)).toBeNull();

    await fireEvent.click(screen.getByRole("button", { name: /remembered 1/i }));
    expect(screen.getByText(MEMORIES[0].text)).toBeInTheDocument();
  });

  it("forgets a memory from the answer it shaped", async () => {
    const onforget = vi.fn();
    render(RecallStrip, { props: { memories: MEMORIES, onforget, oncorrect: vi.fn() } });
    await fireEvent.click(screen.getByRole("button", { name: /remembered 1/i }));
    await fireEvent.click(screen.getByRole("button", { name: "Forget" }));
    expect(onforget).toHaveBeenCalledWith(MEMORIES[0]);
  });

  it("corrects the sentence in place and sends the edited text", async () => {
    const oncorrect = vi.fn();
    render(RecallStrip, { props: { memories: MEMORIES, onforget: vi.fn(), oncorrect } });
    await fireEvent.click(screen.getByRole("button", { name: /remembered 1/i }));
    await fireEvent.click(screen.getByRole("button", { name: "Correct" }));

    const box = screen.getByLabelText("Correct this memory");
    await fireEvent.input(box, { target: { value: "Backups go to the offsite vault." } });
    await fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(oncorrect).toHaveBeenCalledWith(MEMORIES[0], "Backups go to the offsite vault.");
  });
});
