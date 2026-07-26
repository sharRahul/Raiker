import { describe, expect, it } from "vitest";
import {
  BUILD_MODES,
  BUILD_WRITE_CAPABILITIES,
  buildMode,
  DEFAULT_BUILD_MODE,
  modeFromDecisionModes,
  nextBuildMode,
  repoPreamble,
} from "./buildModes";

describe("build composer modes", () => {
  it("maps each mode to the posture the runtime will actually enforce", () => {
    // The mode names are a promise about decision modes, not a tone of voice.
    // Plan denies writes outright, Edit turns each one into a decision, and Auto
    // hands the risk floor to the runtime.
    expect(buildMode("plan").decisionMode).toBe("deny");
    expect(buildMode("plan").planningMode).toBe("always");
    expect(buildMode("edit").decisionMode).toBe("ask");
    expect(buildMode("auto").decisionMode).toBe("auto");
  });

  it("never maps a mode to a permissive `allow`", () => {
    // `allow` would run medium and high risk actions unprompted. No composer
    // mode may reach it — Auto stops at the deterministic risk floor.
    for (const mode of BUILD_MODES) {
      expect(mode.decisionMode).not.toBe("allow");
    }
  });

  it("leaves reading capabilities out of the write set", () => {
    // Plan mode has to stay useful, so it tightens only the acting
    // capabilities; reads are never denied by a mode change.
    expect(BUILD_WRITE_CAPABILITIES).toEqual([
      "file_write_execution",
      "patch_apply_execution",
      "shell_execution",
      "process_execution",
    ]);
  });

  it("defaults to Edit and falls back to it for an unknown id", () => {
    expect(DEFAULT_BUILD_MODE).toBe("edit");
    expect(buildMode("nonsense").id).toBe("edit");
  });

  it("cycles Plan → Edit → Auto → Plan", () => {
    expect(nextBuildMode("plan")).toBe("edit");
    expect(nextBuildMode("edit")).toBe("auto");
    expect(nextBuildMode("auto")).toBe("plan");
  });

  it("reads the live posture back from the capability decision modes", () => {
    const uniform = Object.fromEntries(BUILD_WRITE_CAPABILITIES.map((c) => [c, "deny"]));
    expect(modeFromDecisionModes(uniform)).toBe("plan");
  });

  it("reports null rather than guessing when the capabilities disagree", () => {
    // Someone set permissions individually in Permissions. Showing "Edit" over a
    // half-denied posture would misdescribe what the runtime will do.
    const mixed = Object.fromEntries(BUILD_WRITE_CAPABILITIES.map((c) => [c, "ask"]));
    mixed[BUILD_WRITE_CAPABILITIES[0]] = "deny";
    expect(modeFromDecisionModes(mixed)).toBeNull();
  });

  it("reports null when a capability's mode is missing entirely", () => {
    expect(modeFromDecisionModes({ file_write_execution: "ask" })).toBeNull();
  });

  it("reports null for a decision mode no composer mode represents", () => {
    const permissive = Object.fromEntries(BUILD_WRITE_CAPABILITIES.map((c) => [c, "allow"]));
    expect(modeFromDecisionModes(permissive)).toBeNull();
  });
});

describe("repository preamble", () => {
  it("states a GitHub coordinate so the turn knows what it is working on", () => {
    expect(
      repoPreamble({ kind: "github", github_owner: "octo", github_repo: "app", branch: "main" }),
    ).toBe("Repository: octo/app (branch main).");
  });

  it("omits the branch when none was recorded", () => {
    expect(repoPreamble({ kind: "github", github_owner: "octo", github_repo: "app", branch: null })).toBe(
      "Repository: octo/app.",
    );
  });

  it("says nothing for a local repository, whose path rides the turn as an attachment", () => {
    expect(repoPreamble({ kind: "local" })).toBe("");
    expect(repoPreamble(null)).toBe("");
  });

  it("says nothing for an incomplete GitHub reference rather than inventing one", () => {
    expect(repoPreamble({ kind: "github", github_owner: "octo", github_repo: null })).toBe("");
  });
});
