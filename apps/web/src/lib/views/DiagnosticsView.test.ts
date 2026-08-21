// Diagnostics is operational evidence: stored runtime state plus the redacted
// self-monitoring transitions — no probing, no fabricated health.
import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import DiagnosticsView from "./DiagnosticsView.svelte";
import { DIAGNOSTICS, stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DiagnosticsView", () => {
  it("shows a route-level loading state while diagnostics are fetched", async () => {
    stubFetchPending();
    render(DiagnosticsView);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/loading diagnostics/i);
  });

  it("shows a route-level error state when diagnostics cannot load", async () => {
    stubFetch({});
    render(DiagnosticsView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load diagnostics/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("renders redacted self-monitoring transitions alongside runtime state", async () => {
    stubFetch({
      "GET /api/diagnostics": DIAGNOSTICS,
      "GET /api/security/health": [
        {
          source: "vault_health",
          subject_id: "vault",
          code: "vault_unreachable",
          state: "alerting",
          updated_at: "2026-07-18T00:00:00Z",
        },
        {
          source: "session_store_health",
          subject_id: "sessions",
          code: "session_store_unreachable",
          state: "recovered",
          updated_at: "2026-07-18T01:00:00Z",
        },
      ],
    });
    render(DiagnosticsView);

    await waitFor(() => expect(screen.getByText("Self-monitoring")).toBeInTheDocument());
    expect(screen.getByText("alerting")).toBeInTheDocument();
    expect(screen.getByText("recovered")).toBeInTheDocument();
    expect(screen.getByText(/vault unreachable/i)).toBeInTheDocument();
  });

  it("says plainly when self-monitoring has recorded no transitions", async () => {
    stubFetch({ "GET /api/diagnostics": DIAGNOSTICS, "GET /api/security/health": [] });
    render(DiagnosticsView);
    await waitFor(() => expect(screen.getByText("Self-monitoring")).toBeInTheDocument());
    expect(screen.getByText(/no health transitions recorded/i)).toBeInTheDocument();
  });

  it("shows checkpoint capture failure, non-reversibility, and remediation", async () => {
    stubFetch({
      "GET /api/diagnostics": {
        ...DIAGNOSTICS,
        readiness: {
          ...DIAGNOSTICS.readiness,
          checkpoint_capture: {
            ok: false,
            stage: "snapshot",
            reason_code: "checkpoint_snapshot_os_error",
            display_path: null,
            checked_at: "2026-08-21T00:00:00Z",
            remediation: "Check workspace permissions and enable Windows long-path support.",
          },
        },
      },
      "GET /api/security/health": [],
    });
    render(DiagnosticsView);

    expect(await screen.findByText(/checkpoint capture/i)).toBeInTheDocument();
    expect(screen.getByText(/writes may not be reversible/i)).toBeInTheDocument();
    expect(screen.getByText(/enable Windows long-path support/i)).toBeInTheDocument();
  });
});
