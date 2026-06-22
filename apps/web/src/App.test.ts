import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import App from "./App.svelte";
import { NAV_ITEMS } from "./lib/nav";

// These tests exercise the always-rendered chrome (nav, top bar, STOP). The data-bound screens
// have their own tests; here the API is not mocked, so the app settles into the connection-error
// state — the chrome must still render and the STOP control must still work.
describe("App shell", () => {
  it("renders left-nav links for every IA section", () => {
    render(App);
    for (const item of NAV_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toBeInTheDocument();
    }
  });

  it("opens the STOP confirm dialog (no-op until M3)", async () => {
    render(App);
    expect(screen.queryByRole("dialog")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: /stop all tasks/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm/i })).toBeDisabled();
  });
});
