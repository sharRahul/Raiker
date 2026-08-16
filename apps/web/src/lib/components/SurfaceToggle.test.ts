// Chat and Build are two rooms for the same instrument. The toggle moves a
// half-typed prompt between them without sending it, using the same handoff
// events the destination composers already listen for.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import SurfaceToggle from "./SurfaceToggle.svelte";

afterEach(() => {
  vi.useRealTimers();
  window.location.hash = "";
});

describe("SurfaceToggle", () => {
  it("marks the surface it is in and does not navigate when it is pressed", async () => {
    render(SurfaceToggle, { surface: "chat", draft: "unchanged" });

    const chat = screen.getByRole("button", { name: "Chat" });
    expect(chat).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Build" })).toHaveAttribute("aria-pressed", "false");
    await fireEvent.click(chat);
    expect(window.location.hash).toBe("");
  });

  it("carries the draft and its staged files to the other surface without sending", async () => {
    vi.useFakeTimers();
    const staged = [{ kind: "image", attachment_id: "att_1" }];
    const take = vi.fn(() => staged as never);
    const composed = vi.fn();
    window.addEventListener("raiker:build-compose", composed);
    render(SurfaceToggle, { surface: "chat", draft: "  move me  ", attachments: take });

    await fireEvent.click(screen.getByRole("button", { name: "Build" }));
    expect(window.location.hash).toBe("#/build");
    // The destination has to mount and claim its session before it can accept a
    // draft, exactly as the Workbench handoff did.
    vi.runAllTimers();

    expect(take).toHaveBeenCalledTimes(1);
    expect((composed.mock.calls[0][0] as CustomEvent).detail).toEqual({
      text: "move me",
      attachments: staged,
    });
    window.removeEventListener("raiker:build-compose", composed);
  });

  it("navigates on an empty draft without taking files or dispatching a prompt", async () => {
    vi.useFakeTimers();
    const take = vi.fn(() => [] as never);
    const composed = vi.fn();
    window.addEventListener("raiker:compose", composed);
    render(SurfaceToggle, { surface: "build", draft: "   ", attachments: take });

    await fireEvent.click(screen.getByRole("button", { name: "Chat" }));
    vi.runAllTimers();

    expect(window.location.hash).toBe("#/new-chat");
    expect(take).not.toHaveBeenCalled();
    expect(composed).not.toHaveBeenCalled();
    window.removeEventListener("raiker:compose", composed);
  });

  it("cannot move a prompt while a turn is running", async () => {
    const composed = vi.fn();
    window.addEventListener("raiker:build-compose", composed);
    render(SurfaceToggle, { surface: "chat", draft: "later", disabled: true });

    const build = screen.getByRole("button", { name: "Build" });
    expect(build).toBeDisabled();
    await fireEvent.click(build);
    expect(window.location.hash).toBe("");
    expect(composed).not.toHaveBeenCalled();
    window.removeEventListener("raiker:build-compose", composed);
  });
});
