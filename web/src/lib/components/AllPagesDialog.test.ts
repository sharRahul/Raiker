import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import AllPagesDialog from "./AllPagesDialog.svelte";
import { rememberPage } from "../recentPages";

afterEach(() => window.localStorage.clear());

describe("the More window", () => {
  it("groups by what an owner comes to do, with diagnostics and help last", () => {
    render(AllPagesDialog, { open: true, current: "home" });
    const dialog = screen.getByRole("dialog", { name: /^more$/i });
    const headings = within(dialog).getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings).toEqual(["Review", "Connect", "Settings", "Diagnostics & help"]);
    const connect = within(dialog).getByRole("heading", { name: "Connect" }).closest("section")!;
    for (const label of ["Messaging", "Models", "Extensions"]) {
      expect(within(connect as HTMLElement).getByRole("link", { name: label })).toBeInTheDocument();
    }
    const settings = within(dialog).getByRole("heading", { name: "Settings" }).closest("section")!;
    expect(within(settings as HTMLElement).getByRole("link", { name: "Permissions" })).toBeInTheDocument();
    expect(within(settings as HTMLElement).getByRole("link", { name: /^settings/i })).toHaveAttribute("href", "#/settings");
  });

  it("hands search to the command palette instead of keeping its own box", async () => {
    const onOpenPalette = vi.fn();
    const onClose = vi.fn();
    render(AllPagesDialog, { open: true, current: "home", onOpenPalette, onClose });
    expect(screen.queryByRole("textbox")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: /search pages, settings and commands/i }));
    expect(onClose).toHaveBeenCalled();
    expect(onOpenPalette).toHaveBeenCalled();
  });

  it("lists recent destinations and says where you are", () => {
    rememberPage("models");
    rememberPage("capabilities");
    render(AllPagesDialog, { open: true, current: "capabilities" });
    const recent = screen.getByRole("heading", { name: "Recent" }).closest("section")!;
    expect(within(recent as HTMLElement).getAllByRole("link").map((a) => a.textContent?.trim())).toEqual(["Models"]);
    expect(screen.getByText("You are on", { exact: false })).toHaveTextContent("You are on Permissions");
  });

  it("offers Back, which closes it like Close does", async () => {
    const onClose = vi.fn();
    render(AllPagesDialog, { open: true, current: "home", onClose });
    await fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onClose).toHaveBeenCalled();
  });
});
