import { describe, expect, it } from "vitest";
import { ISSUE_FORMS, REPOSITORY_URL, detectOs, issueUrl } from "./betaFeedback";

describe("beta feedback links", () => {
  const env = { host: "0.9.0-beta.1 (abc1234)", client: "0.9.0-beta.1 (abc1234)", os: "Linux" };

  it("opens the repository's bug form prefilled with build and system", () => {
    const url = new URL(issueUrl("bug", env));
    expect(url.origin + url.pathname).toBe(`${REPOSITORY_URL}/issues/new`);
    expect(url.searchParams.get("template")).toBe(ISSUE_FORMS.bug);
    expect(url.searchParams.get("labels")).toBe("beta,bug");
    expect(url.searchParams.get("version")).toBe("0.9.0-beta.1 (abc1234)");
    expect(url.searchParams.get("os")).toBe("Linux");
  });

  it("names a stale page build beside the host build", () => {
    const url = new URL(issueUrl("feedback", { ...env, client: "0.9.0-beta.0" }));
    expect(url.searchParams.get("template")).toBe("beta-feedback.yml");
    expect(url.searchParams.get("version")).toBe("0.9.0-beta.1 (abc1234) (page 0.9.0-beta.0)");
  });

  it("bounds every field and only ever links to GitHub", () => {
    const url = issueUrl("bug", { ...env, host: "x".repeat(5000) }, { title: "t".repeat(5000), area: "Voice" });
    expect(url.startsWith("https://github.com/")).toBe(true);
    expect(url.length).toBeLessThan(1200);
    expect(new URL(url).searchParams.get("area")).toBe("Voice");
  });

  it("reports a coarse operating system, not the user agent", () => {
    expect(detectOs({ platform: "Win32", userAgent: "Mozilla/5.0 (Windows NT 10.0)" })).toBe("Windows");
    expect(detectOs({ platform: "MacIntel", userAgent: "" })).toBe("macOS");
    expect(detectOs({ platform: "Linux x86_64", userAgent: "" })).toBe("Linux");
    expect(detectOs({})).toBe("Unknown");
  });
});
