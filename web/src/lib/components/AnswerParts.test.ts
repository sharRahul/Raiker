/*
 * BUG-288 — a turn answers with a table Raiker knows is a table.
 *
 * The interface outcome the entry asks for has three halves, and each is here:
 * the table is a real `<table>` that sorts and announces its order; the chart
 * always carries the same numbers as a table, because a picture is unreadable
 * to a screen reader; and a declared block Raiker would not accept is *shown*
 * as refused rather than disappearing out of the answer.
 *
 * The fourth assertion is the one that keeps the change safe: an answer with no
 * declared parts renders exactly as it always did.
 */
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import AnswerParts from "./AnswerParts.svelte";
import type { ContentPart } from "../apiTypes";
import { part } from "../test-helpers";

const TABLE: ContentPart = part({
  type: "table",
  data: {
    caption: "Spend by provider",
    columns: ["Provider", "Spend"],
    rows: [
      ["Ollama", "0.00"],
      ["Anthropic", "4.10"],
    ],
  },
});

const CHART: ContentPart = part({
  type: "chart",
  data: {
    kind: "bar",
    caption: "Turns per day",
    y_label: "Turns",
    labels: ["Mon", "Tue"],
    series: [{ name: "Chat", values: [3, 5] }],
  },
});

describe("an answer with no declared parts", () => {
  it("renders through the markdown renderer, exactly as before", () => {
    render(AnswerParts, { text: "A **plain** answer.", parts: [] });
    expect(screen.getByText("plain").tagName).toBe("STRONG");
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("does the same when the runtime only split it into prose", () => {
    render(AnswerParts, {
      text: "Just prose.",
      parts: [part({ type: "text", text: "Just prose." })],
    });
    expect(screen.getByText("Just prose.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("a declared table", () => {
  it("is a real table with a caption, headers and its row count", () => {
    render(AnswerParts, { text: "", parts: [TABLE] });
    const table = screen.getByRole("table");
    expect(within(table).getByText(/Spend by provider/)).toBeInTheDocument();
    expect(within(table).getByText("2 rows")).toBeInTheDocument();
    expect(within(table).getAllByRole("columnheader")).toHaveLength(2);
  });

  it("sorts, and says which way it is sorted", async () => {
    render(AnswerParts, { text: "", parts: [TABLE] });
    const provider = screen.getByRole("columnheader", { name: /Provider/ });
    expect(provider).toHaveAttribute("aria-sort", "none");

    await fireEvent.click(within(provider).getByRole("button"));

    expect(provider).toHaveAttribute("aria-sort", "ascending");
    const firstCell = screen.getAllByRole("row")[1].querySelectorAll("td")[0];
    expect(firstCell?.textContent).toBe("Anthropic");
    expect(screen.getByText(/sorted by Provider, ascending/)).toBeInTheDocument();
  });

  it("gives the turn's own order back on the third press", async () => {
    // A table an owner has sorted three ways and cannot un-sort is a table they
    // have lost the answer in.
    render(AnswerParts, { text: "", parts: [TABLE] });
    const provider = screen.getByRole("columnheader", { name: /Provider/ });
    const button = within(provider).getByRole("button");

    await fireEvent.click(button);
    await fireEvent.click(button);
    expect(provider).toHaveAttribute("aria-sort", "descending");

    await fireEvent.click(button);
    expect(provider).toHaveAttribute("aria-sort", "none");
    const firstCell = screen.getAllByRole("row")[1].querySelectorAll("td")[0];
    expect(firstCell?.textContent).toBe("Ollama");
  });
});

describe("a declared chart", () => {
  it("draws, and carries the same numbers as a table underneath", () => {
    // Colour and geometry are not a channel everyone has. The SVG is decorative
    // and the table is the content.
    render(AnswerParts, { text: "", parts: [CHART] });
    expect(screen.getByText(/Turns per day/)).toBeInTheDocument();
    const table = screen.getByRole("table", { hidden: false });
    expect(within(table).getByText("Mon")).toBeInTheDocument();
    expect(within(table).getByText("5")).toBeInTheDocument();
  });
});

describe("a block Raiker would not accept", () => {
  it("is shown as refused, with a reason and its code", () => {
    // A part that vanishes is an answer that silently lost a section, and a
    // model that can make a section disappear by writing bad JSON is a worse
    // failure than a message the owner can see.
    render(AnswerParts, {
      text: "",
      parts: [part({ type: "refused", reason_code: "table_row_width_mismatch" })],
    });
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent(/did not guess at the missing cells/i);
    expect(note).toHaveTextContent("table_row_width_mismatch");
  });

  it("still says something useful for a reason code it does not know", () => {
    render(AnswerParts, { text: "", parts: [part({ type: "refused", reason_code: "future_reason" })] });
    expect(screen.getByRole("note")).toHaveTextContent(/did not accept this part/i);
  });

  it("does not take the prose around it with it", () => {
    render(AnswerParts, {
      text: "",
      parts: [
        part({ type: "text", text: "Before." }),
        part({ type: "refused", reason_code: "chart_not_json" }),
        part({ type: "text", text: "After." }),
      ],
    });
    expect(screen.getByText("Before.")).toBeInTheDocument();
    expect(screen.getByText("After.")).toBeInTheDocument();
  });
});

// ── Quiet UI 04: the visual answer vocabulary ──────────────────────────────

const FIGURES: ContentPart = part({
  type: "figures",
  data: {
    caption: "",
    items: [
      { label: "Longest battery", value: 18, unit: "h", of: "MacBook Air", estimate: false },
      { label: "Lightest", value: 1.09, unit: "kg", of: "X1 Carbon", estimate: true },
    ],
    source: "Spec pages, checked 23 Oct 2026",
    estimate: false,
  },
});

const COMPARE: ContentPart = part({
  type: "compare",
  data: {
    caption: "Laptops",
    items: ["Air", "XPS", "X1"],
    rows: [
      { label: "Battery", unit: "h", better: "higher", values: [18, 13, 15], best: [0] },
      { label: "Ports", unit: "", better: "", values: ["USB-C", "USB-C", "HDMI"], best: [] },
    ],
    source: "Spec pages",
    estimate: false,
  },
});

describe("key figures (QUI-A04)", () => {
  it("reads each label with its value, unit, owner and source", () => {
    render(AnswerParts, { text: "", parts: [FIGURES] });
    expect(screen.getByText("Longest battery").tagName).toBe("DT");
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("MacBook Air")).toBeInTheDocument();
    expect(screen.getByText("≈ estimate")).toBeInTheDocument();
    expect(screen.getByText(/Source: Spec pages/)).toBeInTheDocument();
  });
});

describe("a comparison (QUI-A05)", () => {
  it("marks the runtime's best in words, and only where the runtime said", () => {
    render(AnswerParts, { text: "", parts: [COMPARE] });
    const best = screen.getAllByText("Best");
    expect(best).toHaveLength(1);
    expect(best[0].closest("td")?.textContent).toContain("18");
    expect(screen.getByText("higher is better")).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: /Ports/ })).toBeInTheDocument();
  });
});

describe("measure, callout, pros and cons, steps (QUI-A06, A07)", () => {
  it("draws each with its meaning in words", () => {
    render(AnswerParts, {
      text: "",
      parts: [
        part({ type: "measure", data: { label: "Checks passed", value: 31, min: 0, max: 40, unit: "", source: "This run", estimate: false } }),
        part({ type: "callout", data: { tone: "warning", text: "Battery figures are manufacturer claims." } }),
        part({ type: "proscons", data: { caption: "", options: [{ name: "Air", pros: ["Battery"], cons: ["Ports"] }] } }),
        part({ type: "steps", data: { caption: "", steps: [{ label: "Order", when: "Mon", text: "" }, { label: "Set up", when: "", text: "" }] } }),
      ],
    });
    expect(screen.getByText("31 of 40")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toHaveAttribute("aria-label", "Checks passed: 31 of 40");
    expect(screen.getByText("Warning.")).toBeInTheDocument();
    expect(screen.getByText("Pros")).toBeInTheDocument();
    expect(screen.getByText("Cons")).toBeInTheDocument();
    expect(screen.getByText("Mon")).toHaveClass("when");
  });
});

describe("the new chart kinds (QUI-A01 to A03)", () => {
  it("keeps every number in a table for a screen reader", () => {
    render(AnswerParts, {
      text: "",
      parts: [
        part({
          type: "chart",
          data: { kind: "stacked", caption: "Spend mix", y_label: "", labels: ["Oct"], series: [{ name: "Chat", values: [3] }, { name: "Build", values: [1] }] },
        }),
      ],
    });
    const table = screen.getByRole("table");
    expect(within(table).getByText("75%")).toBeInTheDocument();
    expect(within(table).getByText("25%")).toBeInTheDocument();
  });
});

describe("the block toolbar", () => {
  it("switches a chart to its table and back", async () => {
    render(AnswerParts, { text: "", parts: [CHART] });
    await fireEvent.click(screen.getByRole("button", { name: "Table" }));
    expect(screen.getByRole("button", { name: "Table" })).toHaveAttribute("aria-pressed", "true");
    expect(document.querySelector("figure.data-chart svg")).toBeNull();
    expect(screen.getByRole("table")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Chart" }));
    expect(document.querySelector("figure.data-chart svg")).not.toBeNull();
  });

  it("shows any block as text, in the runtime's words", async () => {
    render(AnswerParts, { text: "", parts: [COMPARE] });
    await fireEvent.click(screen.getByRole("button", { name: "Show as text" }));
    expect(screen.getByText(/Battery: Air 18 h \(best\); XPS 13 h; X1 15 h/)).toBeInTheDocument();
    expect(screen.queryByText("higher is better")).toBeNull();
  });

  it("offers CSV only for blocks that are grids", () => {
    render(AnswerParts, {
      text: "",
      parts: [COMPARE, part({ type: "callout", data: { tone: "verdict", text: "Pick the Air." } })],
    });
    expect(screen.getAllByRole("button", { name: "CSV" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Show as text" })).toHaveLength(2);
  });
});

describe("more than three blocks", () => {
  it("offers a document, and only when the surface can make one", async () => {
    const blocks = [FIGURES, COMPARE, TABLE, CHART];
    const { unmount } = render(AnswerParts, { text: "", parts: blocks });
    expect(screen.queryByRole("button", { name: "Create document" })).toBeNull();
    unmount();
    let asked = 0;
    render(AnswerParts, { text: "", parts: blocks, ondocument: () => (asked += 1) });
    expect(screen.getByText(/This answer has 4 blocks/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Create document" }));
    expect(asked).toBe(1);
  });

  it("does not offer one for three", () => {
    render(AnswerParts, { text: "", parts: [FIGURES, COMPARE, TABLE], ondocument: () => {} });
    expect(screen.queryByRole("button", { name: "Create document" })).toBeNull();
  });
});

describe("QUI-F15 Pin in the block toolbar", () => {
  const CALLOUT: ContentPart = part({ type: "callout", data: { tone: "verdict", text: "Ship it." } });

  it("offers Pin only where the surface can pin, and says where it went", async () => {
    const onpin = vi.fn(async () => "Pinned to Quarterly");
    render(AnswerParts, { text: "", parts: [CALLOUT], onpin, pinLabel: "Pin to Quarterly" });
    const pin = screen.getByRole("button", { name: "Pin to Quarterly" });
    expect(pin).toHaveAttribute("aria-pressed", "false");
    await fireEvent.click(pin);
    expect(onpin).toHaveBeenCalledWith(0);
    expect(await screen.findByText("Pinned to Quarterly")).toBeInTheDocument();
  });

  it("reads Pinned for a block already pinned, and has no Pin without a handler", () => {
    const { unmount } = render(AnswerParts, { text: "", parts: [CALLOUT], onpin: async () => "", pinned: new Set([0]) });
    expect(screen.getByRole("button", { name: "Unpin" })).toHaveAttribute("aria-pressed", "true");
    unmount();
    render(AnswerParts, { text: "", parts: [CALLOUT] });
    expect(screen.queryByRole("button", { name: /Pin/ })).not.toBeInTheDocument();
  });

  it("does not offer Pin while the answer is still streaming", () => {
    render(AnswerParts, { text: "", parts: [CALLOUT], onpin: async () => "", streaming: true });
    expect(screen.queryByRole("button", { name: /Pin/ })).not.toBeInTheDocument();
  });
});
