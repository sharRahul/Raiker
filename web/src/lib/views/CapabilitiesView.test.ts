import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import CapabilitiesView from "./CapabilitiesView.svelte";
import { makeGate, stubFetch } from "../test-helpers";

// Decision modes arrive inline on each gate (gate.decision_mode) from the single
// /api/capability-gates read — no per-capability fan-out.
const GATES = [
  makeGate({
    capability: "shell_execution",
    phase: 3,
    state: "enabled_runtime",
    can_current_principal_change: true,
    allowed_transitions: ["disabled"],
    decision_mode: "ask",
  }),
  makeGate({
    capability: "web_fetch",
    phase: 3,
    state: "enabled_runtime",
    can_current_principal_change: true,
    allowed_transitions: ["disabled"],
    decision_mode: "ask",
  }),
  // Deferred: no executor exists, so no row and no selector may render.
  makeGate({
    capability: "finance_runtime",
    phase: 3,
    state: "disabled",
    blocked_reason_code: "activation_blocked:no_executor",
    decision_mode: "ask",
  }),
  // Inherent read-only contract surface: not a tool the agent wields.
  makeGate({
    capability: "web_ui",
    phase: 3,
    state: "enabled_read_only",
    decision_mode: "ask",
  }),
  // Live-runtime shape of a fail-closed domain: no blocked_reason_code, but
  // the backend offers no enabled target — still not a tool.
  makeGate({
    capability: "medical_runtime",
    phase: 4,
    state: "disabled",
    blocked_reason_code: null,
    allowed_transitions: ["disabled", "planned"],
    decision_mode: "ask",
  }),
];

afterEach(() => {
  window.localStorage.clear();
  window.location.hash = "";
  vi.unstubAllGlobals();
});

/** The category rail, QUI-L06. */
function rail() {
  return within(screen.getByRole("navigation", { name: "Permission categories" }));
}

async function openCategory(name: string | RegExp) {
  await screen.findByRole("navigation", { name: "Permission categories" });
  await fireEvent.click(rail().getByRole("button", { name }));
}

/** One permission's detail pane. */
function detail(label: string) {
  return within(screen.getByRole("article", { name: label }));
}

const SHELL_GATE = {
  capability: "shell_execution",
  phase: 3,
  state: "enabled_runtime",
  can_current_principal_change: true,
  allowed_transitions: ["disabled"],
  decision_mode: "ask",
};

// GEP-04 — a switch beside a running feature that it does not govern tells the
// owner something untrue about their own control. The pane has to say so.
describe("CapabilitiesView — what each switch actually decides", () => {
  it("asks two questions instead of showing two parallel systems", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView);
    await openCategory(/Advanced/);
    await fireEvent.click(screen.getByRole("option", { name: /Shell commands/ }));

    const pane = detail("Shell commands");
    expect(pane.getByText("Can Raiker use this?")).toBeInTheDocument();
    expect(pane.getByText("When Raiker wants to use it")).toBeInTheDocument();
    const group = pane.getByRole("group", { name: /when Raiker wants to use/i });
    expect(within(group).getByRole("button", { name: "Never" })).toBeInTheDocument();
    expect(within(group).queryByRole("button", { name: "Deny" })).not.toBeInTheDocument();
  });

  it("shows each permission's policy as text on its row, with no control on the row", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView);
    await openCategory(/Web and research/);
    const row = screen.getByRole("option", { name: /Web fetch/ });
    expect(row).toHaveTextContent(/On · /);
    expect(within(row).queryByRole("button")).toBeNull();
    // One four-way control on the page: the open permission's.
    expect(screen.getAllByRole("group", { name: /when Raiker wants to use/i })).toHaveLength(1);
  });

  it("keeps a gate governed by another control out of the list, and names that control under Advanced", async () => {
    stubFetch({
      "GET /api/capability-gates": [
        makeGate(SHELL_GATE),
        makeGate({
          capability: "scheduled_routines",
          phase: 5,
          state: "enabled_runtime",
          can_current_principal_change: true,
          allowed_transitions: ["disabled"],
          decision_mode: "ask",
          gate_reality: "governed_elsewhere",
          governance_note:
            "A scheduled task runs as one whole governed turn through the Agent Gateway.",
        }),
      ],
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Advanced/);
    expect(screen.queryByRole("option", { name: /Scheduled routines/ })).toBeNull();
    expect(rail().queryByRole("button", { name: /Schedules/ })).toBeNull();

    const reference = within(screen.getByText("Not decided here").closest("details")!);
    expect(reference.getByText("Scheduled routines")).toBeInTheDocument();
    expect(reference.getByText("Governed elsewhere")).toBeInTheDocument();
    expect(
      reference.getByText(/one whole governed turn through the Agent Gateway/i),
    ).toBeInTheDocument();
  });

  it("offers nothing to decide when no gate decides its own capability", async () => {
    stubFetch({
      "GET /api/capability-gates": [
        makeGate({
          capability: "subagents",
          phase: 4,
          state: "enabled_runtime",
          can_current_principal_change: true,
          allowed_transitions: ["disabled"],
          decision_mode: "ask",
          gate_reality: "no_path",
          governance_note: "Nothing in the product constructs an action for this yet.",
        }),
      ],
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    expect(await screen.findByText("No permissions available")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /when Raiker wants to use/i })).toBeNull();
  });
});

