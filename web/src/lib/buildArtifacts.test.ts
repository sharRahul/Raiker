// The pane focuses itself, and knows when not to.
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ARTIFACT_TABS,
  changesSummary,
  focusFor,
  readWorkbenchOpen,
  readWorkbenchTab,
  rememberWorkbenchOpen,
  rememberWorkbenchTab,
  type ArtifactTab,
} from "./buildArtifacts";

describe("the tab list", () => {
  it("is the four views the review names, in that order", () => {
    expect(ARTIFACT_TABS.map((tab) => tab.label)).toEqual([
      "Changes",
      "Preview",
      "Terminal",
      "Runs",
    ]);
  });

  it("gives every tab a distinct id", () => {
    const ids = ARTIFACT_TABS.map((tab) => tab.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("auto-focus", () => {
  it("shows a file the owner just opened", () => {
    expect(focusFor("file-opened", "runs")).toBe("preview");
  });

  it("shows the terminal when a command starts", () => {
    expect(focusFor("command-started", "changes")).toBe("terminal");
  });

  it("shows background work when it is asked for", () => {
    expect(focusFor("background-work", "preview")).toBe("runs");
  });

  it("shows what a turn changed", () => {
    expect(focusFor("turn-changed-files", "preview")).toBe("changes");
  });

  it("does not pull the owner off the output the turn produced", () => {
    // The failure this prevents: reading a command's output, the turn ends, and
    // the pane yanks itself to Changes mid-sentence. They are already looking at
    // the thing the event is about.
    expect(focusFor("turn-changed-files", "terminal")).toBeNull();
  });

  it("is a decision, not a default: every event names a tab or null", () => {
    const events = [
      "file-opened",
      "command-started",
      "turn-changed-files",
      "background-work",
    ] as const;
    const tabs: ArtifactTab[] = ["changes", "preview", "terminal", "runs"];
    for (const event of events) {
      for (const current of tabs) {
        const next = focusFor(event, current);
        expect(next === null || tabs.includes(next)).toBe(true);
      }
    }
  });
});

describe("changesSummary", () => {
  it("says nothing has changed rather than showing a zero", () => {
    expect(changesSummary(null)).toEqual({ count: 0, text: "No uncommitted changes." });
    expect(changesSummary({ entries: [] }).count).toBe(0);
  });

  it("counts one file in the singular", () => {
    expect(changesSummary({ entries: [{ path: "a.ts" }] }).text).toBe(
      "1 file changed and not committed.",
    );
  });

  it("counts several", () => {
    const summary = changesSummary({ entries: [{ path: "a" }, { path: "b" }, { path: "c" }] });
    expect(summary.count).toBe(3);
    expect(summary.text).toBe("3 files changed and not committed.");
  });
});

/**
 * REM-BUILD-01 — the workbench comes back where it was left.
 *
 * The next action still decides which view comes forward; this is the other
 * half, and the one the explorer has had since B13: a pane that closes itself
 * on every reload is one an owner stops opening.
 */
describe("what the workbench remembers", () => {
  afterEach(() => {
    window.localStorage.removeItem("raiker.build.workbenchOpen");
    window.localStorage.removeItem("raiker.build.workbenchTab");
  });

  it("starts closed on Changes, before anyone has left it anywhere", () => {
    expect(readWorkbenchOpen()).toBe(false);
    expect(readWorkbenchTab()).toBe("changes");
  });

  it("keeps the view and the open state it was left with", () => {
    rememberWorkbenchOpen(true);
    rememberWorkbenchTab("terminal");
    expect(readWorkbenchOpen()).toBe(true);
    expect(readWorkbenchTab()).toBe("terminal");
  });

  it("forgets an open pane that was closed again", () => {
    rememberWorkbenchOpen(true);
    rememberWorkbenchOpen(false);
    expect(readWorkbenchOpen()).toBe(false);
  });

  it("selects Changes rather than nothing when the stored view is not a view", () => {
    window.localStorage.setItem("raiker.build.workbenchTab", "diagnostics");
    expect(readWorkbenchTab()).toBe("changes");
  });

  it("survives a storage that refuses to answer", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    try {
      expect(readWorkbenchOpen()).toBe(false);
      expect(readWorkbenchTab()).toBe("changes");
      expect(() => rememberWorkbenchOpen(true)).not.toThrow();
      expect(() => rememberWorkbenchTab("runs")).not.toThrow();
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
    }
  });
});
