/**
 * Settings → Privacy (BUG-215).
 *
 * The retention decision is the one control that changes what Raiker writes to
 * disk about a turn, so the two things that must hold are: it is **off** until
 * the owner turns it on, and the control reports the owner's choice exactly —
 * a toggle that reverts under the finger is worse than no toggle, because the
 * owner walks away believing they changed something.
 */
import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Privacy from "./Privacy.svelte";

const NAME = /Keep the model's working with the turn/;

describe("Settings → Privacy", () => {
  it("is off until the owner turns it on", () => {
    render(Privacy, { settings: {}, save: vi.fn() });
    expect(screen.getByRole("checkbox", { name: NAME })).not.toBeChecked();
  });

  it("reports the owner's choice with the exact setting key", async () => {
    const save = vi.fn();
    render(Privacy, { settings: {}, save });

    await fireEvent.click(screen.getByRole("checkbox", { name: NAME }));

    expect(save).toHaveBeenCalledWith({ "privacy.retain_reasoning": true });
  });

  it("stays on once the setting says it is on", () => {
    render(Privacy, { settings: { "privacy.retain_reasoning": true }, save: vi.fn() });
    expect(screen.getByRole("checkbox", { name: NAME })).toBeChecked();
  });

  it("turns retention back off, rather than only ever on", async () => {
    const save = vi.fn();
    render(Privacy, { settings: { "privacy.retain_reasoning": true }, save });

    await fireEvent.click(screen.getByRole("checkbox", { name: NAME }));

    expect(save).toHaveBeenCalledWith({ "privacy.retain_reasoning": false });
  });

  it("says plainly that turning it off does not hide that there was working", () => {
    render(Privacy, { settings: {}, save: vi.fn() });
    expect(screen.getByText(/does not hide that there was any/)).toBeInTheDocument();
  });
});
