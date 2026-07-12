import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import SecurityLogin from "./SecurityLogin.svelte";
import { setToken } from "../../api";

afterEach(() => {
  vi.unstubAllGlobals();
  setToken(null);
});

function stub(routes: Record<string, (init?: RequestInit) => unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const path = url.split("?")[0];
      const method = (init?.method ?? "GET").toUpperCase();
      const key = `${method} ${path}`;
      const handler = routes[key];
      if (handler) return { ok: true, status: 200, json: async () => handler(init) } as Response;
      return { ok: false, status: 404, json: async () => ({ detail: { reason_code: "unrouted" } }) } as Response;
    }),
  );
}

describe("Security & Login settings", () => {
  it("shows the fail-closed pill when the vault is missing", async () => {
    stub({
      "GET /api/settings": () => ({
        settings: {},
        status: { vault: "missing", mfa_enrolled: false, username: "alice" },
      }),
    });
    render(SecurityLogin);
    await waitFor(() => {
      expect(screen.getByText(/Missing \/ Fail-Closed Active/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Not enrolled/)).toBeInTheDocument();
  });

  it("saves a vault key via elevated re-auth and flips the pill to valid", async () => {
    setToken("control-token");
    stub({
      "GET /api/settings": () => ({
        settings: {},
        status: { vault: "missing", mfa_enrolled: false, username: "alice" },
      }),
      "POST /api/auth/elevate": () => ({ token: "elevated-token" }),
      "PUT /api/vault/key": () => ({ state: "configured_valid" }),
    });
    render(SecurityLogin);
    await waitFor(() => expect(screen.getByLabelText("Vault key")).toBeInTheDocument());
    await fireEvent.input(screen.getByLabelText("Vault key"), { target: { value: "some-fernet-key" } });
    await fireEvent.input(screen.getByLabelText(/Confirm password/), { target: { value: "pw" } });
    await fireEvent.click(screen.getByRole("button", { name: /save key/i }));
    await waitFor(() => {
      expect(screen.getByText(/Active \/ Valid/)).toBeInTheDocument();
    });
  });
});
