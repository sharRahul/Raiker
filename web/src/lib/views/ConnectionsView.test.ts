// QUI-L07 — Connections › Services lists only what is connected; everything
// that could be connected is the catalogue in the Add connection dialog. The
// detail of a connected service keeps the readiness rule: installed, connected,
// enabled and usable are four separate facts, and anything not usable says
// which condition is unmet.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ConnectionsView from "./ConnectionsView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";
import type { ExtensionView, StoreConnector } from "../apiTypes";

function connector(partial: Partial<StoreConnector> = {}): StoreConnector {
  return {
    connector_id: "gmail",
    display_name: "Gmail",
    category: "Email",
    description: "Read and draft email.",
    auth_type: "oauth2",
    host: "gmail.googleapis.com",
    installed: false,
    enabled: false,
    auth_status: "not_connected",
    vault_configured: true,
    activity_status: "idle",
    active_operation: null,
    last_invoked_at: null,
    operations: [],
    ...partial,
  };
}

function extension(partial: Partial<ExtensionView> = {}): ExtensionView {
  return {
    extension_id: "connector:gmail",
    kind: "connector",
    display_name: "Gmail",
    category: "Email",
    installed: true,
    connected: false,
    enabled: false,
    usable: false,
    blocked_reason: "account_not_connected",
    detail: "Read-only mail access",
    capability: "connector_gmail_runtime",
    gate_state: "disabled",
    decision_mode: "ask",
    egress_host: "gmail.googleapis.com",
    egress_allowed: false,
    transport: null,
    monitor_state: null,
    tool_count: 0,
    last_activity_at: null,
    ...partial,
  };
}

function routes(
  connectors: StoreConnector[],
  extensions: ExtensionView[] = [],
  extra: Record<string, unknown> = {},
) {
  return {
    "GET /api/connector-store": { connectors, count: connectors.length, vault_configured: true },
    "GET /api/extensions": {
      extensions,
      counts: {},
      vault_configured: true,
      connector_egress_allowlist_configured: true,
      deferred: [],
    },
    "GET /api/approvals": [],
    ...extra,
  };
}

beforeEach(() => {
  window.location.hash = "#/connections?tab=services";
});
afterEach(() => vi.unstubAllGlobals());

