import { describe, expect, it, vi, afterEach } from "vitest";
import {
  DEVICE_TIMEZONE_KEY,
  TIMEZONE_KEY,
  localTimeIn,
  resolvedTimezone,
  timezoneOptions,
  timezoneProposal,
  timezoneSourceLabel,
} from "./environment";

/**
 * The page's half of "one owner-level timezone source of truth".
 *
 * The failure these guard is the small, plausible one: a browser that helpfully
 * writes its own zone over the owner's choice. It is helpful exactly until
 * somebody sets Europe/London, opens Raiker from a hotel in Denver, and every
 * recurring task moves by seven hours to fix a problem they did not have.
 */
afterEach(() => vi.unstubAllGlobals());

describe("resolvedTimezone", () => {
  it("prefers the owner's explicit choice over a device proposal", () => {
    expect(
      resolvedTimezone({
        [TIMEZONE_KEY]: "Europe/London",
        [DEVICE_TIMEZONE_KEY]: "America/Denver",
      }),
    ).toEqual({ zone: "Europe/London", source: "owner_setting" });
  });

  it("uses a device value when no explicit choice exists", () => {
    expect(resolvedTimezone({ [DEVICE_TIMEZONE_KEY]: "Asia/Kolkata" })).toEqual({
      zone: "Asia/Kolkata",
      source: "device_preference",
    });
  });

  it("falls back to UTC and says that is what happened", () => {
    // Not "UTC because we know you are in UTC" — UTC because nobody has said.
    expect(resolvedTimezone({})).toEqual({ zone: "UTC", source: "fallback" });
    expect(timezoneSourceLabel("fallback")).toContain("falls back to UTC");
  });

  it("treats a blank stored value as unset rather than as a zone", () => {
    expect(resolvedTimezone({ [TIMEZONE_KEY]: "   " }).source).toBe("fallback");
  });
});

describe("timezoneProposal", () => {
  it("offers the device zone when it differs from what is in force", () => {
    vi.stubGlobal("Intl", {
      ...Intl,
      DateTimeFormat: Object.assign(
        () => ({ resolvedOptions: () => ({ timeZone: "America/Denver" }) }),
        { supportedValuesOf: undefined },
      ),
    });
    expect(timezoneProposal({ [TIMEZONE_KEY]: "Europe/London" })).toBe("America/Denver");
  });

  it("offers nothing when the device agrees with the owner", () => {
    vi.stubGlobal("Intl", {
      ...Intl,
      DateTimeFormat: () => ({ resolvedOptions: () => ({ timeZone: "Europe/London" }) }),
    });
    expect(timezoneProposal({ [TIMEZONE_KEY]: "Europe/London" })).toBeNull();
  });

  it("offers nothing when the browser will not say", () => {
    vi.stubGlobal("Intl", {
      ...Intl,
      DateTimeFormat: () => ({ resolvedOptions: () => ({ timeZone: "" }) }),
    });
    expect(timezoneProposal({})).toBeNull();
  });
});

describe("timezoneOptions", () => {
  it("returns a usable list even when the engine cannot enumerate zones", () => {
    vi.stubGlobal("Intl", { ...Intl, supportedValuesOf: undefined });
    const zones = timezoneOptions();
    expect(zones).toContain("UTC");
    expect(zones).toContain("Europe/London");
  });

  it("always includes UTC, which is the documented final fallback", () => {
    expect(timezoneOptions()).toContain("UTC");
  });
});

describe("localTimeIn", () => {
  it("renders the owner's clock in the zone in force", () => {
    const at = new Date("2026-09-07T09:06:21Z");
    expect(localTimeIn("Europe/London", at)).toContain("10:06");
    expect(localTimeIn("Europe/London", at)).toContain("Monday");
  });

  it("shows the same instant differently in a different zone", () => {
    // The sample line exists so the owner can *see* the setting take effect.
    const at = new Date("2026-09-07T09:06:21Z");
    expect(localTimeIn("Asia/Kolkata", at)).toContain("14:36");
  });

  it("returns empty rather than a wrong time for a zone it cannot load", () => {
    expect(localTimeIn("Europe/Lundun")).toBe("");
  });
});
