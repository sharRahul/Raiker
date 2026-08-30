// The per-message actions on the owner's own prompt.
//
// Three of them are conditional — Branch, Summarise and Rewind — and
// "conditional" here means *absent*, not disabled. A control that is visible
// but cannot work is the shape this codebase keeps finding and removing: the
// owner reads it as available and learns otherwise by clicking. So the absence
// is asserted, not just the presence.
//
// B18 moved those three behind **More**, because six labelled buttons under
// every message is the opposite of a transcript you can read. What must survive
// that move is asserted here rather than left to the component's own comment:
//
// * the handle itself does not appear when there is nothing behind it;
// * Summarise still carries the claim that makes it a useful control rather
//   than a frightening one — it shortens what the model is sent and removes
//   nothing from the transcript;
// * Rewind states that it previews and then asks, so it cannot be mistaken for
//   a control that restores files on click.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import MessageActions from "./MessageActions.svelte";

function base() {
  return { text: "the prompt", onedit: vi.fn(), onretry: vi.fn() };
}

/** Open the overflow menu, which is where the conditional actions live. */
async function openMore() {
  await fireEvent.click(screen.getByRole("button", { name: "More actions for this message" }));
}

describe("MessageActions", () => {
  it("offers no overflow at all when the surface can do none of them", () => {
    render(MessageActions, { props: base() });

    expect(screen.queryByRole("button", { name: "More actions for this message" })).toBeNull();
    expect(screen.queryByRole("menuitem")).toBeNull();
  });

  it("keeps the row to Copy, Edit and Retry", async () => {
    render(MessageActions, { props: { ...base(), oncompact: vi.fn(), onrewind: vi.fn() } });

    // The visible row before anything is opened: three actions and the handle.
    expect(screen.getAllByRole("button")).toHaveLength(4);
    await openMore();
    expect(screen.getAllByRole("menuitem")).toHaveLength(2);
  });

  it("summarises up to and including this message, and says nothing is removed", async () => {
    const oncompact = vi.fn();
    render(MessageActions, { props: { ...base(), oncompact } });

    await openMore();
    const item = screen.getByRole("menuitem", { name: /Summarise up to here/ });
    expect(item).toHaveTextContent("Nothing leaves this transcript.");

    await fireEvent.click(item);
    expect(oncompact).toHaveBeenCalledTimes(1);
  });

  it("says it is working and cannot be pressed twice", async () => {
    render(MessageActions, { props: { ...base(), oncompact: vi.fn(), compacting: true } });

    await openMore();
    const item = screen.getByRole("menuitem", { name: /Summarising…/ });
    expect(item).toBeDisabled();
  });

  it("is unavailable while a turn is streaming", async () => {
    render(MessageActions, { props: { ...base(), oncompact: vi.fn(), disabled: true } });

    expect(screen.getByRole("button", { name: "More actions for this message" })).toBeDisabled();
  });

  // B18 — the one action here that can change a file. It must read as a
  // preview-then-ask, because that is what it is.
  it("offers Rewind as a preview that asks for approval, not as a restore", async () => {
    const onrewind = vi.fn();
    render(MessageActions, { props: { ...base(), onrewind } });

    await openMore();
    const item = screen.getByRole("menuitem", { name: /Rewind to before this/ });
    expect(item).toHaveTextContent("Previews the file changes, then asks for approval.");

    await fireEvent.click(item);
    expect(onrewind).toHaveBeenCalledTimes(1);
  });

  it("says Rewind is reading the checkpoint and cannot be pressed twice", async () => {
    render(MessageActions, { props: { ...base(), onrewind: vi.fn(), rewinding: true } });

    await openMore();
    expect(screen.getByRole("menuitem", { name: /Reading checkpoint…/ })).toBeDisabled();
  });
});
