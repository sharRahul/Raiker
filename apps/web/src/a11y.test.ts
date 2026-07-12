import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.svelte";
import { BOOTSTRAP_ROUTES, stubFetch } from "./lib/test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

async function signIn() {
  await waitFor(() => expect(screen.getByLabelText("Username")).toBeInTheDocument());
  await fireEvent.input(screen.getByLabelText("Username"), { target: { value: "owner" } });
  await fireEvent.input(screen.getByLabelText("Password"), { target: { value: "pw" } });
  await fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
}

describe("accessibility landmarks", () => {
  it("exposes a skip link, labelled navigation, and a main landmark", async () => {
    stubFetch(BOOTSTRAP_ROUTES);
    render(App);
    await signIn();
    await waitFor(() => {
      expect(screen.getByText("Runtime ready")).toBeInTheDocument();
    });
    const skip = screen.getByText(/skip to content/i);
    expect(skip).toHaveAttribute("href", "#main");
    expect(screen.getByRole("navigation", { name: /primary/i })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("marks the active nav item with aria-current", async () => {
    stubFetch(BOOTSTRAP_ROUTES);
    window.location.hash = "#/capabilities";
    render(App);
    await signIn();
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /capabilities/i })).toHaveAttribute("aria-current", "page");
    });
  });

  it("announces connection state via a status/alert region on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("refused");
      }),
    );
    render(App);
    await signIn();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
