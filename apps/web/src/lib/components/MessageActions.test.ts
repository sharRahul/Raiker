// The per-message actions on the owner's own prompt.
//
// Two of the five are conditional — Branch and Summarise — and "conditional"
// here means *absent*, not disabled. A control that is visible but cannot work
// is the shape this codebase keeps finding and removing: the owner reads it as
// available and learns otherwise by clicking. So the absence is asserted, not
// just the presence.
//
// The Summarise action carries the claim that most needs to survive a redesign:
// it shortens what the model is sent and removes nothing from the transcript.
// That sentence is the difference between a useful control and a frightening
// one, so it is asserted here rather than left to the component's own comment.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import MessageActions from "./MessageActions.svelte";

function base() {
  return { text: "the prompt", onedit: vi.fn(), onretry: vi.fn() };
}

describe("MessageActions", () => {
  it("offers neither Branch nor Summarise when the surface cannot do them", () => {
    render(MessageActions, { props: base() });

    expect(screen.queryByRole("button", { name: /Branch a second conversation/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Summarise this conversation/ })).toBeNull();
  });

  it("summarises up to and including this message, and says nothing is removed", async () => {
    const oncompact = vi.fn();
    render(MessageActions, { props: { ...base(), oncompact } });

    const button = screen.getByRole("button", {
      name: "Summarise this conversation up to and including this message",
    });
    expect(button).toHaveAttribute(
      "title",
      "Shortens what the model is sent. Nothing is removed from this transcript.",
    );

    await fireEvent.click(button);
    expect(oncompact).toHaveBeenCalledTimes(1);
  });

  it("says it is working and cannot be pressed twice", () => {
    render(MessageActions, { props: { ...base(), oncompact: vi.fn(), compacting: true } });

    const button = screen.getByRole("button", {
      name: "Summarise this conversation up to and including this message",
    });
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Summarising…");
  });

  it("is unavailable while a turn is streaming", () => {
    render(MessageActions, { props: { ...base(), oncompact: vi.fn(), disabled: true } });

    expect(
      screen.getByRole("button", {
        name: "Summarise this conversation up to and including this message",
      }),
    ).toBeDisabled();
  });
});
