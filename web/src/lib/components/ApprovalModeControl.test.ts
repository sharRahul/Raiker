import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import ApprovalModeControl from "./ApprovalModeControl.svelte";

afterEach(() => vi.restoreAllMocks());

function stubModeApi(mode: "manual" | "sandbox" | "dont_ask") {
  vi.spyOn(api, "composerApprovalMode").mockResolvedValue({ approval_mode: mode });
  return vi.spyOn(api, "setComposerApprovalMode").mockResolvedValue({ approval_mode: mode });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => { resolve = complete; });
  return { promise, resolve };
}

async function openMenu() {
  await fireEvent.click(screen.getByRole("button", { name: /approval mode/i }));
  return screen.findByRole("menu", { name: /approval mode/i });
}

describe("ApprovalModeControl", () => {
  it("loads the persisted mode and shows one current-policy checkmark", async () => {
    stubModeApi("sandbox");
    render(ApprovalModeControl);

    expect(await screen.findByRole("button", { name: /work in sandbox/i })).toBeInTheDocument();
    await openMenu();
    expect(screen.getByRole("menuitemradio", { name: /work in sandbox/i })).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByRole("menuitemradio", { name: /Skip all approvals/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("img", { name: "Selected approval mode" })).toHaveLength(1);
  });

  it("closes the choice menu with Escape while the trigger retains keyboard focus", async () => {
    stubModeApi("manual");
    render(ApprovalModeControl);

    await openMenu();
    const trigger = screen.getByRole("button", { name: /approval mode/i });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);
    await fireEvent.keyDown(trigger, { key: "Escape" });
    expect(screen.queryByRole("menu", { name: /approval mode/i })).not.toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("returns focus to its trigger when Escape is pressed inside the menu", async () => {
    stubModeApi("manual");
    render(ApprovalModeControl);
    const menu = await openMenu();
    const choice = screen.getByRole("menuitemradio", { name: /work in sandbox/i });
    choice.focus();

    await fireEvent.keyDown(menu, { key: "Escape" });

    expect(screen.queryByRole("menu", { name: /approval mode/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approval mode/i })).toHaveFocus();
  });

  it("keeps a local selection when the initial persisted-mode load resolves late", async () => {
    const load = deferred<{ approval_mode: "manual" | "sandbox" | "dont_ask" }>();
    vi.spyOn(api, "composerApprovalMode").mockReturnValue(load.promise);
    const save = vi.spyOn(api, "setComposerApprovalMode").mockResolvedValue({ approval_mode: "dont_ask" });
    render(ApprovalModeControl);

    await openMenu();
    await fireEvent.click(screen.getByRole("menuitemradio", { name: /decline/i }));
    await vi.waitFor(() => expect(save).toHaveBeenCalledWith("dont_ask"));

    load.resolve({ approval_mode: "manual" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    await vi.waitFor(() => expect(screen.getByRole("button", { name: /decline/i })).toBeInTheDocument());
  });

  it("persists a clicked policy and closes the menu after confirmation", async () => {
    const save = stubModeApi("manual").mockResolvedValue({ approval_mode: "sandbox" });
    render(ApprovalModeControl);

    await openMenu();
    await fireEvent.click(screen.getByRole("menuitemradio", { name: /Work in sandbox/ }));

    await vi.waitFor(() => expect(save).toHaveBeenCalledWith("sandbox"));
    expect(screen.queryByRole("menu", { name: /approval mode/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /work in sandbox/i })).toBeInTheDocument();
  });

  // BUG-219 — the unattended posture. It must be selectable, and the menu must
  // say what it does, because the mode next to it means the opposite.
  it("offers the unattended decline posture and says what it does", async () => {
    const save = stubModeApi("manual").mockResolvedValue({ approval_mode: "dont_ask" });
    render(ApprovalModeControl);

    await openMenu();
    const decline = screen.getByRole("menuitemradio", { name: /Decline instead of asking/ });
    expect(decline).toHaveTextContent(/refused, not queued/i);
    await fireEvent.click(decline);

    await vi.waitFor(() => expect(save).toHaveBeenCalledWith("dont_ask"));
    expect(screen.getByRole("button", { name: /Decline, don't ask/i })).toBeInTheDocument();
  });

  it("restores the last confirmed policy and reports an error when saving fails", async () => {
    const save = stubModeApi("manual").mockRejectedValue(new Error("offline"));
    render(ApprovalModeControl);

    await openMenu();
    await fireEvent.click(screen.getByRole("menuitemradio", { name: /work in sandbox/i }));

    await vi.waitFor(() => expect(save).toHaveBeenCalledWith("sandbox"));
    expect(screen.getByRole("button", { name: /manually approve/i })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Approval mode was not saved.");
  });
});
