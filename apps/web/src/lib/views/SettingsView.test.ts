import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import SettingsView from "./SettingsView.svelte";

afterEach(() => vi.unstubAllGlobals());

function stubApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const path = url.split("?")[0];
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
    }),
  );
}

describe("9-section settings", () => {
  it("renders all nine sections in the rail", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    for (const label of [
      "General",
      "Notification",
      "Personalisation",
      "Voice",
      "Data Controls",
      "Storage",
      "Security & Login",
      "Trusted Contact",
      "Account",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("switches to the Account section and shows account deletion", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Account" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /delete my account/i })).toBeInTheDocument();
    });
  });

  it("switches to Voice and shows an honest not-yet-active state", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Voice" }));
    await waitFor(() => {
      expect(screen.getAllByText(/not yet active/i).length).toBeGreaterThan(0);
    });
  });
});
