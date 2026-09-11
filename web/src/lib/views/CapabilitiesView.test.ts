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

    const shell = await screen.findByRole("button", { name: /Shell commands/i });
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

  it("marks a gate whose work is governed by a different control, and names it", async () => {
    stubFetch({
      "GET /api/capability-gates": [
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
    const row = await screen.findByRole("button", { name: /Scheduled/i });
    expect(within(row).getByText("Governed elsewhere")).toBeTruthy();

    await fireEvent.click(row);
    await waitFor(() =>
      expect(
        screen.getByText(/one whole governed turn through the Agent Gateway/i),
      ).toBeTruthy(),
    );
  });

  it("marks a gate nothing in the product reaches", async () => {
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
    const row = await screen.findByRole("button", { name: /Subagents/i });
    expect(within(row).getByText("No route yet")).toBeTruthy();
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
    const row = await screen.findByRole("button", { name: /Shell/i });
    expect(within(row).queryByText("Governed elsewhere")).toBeNull();
    expect(within(row).queryByText("No route yet")).toBeNull();
  });
});

/**
 * The registry list, as opposed to the short "Common permissions" section above
 * it. A capability an owner commonly changes appears in both by design, so a
 * test about the grouped list has to say which one it means.
 */
function registry() {
  return within(screen.getByRole("region", { name: "All permissions" }));
}

describe("CapabilitiesView", () => {
  it("groups executable tools by domain and omits non-executors entirely", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(registry().getByText("Shell commands")).toBeInTheDocument();
    });

    // Domain headings replace backend phase numbers.
    expect(registry().getByText("Local execution")).toBeInTheDocument();
    expect(registry().getByText("Network")).toBeInTheDocument();
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
