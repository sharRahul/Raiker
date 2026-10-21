import { describe, expect, it } from "vitest";
import { conversationMatches, matchLabel } from "./conversationSearch";

const TURNS = [
  { prompt: "Draft a reply to Anna", answer: "Here is a reply." },
  { prompt: "Plan my week", answer: "Monday: call Anna." },
  { prompt: "Summarise the report", answer: "It covers Q3." },
];

describe("conversationMatches", () => {
  it("finds turns whose prompt or answer holds every word, ignoring case", () => {
    expect(conversationMatches(TURNS, "anna")).toEqual([0, 1]);
    expect(conversationMatches(TURNS, "REPLY anna")).toEqual([0]);
    expect(conversationMatches(TURNS, "q3")).toEqual([2]);
  });

  it("finds nothing for an empty query or a missing word", () => {
    expect(conversationMatches(TURNS, "   ")).toEqual([]);
    expect(conversationMatches(TURNS, "anna budget")).toEqual([]);
  });
});

describe("matchLabel", () => {
  it("counts from one and says when nothing matched", () => {
    expect(matchLabel(1, 5)).toBe("2 of 5");
    expect(matchLabel(0, 0)).toBe("No matches");
  });
});
