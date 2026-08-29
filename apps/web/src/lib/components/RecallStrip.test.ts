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

describe("RecallStrip", () => {
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
