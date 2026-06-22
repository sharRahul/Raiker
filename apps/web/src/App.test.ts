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

  it("opens the STOP confirm dialog with a wired, enabled confirm action", async () => {
    render(App);
    expect(screen.queryByRole("dialog")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: /stop all tasks/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    // Wired in M3: the confirm action is enabled and the copy is safe-boundary, not force-kill.
    const confirm = screen.getByRole("button", { name: /stop at safe boundary/i });
    expect(confirm).toBeEnabled();
    expect(screen.getByText(/next safe boundary/i)).toBeInTheDocument();
  });
});
