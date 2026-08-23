// The audit log is the append-only evidence view: every governed event, with
// the standard route-level state grammar.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
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

  it("shows the signed turn identity for attributed events", async () => {
    stubFetch({
      "GET /api/events": [
        {
          event_id: "ev_machine",
          event_type: "tool_completed",
          actor: "tool_broker",
          risk_level: "low",
          summary: "Read completed",
          session_id: "sess_1",
          turn_id: "turn_1",
          timestamp: "2026-07-18T00:00:00Z",
          machine_identity: {
            principal_id: "principal_turn_agent_1",
            principal_type: "ai_agent",
            display_name: "Raiker agent · turn_1",
            subject: "spiffe://raiker/ws/agent/turn/turn_1",
            turn_id: "turn_1",
            key_id: "mkey_1",
            issued_at: "2026-07-18T00:00:00Z",
            expires_at: "2026-07-18T00:15:00Z",
            state: "inactive",
          },
        },
      ],
    });
    render(ActivityView);

    expect(await screen.findByText("Raiker agent · turn_1")).toBeInTheDocument();
    expect(screen.getByText("tool_broker")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Turn identity" })).toBeInTheDocument();
  });

  it("loads the audit log scoped to a linked session", async () => {
    const fetchMock = stubFetch({ "GET /api/events": [] });
    render(ActivityView, { sessionId: "sess_alpha" });

    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("session_id=sess_alpha"))).toBe(true);
    });
    expect(screen.getByLabelText("Session id")).toHaveValue("sess_alpha");
  });

  // BUG-231 — evidence that cannot leave the product is evidence that cannot be
  // used in a review, an incident write-up, or a second tool.
  it("offers an export, and says what it is before producing one", async () => {
    stubFetch({
      "GET /api/events": [],
      "GET /api/audit/exports": [
        {
          export_id: "aex_1234567890abcdef",
          manifest_hash: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          event_count: 42,
          redacted: true,
          first_timestamp: "2026-08-01T00:00:00Z",
          last_timestamp: "2026-08-23T00:00:00Z",
          exported_by: "principal_owner",
          created_at: "2026-08-23T00:00:00Z",
        },
      ],
    });
    render(ActivityView);

    await fireEvent.click(await screen.findByRole("button", { name: /^export$/i }));

    expect(screen.getByText(/your account only/i)).toBeInTheDocument();
    expect(screen.getByText(/manifest hash over\s+the event ids it covers/i)).toBeInTheDocument();
    expect(await screen.findByText(/42 events/)).toBeInTheDocument();
    expect(screen.getByText("0123456789ab")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /export and download/i })).toBeEnabled();
  });

  it("explains an empty scope rather than reporting a failure", async () => {
    stubFetch({
      "GET /api/events": [],
      "GET /api/audit/exports": [],
      "POST /api/audit/export": { __status: 409 },
    });
    render(ActivityView);

    await fireEvent.click(await screen.findByRole("button", { name: /^export$/i }));
    await fireEvent.click(screen.getByRole("button", { name: /export and download/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/nothing in scope to export/i);
  });
});
