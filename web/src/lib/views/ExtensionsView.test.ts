// The Extensions hub consolidates connectors and MCP into one destination. Its
// job is to never let metadata alone imply that something works: installed,
// connected, enabled, and usable are four separate facts, and anything not
// usable says which condition is unmet.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent, within } from "@testing-library/dom";
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

  it("points at the decision queue when a call is waiting on approval", async () => {
    stubFetch({
      ...overview([extension({ installed: true, connected: true, enabled: true })]),
      "GET /api/approvals": [
        { approval_id: "appr_1", capability: "connector_gmail_runtime", is_expired: false },
      ],
    });
    render(ExtensionsView, { props: { tab: "connectors" } });
    await waitFor(() => expect(screen.getByLabelText("Open Gmail details")).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText("Open Gmail details"));

    expect(await screen.findByText(/one call is\s+waiting on your decision/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review the decision queue/i })).toHaveAttribute(
      "href",
      "#/approvals",
    );
  });

  it("shows no approval pointer when nothing is pending for that capability", async () => {
    stubFetch({
      ...overview([extension({ installed: true })]),
      "GET /api/approvals": [
        { approval_id: "appr_1", capability: "connector_slack_runtime", is_expired: false },
      ],
    });
    render(ExtensionsView, { props: { tab: "connectors" } });
    await waitFor(() => expect(screen.getByLabelText("Open Gmail details")).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText("Open Gmail details"));
    expect(screen.queryByText(/waiting on your decision/i)).not.toBeInTheDocument();
  });

  it("separates what a plugin may contribute from what it does not yet", async () => {
    // BUG-221 — hooks are contributable now, panels are not. One list saying
    // which is which beats a card that implies a plugin contributes nothing.
    stubFetch({
      "GET /api/plugins": {
        plugins: [],
        signing: { configured: false, summary: "No signing key configured." },
        contribution_kinds: [
          { kind: "hooks", available: true, summary: "Hook rules at plugin scope." },
          { kind: "panels", available: false, summary: "Needs a route contract." },
        ],
      },
    });
    render(ExtensionsView, { props: { tab: "plugins" } });

    const heading = await screen.findByText(/what a plugin may contribute/i);
    // Scoped to the card: "Hooks" is also a tab label, and asserting against the
    // wrong one would pass without proving anything about this list.
    const card = within(heading.closest("section") as HTMLElement);
    expect(card.getByText("Hooks").closest("li")).toHaveTextContent("Available");
    expect(card.getByText("Panels").closest("li")).toHaveTextContent("Not yet");
  });

  it("says what an installed plugin actually provides", async () => {
    stubFetch({
      "GET /api/plugins": {
        plugins: [
          {
            record_id: "plr_1",
            plugin_id: "acme-guard",
            version: "1.2.0",
            trust_level: "local_dev",
            status: "installed",
            source_url: null,
            installed_at: "2026-08-22T00:00:00Z",
            installed_by: "cli",
            checksum_present: true,
            signature: {
              level: "present_only",
              label: "Signature present",
              reason: "no_key",
              method: "hmac",
              verified: false,
              explanation: "A signature is present but no key was configured to check it.",
              remediation: "",
            },
            contributions: {
              hooks: 2,
              events: ["PostToolUse", "PreToolUse"],
              skills: 0,
              skill_names: [],
              mcp_servers: 0,
              mcp_server_names: [],
              error: null,
            },
          },
        ],
        signing: { configured: false, summary: "No signing key configured." },
        contribution_kinds: [],
      },
    });
    render(ExtensionsView, { props: { tab: "plugins" } });

    expect(
      await screen.findByText(/provides 2 hook rules on PostToolUse, PreToolUse/i),
    ).toBeInTheDocument();
  });

  // BUG-221 step 2 — a contributed skill is offered, not switched on. "Provides
  // 2 skills" must not read as two skills already in every turn.
  it("names the skills a plugin provides, and says they are not on yet", async () => {
    stubFetch({
      "GET /api/plugins": {
        plugins: [
          {
            record_id: "plr_2",
            plugin_id: "acme-skills",
            version: "2.0.0",
            trust_level: "local_dev",
            status: "installed",
            source_url: null,
            installed_at: "2026-08-22T00:00:00Z",
            installed_by: "cli",
            checksum_present: true,
            signature: {
              level: "unsigned",
              label: "Unsigned",
              reason: "no_signature",
              method: "none",
              verified: false,
              explanation: "No signature was supplied.",
              remediation: "",
            },
            contributions: {
              hooks: 0,
              events: [],
              skills: 2,
              skill_names: ["acme-release", "acme-review"],
              mcp_servers: 0,
              mcp_server_names: [],
              error: null,
            },
          },
        ],
        signing: { configured: false, summary: "No signing key configured." },
        contribution_kinds: [],
      },
    });
    render(ExtensionsView, { props: { tab: "plugins" } });

    expect(
      await screen.findByText(/provides 2 skills \(acme-release, acme-review\)/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Its skills install switched off/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Activate them on the Skills tab/i })).toHaveAttribute(
      "href",
      "#/extensions?tab=skills",
    );
  });

  it("states the signing posture rather than leaving it to be inferred", async () => {
    // BUG-79 — on a default install a manifest signature is a presence marker,
    // and the owner was never told which state they were in.
    stubFetch({
      "GET /api/plugins": {
        plugins: [],
        signing: {
          configured: false,
          hmac_key_set: false,
          publisher_key_set: false,
          summary:
            "No signing key is configured, so a manifest signature is a presence marker only. " +
            "Installs are unaffected; verification is not.",
          remediation: "Set RAIKER_PLUGIN_SIGNING_KEY before installing.",
        },
      },
    });
    render(ExtensionsView, { props: { tab: "plugins" } });
    expect(await screen.findByText(/presence marker only/i)).toBeInTheDocument();
    expect(screen.getByText(/RAIKER_PLUGIN_SIGNING_KEY/)).toBeInTheDocument();
    expect(screen.getByText(/no plugin code runs in this browser/i)).toBeInTheDocument();
  });

  it("marks a present-only plugin as visibly distinct from a verified one", async () => {
    stubFetch({
      "GET /api/plugins": {
        plugins: [
          {
            record_id: "plr_1",
            plugin_id: "example.plugin",
            version: "1.0.0",
            trust_level: "local_dev",
            status: "installed",
            source_url: null,
            installed_at: "now",
            installed_by: "cli",
            checksum_present: true,
            signature: {
              level: "present_only",
              label: "Present only",
              reason: "signature_present",
              method: "none",
              verified: false,
              explanation: "The manifest carries a signature but no signing key is configured.",
              remediation: "Set RAIKER_PLUGIN_SIGNING_KEY and reinstall.",
            },
          },
        ],
        signing: {
          configured: false,
          hmac_key_set: false,
          publisher_key_set: false,
          summary: "No signing key is configured.",
          remediation: "",
        },
      },
    });
    render(ExtensionsView, { props: { tab: "plugins" } });
    expect(await screen.findByText("example.plugin")).toBeInTheDocument();
    expect(screen.getByTitle("signature_present")).toHaveTextContent("Present only");
  });

  it("mounts the Skills tab as its own destination", async () => {
    stubFetch({ "GET /api/skills": { skills: [] } });
    render(ExtensionsView, { props: { tab: "skills" } });
    expect(await screen.findByRole("heading", { name: "Skills" })).toBeInTheDocument();
    expect(screen.getByText(/grant no capability and run no code/i)).toBeInTheDocument();
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
    expect(screen.getByRole("tab", { name: "Skills" })).toHaveAttribute("aria-selected", "false");
  });
});