describe("CapabilitiesView (QUI-L06)", () => {
  it("lists categories with Overview first and the system permissions last under Advanced", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await screen.findByRole("navigation", { name: "Permission categories" });
    const labels = rail()
      .getAllByRole("button")
      .map((button) => button.textContent?.replace(/\s+/g, " ").trim());
    expect(labels).toEqual(["Overview", "Web and research 1", "Advanced 1"]);
    expect(rail().getByRole("button", { name: /Overview/ })).toHaveAttribute("aria-current", "page");
    // A capability with no executor, a fail-closed domain and an inherent
    // read-only surface are not tools: no row anywhere.
    await openCategory(/Advanced/);
    expect(screen.queryByText("Finance")).toBeNull();
    expect(screen.queryByText("Medical")).toBeNull();
    expect(screen.queryByText("Web dashboard")).toBeNull();
  });

  it("puts the category in the address so a link opens it", async () => {
    window.location.hash = "#/capabilities?category=web-and-research";
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView);
    expect(await screen.findByRole("option", { name: /Web fetch/ })).toBeInTheDocument();
    await openCategory(/Advanced/);
    expect(window.location.hash).toBe("#/capabilities?category=advanced");
  });

  it("offers the technical grouping from the overflow menu", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView);
    await screen.findByRole("navigation", { name: "Permission categories" });
    await fireEvent.click(screen.getByRole("button", { name: /more actions for permissions/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: "Group by technical area" }));
    expect(rail().getByRole("button", { name: /Execution/ })).toBeInTheDocument();
    expect(rail().getByRole("button", { name: /Network/ })).toBeInTheDocument();
  });

  it("loads the whole matrix in a single gates request (no per-capability fan-out)", async () => {
    const mock = stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Advanced/);
    expect(
      mock.mock.calls.filter(([u]) => String(u).includes("/api/capability-modes/")),
    ).toHaveLength(0);
  });

  it("applies a tightening mode (deny) immediately without a step-up dialog", async () => {
    stubFetch({
      "GET /api/capability-gates": GATES,
      "POST /api/capability-modes/shell_execution/deny": {
        ok: true,
        capability: "shell_execution",
        decision_mode: "deny",
      },
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Advanced/);
    const group = detail("Shell commands").getByRole("group", { name: /shell commands/i });
    await fireEvent.click(within(group).getByRole("button", { name: "Never" }));
    await waitFor(() => expect(screen.getByText(/is now set to “Never”/i)).toBeInTheDocument());
    expect(within(group).getByRole("button", { name: "Never", pressed: true })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Shell commands/ })).toHaveTextContent("On · Never");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  // §13.2 item 6 — a change carries the mode the page showed, and a page that
  // is out of date is told so and shows today's value rather than overwriting.
  it("sends the mode it showed, and on a conflict shows what is true now", async () => {
    const changedElsewhere = GATES.map((gate) =>
      gate.capability === "shell_execution" ? { ...gate, decision_mode: "deny" } : gate,
    );
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      void input;
      void init;
      return { ok: true, status: 200, json: async () => GATES } as Response;
    });
    vi.stubGlobal("fetch", mock);
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Advanced/);
    const group = detail("Shell commands").getByRole("group", { name: /shell commands/i });
    expect(within(group).getByRole("button", { name: "Ask me", pressed: true })).toBeInTheDocument();
    mock.mockClear();
    mock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/capability-gates")) {
        return { ok: true, status: 200, json: async () => changedElsewhere } as Response;
      }
      if (url.includes("/api/capability-modes/shell_execution/deny") && init?.method === "POST") {
        return {
          ok: false,
          status: 409,
          json: async () => ({ detail: { ok: false, reason_code: "capability_conflict" } }),
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });
    await fireEvent.click(within(group).getByRole("button", { name: "Never" }));
    await waitFor(() => expect(screen.getByText(/changed somewhere else since this page loaded/)).toBeInTheDocument());
    const sent = mock.mock.calls.find(([u]) => String(u).includes("/capability-modes/shell_execution/deny"));
    expect(JSON.parse(String(sent?.[1]?.body))).toMatchObject({ expected_mode: "ask" });
    expect(mock.mock.calls.some(([u]) => String(u).endsWith("/api/capability-gates"))).toBe(true);
  });

  it("requires the step-up dialog to loosen a mode (allow)", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Advanced/);
    const group = detail("Shell commands").getByRole("group", { name: /shell commands/i });
    await fireEvent.click(within(group).getByRole("button", { name: "Allow" }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByText(/set shell commands to “allow”/i)).toBeInTheDocument();
  });

  it("searches the permissions in a category", async () => {
    stubFetch({
      "GET /api/capability-gates": [
        makeGate(SHELL_GATE),
        makeGate({ ...SHELL_GATE, capability: "telemetry_export" }),
      ],
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Advanced/);
    await fireEvent.input(screen.getByRole("searchbox", { name: "Search permissions" }), {
      target: { value: "shell" },
    });
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByRole("option", { name: /Shell commands/ })).toBeInTheDocument();
  });

  it("shows an explicit empty state when no executable permissions are reported", async () => {
    stubFetch({ "GET /api/capability-gates": [] });
    render(CapabilitiesView);
    expect(await screen.findByText("No permissions available")).toBeInTheDocument();
  });
});