describe("Connections › Services (QUI-L07)", () => {
  it("shows a loading state while connections are read", async () => {
    stubFetchPending();
    render(ConnectionsView);
    expect(await screen.findByText(/loading connections/i)).toBeInTheDocument();
  });

  it("says nothing is connected, with Add connection, when nothing is", async () => {
    stubFetch(routes([connector(), connector({ connector_id: "slack", display_name: "Slack" })]));
    render(ConnectionsView);
    expect(await screen.findByText(/nothing is connected yet/i)).toBeInTheDocument();
    // The catalogue is not on the page: no row, card or search for Gmail.
    expect(screen.queryByText("Gmail")).not.toBeInTheDocument();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /add connection/i }).length).toBeGreaterThan(0);
  });

  it("lists only connected services, with their status in words", async () => {
    stubFetch(
      routes([
        connector({ installed: true, enabled: true, auth_status: "connected" }),
        connector({ connector_id: "slack", display_name: "Slack", installed: true, auth_status: "reauth_required" }),
        connector({ connector_id: "uber", display_name: "Uber" }),
      ]),
    );
    render(ConnectionsView);
    const list = await screen.findByRole("listbox", { name: "Connected services" });
    expect(within(list).getAllByRole("option")).toHaveLength(2);
    expect(within(list).getByText("Connected")).toBeInTheDocument();
    expect(within(list).getByText("Needs you to sign in again")).toBeInTheDocument();
    expect(screen.queryByText("Uber")).not.toBeInTheDocument();
  });

  it("names the unmet readiness condition in the detail", async () => {
    stubFetch(routes([connector({ installed: true })], [extension()]));
    render(ConnectionsView);
    await fireEvent.click(await screen.findByRole("option", { name: /gmail/i }));
    expect(await screen.findByText(/no account credential is stored/i)).toBeInTheDocument();
    expect(screen.getByText(/Blocked at/)).toHaveTextContent("Account connected");
  });

  it("asks for the credential in a password field and never shows it", async () => {
    stubFetch(routes([connector({ installed: true })]));
    render(ConnectionsView);
    await fireEvent.click(await screen.findByRole("option", { name: /gmail/i }));
    expect(screen.getByLabelText("OAuth access token")).toHaveAttribute("type", "password");
    expect(screen.getByText(/encrypted for this profile/)).toBeInTheDocument();
  });

  it("points at the decision queue when a call is waiting on approval", async () => {
    stubFetch(
      routes([connector({ installed: true })], [extension()], {
        "GET /api/approvals": [
          { approval_id: "appr_1", capability: "connector_gmail_runtime", is_expired: false },
        ],
      }),
    );
    render(ConnectionsView);
    await fireEvent.click(await screen.findByRole("option", { name: /gmail/i }));
    expect(await screen.findByText(/one call is\s+waiting on your decision/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review the decision queue/i })).toHaveAttribute(
      "href",
      "#/approvals",
    );
  });

  it("opens the catalogue in the Add connection dialog and adds the chosen service", async () => {
    const mock = stubFetch({
      ...routes([connector(), connector({ connector_id: "slack", display_name: "Slack", category: "Chat" })]),
      "POST /api/connector-store/gmail/install": { ok: true, connector_id: "gmail", installed: true },
    });
    render(ConnectionsView);
    await screen.findByText(/nothing is connected yet/i);
    await fireEvent.click(screen.getAllByRole("button", { name: /add connection/i })[0]);
    const dialog = screen.getByRole("dialog", { name: "Add connection" });
    expect(within(dialog).getByRole("button", { name: /Slack/ })).toBeInTheDocument();
    await fireEvent.click(within(dialog).getByRole("button", { name: /Gmail/ }));
    // Only the chosen service's steps are shown now.
    expect(within(dialog).queryByRole("button", { name: /Slack/ })).not.toBeInTheDocument();
    await fireEvent.click(within(dialog).getByRole("button", { name: "Add Gmail" }));
    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        expect.stringContaining("/api/connector-store/gmail/install"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("offers an MCP server as the other way to connect a service", async () => {
    stubFetch({
      ...routes([connector()]),
      "POST /api/mcp/servers": { ok: true, server_id: "mcp_local", name: "Gmail MCP" },
      "POST /api/mcp/servers/mcp_local/connect": { ok: true, status: "connected", tools: ["inbox"] },
    });
    render(ConnectionsView);
    await screen.findByText(/nothing is connected yet/i);
    await fireEvent.click(screen.getAllByRole("button", { name: /add connection/i })[0]);
    await fireEvent.click(screen.getByRole("button", { name: /Gmail/ }));
    await fireEvent.click(screen.getByRole("button", { name: /through an MCP server instead/i }));
    await fireEvent.click(screen.getByRole("button", { name: "Connect through MCP" }));
    await waitFor(() => expect(screen.getByText(/connected.*1 tool/i)).toBeInTheDocument());
  });

  it("shows the missing vault key as one attention row, only when it is missing", async () => {
    stubFetch({
      ...routes([]),
      "GET /api/connector-store": { connectors: [], count: 0, vault_configured: false },
    });
    render(ConnectionsView);
    expect(await screen.findByText(/linking an account needs the vault key/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Set up" })).toHaveAttribute("href", "#/settings?tab=security");
  });

  it("lists GitHub once its account is signed in", async () => {
    stubFetch(
      routes([], [], {
        "GET /api/github": {
          states: {
            connected_account: true,
            application_installed: false,
            repository_authorised: false,
            credential_available: true,
            capability_enabled: false,
            operation_approved: false,
          },
        },
      }),
    );
    render(ConnectionsView);
    const list = await screen.findByRole("listbox", { name: "Connected services" });
    expect(within(list).getByText("GitHub")).toBeInTheDocument();
  });

  it("registers a manifest for a connected service", async () => {
    stubFetch({
      ...routes([connector({ installed: true })]),
      "POST /api/connector-store/gmail/manifest": { ok: true, operations: [{}] },
    });
    render(ConnectionsView);
    await screen.findByRole("listbox");
    await fireEvent.click(screen.getByRole("button", { name: /Import manifest/ }));
    await fireEvent.change(screen.getByLabelText("Connection"), { target: { value: "gmail" } });
    await fireEvent.input(screen.getByLabelText("Manifest JSON"), {
      target: { value: JSON.stringify({ openapi: "3.0.0", paths: { "/messages": { get: {} } } }) },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Check and register" }));
    await waitFor(() => expect(screen.getByText("1 operations registered")).toBeInTheDocument());
  });
});
