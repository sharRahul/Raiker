// Settings holds only supported preferences and security posture. Saves are
// serialized through one queue, confirmed by the server, and rolled back to
// the last server snapshot on failure — a failed write is never silent.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import SettingsView from "./SettingsView.svelte";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

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
        mode_name: "raiker_runtime",
        status: "active",
        activated_by: "alice",
        activated_at: "",
        reason: "",
        allowed_modes: ["raiker_runtime"],
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
  it("separates Personal and System sections into labelled groups", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    const personal = screen.getByRole("group", { name: "Personal settings" });
    const system = screen.getByRole("group", { name: "System settings" });
    expect(within(personal).getByRole("button", { name: "Account" })).toBeVisible();
    for (const label of ["Web access", "Git credential", "Runtime configuration"]) {
      expect(within(system).getByRole("button", { name: label })).toBeVisible();
      expect(within(personal).queryByRole("button", { name: label })).toBeNull();
    }
  });

  it.each([
    ["general", "General"], ["notification", "Notifications"],
    ["personalisation", "Personalisation"], ["security", "Security & sign-in"],
    ["privacy", "Privacy"], ["account", "Account"], ["web-access", "Web access"],
    ["git-credential", "Git credential"], ["runtime", "Runtime configuration"],
  ])("renders the %s deep link with its named heading", async (tab, heading) => {
    stubApi();
    render(SettingsView, { props: { principal: "alice", tab } });
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });

  it("uses fixed settings spacing rather than viewport-scaled padding", () => {
    for (const file of ["General", "Personalisation", "Privacy", "Account", "Runtime"]) {
      const source = readFileSync(resolve(process.cwd(), `src/lib/views/settings/${file}.svelte`), "utf8");
      expect(source).not.toMatch(/clamp\([^)]*vw/);
    }
    const shell = readFileSync(resolve(process.cwd(), "src/lib/views/SettingsView.svelte"), "utf8");
    expect(shell).not.toMatch(/margin:\s*var\(--space-5\) 0 0 16rem/);
  });

  it("opens the runtime section from a supported deep link", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice", tab: "runtime" } });

    expect(await screen.findByRole("heading", { name: "Runtime configuration" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Runtime configuration" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

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

  it("uses the General dropdown treatment in Personalisation", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Personalisation" }));

    expect(await screen.findByLabelText("Font")).toHaveClass("settings-select");
  });

  // BUG-37 — density is a mode with a stated consequence and a preview of the
  // row height it produces, not a "Layout spacing" dropdown whose effect an
  // owner had to discover by choosing it and looking around.
  it("offers density as three named modes, each saying what it does", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Personalisation" }));

    const group = await screen.findByRole("radiogroup", { name: "Density" });
    for (const mode of ["Compact", "Comfortable", "Spacious"]) {
      expect(within(group).getByRole("radio", { name: new RegExp(mode) })).toBeInTheDocument();
    }
    expect(screen.getByText(/more rows on screen/i)).toBeInTheDocument();
    // Comfortable is the default when nothing has been saved.
    expect(within(group).getByRole("radio", { name: /Comfortable/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("presents Display name as a structured, descriptive profile field", async () => {
    stubApi();
    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Account" }));

    const input = await screen.findByLabelText("Display name");
    expect(input).toHaveClass("settings-input");
    expect(screen.getByText(/shown in greetings and account surfaces/i)).toBeInTheDocument();
  });

  // FIXED-85 — found while verifying BUG-37 live. The controls render before the
  // settings read resolves, so a choice made in that window was overwritten by
  // the arriving snapshot: the control showed the new value, the page stayed
  // dirty, and Save wrote the old one back.
  it("keeps a choice made while the settings read is still in flight", async () => {
    let resolveSettings: ((value: unknown) => void) | undefined;
    const putBodies: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.endsWith("/api/settings") && method === "PUT") {
          putBodies.push(JSON.parse(String(init?.body)));
          return new Response(JSON.stringify({ settings: {} }), { status: 200 });
        }
        if (url.endsWith("/api/settings")) {
          // Held open, so the component renders before the read lands.
          return new Promise((resolve) => {
            resolveSettings = resolve;
          });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );

    render(SettingsView, { props: { principal: "alice" } });
    await fireEvent.click(screen.getByRole("button", { name: "Personalisation" }));
    const group = await screen.findByRole("radiogroup", { name: "Density" });
    await fireEvent.click(within(group).getByRole("radio", { name: /Compact/ }));

    // The server's answer arrives *after* the choice, carrying the old value.
    resolveSettings?.(
      new Response(
        JSON.stringify({
          settings: { "personalisation.spacing": "comfortable" },
          status: { vault: "configured", mfa_enrolled: false, username: "alice" },
        }),
        { status: 200 },
      ),
    );

    // Let the read's continuation run to completion before asserting: the
    // overwrite this test is about happens in that continuation, so checking
    // before it lands would pass against the very bug it exists to catch.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(within(group).getByRole("radio", { name: /Compact/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(putBodies).toHaveLength(1));
    expect(putBodies[0]).toMatchObject({
      settings: { "personalisation.spacing": "compact" },
    });
  });
});
