// The Extensions hub consolidates connectors and MCP into one destination. Its
// job is to never let metadata alone imply that something works: installed,
// connected, enabled, and usable are four separate facts, and anything not
// usable says which condition is unmet.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExtensionsView from "./ExtensionsView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";
import type { ExtensionView } from "../apiTypes";

afterEach(() => {
  vi.unstubAllGlobals();
});

function extension(partial: Partial<ExtensionView>): ExtensionView {
  return {
    extension_id: "connector:gmail",
    kind: "connector",
    display_name: "Gmail",
    category: "Email",
    installed: false,
    connected: false,
    enabled: false,
    usable: false,
    blocked_reason: "not_installed",
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

function overview(extensions: ExtensionView[], counts: Partial<Record<string, number>> = {}) {
  return {
    "GET /api/extensions": {
      extensions,
      counts: {
        total: extensions.length,
        installed: extensions.filter((e) => e.installed).length,
        connected: extensions.filter((e) => e.connected).length,
        enabled: extensions.filter((e) => e.enabled).length,
        usable: extensions.filter((e) => e.usable).length,
        ...counts,
      },
      vault_configured: true,
      connector_egress_allowlist_configured: true,
      deferred: [],
    },
    "GET /api/connector-store": { connectors: [], count: 0, vault_configured: true },
  };
}

describe("ExtensionsView", () => {
  it("shows a loading state while readiness is fetched", async () => {
    stubFetchPending();
    render(ExtensionsView, { props: { tab: "connectors" } });
    expect(await screen.findByText(/reading extension readiness/i)).toBeInTheDocument();
  });

  it("shows an error state without claiming anything is usable", async () => {
    stubFetch({});
    render(ExtensionsView, { props: { tab: "connectors" } });
    // The governed connector view mounted below raises its own alert; the
    // readiness alert must be present alongside it, not instead of it.
    const alerts = await screen.findAllByRole("alert");
    expect(
      alerts.some((alert) => /couldn't load extension readiness/i.test(alert.textContent ?? "")),
    ).toBe(true);
    expect(screen.queryByText("Usable now")).not.toBeInTheDocument();
  });

  it("renders the four lifecycle facts separately for each extension", async () => {
    stubFetch(overview([extension({ installed: true, blocked_reason: "account_not_connected" })]));
    render(ExtensionsView, { props: { tab: "connectors" } });

    await waitFor(() => expect(screen.getByLabelText("Open Gmail details")).toBeInTheDocument());
    const row = screen.getByLabelText("Open Gmail details");
    expect(row).toHaveTextContent("installed");
    expect(row).toHaveTextContent("connected");
    expect(row).toHaveTextContent("enabled");
    expect(row).toHaveTextContent("usable");
  });

  it("names the unmet condition in the detail panel", async () => {
    stubFetch(
      overview([
        extension({ installed: true, connected: true, blocked_reason: "not_enabled_for_session" }),
      ]),
    );
    render(ExtensionsView, { props: { tab: "connectors" } });

    await waitFor(() => expect(screen.getByLabelText("Open Gmail details")).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText("Open Gmail details"));

    expect(await screen.findByText(/not enabled for this session/i)).toBeInTheDocument();
    expect(screen.getByText(/Blocked at/)).toHaveTextContent("Enabled for the session");
  });

  it("says an extension is usable only when the server confirms every condition", async () => {
    stubFetch(
      overview([
        extension({
          installed: true,
          connected: true,
          enabled: true,
          usable: true,
          blocked_reason: null,
        }),
      ]),
    );
    render(ExtensionsView, { props: { tab: "connectors" } });

    await waitFor(() => expect(screen.getByLabelText("Open Gmail details")).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText("Open Gmail details"));

    expect(await screen.findByText(/all four conditions are met/i)).toBeInTheDocument();
    expect(screen.getByText(/ready to use in a governed turn/i)).toBeInTheDocument();
  });

  it("never shows a credential value, only whether one is stored", async () => {
    stubFetch(overview([extension({ installed: true, connected: true })]));
    render(ExtensionsView, { props: { tab: "connectors" } });

    await waitFor(() => expect(screen.getByLabelText("Open Gmail details")).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText("Open Gmail details"));

    expect(
      await screen.findByText(/a credential is stored in the vault/i),
    ).toBeInTheDocument();
  });

  it("states plainly that plugin panels are not available yet", async () => {
    stubFetch({});
    render(ExtensionsView, { props: { tab: "plugins" } });
    expect(await screen.findByText(/plugin panels are not available yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no plugin code runs in this browser/i)).toBeInTheDocument();
  });

  it("states plainly that channels are not available yet", async () => {
    stubFetch({});
    render(ExtensionsView, { props: { tab: "channels" } });
    expect(
      await screen.findByText(/channels and webhooks are not available yet/i),
    ).toBeInTheDocument();
  });

  it("exposes each tab through the ARIA tabs pattern", async () => {
    stubFetch(overview([]));
    render(ExtensionsView, { props: { tab: "connectors" } });
    const tablist = await screen.findByRole("tablist", { name: /extension categories/i });
    expect(tablist).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Connectors" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "MCP servers" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });
});
