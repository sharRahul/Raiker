import { expect, it } from "vitest";
import { rateLimitedLabel } from "./modelReadiness.svelte";

it("names when a rate-limited provider may be asked again, only while that is ahead (MD-5)", () => {
  const now = Date.parse("2026-11-08T10:00:00Z");
  const label = rateLimitedLabel("2026-11-08T10:30:00Z", now);
  expect(label).toMatch(/^Rate-limited until \d{1,2}:\d{2}/);
  expect(rateLimitedLabel("2026-11-08T09:59:00Z", now)).toBeNull();
  expect(rateLimitedLabel(null, now)).toBeNull();
  expect(rateLimitedLabel("not a time", now)).toBeNull();
});
