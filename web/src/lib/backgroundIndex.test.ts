import { describe, expect, it } from "vitest";
import { backgroundIndexCopy } from "./backgroundIndex";

const base = { at: "2026-11-14T10:00:00Z", model: "nomic-embed-text", indexed: 0, reason_code: null, disabled: false };
const now = new Date("2026-11-14T10:05:00Z");

describe("backgroundIndexCopy", () => {
  it("says nothing before the first pass", () => {
    expect(backgroundIndexCopy(null)).toBeNull();
  });
  it("names what was indexed and when", () => {
    const copy = backgroundIndexCopy({ ...base, state: "indexed", indexed: 3 }, now);
    expect(copy?.tone).toBe("ok");
    expect(copy?.text).toContain("Indexed 3 new items with nomic-embed-text");
  });
  it("points a permission wait at Permissions", () => {
    const copy = backgroundIndexCopy({ ...base, state: "waiting_for_permission" }, now);
    expect(copy?.tone).toBe("attention");
    expect(copy?.action?.href).toBe("#/capabilities");
  });
  it("says when it is switched off", () => {
    expect(backgroundIndexCopy({ ...base, state: "disabled", disabled: true })?.text).toContain("off");
  });
  it("keeps an unknown failure's reason", () => {
    expect(backgroundIndexCopy({ ...base, state: "failed", reason_code: "embedding_timeout" }, now)?.text).toContain("embedding_timeout");
  });
});
