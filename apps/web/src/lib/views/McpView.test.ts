import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import McpView from "./McpView.svelte";
import { makeGate, stubFetch } from "../test-helpers";
import type { McpAgentAccess, McpOffer, McpServer } from "../apiTypes";

function server(partial: Partial<McpServer> = {}): McpServer {
  return {
    server_id: "mcp_1",
    name: "echo-server",
    command: ["python", ".raiker/mcp/servers/echo.py"],
    template: "python-stdio-echo",
    transport: "stdio",
    status: "connected",
    created_at: "2026-07-17T00:00:00Z",
    last_connected_at: "2026-07-17T01:00:00Z",
    tools: ["echo", "workspace_ping"],
    tool_count: 2,
    endpoint_url: null,
    auth_ref: null,
    monitor_state: "active",
    paused_reason: null,
    paused_at: null,
    ...partial,
  };
}

const ENABLED_GATES = [
  makeGate({ capability: "mcp_builder_runtime", runtime_enabled: true }),
  makeGate({ capability: "mcp_connector_runtime", runtime_enabled: true }),
];

function access(partial: Partial<McpAgentAccess> = {}): McpAgentAccess {
  return {
    gate_enabled: true,
    decision_mode: "allow",
    callable: true,
    reason_code: "",
    projected_tools: 2,
    connected_servers: 1,
    ...partial,
  };
}

