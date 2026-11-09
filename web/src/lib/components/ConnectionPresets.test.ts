/*
 * QUI-P04 — Read only, Ask before changes, Custom; and recent activity.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConnectionPresets from "./ConnectionPresets.svelte";
import type { StoreConnector } from "../generated/apiContract";
import { PERMISSIONS_CHANGED } from "../permissionSync";
import { stubFetch } from "../test-helpers";

const CONNECTOR = {
  connector_id: "github", display_name: "GitHub", category: "dev", description: "", auth_type: "oauth2",
  support_level: "experimental", host: "api.github.com", installed: true, enabled: true,
  auth_status: "connected", vault_configured: true, activity_status: "idle", active_operation: null,
  last_invoked_at: null, operations: [], accounts: [], preset: "read_only",
} as StoreConnector;

afterEach(() => vi.unstubAllGlobals());

describe("ConnectionPresets", () => {
  it("lets only the newest activity read set the list (found live)", async () => {
    let first: (value: Response) => void = () => {};
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => {
        calls += 1;
        if (calls === 1) return new Promise<Response>((resolve) => (first = resolve));
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ connector_id: "github", items: [] }) } as Response);
      }),
    );
    const view = render(ConnectionPresets, { props: { connector: CONNECTOR } });
    await view.rerender({ connector: { ...CONNECTOR, connector_id: "github", preset: "ask" } });
    expect(await screen.findByText("Nothing yet.")).toBeInTheDocument();
    first({ ok: false, status: 500, json: async () => ({}) } as Response);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
    expect(screen.queryByText("Recent activity could not be read.")).toBeNull();
  });

  it("shows the stored preset, saves a new one and announces it", async () => {
    const fetchMock = stubFetch({
      "GET /api/connector-store/github/activity": {
        connector_id: "github",
        items: [{ operation_id: "list_repos", status: "completed", started_at: "2026-11-08T10:00:00Z" }],
      },
      "PUT /api/connector-store/github/preset": { ok: true, connector_id: "github", preset: "ask" },
    });
    const heard = vi.fn();
    window.addEventListener(PERMISSIONS_CHANGED, heard);
    render(ConnectionPresets, { props: { connector: CONNECTOR, capability: "connector_runtime", onchanged: vi.fn() } });
    expect(screen.getByRole("radio", { name: /Read only/ })).toBeChecked();
    expect(await screen.findByText("List repos")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("radio", { name: /Ask before changes/ }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/preset") && (init as RequestInit).method === "PUT")).toBe(true),
    );
    await waitFor(() => expect(heard).toHaveBeenCalled());
    window.removeEventListener(PERMISSIONS_CHANGED, heard);
  });

  it("opens Permissions at this connection for Custom, and keeps the old choice when saving fails", async () => {
    stubFetch({
      "GET /api/connector-store/github/activity": { connector_id: "github", items: [] },
      "PUT /api/connector-store/github/preset": { __status: 500 },
    });
    render(ConnectionPresets, { props: { connector: { ...CONNECTOR, preset: "custom" }, capability: "connector_runtime" } });
    expect(screen.getByRole("link", { name: "Open GitHub in Permissions" })).toHaveAttribute(
      "href",
      "#/capabilities?item=connector_runtime",
    );
    expect(await screen.findByText("Nothing yet.")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("radio", { name: /Read only/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/not saved/);
    expect(screen.getByRole("radio", { name: /Custom/ })).toBeChecked();
  });
});
