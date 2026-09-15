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
import { describe, expect, it } from "vitest";
import AnswerParts from "./AnswerParts.svelte";
import type { ContentPart } from "../apiTypes";

const TABLE: ContentPart = {
  type: "table",
  data: {
    caption: "Spend by provider",
    columns: ["Provider", "Spend"],
    rows: [
      ["Ollama", "0.00"],
      ["Anthropic", "4.10"],
    ],
  },
};

const CHART: ContentPart = {
  type: "chart",
  data: {
    kind: "bar",
    caption: "Turns per day",
    y_label: "Turns",
    labels: ["Mon", "Tue"],
    series: [{ name: "Chat", values: [3, 5] }],
  },
};

describe("an answer with no declared parts", () => {
  it("renders through the markdown renderer, exactly as before", () => {
    render(AnswerParts, { text: "A **plain** answer.", parts: [] });
    expect(screen.getByText("plain").tagName).toBe("STRONG");
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("does the same when the runtime only split it into prose", () => {
    render(AnswerParts, {
      text: "Just prose.",
      parts: [{ type: "text", text: "Just prose." }],
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
      parts: [{ type: "refused", reason_code: "table_row_width_mismatch" }],
    });
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent(/did not guess at the missing cells/i);
    expect(note).toHaveTextContent("table_row_width_mismatch");
  });

  it("still says something useful for a reason code it does not know", () => {
    render(AnswerParts, { text: "", parts: [{ type: "refused", reason_code: "future_reason" }] });
    expect(screen.getByRole("note")).toHaveTextContent(/did not accept this part/i);
  });

  it("does not take the prose around it with it", () => {
    render(AnswerParts, {
      text: "",
      parts: [
        { type: "text", text: "Before." },
        { type: "refused", reason_code: "chart_not_json" },
        { type: "text", text: "After." },
      ],
    });
    expect(screen.getByText("Before.")).toBeInTheDocument();
    expect(screen.getByText("After.")).toBeInTheDocument();
  });
});
