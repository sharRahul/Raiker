// Settings holds only supported preferences and security posture. Saves are
// serialized through one queue, confirmed by the server, and rolled back to
// the last server snapshot on failure — a failed write is never silent.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import SettingsView from "./SettingsView.svelte";

afterEach(() => vi.unstubAllGlobals());

function stubApi(options: { failPut?: boolean } = {}) {
  const putBodies: unknown[] = [];
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const path = url.split("?")[0];
    const method = (init?.method ?? "GET").toUpperCase();
    if (path === "/api/settings" && method === "PUT") {
      putBodies.push(JSON.parse(String(init?.body)));
      if (options.failPut) {
        return { ok: false, status: 500, json: async () => ({ detail: {} }) } as Response;
      }
      return { ok: true, status: 200, json: async () => ({ ok: true }) } as Response;
    }
    const bodies: Record<string, unknown> = {
      "/api/settings": {
        settings: {},
        status: { vault: "missing", mfa_enrolled: false, username: "alice" },
      },
      "/api/auth/sessions": [],
      "/api/runtime-mode": {
        mode_name: "local_single_user_runtime",
        status: "active",
        activated_by: "alice",
        activated_at: "",
        reason: "",
        allowed_modes: ["local_single_user_runtime"],
      },
      "/api/diagnostics": { counts: { sessions: 0, events: 0, tasks: 0, checkpoints: 0 } },
    };
    if (path in bodies) return { ok: true, status: 200, json: async () => bodies[path] } as Response;
    return { ok: false, status: 404, json: async () => ({ detail: {} }) } as Response;
  });
  vi.stubGlobal("fetch", mock);
  return { mock, putBodies };
}

describe("supported-preferences settings", () => {
  it("renders only sections the runtime actually backs", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    for (const label of [
      "General",
      "Notifications",
      "Personalisation",
      "Security & sign-in",
      "Account",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: "Storage" })).not.toBeInTheDocument();
    // Unsupported surfaces are removed, not presented as settings.
    expect(screen.queryByRole("button", { name: "Voice" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Trusted Contact" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Data Controls" })).toBeNull();
  });

  it("saves a preference through the queue and confirms it", async () => {
    const { putBodies } = stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    const toggle = await screen.findByLabelText(/in-app popups/i);
    await fireEvent.click(toggle);
    expect(screen.getByText(/you have unsaved changes/i)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(putBodies.length).toBe(1));
    expect((putBodies[0] as { settings: Record<string, unknown> }).settings["notification.in_app"]).toBe(false);
    await waitFor(() => expect(screen.getByText(/all changes saved/i)).toBeInTheDocument());
  });

  it("rolls back to the last server snapshot when a save fails", async () => {
    stubApi({ failPut: true });
    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    const toggle = await screen.findByLabelText(/in-app popups/i);
    expect((toggle as HTMLInputElement).checked).toBe(true);
    await fireEvent.click(toggle);
    await fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    // The failed write surfaces a page-level error and the control reverts.
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/couldn't save/i));
    await waitFor(() => expect((screen.getByLabelText(/in-app popups/i) as HTMLInputElement).checked).toBe(true));
  });

  it("switches to the Account section and shows account deletion", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Account" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /delete my account/i })).toBeInTheDocument();
    });
  });
});
