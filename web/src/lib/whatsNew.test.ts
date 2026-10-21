import { afterEach, describe, expect, it } from "vitest";
import { SEEN_VERSION_KEY, markVersionSeen, versionToAnnounce } from "./whatsNew";

afterEach(() => localStorage.removeItem(SEEN_VERSION_KEY));

describe("versionToAnnounce", () => {
  it("remembers the first version silently, so a fresh install never says Updated", () => {
    expect(versionToAnnounce("1.3.0")).toBeNull();
    expect(localStorage.getItem(SEEN_VERSION_KEY)).toBe("1.3.0");
    expect(versionToAnnounce("1.3.0")).toBeNull();
  });

  it("announces a changed version until it is marked seen", () => {
    markVersionSeen("1.3.0");
    expect(versionToAnnounce("1.4.0")).toBe("1.4.0");
    expect(versionToAnnounce("1.4.0")).toBe("1.4.0");
    markVersionSeen("1.4.0");
    expect(versionToAnnounce("1.4.0")).toBeNull();
  });

  it("never announces an unknown version", () => {
    markVersionSeen("1.3.0");
    expect(versionToAnnounce("")).toBeNull();
    expect(versionToAnnounce(undefined)).toBeNull();
  });
});
