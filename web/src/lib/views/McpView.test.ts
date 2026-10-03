import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import McpView from "./McpView.svelte";
import { makeGate, stubFetch } from "../test-helpers";
import type { McpAgentAccess, McpOffer, McpServer } from "../apiTypes";

type Scope = NonNullable<McpServer["scope"]>;

function localScope(partial: Partial<Scope> = {}): Scope {
  return {
    runs_on: "this_machine",
    network: "unrestricted",
    encrypted: null,
    environment: ["HOME", "PATH", "PYTHONIOENCODING", "PYTHONUNBUFFERED"],
    granted_environment: [],
    token_reference: null,
    working_folder: "workspace",
    writable: "account",
    roots_shared: false,
    resources_read: false,
    tool_count: 2,
    required_permissions: ["mcp_connector_runtime", "mcp_builder_runtime"],
    risk: "local_process",
    ...partial,
  };
}

function remoteScope(partial: Partial<Scope> = {}): Scope {
  return localScope({
    runs_on: "remote",
    network: "public",
    encrypted: true,
    environment: [],
    token_reference: "ACME_MCP_TOKEN",
    working_folder: null,
    writable: "none_on_this_machine",
    tool_count: null,
    required_permissions: ["mcp_connector_runtime"],
    risk: "remote_service",
    ...partial,
  });
}

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
    unsupported_features: [],
    tool_declarations: [
      {
        name: "echo",
        title: "Echo",
        description: "Return the text it was given.",
        has_schema: true,
        schema_reason: "",
        arguments: ["text", "uppercase"],
        required: ["text"],
      },
      {
        name: "workspace_ping",
        title: "",
        description: "",
        has_schema: false,
        schema_reason: "not_declared",
        arguments: [],
        required: [],
      },
    ],
    endpoint_url: null,
    auth_ref: null,
    monitor_state: "active",
    paused_reason: null,
    paused_at: null,
    protocol_version: "2026-07-28",
    scope: localScope(),
    source: "raiker_sample",
    source_plugin: null,
    purpose: "Return the text it was given.",
    purpose_from: "server",
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

  // Backlog #16 (MCP half) — the card showed a row of tool-name chips and
  // nothing else, so a server whose tools declare their arguments looked
  // identical to one whose tools do not, and the owner could not tell whether
  // the model was calling them with real arguments or with guesses.
  it("says what each connected tool takes, and which declared nothing", async () => {
    stubFetch({
      "GET /api/mcp/servers": [server()],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    await screen.findByText("echo-server");

    expect(screen.getByText("text · optional: uppercase")).toBeInTheDocument();
    expect(screen.getByText("No arguments declared")).toBeInTheDocument();
  });

  it("says a connection has not been tested rather than implying no arguments", async () => {
    stubFetch({
      "GET /api/mcp/servers": [server({ tool_declarations: [] })],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    await screen.findByText("echo-server");

    expect(screen.getAllByText("Run Test to read what this takes")).toHaveLength(2);
  });

  // BUG-234 — a server offering more of the protocol than Raiker uses was
  // connected with none of that said anywhere.
  it("names what a connected server offers that Raiker does not use", async () => {
    stubFetch({
      "GET /api/mcp/servers": [
        server({
          unsupported_features: [
            { feature: "resources", note: "Raiker reads this server's tools only." },
          ],
        }),
      ],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(),
    });
    render(McpView);
    await screen.findByText("echo-server");

    expect(screen.getByText("resources")).toBeInTheDocument();
    expect(screen.getByText(/reads this server's tools only/)).toBeInTheDocument();
  });

  // A closed connector gate produced two amber notices one under the other,
  // saying the same fact in different words and naming the same page by two
  // different names — which reads as two problems rather than one.
  it("says a closed connector gate once, not twice", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/capability-gates": [
        makeGate({ capability: "mcp_builder_runtime", runtime_enabled: true }),
        makeGate({
          capability: "mcp_connector_runtime",
          state: "disabled",
          runtime_enabled: false,
          allowed_transitions: ["enabled_policy_gated", "enabled_runtime"],
        }),
      ],
      ...monitorRoutes(access({ callable: false, reason_code: "mcp_gate_disabled" })),
    });
    render(McpView);
    await waitFor(() =>
      expect(screen.getByText(/The MCP connector is turned off/)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/cannot call any MCP tool/)).not.toBeInTheDocument();
    // And the page an owner is sent to is called by the name the rail gives it.
    expect(screen.queryByRole("link", { name: "Capabilities" })).not.toBeInTheDocument();
  });

  // The other reasons are not duplicates of anything, so they still show.
  it("still explains a decision mode that withholds every MCP tool", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/capability-gates": ENABLED_GATES,
      ...monitorRoutes(
        access({ callable: false, reason_code: "mcp_denied_by_decision_mode", decision_mode: "deny" }),
      ),
    });
    render(McpView);
    await waitFor(() =>
      expect(screen.getByText(/set to Deny/)).toBeInTheDocument(),
    );
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
    expect(screen.getAllByRole("link", { name: /in Permissions$/ })[0]).toHaveAttribute(
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
    expect(screen.getAllByRole("link", { name: /in Permissions$/ })[0]).toHaveAttribute(
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
    await fireEvent.click(screen.getByRole("button", { name: "Generate example server" }));
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

  // REM-SET-NOTIFY — the notification strip moved to the shell, where the
  // account-wide setting that governs it can mean what it says. This page keeps
  // what is its own: the monitor state, the finding, and the controls.
  it("shows live monitoring details, findings, and stop/resume controls", async () => {
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
      "POST /api/mcp/servers/mcp_1/resume": { ok: true, monitor_state: "active" },
    });
    render(McpView);
    await waitFor(() => expect(screen.getByText("Paused: New host with sensitive data")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/3 tool calls/i)).toBeInTheDocument());
    expect(screen.getByText("high: New host with sensitive data")).toBeInTheDocument();
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
    scope: remoteScope(),
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

// UX-MCP-02 and UX-MCP-03 — the blast radius before activation, and a trust
// explanation rather than tool names.
describe("McpView — scope and trust", () => {
  it("states what an untested local server can reach, with the cautions first-class", async () => {
    stubFetch({
      "GET /api/mcp/servers": [
        server({ status: "created", last_connected_at: null, tools: [], tool_count: 0, scope: localScope({ tool_count: null }) }),
      ],
      "GET /api/capability-gates": ENABLED_GATES,
      "GET /api/mcp/agent-access": access(),
      "GET /api/mcp/offers": [],
      "GET /api/mcp/servers/mcp_1/sessions": [],
      "GET /api/mcp/servers/mcp_1/findings": [],
    });
    render(McpView);
    const reach = await screen.findByText("What it can reach");
    const details = reach.closest("details")!;
    // Open until it has been tested: Test is what lets it run.
    expect(details.open).toBe(true);
    expect(details).toHaveTextContent("Not confined — the process has this machine's network.");
    expect(details).toHaveTextContent("Anything the account Raiker runs as may write");
    expect(details).toHaveTextContent("no provider key");
    expect(details).toHaveTextContent("Raiker tells it no folder and hands it no file");
    expect(details).toHaveTextContent("Not known until Test lists them");
    expect(details).toHaveTextContent("MCP connections and MCP server builder");
  });

  it("names purpose, risk, source and recent outcomes on the card", async () => {
    stubFetch({
      "GET /api/mcp/servers": [server()],
      "GET /api/capability-gates": ENABLED_GATES,
      "GET /api/mcp/agent-access": access(),
      "GET /api/mcp/offers": [],
      "GET /api/mcp/servers/mcp_1/sessions": [
        { session_row_id: "a", server_id: "mcp_1", transport: "stdio", operation: "call", hosts: [], tool_calls: 1, bytes_in: 1, bytes_out: 1, error_count: 0, outcome: "ok", started_at: "2026-07-17T01:00:00Z", ended_at: null },
        { session_row_id: "b", server_id: "mcp_1", transport: "stdio", operation: "call", hosts: [], tool_calls: 1, bytes_in: 1, bytes_out: 1, error_count: 1, outcome: "error", started_at: "2026-07-17T02:00:00Z", ended_at: null },
      ],
      "GET /api/mcp/servers/mcp_1/findings": [],
    });
    render(McpView);
    // The server's own words are labelled as its own.
    expect(await screen.findByText("It says: “Return the text it was given.”")).toBeInTheDocument();
    expect(screen.getByText("Runs code on this machine")).toBeInTheDocument();
    expect(screen.getByText("Sample Raiker generated")).toBeInTheDocument();
    expect(await screen.findByText(/last 2: 1 ok, 1 failed/)).toBeInTheDocument();
    // Tested already, so the scope folds away.
    expect(screen.getByText("What it can reach").closest("details")!.open).toBe(false);
  });

  it("previews an offer's scope before it is added", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/capability-gates": ENABLED_GATES,
      "GET /api/mcp/agent-access": access(),
      "GET /api/mcp/offers": [
        {
          plugin_id: "acme-mcp",
          name: "acme-docs",
          transport: "http",
          description: "Acme's internal documentation index.",
          endpoint_url: "https://mcp.acme.example/v1",
          auth_ref: "ACME_MCP_TOKEN",
          already_added: false,
          scope: remoteScope(),
        },
      ],
    });
    render(McpView);
    const summary = await screen.findByText(/What adding it gives it · Sends data to a remote service/);
    expect(summary.closest("details")).toHaveTextContent(
      "The token in ACME_MCP_TOKEN, sent to this endpoint only.",
    );
    expect(summary.closest("details")).toHaveTextContent("None on this machine.");
  });
});

// Found by the 2026-10-03 live round: the server stores a normalised name, and
// the notice named the one typed — a card that did not exist.
describe("McpView — the name the server kept", () => {
  it("names the stored server, and says why it differs from what was typed", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/capability-gates": ENABLED_GATES,
      "GET /api/mcp/agent-access": access(),
      "GET /api/mcp/offers": [],
      "POST /api/mcp/servers": { ok: true, server_id: "mcp_9", name: "Protocolsample" },
    });
    render(McpView);
    await fireEvent.click(await screen.findByText("Developer example — generate a local sample server"));
    await fireEvent.input(screen.getByLabelText("Server name"), { target: { value: "Protocol sample" } });
    await fireEvent.click(screen.getByRole("button", { name: "Generate example server" }));
    expect(await screen.findByText(/Created “Protocolsample” \(a server name keeps only/)).toBeInTheDocument();
  });
});
