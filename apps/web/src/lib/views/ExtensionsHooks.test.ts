// The Hooks panel. Hooks are the one extension surface whose backend really
// enforces something — a `PreToolUse` deny short-circuits to a denied policy
// decision — and until this panel they were configured by editing JSON on disk
// and observed only by reading the audit log by hand.
//
// The panel is worth more than that file only if it is exact about the three
// ways a configured hook can still do nothing: its file did not parse, its event
// is never dispatched by this build, or nothing about it carries a decision the
// runtime honours. Each of those is asserted here, because each of them is a
// safeguard the owner would otherwise believe was in place.
import { render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExtensionsView from "./ExtensionsView.svelte";
import { stubFetch } from "../test-helpers";
import type { HooksView } from "../apiTypes";

afterEach(() => vi.unstubAllGlobals());

const EVENTS: HooksView["events"] = [
  {
    event: "PreToolUse",
    summary: "Before policy finalises a tool call.",
    dispatched: true,
    can_decide: true,
  },
  {
    event: "PostToolUse",
    summary: "A tool call finished successfully.",
    dispatched: true,
    can_decide: false,
  },
  { event: "SessionEnd", summary: "A conversation ends.", dispatched: false, can_decide: false },
];

function hooks(partial: Partial<HooksView> = {}): HooksView {
  return {
    active: true,
    disabled: false,
    rule_count: 0,
    rules: [],
    sources: [
      {
        path: "config/hooks.json",
        scope: "project",
        exists: true,
        loaded: true,
        rule_count: 0,
        error: null,
      },
    ],
    failed_sources: [],
    events: EVENTS,
    builtins: ["block_destructive_shell"],
    activity: [],
    activity_counts: {},
    ...partial,
  };
}

function rule(partial: Partial<HooksView["rules"][number]>): HooksView["rules"][number] {
  return {
    rule_id: "project:PreToolUse:0",
    event: "PreToolUse",
    event_summary: "Before policy finalises a tool call.",
    matcher: "shell",
    if_guard: null,
    scope: "project",
    source: "config/hooks.json",
    dispatched: true,
    can_decide: true,
    handlers: [
      {
        id: "guard",
        type: "builtin",
        target: "block_destructive_shell",
        timeout_ms: 5000,
        decision_authority: true,
        available: true,
      },
    ],
    ...partial,
  };
}

function routes(view: HooksView) {
  return {
    "GET /api/extensions": { extensions: [], summary: {} },
    "GET /api/plugins": {
      plugins: [],
      signing: { configured: false, summary: "", remediation: null },
      contribution_kinds: [],
    },
    "GET /api/approvals": [],
    "GET /api/hooks": view,
  };
}

describe("Extensions → Hooks", () => {
  it("says a configuration file could not be read instead of showing nothing", async () => {
    stubFetch(
      routes(
        hooks({
          active: false,
          failed_sources: [
            {
              path: ".raiker/hooks.json",
              scope: "local",
              exists: true,
              loaded: false,
              rule_count: 0,
              error: "invalid_json:1:3",
            },
          ],
        }),
      ),
    );
    render(ExtensionsView, { tab: "hooks" });

    // Silence here would leave the owner believing a guard is in place.
    const posture = await screen.findByText(/could not be read/i);
    // Scoped to the error list: the footer card names the same path when it
    // explains where hooks are configured, and that mention is not the failure.
    const section = posture.closest("section") as HTMLElement;
    expect(within(section).getByText(".raiker/hooks.json")).toBeInTheDocument();
    expect(within(section).getByText("invalid_json:1:3")).toBeInTheDocument();
  });

  it("marks a rule whose event this build never emits", async () => {
    stubFetch(
      routes(
        hooks({
          rule_count: 1,
          rules: [
            rule({
              rule_id: "project:SessionEnd:0",
              event: "SessionEnd",
              dispatched: false,
              can_decide: false,
              handlers: [
                {
                  id: "on-end",
                  type: "command",
                  target: "scripts/end.sh",
                  timeout_ms: 5000,
                  decision_authority: false,
                  available: true,
                },
              ],
            }),
          ],
        }),
      ),
    );
    render(ExtensionsView, { tab: "hooks" });

    expect(
      await screen.findByText(/never emits SessionEnd, so this rule is configured but never fires/i),
    ).toBeInTheDocument();
  });

  it("separates a rule that can deny from one that only observes", async () => {
    stubFetch(
      routes(
        hooks({
          rule_count: 2,
          rules: [
            rule({}),
            rule({
              rule_id: "project:PostToolUse:1",
              event: "PostToolUse",
              matcher: "*",
              can_decide: false,
              handlers: [
                {
                  id: "note",
                  type: "command",
                  target: "scripts/note.sh",
                  timeout_ms: 1500,
                  decision_authority: false,
                  available: true,
                },
              ],
            }),
          ],
        }),
      ),
    );
    render(ExtensionsView, { tab: "hooks" });

    expect(await screen.findByText("Can deny or ask")).toBeInTheDocument();
    expect(screen.getByText("Observes only")).toBeInTheDocument();
  });

  it("warns when a rule names a builtin this build does not have", async () => {
    stubFetch(
      routes(
        hooks({
          rule_count: 1,
          rules: [
            rule({
              can_decide: false,
              handlers: [
                {
                  id: "typo",
                  type: "builtin",
                  target: "deny",
                  timeout_ms: 5000,
                  decision_authority: false,
                  available: false,
                },
              ],
            }),
          ],
        }),
      ),
    );
    render(ExtensionsView, { tab: "hooks" });

    // The rule parses and matches, then fails every time. Showing it as
    // enforcing would be the surface asserting a guard that is not there.
    expect(await screen.findByText(/no builtin by this name in this build/i)).toBeInTheDocument();
    expect(screen.queryByText("Can deny or ask")).not.toBeInTheDocument();
  });

  it("credits a plugin rule to the plugin that wrote it, not to its scope", async () => {
    // BUG-221 — every installed plugin loads at scope "plugin", so the scope word
    // stopped identifying a file. Two plugins showing the same label would leave
    // the owner unable to tell which one wrote the rule that just denied them.
    stubFetch(
      routes(
        hooks({
          rule_count: 2,
          rules: [
            rule({
              rule_id: "plugin:PreToolUse:0",
              scope: "plugin",
              source: ".raiker/plugins/acme-guard/hooks.json",
            }),
            rule({
              rule_id: "plugin:PreToolUse:1",
              scope: "plugin",
              source: ".raiker/plugins/beta-watch/hooks.json",
            }),
          ],
        }),
      ),
    );
    render(ExtensionsView, { tab: "hooks" });

    expect(await screen.findByText("acme-guard")).toBeInTheDocument();
    expect(screen.getByText("beta-watch")).toBeInTheDocument();
  });

  it("names the plugin directory among the places hooks come from", async () => {
    stubFetch(routes(hooks()));
    render(ExtensionsView, { tab: "hooks" });

    const footer = await screen.findByText(/hooks are configured in a file, not here/i);
    expect(footer.closest("section")).toHaveTextContent(".raiker/plugins/");
  });

  it("publishes what a rule may name, because the file is written by hand", async () => {
    stubFetch(routes(hooks()));
    render(ExtensionsView, { tab: "hooks" });

    const catalogue = await screen.findByRole("heading", { name: "What fires, and what it can change" });
    const section = catalogue.closest("section") as HTMLElement;
    expect(within(section).getByText("PreToolUse")).toBeInTheDocument();
    expect(within(section).getByText("Decides")).toBeInTheDocument();
    expect(within(section).getByText("Never fires")).toBeInTheDocument();

    const builtins = screen.getByRole("heading", { name: "Built-in handlers" }).closest("section") as HTMLElement;
    expect(within(builtins).getByText("block_destructive_shell")).toBeInTheDocument();
  });

  it("keeps the rules listed when the owner turns hooks off", async () => {
    stubFetch(routes(hooks({ active: false, disabled: true, rule_count: 1, rules: [rule({})] })));
    render(ExtensionsView, { tab: "hooks" });

    // Off is a state to display, not a reason to hide what would otherwise run.
    expect(await screen.findByText(/Hooks are turned off/i)).toBeInTheDocument();
    expect(screen.getByText(/will not run/i)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Turn every hook off/i })).toBeChecked();
    // The rule itself is still on the page — scoped past the builtin catalogue,
    // which names the same handler.
    const rules = screen.getByRole("heading", { name: "Configured rules" }).closest("section")!;
    expect(within(rules as HTMLElement).getByText("block_destructive_shell")).toBeInTheDocument();
  });

  it("says nothing is configured rather than looking like it never checked", async () => {
    stubFetch(routes(hooks({ active: false })));
    render(ExtensionsView, { tab: "hooks" });

    expect(
      await screen.findByText(/No hooks are configured, so the runtime behaves exactly as it does without them/i),
    ).toBeInTheDocument();
  });

  it("reports what hooks have actually done", async () => {
    stubFetch(
      routes(
        hooks({
          activity: [
            {
              event_id: "evt_1",
              event_type: "hook_failed",
              session_id: "sess_1",
              timestamp: new Date().toISOString(),
              summary: "record-tool-use",
            },
          ],
          activity_counts: { hook_failed: 1 },
        }),
      ),
    );
    render(ExtensionsView, { tab: "hooks" });

    await waitFor(() => expect(screen.getByText("failed")).toBeInTheDocument());
    expect(screen.getByText("record-tool-use")).toBeInTheDocument();
  });
});
