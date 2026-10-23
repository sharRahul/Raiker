/*
 * Quiet UI 04 — every block's text and grid forms, which the toolbar's Show as
 * text, Copy and CSV all use. The wording matches the runtime's `as_text`.
 */
import { describe, expect, it } from "vitest";
import { blockCount, blockFilename, blockGrid, blockText, figure, toCsv } from "./answerBlocks";
import { part } from "./test-helpers";

describe("figure", () => {
  it("writes numbers the way a person does", () => {
    expect(figure(18, "h")).toBe("18 h");
    expect(figure(1.09)).toBe("1.09");
    expect(figure(0.1 + 0.2)).toBe("0.3");
  });
});

describe("blockText", () => {
  it("says a measure with its scale and an estimate in words", () => {
    const measure = part({ type: "measure", data: { label: "Rating", value: 4.2, min: 0, max: 5, unit: "", estimate: true } });
    expect(blockText(measure)).toBe("Rating: 4.2 of 5 (≈ estimate)");
  });

  it("numbers steps and leads a callout with its tone", () => {
    expect(blockText(part({ type: "callout", data: { tone: "action", text: "Buy it." } }))).toBe("Next step: Buy it.");
    expect(
      blockText(part({ type: "steps", data: { caption: "", steps: [{ label: "Order", when: "Mon", text: "online" }] } })),
    ).toBe("1. Order (Mon) — online");
  });
});

describe("blockGrid and CSV", () => {
  it("quotes a cell with a comma and keeps the best mark", () => {
    const compare = part({
      type: "compare",
      data: { items: ["A", "B"], rows: [{ label: "Ports", unit: "", better: "", values: ["USB-C, HDMI", "USB-C"], best: [] }, { label: "Price", unit: "£", better: "lower", values: [999, 1399], best: [0] }] },
    });
    expect(toCsv(blockGrid(compare)!)).toBe(',A,B\r\nPorts,"USB-C, HDMI",USB-C\r\nPrice (£),999 (best),1399\r\n');
  });

  it("has no grid for a prose block", () => {
    expect(blockGrid(part({ type: "callout", data: { tone: "verdict", text: "x" } }))).toBeNull();
  });
});

describe("blockCount and filenames", () => {
  it("counts drawn blocks, not prose or refusals", () => {
    expect(blockCount([part({ type: "text", text: "x" }), part({ type: "refused" }), part({ type: "figures", data: {} })])).toBe(1);
  });

  it("names a download from its caption", () => {
    expect(blockFilename(part({ type: "chart", data: { caption: "Spend / day" } }), "csv")).toBe("spend-day.csv");
    expect(blockFilename(part({ type: "chart", data: {} }), "png")).toBe("raiker-chart.png");
  });
});

describe("currency units", () => {
  it("go before the number, the way a price is read", () => {
    expect(figure(999, "£")).toBe("£999");
    expect(figure(-5, "$")).toBe("-$5");
    expect(figure(18, "h")).toBe("18 h");
  });
});
