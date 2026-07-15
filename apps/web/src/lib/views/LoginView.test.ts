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
    // auth affordances (the backend has no remember-me or password reset).
    expect(screen.queryByText(/governed AI agent/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/workspace locked|ready to unlock|checkpoint|scheduled run|task/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/remember me/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/forgot password/i)).not.toBeInTheDocument();
    // The status bar carries only the health-probe-backed item.
    await waitFor(() => expect(screen.getByText("Runtime operational")).toBeInTheDocument());
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

  it("keeps registration visually distinct, greets, and validates confirmation", async () => {
    stubFetch({ ...HEALTH_OK, "POST /api/auth/register": LOGIN_RESULT });
    render(LoginView, { props: { onAuthenticated } });
    await fireEvent.click(screen.getByRole("button", { name: "Create local account" }));
    expect(screen.getByRole("heading", { name: "Create local account" })).toBeInTheDocument();
    expect(screen.getByText("Hello! I am Raiker.")).toBeInTheDocument();
    expect(screen.getByText("Nice to meet you.")).toBeInTheDocument();
    expect(screen.queryByText("I am ready when you are.")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
    await fillCredentials("pw1");
    await fireEvent.input(screen.getByLabelText("Confirm password"), { target: { value: "pw2" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match.");
    await fireEvent.input(screen.getByLabelText("Confirm password"), { target: { value: "pw1" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("prin_owner"));
  });

  it("creates a separate same-server instance from the login screen", async () => {
    stubFetch({ ...HEALTH_OK, "POST /api/instances": { name: "alex", url: "/instances/alex/" } });
    const open = vi.spyOn(window, "open").mockReturnValue({} as Window);
    render(LoginView, { props: { onAuthenticated } });
    await fireEvent.click(screen.getByRole("button", { name: "Create separate instance" }));
    await fireEvent.input(screen.getByLabelText("Instance name"), { target: { value: "alex" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create and open instance" }));
    await waitFor(() => expect(open).toHaveBeenCalledWith("/instances/alex/", "_blank", "noopener"));
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
