import { describe, expect, it } from "vitest";
import type { ExecutionEnvironment } from "./apiTypes";
import { commandsUnavailableReason } from "./commandAvailability";

const env = (partial: Partial<ExecutionEnvironment>): ExecutionEnvironment =>
  ({ profile_id: "native_sandbox", name: "Local sandbox", kind: "native", available: true, selected: true, ...partial }) as ExecutionEnvironment;

describe("commandsUnavailableReason (beta plan §1)", () => {
  it("says nothing while the environment is unread or ready", () => {
    expect(commandsUnavailableReason(null)).toBeNull();
    expect(commandsUnavailableReason(env({}))).toBeNull();
  });

  it("names the unconfirmed sandbox and that planning still works", () => {
    expect(commandsUnavailableReason(env({ available: false }))).toMatch(/sandbox could not be confirmed.*Plan and Propose still work/);
  });

  it("names a removed or remote environment", () => {
    expect(commandsUnavailableReason(env({ available: false, kind: "retired" }))).toMatch(/removed/);
    expect(commandsUnavailableReason(env({ available: false, kind: "ssh", name: "Lab box" }))).toMatch(/Lab box is not ready/);
  });
});
