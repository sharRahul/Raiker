import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
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

/** QUI-L09 — one row per setting; its action opens the form in a dialog. */
function settingRow(label: string): HTMLElement {
  const row = screen
    .getAllByRole("heading", { name: label })
    .map((heading) => heading.closest(".setting-row"))
    .find((found) => found !== null);
  if (!(row instanceof HTMLElement)) throw new Error(`no row for ${label}`);
  return row;
}

async function openRow(label: string, action: string | RegExp) {
  await waitFor(() => settingRow(label));
  await fireEvent.click(within(settingRow(label)).getByRole("button", { name: action }));
  return within(screen.getByRole("dialog"));
}

describe("Security settings", () => {
  // QUI-P06 — how long an unanswered approval waits, in force and changeable.
  it("shows the approval time limit, 30 minutes by default, and saves a new one", async () => {
    let saved: Record<string, unknown> | null = null;
    stub({
      "GET /api/settings": () => ({
        settings: {},
        revision: "r1",
        status: { vault: "ok", mfa_enrolled: false, username: "alice" },
      }),
      "PUT /api/settings": (init) => {
        saved = JSON.parse(String(init?.body ?? "{}"));
        return { settings: {}, revision: "r2", merged_keys: [] };
      },
    });
    render(SecurityLogin);
    const select = await screen.findByRole("combobox", { name: "Unanswered approvals expire after" });
    await waitFor(() => expect(select).toHaveValue("30"));
    await fireEvent.change(select, { target: { value: "60" } });
    await waitFor(() => expect(saved).not.toBeNull());
    expect((saved as unknown as { settings: Record<string, unknown> }).settings).toMatchObject({
      "security.approval_timeout_minutes": 60,
    });
  });

  it("is a list of rows, each with its value and one action", async () => {
    stub({
      "GET /api/settings": () => ({ settings: {}, status: { vault: "missing", mfa_enrolled: false, username: "alice" } }),
    });
    render(SecurityLogin);
    for (const [label, action] of [
      ["Password", "Change"],
      ["Two-step sign-in", "Turn on"],
      ["Devices", "Manage"],
      ["Encryption", "Details"],
      ["Vault key", "Set up"],
      ["Standing approval grants", "Manage"],
    ]) {
      expect(await screen.findByRole("heading", { name: label })).toBeInTheDocument();
      expect(within(settingRow(label)).getAllByRole("button")).toHaveLength(1);
      expect(within(settingRow(label)).getByRole("button")).toHaveTextContent(action);
    }
    // No form is open on the page itself.
    expect(screen.queryByLabelText("Current password")).toBeNull();
    expect(screen.queryByLabelText("Vault key")).toBeNull();
  });

  it("shows encrypted storage separately from key-memory locking", async () => {
    stub({
      "GET /api/settings": () => ({ settings: {}, status: { vault: "configured_valid", mfa_enrolled: false, username: "alice" } }),
      "GET /api/security/credentials": () => [],
      "GET /api/security/findings": () => [],
      "GET /api/security/health": () => [],
      "GET /api/health": () => ({
        status: "ok",
        store: "ok",
        cipher_memory_security: "off",
        memory_security_mode: "auto",
        memory_security_probe: "failed",
        memory_security_reason: "auto_probe_host_crash",
        sqlcipher_version: "4.12.0",
      }),
    });

    render(SecurityLogin);

    await waitFor(() => expect(within(settingRow("Encryption")).getByText("On")).toBeInTheDocument());
    const dialog = await openRow("Encryption", "Details");
    expect(dialog.getByText("Encrypted")).toBeInTheDocument();
    expect(dialog.getByText("Degraded on this host")).toBeInTheDocument();
    expect(dialog.getByText(/4\.12\.0/)).toBeInTheDocument();
  });

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
      expect(within(settingRow("Vault key")).getByText(/Missing — connections fail closed/)).toBeInTheDocument();
    });
    expect(within(settingRow("Two-step sign-in")).getByText("Off")).toBeInTheDocument();
    await waitFor(() => expect(within(settingRow("Security scan")).getByText("1 finding")).toBeInTheDocument());
    const dialog = await openRow("Security scan", "Review");
    expect(dialog.getByText(/github.*warning/i)).toBeInTheDocument();
    expect(dialog.getByText(/Credential-like content detected/i)).toBeInTheDocument();
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
    const dialog = await openRow("Vault key", "Set up");
    await fireEvent.input(dialog.getByLabelText("Vault key"), { target: { value: "some-fernet-key" } });
    await fireEvent.input(dialog.getByLabelText(/Confirm password/), { target: { value: "pw" } });
    await fireEvent.click(dialog.getByRole("button", { name: /save key/i }));
    await waitFor(() => {
      expect(within(settingRow("Vault key")).getByText("Set")).toBeInTheDocument();
    });
  });

  it("shows the one-time recovery codes enrollment issues", async () => {
    stub({
      "GET /api/settings": () => ({ settings: {}, status: { vault: "configured_valid", mfa_enrolled: false, username: "alice" } }),
      "GET /api/security/credentials": () => [],
      "GET /api/security/findings": () => [],
      "GET /api/security/health": () => [],
      "POST /api/auth/mfa/enroll": () => ({
        secret: "JBSWY3DPEHPK3PXP",
        provisioning_uri: "otpauth://totp/Raiker:alice?secret=JBSWY3DPEHPK3PXP",
        backup_codes: ["aaaa-1111", "bbbb-2222"],
      }),
    });
    render(SecurityLogin);
    const dialog = await openRow("Two-step sign-in", "Turn on");
    await fireEvent.click(dialog.getByRole("button", { name: "Enroll in MFA" }));

    const codes = await screen.findByRole("list", { name: "Recovery codes" });
    expect(codes).toHaveTextContent("aaaa-1111");
    expect(codes).toHaveTextContent("bbbb-2222");
    expect(screen.getByText(/they are not shown again/)).toBeInTheDocument();
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
    await waitFor(() =>
      expect(within(settingRow("Standing approval grants")).getByText("1 active")).toBeInTheDocument(),
    );
    const dialog = await openRow("Standing approval grants", "Manage");
    expect(dialog.getByText("write_file")).toBeInTheDocument();
    await fireEvent.click(dialog.getByRole("button", { name: "Revoke" }));
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
    await openRow("Security scan", "Review");
    const button = await screen.findByRole("button", { name: "Check breach corpus" });
    await fireEvent.input(screen.getByLabelText("Password to check"), { target: { value: "example-password" } });
    expect(button).toBeDisabled();
    await fireEvent.click(screen.getByLabelText(/I opt in to a breach check/i));
    await fireEvent.click(button);
    await waitFor(() => expect(requestBody).toEqual({ password: "example-password", enabled: true }));
  });
});
