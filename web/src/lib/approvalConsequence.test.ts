import { describe, expect, it } from "vitest";
import { consequenceFacts, destinationHost } from "./approvalConsequence";

/*
 * REM-APPROVAL — an approval with no diff answered the question "what would
 * this do?" with the request body. These are the rules that let the page answer
 * it in words instead without ever answering it wrongly.
 */
describe("what an approval says it would do", () => {
  it("lifts the facts the proposal actually names", () => {
    expect(
      consequenceFacts({ command: "rm -rf build", cwd: "/srv/app", unrelated: { a: 1 } }),
    ).toEqual([
      { label: "Command", value: "rm -rf build" },
      { label: "Working directory", value: "/srv/app" },
    ]);
  });

  it("invents nothing for a key that is not there", () => {
    // The whole safety property: an absent destination must produce no row, not
    // a plausible one. A reviewer reads these as statements about the request.
    expect(consequenceFacts({ prompt: "hello" })).toEqual([]);
    expect(consequenceFacts({})).toEqual([]);
    expect(consequenceFacts(null)).toEqual([]);
  });

  it("takes the first key of a group and does not repeat its label", () => {
    const facts = consequenceFacts({ path: "/a", file_path: "/b" });
    expect(facts).toEqual([{ label: "Path", value: "/a" }]);
  });

  it("flattens a list of scalars and leaves a list of objects to the payload", () => {
    expect(consequenceFacts({ argv: ["git", "push"] })).toEqual([
      { label: "Command", value: "git push" },
    ]);
    expect(consequenceFacts({ files: [{ path: "/a" }] })).toEqual([]);
  });

  it("truncates a value long enough to be a payload wearing a label", () => {
    const [fact] = consequenceFacts({ command: "x".repeat(400) });
    expect(fact.value.length).toBe(241);
    expect(fact.value.endsWith("…")).toBe(true);
  });

  it("names the host a request would reach, and nothing when it cannot", () => {
    expect(destinationHost({ url: "https://api.example.com/v1/send?k=1" })).toBe(
      "api.example.com",
    );
    // Not parseable is not a licence to guess: the string itself is already
    // shown as the destination.
    expect(destinationHost({ url: "not a url" })).toBe("");
    expect(destinationHost({})).toBe("");
  });
});
