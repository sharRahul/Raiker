/**
 * Settings → Privacy (BUG-215).
 *
 * The retention decision is the one control that changes what Raiker writes to
 * disk about a turn, so the two things that must hold are: it is **off** until
 * the owner turns it on, and the control reports the owner's choice exactly —
 * a toggle that reverts under the finger is worse than no toggle, because the
 * owner walks away believing they changed something.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Privacy from "./Privacy.svelte";
import { makeGate, stubFetch } from "../../test-helpers";

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

/*
 * REM-SET-PRIVACY — the page owes an inventory, not a slogan.
 *
 * It was one toggle under a heading that names the whole subject: an owner who
 * came to find out what Raiker holds, or what has left the machine, met a
 * control about reasoning traces and a page that looked finished.
 */
describe("Settings → Privacy — the data inventory", () => {
  const GATES = [
    makeGate({
      capability: "hosted_model_runtime",
      state: "enabled_runtime",
      decision_mode: "ask",
    }),
    makeGate({ capability: "web_fetch", state: "disabled", decision_mode: "ask" }),
  ];

  it("names what is kept locally and links the page that governs each", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(Privacy, { settings: {}, save: vi.fn() });

    const kept = screen.getByRole("region", { name: "Kept on this machine" });
    expect(within(kept).getByText("Approved memories")).toBeInTheDocument();
    expect(within(kept).getByRole("link", { name: "Memory" })).toHaveAttribute("href", "#/memory");
    // The limit that decides whether deletion can be relied on.
    expect(within(kept).getByText(/not from a backup already written/)).toBeInTheDocument();
  });

  it("says what each outbound capability carries, and where", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(Privacy, { settings: {}, save: vi.fn() });

    const out = await screen.findByRole("region", { name: "What can leave this machine" });
    expect(within(out).getAllByRole("listitem").length).toBeGreaterThan(3);
    expect(within(out).getByText(/as much of the conversation as the turn needs/)).toBeInTheDocument();
    // The availability sentence is the one Permissions prints, not a second one.
    await waitFor(() => expect(within(out).getByText("On · Ask me")).toBeInTheDocument());
    expect(within(out).getByText("Off · Ask me")).toBeInTheDocument();
  });

  it("calls an unread permission list unknown rather than off", async () => {
    // A shorter inventory reads as a smaller footprint, which is the failure
    // this whole page exists to avoid.
    stubFetch({ "GET /api/capability-gates": { __status: 503 } });
    render(Privacy, { settings: {}, save: vi.fn() });

    const out = await screen.findByRole("region", { name: "What can leave this machine" });
    await waitFor(() =>
      expect(within(out).getByText(/could not be read/)).toBeInTheDocument(),
    );
    expect(within(out).queryByText("Off · Ask me")).toBeNull();
  });
});