/*
 * NEW-PERM-01 / NEW-PERM-02 / NEW-PERM-03 — a summary that cannot act, a summary
 * that disagrees with the control, and an unrecognised mode read as permission.
 */
describe("Permissions — summaries, shortcuts and review", () => {
  const AUTO_GATES = [
    makeGate({ ...SHELL_GATE, decision_mode: "auto" }),
    makeGate({ ...SHELL_GATE, capability: "web_fetch", decision_mode: "ask" }),
  ];

  it("opens the permission a goal sentence names, with focus on its control", async () => {
    stubFetch({ "GET /api/capability-gates": AUTO_GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    const goals = await screen.findByRole("region", { name: "What Raiker can do for you" });
    await fireEvent.click(within(goals).getAllByRole("button", { name: /Change: .*commands/i })[0]);
    expect(await screen.findByRole("article", { name: "Shell commands" })).toBeInTheDocument();
    expect(rail().getByRole("button", { name: /Advanced/ })).toHaveAttribute("aria-current", "page");
    await waitFor(() =>
      expect(screen.getByRole("article", { name: "Shell commands" }).contains(document.activeElement)).toBe(true),
    );
  });

  it("marks what needs review on the rail, the row and the detail", async () => {
    stubFetch({ "GET /api/capability-gates": AUTO_GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    expect(await screen.findByRole("button", { name: /Advanced 1 to review/ })).toBeInTheDocument();
    await openCategory(/Advanced/);
    expect(screen.getByRole("option", { name: /Shell commands/ })).toHaveTextContent("Needs review");
    expect(detail("Shell commands").getByRole("note")).toHaveTextContent(/Needs review/);
  });

  it("moves every summary when one mode is confirmed", async () => {
    stubFetch({
      "GET /api/capability-gates": AUTO_GATES,
      "POST /api/capability-modes/shell_execution/deny": {
        ok: true,
        capability: "shell_execution",
        decision_mode: "deny",
      },
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Advanced/);
    expect(screen.getByRole("option", { name: /Shell commands/ })).toHaveTextContent("On · Automatic");
    const board = detail("Shell commands").getByRole("group", { name: /when Raiker wants to use Shell commands/i });
    await fireEvent.click(within(board).getByRole("button", { name: "Never" }));
    await waitFor(() =>
      expect(screen.getByRole("option", { name: /Shell commands/ })).toHaveTextContent("On · Never"),
    );
    // The review was there because of the mode, so it goes with it.
    expect(rail().queryByText(/to review/)).toBeNull();
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("does not say an unavailable capability is running automatically", async () => {
    stubFetch({
      "GET /api/capability-gates": [
        makeGate({
          ...SHELL_GATE,
          capability: "web_fetch",
          decision_mode: "auto",
          readiness: { provider_ready: false },
        }),
      ],
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Web and research/);
    const note = detail("Web fetch").getByRole("note");
    expect(note).toHaveTextContent(/is not available right now/);
    expect(note.textContent).not.toMatch(/runs automatically, without asking you/);
  });

  it("reads an unrecognised mode as unknown rather than as permission", async () => {
    stubFetch({
      "GET /api/capability-gates": [makeGate({ ...SHELL_GATE, decision_mode: "supervise" })],
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await openCategory(/Advanced/);
    expect(screen.getByRole("option", { name: /Shell commands/ })).toHaveTextContent("On · Unknown");
    expect(detail("Shell commands").getByText("When Raiker wants to use it")).toBeInTheDocument();
    expect(detail("Shell commands").getByText(/does not recognise this setting/i)).toBeInTheDocument();
  });
});

describe("Permissions — Select several", () => {
  async function selectSeveral(category: RegExp) {
    await openCategory(category);
    await fireEvent.click(screen.getByRole("button", { name: /more actions for permissions/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: "Select several" }));
  }
  const TWO = [
    makeGate({ ...SHELL_GATE, decision_mode: "auto" }),
    makeGate({ ...SHELL_GATE, capability: "telemetry_export", decision_mode: "auto" }),
  ];

  it("names what a partly refused bulk change actually did", async () => {
    stubFetch({
      "GET /api/capability-gates": TWO,
      "POST /api/capability-modes/shell_execution/ask": {
        ok: true,
        capability: "shell_execution",
        decision_mode: "ask",
      },
      "POST /api/capability-modes/telemetry_export/ask": {
        __status: 409,
        detail: { reason_code: "capability_change_refused" },
      },
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await selectSeveral(/Advanced/);
    await fireEvent.click(screen.getByRole("checkbox", { name: "Select Shell commands" }));
    await fireEvent.click(screen.getByRole("checkbox", { name: /^Select Telemetry/ }));
    const bulk = within(screen.getByRole("toolbar", { name: "Bulk capability actions" }));
    await fireEvent.click(bulk.getByRole("button", { name: "Ask me" }));
    const notice = await screen.findByRole("status");
    expect(notice.textContent).toMatch(/1 changed/);
    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });

  it("excludes read-only permissions from selection", async () => {
    stubFetch({
      "GET /api/capability-gates": [TWO[0], { ...TWO[1], can_current_principal_change: false }],
    });
    render(CapabilitiesView);
    await selectSeveral(/Advanced/);
    expect(screen.getByRole("checkbox", { name: /^Select Telemetry/ })).toBeDisabled();
    await fireEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });

  it("locks selection until a bulk update settles", async () => {
    const fetchMock = stubFetch({ "GET /api/capability-gates": TWO });
    render(CapabilitiesView);
    await selectSeveral(/Advanced/);
    await fireEvent.click(screen.getByRole("checkbox", { name: "Select Shell commands" }));
    let finish!: (response: Response) => void;
    fetchMock.mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; }));
    const bulk = within(screen.getByRole("toolbar", { name: "Bulk capability actions" }));
    await fireEvent.click(bulk.getByRole("button", { name: "Never" }));
    expect(screen.getByRole("checkbox", { name: /^Select Telemetry/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Refresh capabilities" })).toBeDisabled();
    finish({ ok: true, status: 200, json: async () => ({ ok: true }) } as Response);
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /^Select Telemetry/ })).toBeEnabled());
    expect(screen.getByRole("checkbox", { name: "Select Shell commands" })).not.toBeChecked();
  });

  it("drops selected permissions when refresh revokes editing access", async () => {
    const routes = { "GET /api/capability-gates": TWO };
    stubFetch(routes);
    render(CapabilitiesView);
    await selectSeveral(/Advanced/);
    await fireEvent.click(screen.getByRole("checkbox", { name: "Select Shell commands" }));
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    routes["GET /api/capability-gates"] = TWO.map(gate => ({ ...gate, can_current_principal_change: false }));
    await fireEvent.click(screen.getByRole("button", { name: "Refresh capabilities" }));
    await waitFor(() => expect(screen.getByText("0 selected")).toBeInTheDocument());
    expect(screen.getByRole("checkbox", { name: "Select Shell commands" })).toBeDisabled();
  });
});

// BUG-308 — code that runs with this machine's network is its own permission,
// and its detail says, measured, whether it has the network here.
it("names the host-network capability and says where code runs on this machine", async () => {
  stubFetch({
    "GET /api/capability-gates": [
      makeGate({
        capability: "host_network_code_execution",
        phase: 2,
        state: "enabled_runtime",
        can_current_principal_change: true,
        allowed_transitions: ["disabled"],
        decision_mode: "ask",
        network_boundary:
          "The native sandbox is unavailable. Governed commands are refused until the required boundary can be established.",
      }),
    ],
  });
  render(CapabilitiesView);
  await openCategory(/Advanced/);
  expect(await screen.findByRole("option", { name: /Code with host-network risk/ })).toBeInTheDocument();
  expect(await screen.findByTestId("network-boundary")).toHaveTextContent(
    /native sandbox is unavailable.*commands are refused/,
  );
});

// UX-PERM-05 — the owner's question is "can Raiker edit my files?", not what
// one registry row is set to. The page says it by goal, read-only, from the
// same effective gates the rows render.
describe("CapabilitiesView — posture by goal", () => {
  it("summarises what Raiker can do for the owner, and leaves out goals nothing reports", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { props: { principal: "prin_owner" } });

    const goals = await screen.findByRole("region", { name: "What Raiker can do for you" });
    expect(within(goals).getByText("Can run commands and code after asking you")).toBeInTheDocument();
    expect(within(goals).getByText("Can read web pages after asking you")).toBeInTheDocument();
    // Nothing in this runtime reports a way to edit files, so the page does
    // not claim either answer about it.
    expect(within(goals).queryByText(/edit project files/)).toBeNull();
    expect(within(goals).getAllByRole("button", { name: /Change/ })).toHaveLength(2);
  });
});
