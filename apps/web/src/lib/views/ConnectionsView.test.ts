import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConnectionsView from "./ConnectionsView.svelte";
import { stubFetch } from "../test-helpers";
import type { ConnectorView } from "../apiTypes";

function connector(partial: Partial<ConnectorView> = {}): ConnectorView {
  return {
    connector_id: "github",
    display_name: "GitHub (read-only)",
    capability: "connector_github_runtime",
    gate_state: "enabled_runtime",
    capability_enabled: true,
    decision_mode: "ask",
    credential_env: "RAIKER_GITHUB_TOKEN",
    credential_configured: false,
    egress_host: "api.github.com",
    egress_allowed: false,
    actions: ["read_issue", "read_pull_request"],
    kind: "read_only",
    ...partial,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ConnectionsView", () => {
  it("shows a connector as fail-closed when preconditions are unmet, without exposing a token", async () => {
    stubFetch({
      "GET /api/connections": {
        connectors: [connector()],
        connector_egress_allowlist_configured: false,
      },
    });
    render(ConnectionsView);
    await waitFor(() => {
      expect(screen.getByText("GitHub (read-only)")).toBeInTheDocument();
    });
    // Fail-closed status and the missing-precondition guidance are surfaced.
    expect(screen.getByText("Fail-closed")).toBeInTheDocument();
    expect(screen.getByText(/RAIKER_GITHUB_TOKEN/)).toBeInTheDocument();
    // The env name appears in both the top warning and the egress check detail.
    expect(screen.getAllByText(/RAIKER_CONNECTOR_EGRESS_ALLOWLIST/).length).toBeGreaterThan(0);
    // The read-only surface never renders a credential value — only its env name.
    expect(screen.queryByText(/ghp_/)).not.toBeInTheDocument();
  });

  it("renders every governed connector (GitHub, Gmail, Calendar, Slack) with its own env name", async () => {
    stubFetch({
      "GET /api/connections": {
        connectors: [
          connector(),
          connector({
            connector_id: "gmail",
            display_name: "Gmail (read-only)",
            capability: "connector_gmail_runtime",
            credential_env: "RAIKER_GMAIL_TOKEN",
            egress_host: "gmail.googleapis.com",
            actions: ["read_message", "read_thread"],
          }),
          connector({
            connector_id: "gcal",
            display_name: "Google Calendar (read-only)",
            capability: "connector_gcal_runtime",
            credential_env: "RAIKER_GCAL_TOKEN",
            egress_host: "www.googleapis.com",
            actions: ["read_event", "read_calendar"],
          }),
          connector({
            connector_id: "slack",
            display_name: "Slack (read-only)",
            capability: "connector_slack_runtime",
            credential_env: "RAIKER_SLACK_TOKEN",
            egress_host: "slack.com",
            actions: ["read_channel_info", "read_channel_history"],
          }),
        ],
        connector_egress_allowlist_configured: false,
      },
    });
    render(ConnectionsView);
    await waitFor(() => {
      expect(screen.getByText("Slack (read-only)")).toBeInTheDocument();
    });
    // Every connector is listed and each surfaces its own credential env name.
    expect(screen.getByText("GitHub (read-only)")).toBeInTheDocument();
    expect(screen.getByText("Gmail (read-only)")).toBeInTheDocument();
    expect(screen.getByText("Google Calendar (read-only)")).toBeInTheDocument();
    expect(screen.getByText(/RAIKER_GMAIL_TOKEN/)).toBeInTheDocument();
    expect(screen.getByText(/RAIKER_GCAL_TOKEN/)).toBeInTheDocument();
    expect(screen.getByText(/RAIKER_SLACK_TOKEN/)).toBeInTheDocument();
  });

  it("reports a connector as ready only when every precondition is met", async () => {
    stubFetch({
      "GET /api/connections": {
        connectors: [
          connector({
            capability_enabled: true,
            decision_mode: "allow",
            credential_configured: true,
            egress_allowed: true,
          }),
        ],
        connector_egress_allowlist_configured: true,
      },
    });
    render(ConnectionsView);
    await waitFor(() => {
      expect(screen.getByText("Ready")).toBeInTheDocument();
    });
    expect(screen.queryByText("Fail-closed")).not.toBeInTheDocument();
  });
});
