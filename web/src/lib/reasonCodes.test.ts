import { describe, expect, it } from "vitest";
import { explainReasonCode } from "./reasonCodes";

describe("explainReasonCode", () => {
  it("resolves an exact code to plain English with remediation", () => {
    const r = explainReasonCode("disabled_by_capability_gate");
    expect(r?.plain).toMatch(/turned off/i);
    expect(r?.remediation).toMatch(/Capabilities page/);
  });

  it("resolves prefixed codes with a variable suffix", () => {
    const r = explainReasonCode("domain_scope_denied:email");
    expect(r?.plain).toMatch(/domain isn't in your granted scopes/i);
    expect(r?.code).toBe("domain_scope_denied:email");
  });

  it("never hides an unknown code — surfaces it raw", () => {
    const r = explainReasonCode("some_brand_new_code");
    expect(r?.code).toBe("some_brand_new_code");
    expect(r?.plain).toContain("some_brand_new_code");
  });

  it("returns null for empty input", () => {
    expect(explainReasonCode(null)).toBeNull();
    expect(explainReasonCode(undefined)).toBeNull();
  });
});
