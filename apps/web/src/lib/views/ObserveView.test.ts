// The Observability hub is read-first. Its overview must answer "is Raiker
// ready, is anything waiting, what changed, can I safely share this" using only
// server-supplied facts — and must say it cannot reach the runtime rather than
// showing a stale green status.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ObserveView from "./ObserveView.svelte";
import { DIAGNOSTICS, stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const READINESS = { mode: "raiker_runtime", gates: [], summary: {} };

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/diagnostics": DIAGNOSTICS,
    "GET /api/runtime-readiness": READINESS,
    "GET /api/approvals": [],
    "GET /api/tasks": [],
    "GET /api/events": [],
    "GET /api/notifications": [],
    ...overrides,
  };
}

function gate(partial: Record<string, unknown> = {}) {
  return {
    capability: "shell_execution",
    phase: 1,
    state: "disabled",
    default_state: "disabled",
    source: "principal_fail_closed",
    runtime_enabled: false,
    // A gate an owner can open offers an enable target. A disabled gate with
    // none is a capability with no executor, which Permissions does not list
    // and this tile therefore does not count.
    allowed_transitions: ["enabled_runtime"],
    can_current_principal_change: true,
    blocked_reason_code: null,
    readiness: {},
    decision_mode: "ask",
    ...partial,
  };
}

