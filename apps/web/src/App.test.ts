import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import App from "./App.svelte";
import { NAV_ITEMS } from "./lib/nav";

describe("App shell", () => {
  it("renders left-nav links for every IA section", () => {
    render(App);
    for (const item of NAV_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toBeInTheDocument();
    }
  });

  it("shows the fixture-data indicator instead of implying a live runtime", () => {
    render(App);
    expect(screen.getByText(/fixture data/i)).toBeInTheDocument();
  });

  it("opens the STOP confirm dialog (no-op in M1)", async () => {
    render(App);
    expect(screen.queryByRole("dialog")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: /stop all tasks/i }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    // Confirm is disabled until wired in M3.
    expect(screen.getByRole("button", { name: /confirm/i })).toBeDisabled();
  });
});
