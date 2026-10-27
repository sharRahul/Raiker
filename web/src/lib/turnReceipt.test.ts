import { describe, expect, it } from "vitest";

import type { TurnReceipt } from "./generated/apiContract";
import { receiptLine, receiptRows, taskReceiptLine } from "./turnReceipt";

const base: TurnReceipt = {
  turn_id: "t1",
  model: "claude-haiku-4-5-20251001",
  provider: "anthropic",
  local: false,
  cost_usd: 0.0143,
  cost_basis: "priced",
  reads: { file: 2 },
  changes: [],
  left_computer: [],
};

describe("QUI-F16 task receipt", () => {
  it("says model, cost, reads and that nothing else left", () => {
    expect(receiptLine(base)).toBe("Haiku 4.5 · ≈ $0.0143 · 2 files read · nothing else left this computer");
  });

  it("names a change with its approval time and the services reached", () => {
    const line = receiptLine({
      ...base,
      reads: {},
      changes: [{ label: "Send email", approved_at: "2026-10-24T10:41:00Z" }],
      left_computer: ["Gmail"],
    });
    expect(line).toMatch(/^Haiku 4\.5 · ≈ \$0\.0143 · Send email \(approved \d{1,2}:\d{2}( [AP]M)?\) · also reached Gmail$/i);
  });

  it("never calls an unpriced billable model free, and a local one leaves nothing", () => {
    expect(receiptLine({ ...base, cost_usd: null, cost_basis: "unknown" })).toContain("cost not known");
    const local = receiptLine({ ...base, model: "llama3", provider: "ollama", local: true, cost_usd: null, cost_basis: "free" });
    expect(local).toContain("no charge");
    expect(local).toContain("nothing left this computer");
  });

  it("says in the expanded rows that the conversation went to the provider", () => {
    const rows = receiptRows(base);
    expect(rows.find((row) => row.label === "Left this computer")?.value).toBe("The conversation, to Anthropic");
    expect(rows.find((row) => row.label === "Changed or sent")?.value).toBe("Nothing");
  });
});

describe("QUI-F16 a task's receipt", () => {
  it("says how many turns it adds up and names every model", () => {
    const line = taskReceiptLine({
      task_id: "task_1",
      turns: 3,
      models: ["claude-haiku-4-5", "claude-sonnet-4-5"],
      local: false,
      cost_usd: 0.03,
      cost_basis: "priced",
      reads: { "web page": 3 },
      changes: [],
      left_computer: ["the web"],
    });
    expect(line.startsWith("Across 3 turns · ")).toBe(true);
    expect(line).toContain(" + ");
    expect(line).toContain("3 web pages read");
  });

  it("says plainly when nothing has run", () => {
    expect(
      taskReceiptLine({ task_id: "t", turns: 0, models: [], local: false, cost_usd: null, cost_basis: "free", reads: {}, changes: [], left_computer: [] }),
    ).toBe("Nothing has run yet.");
  });
});
