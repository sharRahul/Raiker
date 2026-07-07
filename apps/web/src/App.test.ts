import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.svelte";
import { BOOTSTRAP_ROUTES, stubFetch } from "./lib/test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

describe("App shell", () => {
  it("connects, then shows the runtime status and grouped navigation", async () => {
    stubFetch(BOOTSTRAP_ROUTES);
    render(App);
    await waitFor(() => {
      expect(screen.getByText("Runtime ready")).toBeInTheDocument();
    });
    // Grouped nav with every governed surface reachable.
    const nav = screen.getByRole("navigation", { name: /primary/i });
    expect(nav).toBeInTheDocument();
    for (const label of [
      "Chat",
      "Approvals",
      "Tasks",
      "Sessions",
      "Capabilities",
      "Models",
      "Checkpoints",
      "Audit log",
      "Diagnostics",
      "Settings",
    ]) {
      expect(screen.getByRole("link", { name: new RegExp(label, "i") })).toBeInTheDocument();
    }
    // The acting principal and mode are surfaced, honestly, from the API.
    expect(screen.getByText("prin_owner")).toBeInTheDocument();
    expect(screen.getByText("local_single_user_runtime")).toBeInTheDocument();
  });

  it("shows an honest connection error when the local API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );
    render(App);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach the local raiker api/i);
    });
    expect(screen.getByText(/never fabricates data/i)).toBeInTheDocument();
  });
});
