// The collector card. Two things it must never do: print a reason code at the
// owner, and let them believe events are flowing when nothing has run.
//
// The first only became visible when destinations gained a cadence (FIXED-386).
// While delivery happened solely on a button press, a failed run was read by
// somebody who had just pressed it and was watching; an unattended failure on a
// timer is met later, on a page nobody was looking at, and
// `telemetry_delivery_failed:fetch_failed:URLError` is not an answer.
import { render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TelemetryExport from "./TelemetryExport.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

function destination(overrides: Record<string, unknown> = {}) {
  return {
    destination_id: "otlp_1",
    name: "Local collector",
    endpoint_url: "http://127.0.0.1:4318",
    header_ref: null,
    include_content: false,
    enabled: true,
    cursor_timestamp: null,
    cursor_event_id: null,
    last_status: "ok",
    last_attempt_at: "2026-09-04T00:00:00Z",
    exported_count: 12,
    created_at: "2026-09-04T00:00:00Z",
    delivery_cadence: "off",
    next_delivery_at: null,
    ...overrides,
  };
}

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/telemetry/destinations": [destination()],
    "GET /api/capability-gates": [
      { capability: "telemetry_export", state: "enabled_runtime", enforced_enabled: true },
    ],
    ...overrides,
  };
}

describe("TelemetryExport", () => {
  it("says what a failed delivery means rather than printing its code", async () => {
    stubFetch(
      routes({
        "GET /api/telemetry/destinations": [
          destination({ last_status: "telemetry_delivery_failed:fetch_failed:URLError" }),
        ],
      }),
    );
    render(TelemetryExport);

    expect(
      await screen.findByText(/Last run could not reach the collector/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/fetch_failed:URLError/)).toBeNull();
  });

  it("keeps the code reachable for correlating against the log", async () => {
    // A reason code is the audit vocabulary and must not vanish — it moves to
    // the hover, where it does not read at somebody who wanted a sentence.
    const status = "telemetry_delivery_failed:fetch_failed:URLError";
    stubFetch(
      routes({
        "GET /api/telemetry/destinations": [destination({ last_status: status })],
      }),
    );
    render(TelemetryExport);
    const line = await screen.findByText(/Last run could not reach the collector/i);
    expect(line).toHaveAttribute("title", status);
  });

  it.each([
    ["telemetry_credential_missing", /credential variable is unset/i],
    ["telemetry_rejected_503", /refused by the collector \(503\)/i],
    ["telemetry_destination_disabled", /destination off/i],
    ["something_nobody_mapped", /did not complete/i],
  ])("reads %s as a sentence", async (status, expected) => {
    stubFetch(
      routes({
        "GET /api/telemetry/destinations": [destination({ last_status: status })],
      }),
    );
    render(TelemetryExport);
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });

  it("says a destination has never run rather than leaving the line blank", async () => {
    stubFetch(
      routes({
        "GET /api/telemetry/destinations": [
          destination({ last_status: null, last_attempt_at: null }),
        ],
      }),
    );
    render(TelemetryExport);
    expect(await screen.findByText("Never run")).toBeInTheDocument();
  });

  // FIXED-386's interface outcome, guarded here rather than only in the live
  // spec: a card must never let an owner believe events are flowing.
  it("states the cadence it is delivered on, and claims no next run without one", async () => {
    stubFetch(routes());
    render(TelemetryExport);
    const cadence = await screen.findByLabelText(/Delivery cadence for Local collector/i);
    expect(cadence).toHaveValue("off");
    expect(screen.queryByText(/^Next /)).toBeNull();
  });

  it("names the next run once a cadence is set", async () => {
    stubFetch({
      "GET /api/telemetry/destinations": [
        destination({
          delivery_cadence: "hourly",
          next_delivery_at: new Date(Date.now() + 45 * 60_000).toISOString(),
        }),
      ],
      "GET /api/capability-gates": [
        { capability: "telemetry_export", state: "enabled_runtime", enforced_enabled: true },
      ],
    });
    render(TelemetryExport);
    expect(await screen.findByText(/^Next in \d+m$/)).toBeInTheDocument();
  });
});
