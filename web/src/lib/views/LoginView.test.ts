import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginView from "./LoginView.svelte";
import { LOGIN_RESULT, stubFetch } from "../test-helpers";

const onAuthenticated = vi.fn();
const HEALTH_OK = { "GET /api/health": { status: "ok" } };

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

async function fillCredentials(password = "pw") {
  await fireEvent.input(screen.getByLabelText("Username"), { target: { value: "owner" } });
  await fireEvent.input(screen.getByLabelText("Password"), { target: { value: password } });
}

describe("LoginView", () => {
  it("renders the approved lock screen with exact identity and button text", async () => {
    stubFetch({ ...HEALTH_OK });
    render(LoginView, { props: { onAuthenticated } });
    expect(screen.getByRole("heading", { name: "Unlock Raiker" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unlock Raiker" })).toBeInTheDocument();
    // The large Raiker core and the top-left mark are the production rendered
    // icon, exposed as labelled images (theme-swapped via CSS background).
    expect(screen.getAllByRole("img", { name: "Raiker" }).length).toBeGreaterThanOrEqual(2);
    await waitFor(() => expect(screen.getByText("I am ready when you are.")).toBeInTheDocument());
    // The greeting and the idle statement are never shown together.
    expect(screen.queryByText("Hello! I am Raiker.")).not.toBeInTheDocument();
    // No marketing copy, fabricated pre-auth status details, or unsupported
    // auth affordances unsupported by the local backend.
    expect(screen.queryByText(/governed AI agent/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/workspace locked|ready to unlock|checkpoint|scheduled run|task/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/remember me/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Forgot password?" })).toBeInTheDocument();
    // The status bar carries only the health-probe-backed item.
    await waitFor(() => expect(screen.getByText("Runtime operational")).toBeInTheDocument());
  });

  it("submits the unlock form from the keyboard", async () => {
    const fetchMock = stubFetch({
      ...HEALTH_OK,
      "POST /api/auth/login": LOGIN_RESULT,
      "POST /api/auth/session": {
        token: "test-token",
        session_id: "apisess_1",
        principal_id: "prin_owner",
        expires_at: null,
      },
    });
    render(LoginView, { props: { onAuthenticated } });
    await fillCredentials();

    // Enter in the password field submits through the real <form>, so the
    // whole flow is keyboard-operable without reaching for the button.
    const form = screen.getByLabelText("Password").closest("form")!;
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/login",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("shows no state message until the health probe resolves", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );
    render(LoginView, { props: { onAuthenticated } });
    expect(screen.queryByText("I am ready when you are.")).not.toBeInTheDocument();
    expect(screen.queryByText("I cannot reach my runtime.")).not.toBeInTheDocument();
  });

  it("welcomes a first-run user and calls account creation consistently", async () => {
    stubFetch({ ...HEALTH_OK, "GET /api/auth/bootstrap-status": { can_register: true } });
    render(LoginView, { props: { onAuthenticated } });
    expect(await screen.findByRole("heading", { name: "Welcome to Raiker" })).toBeInTheDocument();
    expect(screen.getByText("Create a User Account to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create a User Account" })).toBeInTheDocument();
  });

  it("reports an unreachable runtime from the real health probe", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );
    render(LoginView, { props: { onAuthenticated } });
    await waitFor(() =>
      expect(screen.getByText("I cannot reach my runtime.")).toBeInTheDocument(),
    );
  });

  it("uses an honest busy label while unlocking", async () => {
    let resolve!: (value: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((r) => {
            resolve = r;
          }),
      ),
    );
    render(LoginView, { props: { onAuthenticated } });
    await fillCredentials();
    await fireEvent.click(screen.getByRole("button", { name: "Unlock Raiker" }));
    expect(screen.getByRole("button", { name: "Unlocking…" })).toBeDisabled();
    resolve({ ok: true, status: 200, json: async () => LOGIN_RESULT } as Response);
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("prin_owner"));
  });

  it("logs in successfully without persisting the bearer token", async () => {
    stubFetch({ ...HEALTH_OK, "POST /api/auth/login": LOGIN_RESULT });
    render(LoginView, { props: { onAuthenticated } });
    await fillCredentials();
    await fireEvent.click(screen.getByRole("button", { name: "Unlock Raiker" }));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("prin_owner"));
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("shows generic login failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          ({ ok: false, status: 401, json: async () => ({ detail: "bad" }) }) as Response,
      ),
    );
    render(LoginView, { props: { onAuthenticated } });
    await fillCredentials();
    await fireEvent.click(screen.getByRole("button", { name: "Unlock Raiker" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Authentication failed.");
  });

  it("transitions to MFA, moves focus, and verifies the one-time code", async () => {
    stubFetch({
      ...HEALTH_OK,
      "POST /api/auth/login": { stage: "mfa_required", principal_id: "", token: null, ticket: "ticket_1" },
      "POST /api/auth/mfa/verify": LOGIN_RESULT,
    });
    render(LoginView, { props: { onAuthenticated } });
    await fillCredentials();
    await fireEvent.click(screen.getByRole("button", { name: "Unlock Raiker" }));
    const codeInput = await screen.findByLabelText("Authentication code");
    expect(codeInput).toHaveAttribute("autocomplete", "one-time-code");
    await waitFor(() => expect(document.activeElement).toBe(codeInput));
    await fireEvent.input(codeInput, { target: { value: "123456" } });
    await fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("prin_owner"));
  });

  it("registers the first account directly from the first-run CTA and validates confirmation", async () => {
    // FIX-01: on first run the primary CTA must create the account, not attempt a
    // login there is no account for. The greeting, the confirm-password field, and
    // the register submit all follow the first-run intent — no mode switch needed.
    const fetchMock = stubFetch({ ...HEALTH_OK, "GET /api/auth/bootstrap-status": { can_register: true }, "POST /api/auth/register": LOGIN_RESULT });
    render(LoginView, { props: { onAuthenticated } });
    await screen.findByRole("heading", { name: "Welcome to Raiker" });
    // The account-creation greeting shows immediately on first run.
    await waitFor(() => expect(screen.getByText("Hello! I am Raiker.")).toBeInTheDocument());
    expect(screen.getByText("Nice to meet you.")).toBeInTheDocument();
    expect(screen.queryByText("I am ready when you are.")).not.toBeInTheDocument();
    // The primary CTA creates the account, so the password is a new one.
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
    const primary = screen.getByRole("button", { name: "Create a User Account" });
    await fillCredentials("pw1");
    await fireEvent.input(screen.getByLabelText("Confirm password"), { target: { value: "pw2" } });
    await fireEvent.click(primary);
    expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match.");
    await fireEvent.input(screen.getByLabelText("Confirm password"), { target: { value: "pw1" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create a User Account" }));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("prin_owner"));
    // The CTA registered rather than attempting a doomed login.
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/register", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).not.toHaveBeenCalledWith("/api/auth/login", expect.anything());
  });

  it("creates an account in a separate same-server instance from the login screen", async () => {
    // REM-LAUNCH-02 — this control used to be labelled "Create a User Account",
    // identical to the register button that makes an account on *this*
    // instance, and sat at the same weight as "Forgot password?". It opens a
    // separate Raiker with its own database in a new tab, and the only way to
    // find that out was to press it.
    stubFetch({ ...HEALTH_OK, "POST /api/instances": { name: "alex", url: "/instances/alex/" } });
    const open = vi.spyOn(window, "open").mockReturnValue({} as Window);
    render(LoginView, { props: { onAuthenticated } });
    // Unlock stays the primary action, and the branch explains itself before it
    // is taken rather than after.
    expect(screen.getByRole("button", { name: /^Unlock Raiker$/ })).toHaveClass("btn-primary");
    expect(
      screen.getByText(/own workspace, models and memory/i),
    ).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Use or create another instance" }));
    await fireEvent.input(screen.getByLabelText("Instance name"), { target: { value: "alex" } });
    await fillCredentials();
    await fireEvent.input(screen.getByLabelText("Confirm password"), { target: { value: "pw" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create account and open Raiker" }));
    await waitFor(() => expect(open).toHaveBeenCalledWith("/instances/alex/", "_blank", "noopener"));
  });

  it("runs the local password recovery flow with an accessible pending state", async () => {
    stubFetch({
      ...HEALTH_OK,
      "POST /api/auth/password-recovery/begin": { ok: true, ticket: "recovery_1" },
      "POST /api/auth/password-recovery/complete": { ok: true },
    });
    render(LoginView, { props: { onAuthenticated } });
    await fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
    await fireEvent.input(screen.getByLabelText("Username"), { target: { value: "owner" } });
    await fireEvent.click(screen.getByRole("button", { name: "Begin recovery" }));
    const code = await screen.findByLabelText("Recovery verification code");
    expect(screen.getByText(/existing authenticator code or one-time backup recovery code is required/i)).toBeInTheDocument();
    expect(code).toHaveAttribute("autocomplete", "one-time-code");
    await fireEvent.input(code, { target: { value: "123456" } });
    await fireEvent.input(screen.getByLabelText("New password"), { target: { value: "new-password" } });
    await fireEvent.click(screen.getByRole("button", { name: "Reset password" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Unlock Raiker" })).toBeInTheDocument());
    expect(screen.getByText("Your password was changed. Unlock with the new one.")).toHaveAttribute("role", "status");
  });

  it("supports password visibility with an accessible toggle", async () => {
    stubFetch({ ...HEALTH_OK });
    render(LoginView, { props: { onAuthenticated } });
    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await fireEvent.click(toggle);
    expect(password).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("disables the form and announces progress while verifying the runtime", async () => {
    stubFetch({ ...HEALTH_OK });
    const { rerender } = render(LoginView, { props: { onAuthenticated } });
    await rerender({ onAuthenticated, runtimeState: "verifying" });
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Verifying runtime…");
    await waitFor(() => expect(document.activeElement).toBe(status));
    expect(screen.getByLabelText("Username")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Unlock Raiker" })).toBeDisabled();
    expect(screen.getByRole("main")).toHaveAttribute("aria-busy", "true");
  });

  it("keeps the workspace locked and honest when runtime verification fails", async () => {
    stubFetch({ ...HEALTH_OK });
    const { rerender } = render(LoginView, { props: { onAuthenticated } });
    await rerender({ onAuthenticated, runtimeState: "verification_failed" });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/workspace remains locked/i);
    await waitFor(() => expect(document.activeElement).toBe(alert));
    expect(screen.getByText("I cannot reach my runtime.")).toBeInTheDocument();
    // The form stays usable so the user can retry.
    expect(screen.getByLabelText("Username")).not.toBeDisabled();
  });
});

it("says an instance already has its owner instead of blaming the password", async () => {
  // BUG-265 — the server refuses a second account by policy and says so. The
  // screen used to replace that with "Authentication failed.", which sends an
  // owner looking for a wrong password that was in fact correct.
  stubFetch({
    "GET /api/health": { status: "ok", store: "ok" },
    "GET /api/auth/bootstrap-status": { can_register: true },
    "POST /api/auth/register": {
      __status: 409,
      detail: "Create new user and separate Raiker instance instead",
    },
  });
  render(LoginView, { onAuthenticated: vi.fn(), runtimeState: "locked" });

  await screen.findByText(/Create a User Account to get started/);
  await fireEvent.input(screen.getByLabelText("Username"), { target: { value: "Rahul" } });
  await fireEvent.input(screen.getByLabelText("Password"), { target: { value: "Ithink@10" } });
  await fireEvent.input(screen.getByLabelText("Confirm password"), {
    target: { value: "Ithink@10" },
  });
  await fireEvent.click(screen.getByRole("button", { name: "Create a User Account" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(/already has its owner/);
});

// BUG-323 — a workspace whose database will not open can be restored from the
// lock screen, because Account (where backups live) needs a sign-in it cannot give.
describe("LoginView — restoring from the lock screen", () => {
  const BACKUP = {
    backup_id: "bkp_one",
    reason: "owner",
    created_at: "2026-10-05T10:00:00Z",
    size_bytes: 2_400_000,
    sha256: "x",
    schema_migrations: 190,
    latest_migration: "RAIKER-2093-task-tool-limit",
    counts: { sessions: 3, approved_memory: 2 },
    key_fingerprint: "fp1",
    included: ["database", "memory_files"],
    not_included: ["checkpoints"],
    state: "verified",
    verified_at: "2026-10-05T10:00:00Z",
    detail: "",
    schema_generation: 195,
    opens_here: true,
  };
  const UNREADABLE = {
    status: "degraded",
    store: "unavailable",
    reason: "store_unreadable",
    detail: "The workspace database exists but this workspace key does not open it.",
  };

  function sequencedFetch(listing: unknown) {
    let healthCalls = 0;
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const method = (init?.method ?? "GET").toUpperCase();
      const answer = (status: number, body: unknown) =>
        ({ ok: status < 400, status, json: async () => body }) as Response;
      if (url.endsWith("/api/health")) {
        healthCalls += 1;
        return answer(200, healthCalls > 1 && restoredOnce ? { status: "ok", store: "ok", reason: "", detail: "" } : UNREADABLE);
      }
      if (url.endsWith("/api/recovery/backups")) return answer(200, listing);
      if (url.endsWith("/api/recovery/restore") && method === "POST") {
        restoredOnce = true;
        return answer(200, {
          ok: true,
          backup_id: "bkp_one",
          quarantine: ".raiker/quarantine/20261005T120000Z",
          counts: { sessions: 3, approved_memory: 2 },
          deletions_applied: { memory_forget: 1, memory_purge: 0, session_delete: 0 },
        });
      }
      if (url.endsWith("/api/auth/bootstrap-status")) return answer(200, { can_register: false });
      return answer(404, { detail: { reason_code: "unrouted" } });
    });
    let restoredOnce = false;
    vi.stubGlobal("fetch", mock);
    return mock;
  }

  it("lists the backups, asks once, restores, and lets the owner sign in", async () => {
    const fetchMock = sequencedFetch({
      reason: "store_unreadable",
      key_fingerprint: "fp1",
      schema_generation: 195,
      backups: [BACKUP],
    });
    render(LoginView, { props: { onAuthenticated } });
    await waitFor(() => expect(screen.getByTestId("lock-recovery")).toBeInTheDocument());
    expect(await screen.findByText(/3 conversations · 2 memories/)).toBeInTheDocument();
    // One deliberate step before anything changes.
    await fireEvent.click(screen.getByRole("button", { name: "Restore…" }));
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/api/recovery/restore"))).toBe(false);
    await fireEvent.click(screen.getByRole("button", { name: "Restore this backup" }));
    const restored = await screen.findByTestId("lock-restored");
    expect(restored).toHaveTextContent(".raiker/quarantine/20261005T120000Z");
    // The store opens now: the panel and the error went with it, the form is live.
    expect(screen.queryByTestId("lock-recovery")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Username")).not.toBeDisabled());
  });

  it("does not offer a backup a newer Raiker made, or one made with another key", async () => {
    sequencedFetch({
      reason: "store_schema_newer",
      key_fingerprint: "fp1",
      schema_generation: 195,
      backups: [
        { ...BACKUP, backup_id: "bkp_newer", schema_generation: 199, opens_here: false },
        { ...BACKUP, backup_id: "bkp_other", key_fingerprint: "fp2" },
      ],
    });
    render(LoginView, { props: { onAuthenticated } });
    expect(await screen.findByText(/Made by a newer Raiker/)).toBeInTheDocument();
    expect(screen.getByText("Made with another workspace key.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Restore…" })).not.toBeInTheDocument();
    expect(screen.getByText(/A newer Raiker last opened this workspace/)).toBeInTheDocument();
  });

  it("offers nothing when the key itself is missing", async () => {
    stubFetch({
      "GET /api/health": { ...UNREADABLE, reason: "store_key_missing" },
      "GET /api/auth/bootstrap-status": { can_register: false },
    });
    render(LoginView, { props: { onAuthenticated } });
    await waitFor(() => expect(screen.getByText(/I cannot open my encrypted store/)).toBeInTheDocument());
    expect(screen.queryByTestId("lock-recovery")).not.toBeInTheDocument();
  });
});
