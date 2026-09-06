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
    expect(status).toHaveTextContent(/reading runtime health/i);
  });

  it("shows a route-level error state when diagnostics cannot load", async () => {
    stubFetch({});
    render(DiagnosticsView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't read runtime health/i);
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

  // MEM-09 — the integrity report existed and nothing displayed it, so a
  // divergence between a table and its index was invisible: search simply
  // stopped finding things. It is a page now, with its repair beside it.
  const CLEAN_INTEGRITY = {
    ok: true,
    clean: true,
    active_memory_count: 4,
    fts_count: 4,
    stale_fts_count: 0,
    missing_markdown_count: 0,
    stale_projection_count: 0,
    stale_graph_edge_count: 0,
    checksum_mismatch_count: 0,
    orphaned_markdown_count: 0,
    failed_purge_location_count: 0,
    project_path_inconsistency_count: 0,
    text_search_engine: "fts5",
    index_engine_mismatch_count: 0,
    conversation_index_count: 12,
    stale_conversation_index_count: 0,
  };

  it("reports a clean memory store without listing ten zeroes", async () => {
    stubFetch({
      "GET /api/diagnostics": DIAGNOSTICS,
      "GET /api/security/health": [],
      "GET /api/memory/integrity": CLEAN_INTEGRITY,
    });
    render(DiagnosticsView);

    expect(await screen.findByText("Memory integrity")).toBeInTheDocument();
    expect(await screen.findByText("clean")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /rebuild conversation index/i })).toBeNull();
  });

  it("names conversation-index drift and offers the rebuild that repairs it", async () => {
    const fetchMock = stubFetch({
      "GET /api/diagnostics": DIAGNOSTICS,
      "GET /api/security/health": [],
      "GET /api/memory/integrity": {
        ...CLEAN_INTEGRITY,
        clean: false,
        conversation_index_count: 3,
        stale_conversation_index_count: 9,
      },
      "POST /api/memory/conversation-index/rebuild": { ok: true, indexed_rows: 12 },
    });
    render(DiagnosticsView);

    expect(await screen.findByText("Conversation search index")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();

    const rebuild = screen.getByRole("button", { name: /rebuild conversation index/i });
    rebuild.click();

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("/api/memory/conversation-index/rebuild"),
        ),
      ).toBe(true),
    );
    expect(await screen.findByText(/12 rows indexed/i)).toBeInTheDocument();
  });
  it("names a background pass that keeps failing, and how long since it worked", async () => {
    // GCR-38 — the host tick's four passes were each `with suppress(Exception)`.
    // A pass could throw every fifteen seconds for days and this page reported a
    // healthy runtime, because nothing counted the failure and no surface showed
    // it. The streak and the exception class are the two facts that separate a
    // blip from a systemic fault.
    stubFetch({
      "GET /api/diagnostics": {
        ...DIAGNOSTICS,
        background_workers: [
          {
            pass_name: "telemetry_delivery",
            last_success_at: null,
            last_failure_at: "2026-07-18T01:00:00Z",
            last_error_class: "ProviderConnectionError",
            consecutive_failures: 240,
            total_failures: 240,
            healthy: false,
            updated_at: "2026-07-18T01:00:00Z",
          },
          {
            pass_name: "scheduled_tasks",
            last_success_at: "2026-07-18T01:00:00Z",
            last_failure_at: null,
            last_error_class: null,
            consecutive_failures: 0,
            total_failures: 0,
            healthy: true,
            updated_at: "2026-07-18T01:00:00Z",
          },
        ],
      },
      "GET /api/security/health": [],
    });
    render(DiagnosticsView);

    expect(await screen.findByText("Background passes")).toBeInTheDocument();
    expect(screen.getByText("240 in a row")).toBeInTheDocument();
    expect(screen.getByText("ProviderConnectionError")).toBeInTheDocument();
    expect(screen.getByText(/never succeeded/i)).toBeInTheDocument();
    expect(screen.getByText(/telemetry delivery/i)).toBeInTheDocument();
  });

  it("says plainly when no background pass has run yet", async () => {
    stubFetch({ "GET /api/diagnostics": DIAGNOSTICS, "GET /api/security/health": [] });
    render(DiagnosticsView);
    expect(await screen.findByText("Background passes")).toBeInTheDocument();
    expect(screen.getByText(/no pass has run yet on this host/i)).toBeInTheDocument();
  });
});
