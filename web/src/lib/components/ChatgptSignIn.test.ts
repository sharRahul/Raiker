import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ChatgptSignIn from "./ChatgptSignIn.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("ChatgptSignIn (FIXED-1390)", () => {
  it("opens the sign-in page in the owner's browser and adopts the account once signed in", async () => {
    const opened: string[] = [];
    vi.stubGlobal("open", (url: string) => {
      opened.push(url);
      return null;
    });
    const fetchMock = stubFetch({
      "POST /api/models/chatgpt-codex/login": {
        ok: true,
        connection_status: "login_pending",
        method: "browser",
        url: "https://auth.openai.com/oauth/authorize?state=x",
        user_code: null,
      },
      "GET /api/models/chatgpt-codex/status": { connection_status: "available", plan_type: "plus" },
      "POST /api/models/chatgpt-codex/connection": {
        ok: true,
        connection_status: "connected",
        plan_type: "plus",
        connection_configured: true,
      },
    });
    const onconnected = vi.fn();
    render(ChatgptSignIn, { onconnected });
    await fireEvent.click(screen.getByRole("button", { name: "Sign in with ChatGPT" }));
    expect(await screen.findByText(/Finish signing in to ChatGPT/)).toBeInTheDocument();
    expect(opened).toEqual(["https://auth.openai.com/oauth/authorize?state=x"]);
    // Even if the window was blocked, the same page is one link away.
    expect(screen.getByRole("link", { name: "Open sign-in again" })).toHaveAttribute(
      "href",
      "https://auth.openai.com/oauth/authorize?state=x",
    );
    await waitFor(() => expect(onconnected).toHaveBeenCalledWith("plus"), { timeout: 4000 });
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) => String(url).endsWith("/connection") && (init as RequestInit).method === "POST",
      ),
    ).toBe(true);
  });

  it("shows a device code and its page, and cancels the sign-in", async () => {
    const fetchMock = stubFetch({
      "POST /api/models/chatgpt-codex/login": {
        ok: true,
        connection_status: "login_pending",
        method: "device_code",
        url: "https://auth.openai.com/codex/device",
        user_code: "WXYZ-9876",
      },
      "GET /api/models/chatgpt-codex/status": { connection_status: "not_connected", plan_type: null },
      "DELETE /api/models/chatgpt-codex/login": { ok: true },
    });
    render(ChatgptSignIn);
    await fireEvent.click(screen.getByRole("button", { name: "Sign in with a code" }));
    expect(await screen.findByLabelText("One-time code")).toHaveTextContent("WXYZ-9876");
    expect(screen.getByRole("link", { name: "Open the sign-in page" })).toHaveAttribute(
      "href",
      "https://auth.openai.com/codex/device",
    );
    const body = JSON.parse(
      String((fetchMock.mock.calls.find(([url]) => String(url).endsWith("/login"))?.[1] as RequestInit).body),
    );
    expect(body).toEqual({ method: "device_code" });
    await fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Sign in with ChatGPT" })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) => String(url).endsWith("/login") && (init as RequestInit).method === "DELETE",
        ),
      ).toBe(true),
    );
  });

  it("tells the owner how to install Codex when it is missing", async () => {
    stubFetch({
      "POST /api/models/chatgpt-codex/login": {
        __status: 409,
        detail: { reason_code: "codex_app_server_not_installed" },
      },
    });
    render(ChatgptSignIn);
    await fireEvent.click(screen.getByRole("button", { name: "Sign in with ChatGPT" }));
    expect(await screen.findByText("Codex is not installed on this device.")).toBeInTheDocument();
    expect(screen.getByText("npm install -g @openai/codex")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check again" })).toBeInTheDocument();
  });

  it("reports a sign-in Codex said failed instead of waiting forever", async () => {
    vi.stubGlobal("open", () => null);
    stubFetch({
      "POST /api/models/chatgpt-codex/login": {
        ok: true,
        connection_status: "login_pending",
        method: "browser",
        url: "https://auth.openai.com/oauth/authorize",
        user_code: null,
      },
      "GET /api/models/chatgpt-codex/status": {
        connection_status: "signed_out",
        plan_type: null,
        login_error: "access_denied",
      },
    });
    render(ChatgptSignIn);
    await fireEvent.click(screen.getByRole("button", { name: "Sign in with ChatGPT" }));
    expect(await screen.findByRole("alert", {}, { timeout: 4000 })).toHaveTextContent(
      "ChatGPT sign-in did not finish (access_denied)",
    );
  });
});
