import { describe, expect, it } from "vitest";
import { goalSummaries } from "./permissionGoals";
import { makeGate } from "./test-helpers";

const on = { state: "enabled_runtime", runtime_enabled: true, enforced_enabled: true } as const;

function goal(id: string, gates: Parameters<typeof goalSummaries>[0]) {
  const summary = goalSummaries(gates).find((entry) => entry.id === id);
  if (summary === undefined) throw new Error(`no goal ${id}`);
  return summary;
}

describe("goalSummaries (UX-PERM-05)", () => {
  it("says a goal is possible after asking when its capability asks", () => {
    const files = goal("files", [makeGate({ capability: "file_write_execution", ...on, decision_mode: "ask" })]);
    expect(files.verdict).toBe("ask");
    expect(files.sentence).toBe("Can edit project files after asking you");
  });

  it("takes the most open usable path, and says when only some paths are open", () => {
    const commands = goal("commands", [
      makeGate({ capability: "shell_execution", ...on, decision_mode: "allow" }),
      makeGate({ capability: "process_execution", ...on, decision_mode: "ask" }),
      makeGate({ capability: "host_network_code_execution", decision_mode: "auto" }),
    ]);
    // The automatic one is off, so it does not make the goal automatic.
    expect(commands.verdict).toBe("allow");
    expect(commands.sentence).toBe("Can run commands and code without asking (2 of 3 ways)");
  });

  it("reads off and Never alike as cannot", () => {
    expect(goal("web", [makeGate({ capability: "web_fetch", decision_mode: "allow" })]).sentence).toBe(
      "Cannot read web pages",
    );
    expect(
      goal("messages", [makeGate({ capability: "email_runtime", ...on, decision_mode: "deny" })]).verdict,
    ).toBe("never");
  });

  it("never reads an unrecognised mode as permission", () => {
    const memory = goal("memory", [
      makeGate({ capability: "memory_write_execution", ...on, decision_mode: "sometimes" }),
    ]);
    expect(memory.verdict).toBe("unknown");
  });

  it("does not guess about a goal the runtime reported nothing for", () => {
    expect(goal("schedule", []).verdict).toBe("not_reported");
  });
});
