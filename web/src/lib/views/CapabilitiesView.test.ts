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
  vi.unstubAllGlobals();
});

/**
 * The registry list, as opposed to the short "Common permissions" section above
 * it. A capability an owner commonly changes appears in both by design, so a
 * test about the grouped list has to say which one it means.
 */
function registry() {
  return within(screen.getByRole("region", { name: "All permissions" }));
}

/** The same, for a test that renders and reads before the gates have arrived. */
async function registryWhenLoaded() {
  return within(await screen.findByRole("region", { name: "All permissions" }));
}

/** The posture chips, which are the page's one status filter. */
function status() {
  return within(screen.getByRole("group", { name: "Filter permissions by status" }));
}

// GEP-04 — a switch beside a running feature that it does not govern tells the
// owner something untrue about their own control. The card has to say so.
describe("CapabilitiesView — what each switch actually decides", () => {
  it("asks two questions instead of showing two parallel systems", async () => {
    // The page showed availability and decision mode side by side at nearly
    // equal weight, which left an owner asking how a capability can be On and
    // Deny. They are not parallel: one is whether Raiker may use this at all,
    // the other is what happens when it wants to — so the card asks them in
    // that order, and `deny` reads as "Never".
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView);

    const shell = (await registryWhenLoaded()).getByRole("button", { name: /Shell commands/i });
    await fireEvent.click(shell);

    expect(screen.getByText("Can Raiker use this?")).toBeInTheDocument();
    expect(screen.getByText("When Raiker wants to use it")).toBeInTheDocument();
    const group = screen.getAllByRole("group", { name: /when Raiker wants to use/i })[0];
    expect(within(group).getByRole("button", { name: "Never" })).toBeInTheDocument();
    expect(within(group).queryByRole("button", { name: "Deny" })).not.toBeInTheDocument();
  });

  it("says what is on and what happens, on a row that is still closed", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView);

    // A permission list that has to be opened row by row to learn what is on
    // cannot be scanned, and scanning is the reason to have the list.
    await waitFor(() => expect(screen.getAllByText(/^(On|Off) · /).length).toBeGreaterThan(0));
  });

  /*
   * GEP-04's second answer. A gate that decides nothing when flipped is not a
   * decision, and it used to be rendered as one: a row with four mode buttons,
   * a selection box and a grey chip. It is read-only reference now, and the
   * note — what really governs this, or why nothing runs — is the content
   * rather than a caveat under a control that should not exist.
   */
  it("keeps a gate governed by another control out of the registry, and names that control", async () => {
    stubFetch({
      "GET /api/capability-gates": [
        makeGate({
          capability: "shell_execution",
          phase: 3,
          state: "enabled_runtime",
          can_current_principal_change: true,
          allowed_transitions: ["disabled"],
          decision_mode: "ask",
        }),
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
    await waitFor(() => expect(registry().getByText("Shell commands")).toBeInTheDocument());

    // No row, so no mode control, no selection box, and nothing counted as a
    // permission the owner has decided.
    expect(registry().queryByText("Scheduled routines")).not.toBeInTheDocument();
    expect(screen.getByText("Showing 1 of 1 permissions")).toBeInTheDocument();

    const reference = within(screen.getByText("Not decided here").closest("details")!);
    expect(reference.getByText("Scheduled routines")).toBeInTheDocument();
    expect(reference.getByText("Governed elsewhere")).toBeInTheDocument();
    expect(
      reference.getByText(/one whole governed turn through the Agent Gateway/i),
    ).toBeInTheDocument();
  });

  it("keeps a gate nothing in the product reaches out of the registry, and says why", async () => {
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

    const reference = within(
      (await screen.findByText("Not decided here")).closest("details")!,
    );
    expect(reference.getByText("Subagents")).toBeInTheDocument();
    expect(reference.getByText("No route yet")).toBeInTheDocument();
    // And the page does not offer it as something to decide.
    expect(screen.queryByRole("group", { name: /when Raiker wants to use/i })).toBeNull();
    expect(screen.getByText("No permissions available")).toBeInTheDocument();
  });

  it("adds no caveat to a switch that means what it says", async () => {
    stubFetch({
      "GET /api/capability-gates": [
        makeGate({
          capability: "shell_execution",
          phase: 3,
          state: "enabled_runtime",
          can_current_principal_change: true,
          allowed_transitions: ["disabled"],
          decision_mode: "ask",
        }),
      ],
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    const row = (await registryWhenLoaded()).getByRole("button", { name: /Shell/i });
    expect(within(row).queryByText("Governed elsewhere")).toBeNull();
    expect(within(row).queryByText("No route yet")).toBeNull();
  });
});

describe("CapabilitiesView", () => {
  it("groups executable tools by domain and omits non-executors entirely", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(registry().getByText("Shell commands")).toBeInTheDocument();
    });

    // Domain headings replace backend phase numbers.
    expect(registry().getByRole("checkbox", { name: "Select all Execution capabilities" })).toBeInTheDocument();
    expect(registry().getByRole("checkbox", { name: "Select all Network capabilities" })).toBeInTheDocument();
    expect(registry().queryByText(/^Phase \d/)).not.toBeInTheDocument();

    // A capability with no executor is a future, not a tool: no row, no selector.
    expect(registry().queryByText("Finance")).not.toBeInTheDocument();
    // Same for a fail-closed domain that reports no reason code but offers no
    // enable path (the live runtime's shape for sensitive domains).
    expect(registry().queryByText("Medical")).not.toBeInTheDocument();
    // Inherent read-only contract surfaces are omitted too.
    expect(registry().queryByText("Web dashboard")).not.toBeInTheDocument();

    // Only the two real tools expose the Ask/Allow/Auto/Deny control.
    expect(registry().getAllByRole("group", { name: /when Raiker wants to use/i })).toHaveLength(2);
    expect(registry().getAllByRole("button", { name: "Ask me", pressed: true })).toHaveLength(2);

    // The implementation-status badges (Implemented / Deferred / Disabled) are gone.
    expect(registry().queryByText("Implemented")).not.toBeInTheDocument();
    expect(registry().queryByText("Deferred")).not.toBeInTheDocument();
    expect(registry().queryByText("Disabled")).not.toBeInTheDocument();
  });

  it("loads the whole matrix in a single gates request (no per-capability fan-out)", async () => {
    const mock = stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(registry().getAllByRole("group", { name: /when Raiker wants to use/i })).toHaveLength(2);
    });
    // No GET to the per-capability decision-mode endpoint.
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
    const shellGroup = await waitFor(() =>
      registry().getByRole("group", { name: /shell commands/i }),
    );
    await fireEvent.click(within(shellGroup).getByRole("button", { name: "Never" }));
    await waitFor(() => {
      expect(screen.getByText(/is now set to “Never”/i)).toBeInTheDocument();
    });
    expect(within(shellGroup).getByRole("button", { name: "Never", pressed: true })).toBeInTheDocument();
    // No step-up dialog for a tightening change.
    expect(registry().queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("requires the step-up dialog to loosen a mode (allow)", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    const shellGroup = await waitFor(() =>
      registry().getByRole("group", { name: /shell commands/i }),
    );
    await fireEvent.click(within(shellGroup).getByRole("button", { name: "Allow" }));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByText(/set shell commands to “allow”/i)).toBeInTheDocument();
  });

  it("filters capabilities by search", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(registry().getByText("Shell commands")).toBeInTheDocument();
    });
    await fireEvent.input(screen.getByLabelText(/search capabilities/i), {
      target: { value: "web fetch" },
    });
    expect(registry().queryByText("Shell commands")).not.toBeInTheDocument();
    expect(registry().getByText("Web fetch")).toBeInTheDocument();
  });

  // 66 gates across a dozen domains all rendered expanded, so reaching the one
  // you came for meant scrolling past every one you did not.
  it("folds a domain group away and brings it back", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => expect(registry().getByText("Shell commands")).toBeInTheDocument());

    const fold = screen
      .getAllByRole("button", { expanded: true })
      .find((b) => b.className.includes("phase-fold"));
    expect(fold).toBeDefined();
    await fireEvent.click(fold!);

    expect(registry().queryByText("Shell commands")).not.toBeInTheDocument();
    // The heading and the count stay, so a folded group still says what is in it.
    expect(fold).toHaveAttribute("aria-expanded", "false");

    await fireEvent.click(fold!);
    expect(registry().getByText("Shell commands")).toBeInTheDocument();
  });

  // A search is a request to see matches; answering it with a folded group would
  // be the page arguing with the query.
  it("overrides a fold while a search is active", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => expect(registry().getByText("Shell commands")).toBeInTheDocument());

    const fold = screen
      .getAllByRole("button", { expanded: true })
      .find((b) => b.className.includes("phase-fold"));
    await fireEvent.click(fold!);
    expect(registry().queryByText("Shell commands")).not.toBeInTheDocument();

    await fireEvent.input(screen.getByLabelText(/search capabilities/i), {
      target: { value: "shell" },
    });
    expect(registry().getByText("Shell commands")).toBeInTheDocument();
  });
});

