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
      "GET /api/security/credentials": () => [{ provider: "github", status: "warning", due_at: "2026-07-20T00:00:00Z" }],
      "GET /api/security/findings": () => [{ code: "local_sensitive_pattern", severity: "high", summary: "Credential-like content detected." }],
      "GET /api/security/health": () => [],
    });
    render(SecurityLogin);
    await waitFor(() => {
      expect(screen.getByText(/Missing \/ Fail-Closed Active/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Not enrolled/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Credential security")).toBeInTheDocument();
      expect(screen.getByText(/github.*warning/i)).toBeInTheDocument();
      expect(screen.getByText(/Credential-like content detected/i)).toBeInTheDocument();
    });
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

  it("lists and revokes a standing approval grant", async () => {
    let revoked = false;
    stub({
      "GET /api/settings": () => ({ settings: {}, status: { vault: "configured_valid", mfa_enrolled: true, username: "alice" } }),
      "GET /api/security/credentials": () => [],
      "GET /api/security/findings": () => [],
      "GET /api/security/health": () => [],
      "GET /api/standing-grants": () => ({
        ok: true,
        grants: revoked
          ? []
          : [
              {
                grant_id: "grn_1",
                principal_id: "ai",
                granted_by: "principal_owner",
                action_type: "write_file",
                tool_name: "",
                scope_pattern: "coding",
                risk_ceiling: "medium",
                reason: "",
                created_at: "2026-07-20T00:00:00Z",
                expires_at: "2026-07-27T00:00:00Z",
                revoked: 0,
                use_count: 2,
                last_used_at: null,
              },
            ],
      }),
      "POST /api/standing-grants/grn_1/revoke": () => {
        revoked = true;
        return { ok: true, grant_id: "grn_1" };
      },
    });
    render(SecurityLogin);
    await waitFor(() => {
      expect(screen.getByText("Standing approval grants")).toBeInTheDocument();
      expect(screen.getByText("write_file")).toBeInTheDocument();
    });
    await fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(screen.getByText("No standing grants.")).toBeInTheDocument());
  });

  it("requires explicit consent before an opt-in breach check", async () => {
    let requestBody: unknown;
    stub({
      "GET /api/settings": () => ({ settings: {}, status: { vault: "configured_valid", mfa_enrolled: true, username: "alice" } }),
      "GET /api/security/credentials": () => [],
      "GET /api/security/findings": () => [],
      "GET /api/security/health": () => [],
      "POST /api/security/breach-check": (init) => {
        requestBody = JSON.parse(String(init?.body));
        return [];
      },
    });
    render(SecurityLogin);
    const button = await screen.findByRole("button", { name: "Check breach corpus" });
    await fireEvent.input(screen.getByLabelText("Password to check"), { target: { value: "example-password" } });
    expect(button).toBeDisabled();
    await fireEvent.click(screen.getByLabelText(/I opt in to a breach check/i));
    await fireEvent.click(button);
    await waitFor(() => expect(requestBody).toEqual({ password: "example-password", enabled: true }));
  });
});
