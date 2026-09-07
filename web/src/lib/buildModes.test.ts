import { describe, expect, it } from "vitest";
import {
  BUILD_MODES,
  BUILD_WRITE_CAPABILITIES,
  buildMode,
  DEFAULT_BUILD_MODE,
  nextBuildMode,
  repoPreamble,
  standingPostureNote,
  turnCapabilityModes,
} from "./buildModes";

describe("build composer modes", () => {
  it("maps each mode to the turn-scoped posture the runtime will enforce", () => {
    // The mode names are a promise about what this turn may do, not a tone of
    // voice. Plan refuses writes for the turn, Edit turns each one into a
    // decision, and Auto adds no restriction of its own.
    expect(buildMode("plan").turnMode).toBe("deny");
    expect(buildMode("plan").planningMode).toBe("always");
    expect(buildMode("edit").turnMode).toBe("ask");
    expect(buildMode("auto").turnMode).toBeNull();
  });

  it("never lets a mode loosen anything", () => {
    // BUG-70 — the chips used to POST four standing decision-mode changes with
    // no step-up. A turn-scoped posture may only ever tighten, so no mode may
    // carry `allow` or `auto`: those loosen, and loosening is a change to
    // standing authority that belongs to the Permissions step-up.
    for (const mode of BUILD_MODES) {
      expect(mode.turnMode === null || mode.turnMode === "ask" || mode.turnMode === "deny").toBe(true);
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

  it("defaults to Auto and falls back to it for an unknown id", () => {
    expect(DEFAULT_BUILD_MODE).toBe("auto");
    expect(buildMode("nonsense").id).toBe("auto");
  });

  it("keeps the default free of any turn-scoped override", () => {
    // Opening in Auto must not widen anything: Auto sends no capability
    // override and no planning override, so a new Build conversation runs under
    // exactly the owner's standing permissions and nothing more.
    expect(turnCapabilityModes(DEFAULT_BUILD_MODE)).toEqual({});
    expect(buildMode(DEFAULT_BUILD_MODE).planningMode).toBeNull();
  });

  it("cycles Plan → Edit → Auto → Plan", () => {
    expect(nextBuildMode("plan")).toBe("edit");
    expect(nextBuildMode("edit")).toBe("auto");
    expect(nextBuildMode("auto")).toBe("plan");
  });
});

describe("the map a mode sends with its turn", () => {
  it("covers every write capability for a tightening mode", () => {
    expect(turnCapabilityModes("plan")).toEqual({
      file_write_execution: "deny",
      patch_apply_execution: "deny",
      shell_execution: "deny",
      process_execution: "deny",
    });
    expect(turnCapabilityModes("edit")).toEqual({
      file_write_execution: "ask",
      patch_apply_execution: "ask",
      shell_execution: "ask",
      process_execution: "ask",
    });
  });

  it("sends nothing at all for Auto", () => {
    // This is the whole of BUG-70's fix on the wire: Auto asks for no override,
    // so the turn runs under the owner's standing permissions and the chip
    // changes nothing.
    expect(turnCapabilityModes("auto")).toEqual({});
  });
});

describe("what Auto amounts to under the owner's standing permissions", () => {
  const all = (mode: string) =>
    Object.fromEntries(BUILD_WRITE_CAPABILITIES.map((c) => [c, mode]));

  it("says nothing for the modes that carry their own posture", () => {
    expect(standingPostureNote("plan", all("ask"))).toBeNull();
    expect(standingPostureNote("edit", all("ask"))).toBeNull();
  });

  it("tells the owner when every write still asks", () => {
    // The old chip would have silently set all four to `auto` here. The new one
    // reports the truth instead of manufacturing it.
    expect(standingPostureNote("auto", all("ask"))).toContain("still be proposed");
  });

  it("tells the owner when every write is denied", () => {
    expect(standingPostureNote("auto", all("deny"))).toContain("change nothing");
  });

  it("counts the partially-tightened case rather than rounding it", () => {
    const mixed = all("auto");
    mixed[BUILD_WRITE_CAPABILITIES[0]] = "ask";
    expect(standingPostureNote("auto", mixed)).toContain("1 of 4");
  });

  it("confirms an actually permissive posture", () => {
    expect(standingPostureNote("auto", all("auto"))).toContain("low-risk changes run unprompted");
  });

  it("admits it could not read them rather than assuming the happy answer", () => {
    expect(standingPostureNote("auto", null)).toContain("could not read");
    expect(standingPostureNote("auto", { file_write_execution: "auto" })).toContain("could not read");
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