describe("ObserveView", () => {
  // BUG-239 — a gate the enforcing path would run is not a closed gate.
  // Counting `!runtime_enabled` alone said "2 closed" on a workspace where one
  // of the two would have run, which is the defect Permissions had one surface
  // over.
  it("counts as closed only the gates that would actually fail closed", async () => {
    stubFetch(
      routes({
        "GET /api/runtime-readiness": {
          ...READINESS,
          gates: [
            gate(),
            gate({ capability: "web_fetch", enforced_enabled: true }),
          ],
        },
      }),
    );
    render(ObserveView, { props: { tab: "overview" } });
    const tile = (await screen.findByText("Closed capability gates")).closest("article.tile");
    expect(tile).not.toBeNull();
    expect(tile?.querySelector(".value")).toHaveTextContent("1");
  });

  // The tile links to Permissions, and Permissions lists only capabilities that
  // have an executor. Counting the ones it omits made the tile say 65 under a
  // link to a page with 48 rows on it.
  it("counts only the closed gates the page it links to can open", async () => {
    stubFetch(
      routes({
        "GET /api/runtime-readiness": {
          ...READINESS,
          gates: [
            gate(),
            gate({ capability: "admin_mutation", allowed_transitions: [] }),
            gate({ capability: "calendar_runtime", allowed_transitions: [] }),
          ],
        },
      }),
    );
    render(ObserveView, { props: { tab: "overview" } });
    const tile = (await screen.findByText("Closed capability gates")).closest("article.tile");
    expect(tile?.querySelector(".value")).toHaveTextContent("1");
    expect(tile).toHaveTextContent("2 more have no executor and stay closed.");
  });

  it("shows a loading state while the runtime status is read", async () => {
    stubFetchPending();
    render(ObserveView, { props: { tab: "overview" } });
    expect(await screen.findByText(/reading runtime status/i)).toBeInTheDocument();
  });

  it("says the runtime is unreachable instead of showing stale readiness", async () => {
    stubFetch({});
    render(ObserveView, { props: { tab: "overview" } });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't read the runtime status/i);
    expect(alert).toHaveTextContent(/nothing was started or changed/i);
    expect(screen.queryByText("Ready")).not.toBeInTheDocument();
  });

  it("answers the four overview questions with evidence links", async () => {
    stubFetch(routes());
    render(ObserveView, { props: { tab: "overview" } });

    await waitFor(() => expect(screen.getByText("Is Raiker ready?")).toBeInTheDocument());
    expect(screen.getByText("Is anything waiting for me?")).toBeInTheDocument();
    expect(screen.getByText("What changed?")).toBeInTheDocument();
    expect(screen.getByText("Can I safely share this?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open diagnostics/i })).toHaveAttribute(
      "href",
      "#/observe?tab=diagnostics",
    );
    expect(screen.getByRole("link", { name: /open the decision queue/i })).toHaveAttribute(
      "href",
      "#/approvals",
    );
  });

  it("counts pending and expired approvals separately", async () => {
    stubFetch(
      routes({
        "GET /api/approvals": [
          { approval_id: "appr_1", is_expired: false },
          { approval_id: "appr_2", is_expired: true },
        ],
      }),
    );
    render(ObserveView, { props: { tab: "overview" } });

    await waitFor(() => expect(screen.getByText("Pending approvals")).toBeInTheDocument());
    expect(
      screen.getByText(/these can no longer be approved/i),
    ).toBeInTheDocument();
  });

  it("builds the support bundle only from what the server returns", async () => {
    const bundle = {
      generated_at: "2026-07-24T00:00:00Z",
      scope: "local single-user runtime",
      runtime_mode: "raiker_runtime",
      counts: {},
      missing_config: [],
      disabled_capabilities: [],
      gates: [],
      note: "Redacted diagnostic summary.",
    };
    stubFetch(routes({ "GET /api/diagnostics/export": bundle }));
    render(ObserveView, { props: { tab: "overview" } });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /build support bundle/i })).toBeInTheDocument(),
    );
    await fireEvent.click(screen.getByRole("button", { name: /build support bundle/i }));

    const output = await screen.findByLabelText(/redacted support bundle/i);
    expect(output).toHaveTextContent("local single-user runtime");
    expect(output).toHaveTextContent("Redacted diagnostic summary.");
  });

  it("reports a failed bundle build rather than showing a partial one", async () => {
    stubFetch(routes());
    render(ObserveView, { props: { tab: "overview" } });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /build support bundle/i })).toBeInTheDocument(),
    );
    await fireEvent.click(screen.getByRole("button", { name: /build support bundle/i }));

    expect(
      await screen.findByText(/could not build the support bundle \(404\)/i),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/redacted support bundle/i)).not.toBeInTheDocument();
  });

  it("shows notification history with an unread badge on its tab", async () => {
    stubFetch(
      routes({
        "GET /api/notifications": [
          {
            notification_id: "note_1",
            title: "Approval needed",
            body: "A governed write is waiting.",
            created_at: "2026-07-24T00:00:00Z",
            read: false,
          },
        ],
      }),
    );
    render(ObserveView, { props: { tab: "notifications" } });

    await waitFor(() => expect(screen.getByText("Approval needed")).toBeInTheDocument());
    expect(screen.getByRole("tab", { name: /notifications 1/i })).toBeInTheDocument();
  });

  it("links a change back to its session when the id is addressable", async () => {
    stubFetch(
      routes({
        "GET /api/events": [
          {
            event_id: "ev_1",
            session_id: "sess_alpha",
            turn_id: "turn_1",
            event_type: "turn_completed",
            actor: "agent",
            timestamp: "2026-07-24T00:00:00Z",
            risk_level: "low",
            summary: "The turn finished.",
          },
        ],
      }),
    );
    render(ObserveView, { props: { tab: "overview" } });
    await waitFor(() => expect(screen.getByText("The turn finished.")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /session sess_alpha/i })).toHaveAttribute(
      "href",
      "#/sessions?session=sess_alpha",
    );
  });

  // An authorization resolution has no conversation, so it carries the scope
  // name `authz` where a session id goes. That is a real string, so the
  // redaction guard did not catch it and the timeline offered
  // `#/sessions?session=authz` — a link to a session that does not exist.
  it("offers no session link for an event scoped to authorization", async () => {
    stubFetch(
      routes({
        "GET /api/events": [
          {
            event_id: "ev_1",
            session_id: "authz",
            turn_id: null,
            event_type: "principal_resolution_failed",
            actor: "system",
            timestamp: "2026-07-24T00:00:00Z",
            risk_level: "high",
            summary: "No owner principal is configured.",
          },
        ],
      }),
    );
    render(ObserveView, { props: { tab: "overview" } });
    await waitFor(() =>
      expect(screen.getByText("No owner principal is configured.")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("link", { name: /session/i })).toBeNull();
    expect(screen.queryByText("session withheld")).toBeNull();
  });

  // Every governed read resolves the acting principal first and records it, so
  // the newest twelve events on a quiet workspace were twelve identical
  // lookups under a heading asking what changed.
  it("answers What changed with changes, not with every authorization lookup", async () => {
    stubFetch(
      routes({
        "GET /api/events": [
          ...Array.from({ length: 12 }, (_unused, index) => ({
            event_id: `ev_authz_${index}`,
            session_id: "authz",
            turn_id: null,
            event_type: "principal_resolved",
            actor: "system",
            timestamp: "2026-07-24T00:00:00Z",
            risk_level: null,
            summary: null,
          })),
          {
            event_id: "ev_real",
            session_id: "sess_alpha",
            turn_id: "turn_1",
            event_type: "capability_enabled",
            actor: "owner",
            timestamp: "2026-07-23T00:00:00Z",
            risk_level: "medium",
            summary: "Web fetch was turned on.",
          },
        ],
      }),
    );
    render(ObserveView, { props: { tab: "overview" } });
    await waitFor(() =>
      expect(screen.getByText("Web fetch was turned on.")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Principal resolved")).toBeNull();
  });

  it("offers no dead link when the server redacted the session id", async () => {
    stubFetch(
      routes({
        "GET /api/events": [
          {
            event_id: "ev_1",
            session_id: "[REDACTED_SECRET]",
            turn_id: null,
            event_type: "turn_completed",
            actor: "agent",
            timestamp: "2026-07-24T00:00:00Z",
            risk_level: "low",
            summary: "The turn finished.",
          },
        ],
      }),
    );
    render(ObserveView, { props: { tab: "overview" } });
    await waitFor(() => expect(screen.getByText("The turn finished.")).toBeInTheDocument());
    expect(screen.getByText("session withheld")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /session/i })).not.toBeInTheDocument();
  });

  it("hosts the rewind timeline as a tab rather than a separate destination", async () => {
    stubFetch({ ...routes(), "GET /api/checkpoints": [] });
    render(ObserveView, { props: { tab: "checkpoints" } });
    expect(await screen.findByRole("tab", { name: "Checkpoints" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    // BUG-208 slice C moved the panel's explanation into the guide, so the panel
    // is identified by what it is rather than by the paragraph that described it.
    expect(
      await screen.findByRole("link", { name: /how checkpoints work/i }),
    ).toHaveAttribute("href", "#/guide?section=permissions-and-runtime-modes");
  });

  it("exposes each section through the ARIA tabs pattern", async () => {
    stubFetch(routes());
    render(ObserveView, { props: { tab: "overview" } });
    expect(
      await screen.findByRole("tablist", { name: /observability sections/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
  });
});
