// C6 — the one property these have to hold: a citation the ledger does not
// know about is not a citation. Everything a model can assert on its own — an
// invented marker, a marker copied out of a file it read — has to come back
// empty, because a chip that resolves to nothing is provenance theatre.
import { describe, expect, it } from "vitest";
import {
  citedSourceIds,
  renderableCitations,
  sentenceAround,
  sourcesForTurn,
  splitExcerpt,
} from "./citations";
import type { TurnSourceView } from "./apiTypes";

function source(over: Partial<TurnSourceView> = {}): TurnSourceView {
  return {
    source_id: "s1",
    ordinal: 1,
    kind: "web",
    title: "Example page",
    locator: "https://example.test/a",
    tool_name: "web_fetch",
    detail: "",
    attachment_id: "",
    turn_id: "turn_1",
    openable: true,
    ...over,
  };
}

describe("the sources belonging to a turn", () => {
  it("keeps only this turn's, in the order the turn used them", () => {
    const all = [
      source({ source_id: "s2", ordinal: 2 }),
      source({ source_id: "s1", ordinal: 1 }),
      source({ source_id: "s1", ordinal: 1, turn_id: "turn_2" }),
    ];
    expect(sourcesForTurn(all, "turn_1").map((s) => s.source_id)).toEqual(["s1", "s2"]);
  });

  it("has nothing to show for a turn that has not landed yet", () => {
    expect(sourcesForTurn([source()], null)).toEqual([]);
    expect(sourcesForTurn([source()], "")).toEqual([]);
  });
});

describe("reading citation markers out of an answer", () => {
  it("finds the markers the ledger recorded", () => {
    const cited = citedSourceIds("Renewal is 14 March [s1], per the thread [s2].", [
      source({ source_id: "s1" }),
      source({ source_id: "s2", ordinal: 2 }),
    ]);
    expect([...cited].sort()).toEqual(["s1", "s2"]);
  });

  it("refuses a marker the runtime never recorded", () => {
    // The model asserting `[s9]` must not produce a ninth source out of nothing.
    expect(citedSourceIds("Answer [s9].", [source({ source_id: "s1" })]).size).toBe(0);
  });

  it("refuses a marker that came out of the material rather than the model", () => {
    // A file that literally contains "[s4]" is quoted back verbatim; that is
    // text, not a claim about provenance.
    expect(citedSourceIds("The config reads `[s4]`.", [source({ source_id: "s1" })]).size).toBe(0);
  });

  it("has no citations for an answer that made none", () => {
    expect(citedSourceIds("Plain answer.", [source()]).size).toBe(0);
  });
});

describe("what the renderer may turn into a chip", () => {
  it("is exactly the ledger, never more", () => {
    const ids = renderableCitations([source({ source_id: "s1" }), source({ source_id: "s3" })]);
    expect(ids.has("s1")).toBe(true);
    expect(ids.has("s3")).toBe(true);
    expect(ids.has("s2")).toBe(false);
  });
});

describe("the sentence a marker terminates", () => {
  it("is the claim the citation is attached to, not the paragraph around it", () => {
    const answer =
      "I read the contract. The Meridian licence renews on 14 March 2029 [s1]. Legal owns it.";
    expect(sentenceAround(answer, "s1")).toBe(
      "The Meridian licence renews on 14 March 2029 [s1]",
    );
  });

  it("handles a marker in the first sentence and one with no full stop after it", () => {
    expect(sentenceAround("Renews in March [s1]", "s1")).toBe("Renews in March [s1]");
  });

  it("is empty when the answer never cited that source", () => {
    expect(sentenceAround("No citations here.", "s1")).toBe("");
  });

  it("is bounded, so a wall of text is never sent as a quote", () => {
    const answer = `${"word ".repeat(400)}[s1]`;
    expect(sentenceAround(answer, "s1").length).toBeLessThanOrEqual(600);
  });
});

describe("marking a run inside an excerpt", () => {
  it("slices the text rather than trusting markup from it", () => {
    expect(splitExcerpt("abcdef", 2, 3)).toEqual({ before: "ab", passage: "cde", after: "f" });
  });

  it("marks nothing when there is no located run", () => {
    expect(splitExcerpt("abcdef", -1, 0)).toEqual({ before: "abcdef", passage: "", after: "" });
  });
});

describe("a marker on the far side of the full stop", () => {
  it("still takes the sentence, not the empty run after it", () => {
    // Live models write both "… 2029 [s1]." and "… 2029.[s1]"; the second used
    // to yield "[s1]" and locate nothing.
    const answer = "I'll read the file.The Meridian licence renews on 14 March 2029.[s1]";
    expect(sentenceAround(answer, "s1")).toBe(
      "The Meridian licence renews on 14 March 2029.[s1]",
    );
  });
});
