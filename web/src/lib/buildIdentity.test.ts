import { describe, expect, it } from "vitest";
import { UNRELEASED, clientBuild, clientIsStale, describeBuild } from "./buildIdentity";

// GCR-16 — one build identity, said the same way everywhere it is read.

describe("describeBuild", () => {
  it("names the release and the commit it came from", () => {
    expect(describeBuild("1.2.3", "abc1234def5678")).toBe("1.2.3 (abc1234)");
    expect(describeBuild("1.2.3", null)).toBe("1.2.3");
  });

  it("says a tree that has never been released has not been", () => {
    // `0.0.0` is the placeholder, not a version. Printing it as one is how a
    // development checkout came to look like release zero.
    expect(describeBuild(UNRELEASED, null)).toBe("Unreleased build");
    expect(describeBuild(UNRELEASED, "abc1234def5678")).toBe("Unreleased build (abc1234)");
  });
});

describe("clientIsStale", () => {
  it("is true only when a released page and a released host disagree", () => {
    expect(clientIsStale("1.2.3", "1.2.2")).toBe(true);
    expect(clientIsStale("1.2.3", "1.2.3")).toBe(false);
  });

  it("never fires while either side is unreleased", () => {
    // The development case, and the only reason this takes a parameter: a test
    // bundle is never a released client, so the rule could not otherwise be
    // proved in either direction.
    expect(clientIsStale(UNRELEASED, "1.2.3")).toBe(false);
    expect(clientIsStale("1.2.3", UNRELEASED)).toBe(false);
    expect(clientIsStale(UNRELEASED, UNRELEASED)).toBe(false);
  });

  it("defaults to the build this bundle was stamped with", () => {
    expect(clientBuild).toBeTruthy();
    expect(clientIsStale("1.2.3")).toBe(clientIsStale("1.2.3", clientBuild));
  });
});