/*
 * NEW-PERM-01 / NEW-PERM-02 / NEW-PERM-03 — the three defects the release
 * review found in the two sections above the registry.
 *
 * They are one page and they were three different readings of it: a prominent
 * list of the permissions an owner arrives to change with no way to change one;
 * summaries derived from the raw read while the control below them showed the
 * mode the owner had just set; and a table that answered an unrecognised mode
 * with the most permissive verdict it can print.
 */
describe("Permissions — the sections above the registry", () => {
  const AUTO_GATES = [
    makeGate({
      capability: "shell_execution",
      phase: 3,
      state: "enabled_runtime",
      can_current_principal_change: true,
      allowed_transitions: ["disabled"],
      decision_mode: "auto",
    }),
    makeGate({
      capability: "web_fetch",
      phase: 3,
      state: "enabled_runtime",
      can_current_principal_change: true,
      allowed_transitions: ["disabled"],
      decision_mode: "ask",
    }),
  ];

  function common() {
    return within(screen.getByRole("region", { name: "Common permissions" }));
  }
  function attention() {
    return within(screen.getByRole("region", { name: "Needs your attention" }));
  }

  it("gives a common permission a control to reach, not just a name to read", async () => {
    // The owner-reported symptom: the top sections "are not working". They were
    // lists of spans. Prominence that does not act is friction wearing the
    // clothes of help.
    stubFetch({ "GET /api/capability-gates": AUTO_GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => expect(registry().getByText("Shell commands")).toBeInTheDocument());

    // Fold the group away, so the shortcut has to undo it to reach the row.
    const fold = screen
      .getAllByRole("button", { expanded: true })
      .find((b) => b.className.includes("phase-fold"));
    await fireEvent.click(fold!);
    expect(registry().queryByText("Shell commands")).not.toBeInTheDocument();

    await fireEvent.click(common().getByRole("button", { name: /Manage Shell commands/i }));

    // The group is open, the row is expanded, and the keyboard is on the row's
    // own control rather than left behind on the shortcut.
    const row = await waitFor(() => registry().getByRole("button", { name: /Shell commands/i }));
    expect(row.getAttribute("aria-expanded")).toBe("true");
    await waitFor(() => expect(document.activeElement).toBe(row));
  });

  it("offers a review action on what it says needs reviewing", async () => {
    stubFetch({ "GET /api/capability-gates": AUTO_GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => expect(registry().getByText("Shell commands")).toBeInTheDocument());

    await fireEvent.click(attention().getByRole("button", { name: /Review Shell commands/i }));
    expect(
      registry().getByRole("button", { name: /Shell commands/i }).getAttribute("aria-expanded"),
    ).toBe("true");
  });

  it("moves every summary when one mode is confirmed", async () => {
    // NEW-PERM-02 — the control said Never and the two sections above it went on
    // saying Automatic, because they read the gate list and it read the
    // override. A permissions page cannot answer the same question two ways.
    stubFetch({
      "GET /api/capability-gates": AUTO_GATES,
      "POST /api/capability-modes/shell_execution/deny": {
        ok: true,
        capability: "shell_execution",
        decision_mode: "deny",
      },
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => expect(registry().getByText("Shell commands")).toBeInTheDocument());

    expect(common().getByText("On · Automatic")).toBeInTheDocument();
    expect(
      attention().getByRole("button", { name: /Review Shell commands/i }),
    ).toBeInTheDocument();

    const board = screen.getAllByRole("group", { name: /when Raiker wants to use/i })[0];
    await fireEvent.click(within(board).getByRole("button", { name: "Never" }));

    await waitFor(() => expect(common().getByText("On · Never")).toBeInTheDocument());
    // The attention entry was there *because* of the mode, so it goes with it —
    // and with it the whole section, which no longer has anything in it.
    expect(screen.queryByRole("region", { name: "Needs your attention" })).toBeNull();
    expect(registry().getByText("On · Never")).toBeInTheDocument();
  });

  it("does not say an unavailable capability is running automatically", async () => {
    // NEW-PERM-03 — configured Automatic is a fact about the account. It is not
    // evidence that an executor which is not ready is doing anything.
    stubFetch({
      "GET /api/capability-gates": [
        makeGate({
          capability: "web_fetch",
          phase: 3,
          state: "enabled_runtime",
          can_current_principal_change: true,
          allowed_transitions: ["disabled"],
          decision_mode: "auto",
          readiness: { provider_ready: false },
        }),
      ],
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => expect(registry().getByText("Web fetch")).toBeInTheDocument());

    expect(attention().getByText(/is not available right now/)).toBeInTheDocument();
    expect(attention().queryByText(/runs automatically, without asking you/)).toBeNull();
  });

  it("reads an unrecognised mode as unknown rather than as permission", async () => {
    stubFetch({
      "GET /api/capability-gates": [
        makeGate({
          capability: "shell_execution",
          phase: 3,
          state: "enabled_runtime",
          can_current_principal_change: true,
          allowed_transitions: ["disabled"],
          decision_mode: "supervise",
        }),
      ],
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => expect(registry().getByText("Shell commands")).toBeInTheDocument());

    expect(registry().getByText("On · Unknown")).toBeInTheDocument();
    await fireEvent.click(registry().getByRole("button", { name: /Shell commands/i }));
    // The card answers the behaviour question instead of falling silent on it.
    expect(screen.getByText("When Raiker wants to use it")).toBeInTheDocument();
    expect(screen.getByText(/does not recognise this setting/i)).toBeInTheDocument();
  });

  it("names what a partly refused bulk change actually did", async () => {
    // NEW-PERM-02 — the loop stopped at the first refusal and reported "The bulk
    // change was rejected", while the capabilities already changed stayed
    // changed. Every selection is attempted and the report names both halves.
    stubFetch({
      "GET /api/capability-gates": AUTO_GATES,
      "POST /api/capability-modes/shell_execution/ask": {
        ok: true,
        capability: "shell_execution",
        decision_mode: "ask",
      },
      "POST /api/capability-modes/web_fetch/ask": {
        __status: 409,
        detail: { reason_code: "capability_change_refused" },
      },
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => expect(registry().getByText("Shell commands")).toBeInTheDocument());

    // The per-capability boxes only: pressing a group's "select all" as well
    // would toggle the same capabilities straight back off.
    for (const name of [/^Select Shell commands$/, /^Select Web fetch$/]) {
      await fireEvent.click(registry().getByRole("checkbox", { name }));
    }
    // REM-PERM-02 — the bulk buttons speak the page's one vocabulary now:
    // "Ask me" and "Never", not "Ask" and "Deny" about the same stored values.
    // Scoped to the toolbar, because that is now the same word the per-row
    // controls use — which is the point, and is why the toolbar names itself.
    const bulk = within(screen.getByRole("toolbar", { name: "Bulk capability actions" }));
    await fireEvent.click(bulk.getByRole("button", { name: "Ask me" }));

    const notice = await screen.findByRole("status");
    expect(notice.textContent).toMatch(/1 changed/);
    expect(notice.textContent).toMatch(/Web fetch/);
    // The one that was refused stays selected, so it can be retried where it is.
    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });
});

describe("Permissions workspace", () => {
  it("combines search, group and status filters and recovers from no matches", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView);
    await registryWhenLoaded();
    await fireEvent.change(screen.getByRole("combobox", { name: "Permission group" }), { target: { value: "Network" } });
    expect(registry().queryByRole("button", { name: /Shell commands/i })).not.toBeInTheDocument();
    expect(registry().getByRole("button", { name: /Web fetch/i })).toBeInTheDocument();
    // REM-PERM-01 — the status filter is the posture chips, which are also the
    // page's one statement of what is on. It used to be both four page-width
    // tiles at the top and a select two-thirds of the way down.
    await fireEvent.click(status().getByRole("button", { name: /Unavailable/ }));
    expect(screen.getByText("No matching permissions")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("Showing 2 of 2 permissions")).toBeInTheDocument();
    // Domain names are searchable even when they do not occur in tool labels.
    await fireEvent.input(screen.getByRole("searchbox"), { target: { value: "Network" } });
    expect(screen.getByText("Showing 1 of 2 permissions")).toBeInTheDocument();
    expect(registry().getByRole("button", { name: /Web fetch/i })).toBeInTheDocument();
  });

  it("excludes read-only permissions from group selection", async () => {
    stubFetch({ "GET /api/capability-gates": [GATES[0], { ...GATES[1], can_current_principal_change: false }] });
    render(CapabilitiesView);
    const list = await registryWhenLoaded();
    expect(list.getByRole("checkbox", { name: "Select Web fetch" })).toBeDisabled();
    expect(list.getByRole("checkbox", { name: "Select all Network capabilities" })).toBeDisabled();
    await fireEvent.click(list.getByRole("checkbox", { name: "Select Shell commands" }));
    // The Selected chip appears only once there is a selection to filter to.
    await fireEvent.click(status().getByRole("button", { name: /Selected/ }));
    expect(screen.getByText("Showing 1 of 2 permissions")).toBeInTheDocument();
    expect(registry().queryByRole("checkbox", { name: "Select Web fetch" })).not.toBeInTheDocument();
  });

  it("makes search results visible after all groups are collapsed", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView);
    await registryWhenLoaded();
    await fireEvent.click(screen.getByRole("button", { name: "Collapse groups" }));
    expect(registry().queryByRole("button", { name: /Shell commands/i })).not.toBeInTheDocument();
    await fireEvent.input(screen.getByRole("searchbox"), { target: { value: "shell" } });
    expect(registry().getByRole("button", { name: /Shell commands/i })).toBeInTheDocument();
  });

  it("shows an explicit empty state when no executable permissions are reported", async () => {
    stubFetch({ "GET /api/capability-gates": [] });
    render(CapabilitiesView);
    expect(await screen.findByText("No permissions available")).toBeInTheDocument();
  });
});

it("locks selection and individual controls until a bulk update settles", async () => {
  const fetchMock = stubFetch({ "GET /api/capability-gates": GATES });
  render(CapabilitiesView);
  const list = await registryWhenLoaded();
  await fireEvent.click(list.getByRole("checkbox", { name: "Select Shell commands" }));
  let finish!: (response: Response) => void;
  fetchMock.mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; }));
  const bulk = within(screen.getByRole("toolbar", { name: "Bulk capability actions" }));
  await fireEvent.click(bulk.getByRole("button", { name: "Never" }));
  expect(list.getByRole("checkbox", { name: "Select Web fetch" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Refresh capabilities" })).toBeDisabled();
  const controls = within(list.getByRole("group", { name: "When Raiker wants to use Web fetch" }));
  expect(controls.getByRole("button", { name: "Allow" })).toBeDisabled();
  finish({ ok: true, status: 200, json: async () => ({ ok: true }) } as Response);
  await waitFor(() => expect(controls.getByRole("button", { name: "Allow" })).toBeEnabled());
  expect(list.getByRole("checkbox", { name: "Select Shell commands" })).not.toBeChecked();
});

it("drops selected permissions when refresh revokes editing access", async () => {
  const routes = { "GET /api/capability-gates": GATES };
  stubFetch(routes);
  render(CapabilitiesView);
  const list = await registryWhenLoaded();
  await fireEvent.click(list.getByRole("checkbox", { name: "Select Shell commands" }));
  routes["GET /api/capability-gates"] = GATES.map(gate => ({ ...gate, can_current_principal_change: false }));
  await fireEvent.click(screen.getByRole("button", { name: "Refresh capabilities" }));
  await waitFor(() => expect(screen.queryByRole("toolbar", { name: "Bulk capability actions" })).not.toBeInTheDocument());
  expect(registry().getByRole("checkbox", { name: "Select Shell commands" })).toBeDisabled();
});
