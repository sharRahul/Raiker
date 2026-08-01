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

describe("ObserveView", () => {
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
    expect(await screen.findByText(/the recorder timeline/i)).toBeInTheDocument();
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
