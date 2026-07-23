// The audit log is the append-only evidence view: every governed event, with
// the standard route-level state grammar.
import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ActivityView from "./ActivityView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ActivityView", () => {
  it("shows a route-level loading state while events are fetched", async () => {
    stubFetchPending();
    render(ActivityView);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/loading events/i);
  });

  it("shows a route-level error state when events cannot load", async () => {
    stubFetch({});
    render(ActivityView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load events/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("lists governed events with actor, risk, and summary", async () => {
    stubFetch({
      "GET /api/events": [
        {
          event_id: "ev_1",
          event_type: "security_finding_recorded",
          actor: "runtime_monitor",
          risk_level: "high",
          summary: "Credential rotation overdue for provider anthropic.",
          session_id: "sess_1",
          turn_id: null,
          timestamp: "2026-07-18T00:00:00Z",
        },
      ],
    });
    render(ActivityView);

    await waitFor(() =>
      expect(screen.getByText(/credential rotation overdue/i)).toBeInTheDocument(),
    );
    expect(screen.getByText("Security finding recorded")).toBeInTheDocument();
    expect(screen.getByText("runtime_monitor")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("loads the audit log scoped to a linked session", async () => {
    const fetchMock = stubFetch({ "GET /api/events": [] });
    render(ActivityView, { sessionId: "sess_alpha" });

    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("session_id=sess_alpha"))).toBe(true);
    });
    expect(screen.getByLabelText("Session id")).toHaveValue("sess_alpha");
  });
});
