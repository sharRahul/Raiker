// QUI-L07 — Connections: Services, Channels, and Advanced (MCP servers, skills,
// hooks and plugins as one segmented list). The readiness facts of a connected
// service are tested with Services, in ConnectionsView.test.ts.
import { render, screen } from "@testing-library/svelte";
import { fireEvent, within } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExtensionsView from "./ExtensionsView.svelte";
import { stubFetch } from "../test-helpers";
import type { ExtensionView } from "../apiTypes";

afterEach(() => {
  vi.unstubAllGlobals();
});

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
    render(ExtensionsView, { props: { tab: "advanced", kind: "plugins" } });

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
    render(ExtensionsView, { props: { tab: "advanced", kind: "plugins" } });

    expect(
      await screen.findByText(/provides 2 hook rules on PostToolUse, PreToolUse/i),
    ).toBeInTheDocument();
  });

  // BUG-308 — never a claim of containment the machine cannot keep.
  it("says where a plugin's own code would run on this machine", async () => {
    stubFetch({
      "GET /api/plugins": {
        plugins: [
          {
            record_id: "plr_net",
            plugin_id: "acme-runner",
            version: "1.0.0",
            trust_level: "local_dev",
            status: "installed",
            source_url: null,
            installed_at: "2026-09-28T00:00:00Z",
            installed_by: "cli",
            checksum_present: true,
            signature: {
              level: "unsigned",
              label: "Unsigned",
              reason: "no_signature",
              method: "",
              verified: false,
              explanation: "No signature.",
              remediation: "",
            },
            contributions: {
              hooks: 0,
              events: [],
              skills: 0,
              skill_names: [],
              mcp_servers: 0,
              mcp_server_names: [],
              error: null,
            },
            code_runtime: {
              where: "host_network",
              summary:
                "Its code runs as a bounded process with this machine's network: no plugin container is set up here.",
            },
          },
        ],
        signing: { configured: false, summary: "No signing key configured." },
        contribution_kinds: [],
      },
    });
    render(ExtensionsView, { props: { tab: "advanced", kind: "plugins" } });

    expect(await screen.findByTestId("plugin-code-runtime")).toHaveTextContent(
      /with this machine's network/,
    );
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
    render(ExtensionsView, { props: { tab: "advanced", kind: "plugins" } });

    expect(
      await screen.findByText(/provides 2 skills \(acme-release, acme-review\)/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Its skills install switched off/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Turn them on in Skills/i })).toHaveAttribute(
      "href",
      "#/connections?tab=advanced&kind=skills",
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
    render(ExtensionsView, { props: { tab: "advanced", kind: "plugins" } });
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
    render(ExtensionsView, { props: { tab: "advanced", kind: "plugins" } });
    expect(await screen.findByText("example.plugin")).toBeInTheDocument();
    expect(screen.getByTitle("signature_present")).toHaveTextContent("Present only");
  });

  it("mounts the Skills tab as its own destination", async () => {
    stubFetch({ "GET /api/skills": { skills: [] } });
    render(ExtensionsView, { props: { tab: "advanced", kind: "skills" } });
    expect(await screen.findByRole("heading", { name: "Skills" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add a skill/i })).toBeInTheDocument();
  });

  it("has three tabs, Services, Channels and Advanced (QUI-L07)", async () => {
    stubFetch(overview([]));
    render(ExtensionsView, { props: { tab: "services" } });
    const tablist = await screen.findByRole("tablist", { name: /connection categories/i });
    expect(within(tablist).getAllByRole("tab").map((tab) => tab.textContent?.trim())).toEqual([
      "Services",
      "Channels",
      "Advanced",
    ]);
    expect(screen.getByRole("tab", { name: "Services" })).toHaveAttribute("aria-selected", "true");
  });

  it("lists MCP servers, skills, hooks and plugins as one segmented list under Advanced", async () => {
    stubFetch({ "GET /api/skills": { skills: [] } });
    render(ExtensionsView, { props: { tab: "advanced", kind: "mcp" } });
    const group = await screen.findByRole("group", { name: "Advanced connections" });
    expect(within(group).getByRole("button", { name: "MCP servers" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await fireEvent.click(within(group).getByRole("button", { name: "Skills" }));
    expect(within(group).getByRole("button", { name: "Skills" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(window.location.hash).toBe("#/connections?tab=advanced&kind=skills");
  });
});
