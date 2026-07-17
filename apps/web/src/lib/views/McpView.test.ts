import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import McpView from "./McpView.svelte";
import { makeGate, stubFetch } from "../test-helpers";
import type { McpServer } from "../apiTypes";

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
    ...partial,
  };
}

const ENABLED_GATES = [
  makeGate({ capability: "mcp_builder_runtime", runtime_enabled: true }),
  makeGate({ capability: "mcp_connector_runtime", runtime_enabled: true }),
];

afterEach(() => vi.unstubAllGlobals());

describe("McpView", () => {
  it("lists servers with status and discovered tools", async () => {
    stubFetch({
      "GET /api/mcp/servers": [server()],
      "GET /api/capability-gates": ENABLED_GATES,
    });
    render(McpView);
    await waitFor(() => expect(screen.getByText("echo-server")).toBeInTheDocument());
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("workspace_ping")).toBeInTheDocument();
    expect(screen.getByText(/python .raiker\/mcp\/servers\/echo.py/)).toBeInTheDocument();
  });

  it("warns and points to Capabilities when the gate is disabled", async () => {
    stubFetch({
      "GET /api/mcp/servers": [],
      "GET /api/capability-gates": [
        makeGate({ capability: "mcp_builder_runtime", runtime_enabled: false }),
        makeGate({ capability: "mcp_connector_runtime", runtime_enabled: false }),
      ],
    });
    render(McpView);
    await waitFor(() => expect(screen.getByText(/disabled/i)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Capabilities" })).toHaveAttribute("href", "#/capabilities");
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
});
