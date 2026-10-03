// UX-DESIGN-03 — research becomes a named, sourced reference, sent only on consent.
import { describe, expect, it } from "vitest";
import {
  MAX_REFERENCE_TEXT_CHARS,
  plainText,
  referenceFromResearch,
  referenceSources,
  referencesToSend,
} from "./designReferences";
import type { TurnSourceView } from "./apiTypes";

function source(id: string, locator: string): TurnSourceView {
  return {
    source_id: id,
    ordinal: 1,
    kind: "web",
    title: id,
    locator,
    tool_name: "web_read",
    detail: "",
    attachment_id: "",
    turn_id: "turn_1",
    openable: true,
  };
}

describe("a research answer as a reference", () => {
  it("reads markdown as plain text", () => {
    expect(plainText("## Colours\n- **white** walls [1]\n- [red](https://x.example) lantern")).toBe(
      "Colours white walls red lantern",
    );
  });

  it("keeps only openable web pages, cited first, deduplicated and bounded", () => {
    const sources = [
      source("a", "https://a.example/one"),
      source("b", "file:///etc/hosts"),
      source("c", "https://c.example/three"),
      source("d", "https://a.example/one"),
    ];
    expect(referenceSources(sources, ["c"])).toEqual(["https://c.example/three", "https://a.example/one"]);
    const many = Array.from({ length: 9 }, (_, i) => source(`s${i}`, `https://e.example/${i}`));
    expect(referenceSources(many)).toHaveLength(5);
  });

  it("is named for the question, bounded, and not consented until the owner ticks it", () => {
    const reference = referenceFromResearch("Lighthouse colours", "word ".repeat(400), [], [], "k1");
    expect(reference).not.toBeNull();
    expect(reference!.name).toBe("Lighthouse colours");
    expect(reference!.text.length).toBeLessThanOrEqual(MAX_REFERENCE_TEXT_CHARS);
    expect(reference!.text.endsWith("…")).toBe(true);
    expect(reference!.consented).toBe(false);
  });

  it("makes nothing from an empty answer", () => {
    expect(referenceFromResearch("q", "  **  ", [])).toBeNull();
  });

  it("sends only what was ticked, without page-only fields", () => {
    const one = referenceFromResearch("one", "first", [], [], "k1")!;
    const two = { ...referenceFromResearch("two", "second", [source("a", "https://a.example")], [], "k2")!, consented: true };
    expect(referencesToSend([one, two])).toEqual([
      { name: "two", text: "second", sources: ["https://a.example"] },
    ]);
  });
});
