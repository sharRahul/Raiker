import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginView from "./LoginView.svelte";
import { LOGIN_RESULT, stubFetch } from "../test-helpers";

const onAuthenticated = vi.fn();

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

async function fillCredentials(password = "pw") {
  await fireEvent.input(screen.getByLabelText("Username"), { target: { value: "owner" } });
  await fireEvent.input(screen.getByLabelText("Password"), { target: { value: password } });
}

describe("LoginView", () => {
  it("renders the approved lock screen with exact identity and button text", () => {
    render(LoginView, { props: { onAuthenticated } });
    expect(screen.getByRole("heading", { name: "Unlock Raiker" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unlock Raiker" })).toBeInTheDocument();
    expect(screen.getByText("Γ_")).toBeInTheDocument();
    expect(screen.getByText("I am ready when you are.")).toBeInTheDocument();
    expect(screen.queryByText(/governed AI agent/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/workspace locked|ready to unlock|checkpoint|scheduled run/i)).not.toBeInTheDocument();
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
    stubFetch({ "POST /api/auth/login": LOGIN_RESULT });
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
      vi.fn(async () => ({ ok: false, status: 401, json: async () => ({ detail: "bad" }) }) as Response),
    );
    render(LoginView, { props: { onAuthenticated } });
    await fillCredentials();
    await fireEvent.click(screen.getByRole("button", { name: "Unlock Raiker" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Authentication failed.");
  });

  it("transitions to MFA and verifies the one-time code", async () => {
    stubFetch({
      "POST /api/auth/login": { stage: "mfa_required", principal_id: "", token: null, ticket: "ticket_1" },
      "POST /api/auth/mfa/verify": LOGIN_RESULT,
    });
    render(LoginView, { props: { onAuthenticated } });
    await fillCredentials();
    await fireEvent.click(screen.getByRole("button", { name: "Unlock Raiker" }));
    expect(await screen.findByLabelText("Authentication code")).toHaveAttribute("autocomplete", "one-time-code");
    await fireEvent.input(screen.getByLabelText("Authentication code"), { target: { value: "123456" } });
    await fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("prin_owner"));
  });

  it("keeps registration visually distinct and validates confirmation", async () => {
    stubFetch({ "POST /api/auth/register": LOGIN_RESULT });
    render(LoginView, { props: { onAuthenticated } });
    await fireEvent.click(screen.getByRole("button", { name: "Create local account" }));
    expect(screen.getByRole("heading", { name: "Create local account" })).toBeInTheDocument();
    expect(screen.getByText("Hello! I am Raiker. Nice to meet you.")).toBeInTheDocument();
    await fillCredentials("pw1");
    await fireEvent.input(screen.getByLabelText("Confirm password"), { target: { value: "pw2" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match.");
    await fireEvent.input(screen.getByLabelText("Confirm password"), { target: { value: "pw1" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("prin_owner"));
  });

  it("supports password visibility and runtime verification states", async () => {
    const { rerender } = render(LoginView, { props: { onAuthenticated } });
    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");
    await fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    await rerender({ onAuthenticated, runtimeState: "verifying" });
    expect(screen.getByRole("status")).toHaveTextContent("Verifying runtime…");
    expect(screen.getByLabelText("Username")).toBeDisabled();
    await rerender({ onAuthenticated, runtimeState: "verification_failed" });
    expect(screen.getByRole("alert")).toHaveTextContent(/workspace remains locked/i);
    expect(screen.getByText("I cannot reach my runtime.")).toBeInTheDocument();
  });
});