function monitorRoutes(agentAccess: McpAgentAccess = access()) {
  return {
    "GET /api/mcp/servers/mcp_1/sessions": [],
    "GET /api/mcp/servers/mcp_1/findings": [],
    "GET /api/notifications": [],
    "GET /api/mcp/agent-access": agentAccess,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("McpView", () => {
  it("lists servers with status and discovered tools", async () => {
    stubFetch({
      "GET /api/mcp/servers": [server()],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    await waitFor(() => expect(screen.getByText("echo-server")).toBeInTheDocument());
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("workspace_ping")).toBeInTheDocument();
    expect(screen.getByText(/python .raiker\/mcp\/servers\/echo.py/)).toBeInTheDocument();
  });

  it("warns and points to Permissions when the gate is off", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/capability-gates": [
        makeGate({
          capability: "mcp_builder_runtime",
          state: "disabled",
          runtime_enabled: false,
          allowed_transitions: ["enabled_policy_gated", "enabled_runtime"],
        }),
        makeGate({
          capability: "mcp_connector_runtime",
          state: "disabled",
          runtime_enabled: false,
          allowed_transitions: ["enabled_policy_gated", "enabled_runtime"],
        }),
      ],
    });
    render(McpView);
    await waitFor(() => expect(screen.getAllByText(/is turned off/i).length).toBe(2));
    expect(screen.getAllByRole("link", { name: "Open Permissions" })[0]).toHaveAttribute(
      "href",
      "#/capabilities",
    );
  });

  // BUG-11 — the old copy said "disabled … enable it in Capabilities" even when
  // the capability was already enabled, just below runtime level. Following it
  // changed nothing; the real blocker is the runtime mode.
  it("says a capability is enabled but below runtime level, and points at the runtime mode", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/capability-gates": [
        makeGate({
          capability: "mcp_builder_runtime",
          state: "enabled_policy_gated",
          runtime_enabled: false,
          allowed_transitions: ["disabled", "enabled_runtime"],
        }),
        makeGate({
          capability: "mcp_connector_runtime",
          state: "enabled_policy_gated",
          runtime_enabled: false,
          allowed_transitions: ["disabled", "enabled_runtime"],
        }),
      ],
    });
    render(McpView);
    await waitFor(() =>
      expect(screen.getAllByText(/enabled, but only at/i).length).toBe(2),
    );
    expect(screen.queryByText(/is turned off/i)).not.toBeInTheDocument();
    // One runtime: raising a capability to runtime level is a Permissions
    // action, so the link goes there rather than to a mode picker.
    expect(screen.getAllByRole("link", { name: "Open Permissions" })[0]).toHaveAttribute(
      "href",
      "#/capabilities",
    );
  });

  it("creates a server from a template through the governed API", async () => {
    const mock = stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/capability-gates": ENABLED_GATES,
      "POST /api/mcp/servers": { ok: true, server_id: "mcp_new", name: "my-tools" },
    });
    render(McpView);
    await waitFor(() => expect(screen.getByText(/No MCP servers yet/)).toBeInTheDocument());
    await fireEvent.input(screen.getByLabelText("Server name"), { target: { value: "my-tools" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create server" }));
    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        expect.stringContaining("/api/mcp/servers"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("deletes a server after confirmation", async () => {
    vi.stubGlobal("confirm", () => true);
    const mock = stubFetch({
      "GET /api/mcp/servers": [server()],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
      "DELETE /api/mcp/servers/mcp_1": { ok: true, server_id: "mcp_1" },
    });
    render(McpView);
    await waitFor(() => expect(screen.getByText("echo-server")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        expect.stringContaining("/api/mcp/servers/mcp_1"),
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });

  it("shows live monitoring details, findings, notification, and stop/resume controls", async () => {
    const mock = stubFetch({
      "GET /api/mcp/servers": [server({ monitor_state: "paused", paused_reason: "New host with sensitive data" })],
      "GET /api/capability-gates": ENABLED_GATES,
      "GET /api/mcp/servers/mcp_1/sessions": [{
        session_row_id: "mses_1", server_id: "mcp_1", transport: "http", operation: "tools/call",
        hosts: ["mcp.example.test"], tool_calls: 3, bytes_in: 10, bytes_out: 20, error_count: 0,
        outcome: "ok", started_at: "2026-07-18T10:00:00Z", ended_at: null,
      }],
      "GET /api/mcp/servers/mcp_1/findings": [{
        finding_id: "find_1", source: "mcp_monitor", severity: "high", code: "new_host_sensitive",
        summary: "New host with sensitive data", redacted_detail: {}, subject_id: "mcp_1", state: "open",
        created_at: "2026-07-18T10:00:00Z",
      }],
      "GET /api/notifications": [{
        notification_id: "note_1", kind: "mcp_anomaly", title: "MCP anomaly detected", body: "New host with sensitive data",
        finding_id: "find_1", subject_id: "mcp_1", read: false, created_at: "2026-07-18T10:00:00Z",
      }],
      "POST /api/mcp/servers/mcp_1/resume": { ok: true, monitor_state: "active" },
    });
    render(McpView);
    await waitFor(() => expect(screen.getByText("Paused: New host with sensitive data")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/3 tool calls/i)).toBeInTheDocument());
    expect(screen.getByText("MCP anomaly detected")).toBeInTheDocument();
    expect(screen.getByText("New host with sensitive data")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(mock).toHaveBeenCalledWith(
      expect.stringContaining("/api/mcp/servers/mcp_1/resume"),
      expect.objectContaining({ method: "POST" }),
    ));
  });

  // B8 — connecting a server and the agent being able to call it are two
  // different facts. The page used to state only the first, so a withheld
  // server read `Connected` beside tools nothing could reach.
  it("says the connected tools are callable when they really are", async () => {
    stubFetch({
      "GET /api/mcp/servers": [server()],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    await waitFor(() =>
      expect(screen.getByText(/available to Raiker in Chat and Build/)).toBeInTheDocument(),
    );
    expect(screen.getByText("Callable by Raiker")).toBeInTheDocument();
  });

  it("names the decision mode when a connected server's tools are withheld", async () => {
    stubFetch({
      "GET /api/mcp/servers": [server()],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(
        access({
          decision_mode: "ask",
          callable: false,
          reason_code: "mcp_withheld_ask",
          projected_tools: 0,
        }),
      ),
    });
    render(McpView);
    await waitFor(() =>
      expect(screen.getByText(/withheld from every turn/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/the MCP decision mode is/)).toBeInTheDocument();
    // The card agrees with the banner rather than claiming the tools work.
    expect(screen.getByText("Not callable yet — see above")).toBeInTheDocument();
  });

  it("stays usable when the reachability read fails", async () => {
    stubFetch({
      "GET /api/mcp/servers": [server()],
      "GET /api/capability-gates": ENABLED_GATES,
      "GET /api/mcp/servers/mcp_1/sessions": [],
      "GET /api/mcp/servers/mcp_1/findings": [],
      "GET /api/notifications": [],
    });
    render(McpView);
    await waitFor(() => expect(screen.getByText("echo-server")).toBeInTheDocument());
    expect(screen.queryByText(/withheld from every turn/)).not.toBeInTheDocument();
  });
});

// BUG-221 — a plugin may *offer* a server. The tab has to make "offered" and
// "added" different things on screen, because the difference is the whole
// safety property: an offer is inert until the owner runs the create path.
describe("McpView — servers a plugin offers", () => {
  const offer = (partial: Partial<McpOffer> = {}): McpOffer => ({
    plugin_id: "acme-mcp",
    name: "acme-docs",
    transport: "http",
    description: "Acme's internal documentation index.",
    endpoint_url: "https://mcp.acme.example/v1",
    auth_ref: "ACME_MCP_TOKEN",
    already_added: false,
    ...partial,
  });

  it("lists an offer, credits the plugin, and says nothing is connected", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/mcp/offers": [offer()],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    expect(await screen.findByText("acme-docs")).toBeInTheDocument();
    expect(screen.getByText(/from plugin/i)).toBeInTheDocument();
    expect(screen.getByText(/Nothing here is connected or reachable/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add server" })).toBeInTheDocument();
  });

  it("names the environment variable rather than showing a token", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/mcp/offers": [offer()],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    expect(await screen.findByText("ACME_MCP_TOKEN")).toBeInTheDocument();
    expect(screen.getByText(/The token is never stored here/i)).toBeInTheDocument();
  });

  it("adding one posts to the ordinary governed create route", async () => {
    const fetchMock = stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/mcp/offers": [offer()],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
      "POST /api/mcp/servers/remote": { ok: true, server_id: "mcp_1", name: "acme-docs" },
    });
    render(McpView);
    await fireEvent.click(await screen.findByRole("button", { name: "Add server" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).endsWith("/api/mcp/servers/remote")),
      ).toBe(true),
    );
  });

  it("shows an offer the owner already took up as added, with no button", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/mcp/offers": [offer({ already_added: true })],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    expect(await screen.findByText("Added")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add server" })).not.toBeInTheDocument();
  });

  it("says nothing about offers when a plugin has not made one", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/mcp/offers": [],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    await screen.findByText(/No MCP servers yet/i);
    expect(screen.queryByText(/Offered by your plugins/i)).not.toBeInTheDocument();
  });
});
