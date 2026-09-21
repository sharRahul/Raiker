/**
 * BUG-306 / REM-CHAT-02 — one command set behind every conversation menu.
 *
 * Two things are held here. The bookkeeping half: a command's label, its
 * confirmation and its failure sentence come from one place, so Chat, Threads
 * and the session detail cannot describe the same refusal differently.
 *
 * And the half that is not bookkeeping. **Retry re-sends a prompt**, so a turn
 * that already wrote a file, ran a command or sent a message will do it again.
 * The row's own acceptance criterion is a retry after an ambiguous external
 * effect, and this is what makes that decision the owner's rather than a
 * surprise.
 */
import { describe, expect, it } from "vitest";
import type { ToolCallRow } from "./chatPresentation";
import {
  archiveConfirmation,
  command,
  commandFailure,
  retryConfirmation,
  retryConsequence,
} from "./conversationCommands";

function row(partial: Partial<ToolCallRow>): ToolCallRow {
  return {
    actionId: "act_1",
    toolName: "read_file",
    family: "file-read",
    label: "Read file",
    action: "README.md",
    state: "success",
    reasons: [],
    ...partial,
  };
}

describe("the command set", () => {
  it("confirms the one command that takes a thread off the board", () => {
    expect(command("archive").confirms).toBe(true);
    // Everything else changes what a thread is called or where it is filed,
    // and is undoable from the same surface.
    for (const id of ["rename", "restore", "pin", "unpin", "move", "tag", "untag"] as const) {
      expect(command(id).confirms, id).toBe(false);
    }
  });

  it("says what archiving keeps, not only that it is archiving", () => {
    const question = archiveConfirmation("Release planning");
    expect(question).toContain("Release planning");
    expect(question).toContain("Restore");
    expect(question).toContain("evidence");
  });

  it("reports a failure the same way with or without a status", () => {
    expect(commandFailure("pin")).toBe("Could not pin this thread.");
    expect(commandFailure("pin", 409)).toBe("Could not pin this thread (409).");
  });
});

describe("whether a retry would repeat something", () => {
  it("is free to repeat a turn that only read", () => {
    const consequence = retryConsequence([
      row({}),
      row({ actionId: "act_2", family: "web", label: "Read a page" }),
      row({ actionId: "act_3", family: "memory", label: "Open memory" }),
    ]);
    expect(consequence.repeats).toBe(false);
  });

  it("names what a turn that wrote would do again", () => {
    const consequence = retryConsequence([
      row({}),
      row({
        actionId: "act_2",
        family: "file-write",
        label: "Write file",
        action: "notes.md",
      }),
      row({ actionId: "act_3", family: "connector", label: "Send a message", action: "#team" }),
    ]);

    expect(consequence.repeats).toBe(true);
    expect(consequence.effects).toEqual(["Write file — notes.md", "Send a message — #team"]);
  });

  it("counts only the calls that actually happened", () => {
    // A refused call did not run, and a failed one did not complete. Warning
    // about either teaches an owner to dismiss the warning.
    const consequence = retryConsequence([
      row({ family: "shell", label: "Run command", state: "refused" }),
      row({ actionId: "act_2", family: "shell", label: "Run command", state: "failed" }),
      row({ actionId: "act_3", family: "shell", label: "Run command", state: "denied" }),
    ]);
    expect(consequence.repeats).toBe(false);
  });

  it("treats a tool it has no family for as an effect, not as a read", () => {
    const consequence = retryConsequence([
      row({ family: "tool", label: "Some plugin tool", action: "" }),
    ]);
    expect(consequence.repeats).toBe(true);
    expect(consequence.effects).toEqual(["Some plugin tool"]);
  });

  it("asks a question that names what would happen twice", () => {
    const question = retryConfirmation(
      retryConsequence([row({ family: "shell", label: "Run command", action: "npm test" })]),
    );
    expect(question).toContain("Run command — npm test");
    expect(question).toContain("a second time");
    expect(question).toContain("yours to decide");
  });

  it("bounds the list rather than pasting a hundred calls into a dialog", () => {
    const rows = Array.from({ length: 8 }, (_, index) =>
      row({ actionId: `act_${index}`, family: "file-write", label: "Write file", action: `f${index}` }),
    );
    const question = retryConfirmation(retryConsequence(rows));
    expect(question).toContain("…and 3 more");
  });
});
