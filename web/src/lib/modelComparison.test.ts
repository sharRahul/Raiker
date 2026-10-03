// UX-MODEL-04 — one comparable table, where an unknown fact says Unknown.
import { describe, expect, it } from "vitest";
import { modelProfile } from "./test-helpers";
import {
  UNKNOWN,
  comparisonRows,
  contextOf,
  costOf,
  declared,
  localityOf,
} from "./modelComparison";

const hosted = modelProfile({
  profile_id: "anthropic-hosted",
  provider: "anthropic",
  model: "claude-sonnet-5-5",
  local_only: false,
  endpoint_kind: "remote_hosted",
  billable: true,
  off_machine: true,
  connection_configured: true,
  configured: true,
  context_window_tokens: 200_000,
  supports_tool_calls: true,
  supports_vision: true,
  rate_input_per_mtok: "3",
  rate_output_per_mtok: "15",
  rate_currency: "USD",
  ready: true,
  readiness_state: "ready",
});
const local = modelProfile({
  profile_id: "ollama-local-openai-compatible",
  provider: "ollama",
  model: "qwen3:8b",
  local_only: true,
  endpoint_kind: "local_process",
  billable: false,
  configured: true,
  readiness_state: "runtime_stopped",
  ready: false,
});

describe("UX-MODEL-04 — the comparison projection", () => {
  it("states where each model runs before anything else", () => {
    expect(localityOf(local)).toBe("On this device");
    expect(localityOf(hosted)).toBe("Hosted service");
    expect(localityOf(modelProfile({ local_only: false, endpoint_kind: "private_network" }))).toBe(
      "Private server",
    );
    expect(localityOf(modelProfile({ local_only: false, endpoint_kind: "mystery" }))).toBe(UNKNOWN);
  });

  it("keeps a silence about a capability distinct from a declared no", () => {
    expect(declared(true)).toBe("Yes");
    expect(declared(false)).toBe("No");
    expect(declared(null)).toBe(UNKNOWN);
    expect(declared(undefined)).toBe(UNKNOWN);
  });

  it("never prints an unknown price as free", () => {
    expect(costOf(hosted)).toBe("$3.00 in · $15.00 out per 1M tokens");
    expect(costOf(local)).toBe("No API cost");
    expect(costOf(modelProfile({ ...hosted, rate_input_per_mtok: null, rate_output_per_mtok: null }))).toBe(
      UNKNOWN,
    );
    expect(costOf(modelProfile({ ...hosted, rate_input_per_mtok: "0.25", rate_output_per_mtok: "1.25" }))).toBe(
      "$0.25 in · $1.25 out per 1M tokens",
    );
  });

  it("says a context window only when a source states one", () => {
    expect(contextOf(hosted)).toBe("200k tokens");
    expect(contextOf(modelProfile({ context_window_tokens: 1_000_000 }))).toBe("1M tokens");
    expect(contextOf(local)).toBe(UNKNOWN);
  });

  it("lists what the owner could choose, ready first, and nothing they could not", () => {
    const placeholder = modelProfile({ profile_id: "lmstudio", model: "<model>" });
    // A managed slot with nothing deployed, and a hosted provider never connected.
    const emptySlot = modelProfile({ profile_id: "raiker-local-llama-cpp", model: "local-gguf", configured: false });
    const unconnected = modelProfile({
      ...hosted,
      profile_id: "openai-hosted",
      model: "gpt-5",
      connection_configured: false,
      off_machine: true,
      ready: false,
      readiness_state: "not_configured",
    });
    const rows = comparisonRows([local, placeholder, emptySlot, unconnected, hosted]);
    expect(rows.map((row) => row.profile.model)).toEqual(["claude-sonnet-5-5", "qwen3:8b"]);
    expect(rows[0]).toMatchObject({ availability: "Ready", tools: "Yes", vision: "Yes", leavesDevice: true });
    expect(rows[1]).toMatchObject({ tools: UNKNOWN, vision: UNKNOWN, leavesDevice: false });
    // Kept although its runtime is stopped: Availability is there to say so.
    expect(rows[1].availability).not.toBe("Ready");
  });
});
