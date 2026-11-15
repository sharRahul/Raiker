import { describe, expect, it } from "vitest";
import { allowLeaveOnce, consumeAllowedLeave, mayLeave, registerLeaveGuard } from "./leaveGuard";

describe("leave guards", () => {
  it("lets a navigation go when nothing is registered", () => {
    expect(mayLeave("#/chat")).toBe(true);
  });

  it("stops a navigation any guard refuses, and forgets a removed guard", () => {
    const seen: string[] = [];
    const remove = registerLeaveGuard((next) => {
      seen.push(next);
      return next !== "#/chat";
    });
    expect(mayLeave("#/build")).toBe(true);
    expect(mayLeave("#/chat")).toBe(false);
    remove();
    expect(mayLeave("#/chat")).toBe(true);
    expect(seen).toEqual(["#/build", "#/chat"]);
  });

  it("waits on a guard that asks the owner in Raiker's dialog", async () => {
    let answer: (go: boolean) => void = () => {};
    const remove = registerLeaveGuard(() => new Promise<boolean>((resolve) => (answer = resolve)));
    const verdict = mayLeave("#/chat");
    expect(verdict).toBeInstanceOf(Promise);
    answer(true);
    expect(await verdict).toBe(true);
    remove();
  });

  it("lets one navigation the owner agreed to through, once", () => {
    allowLeaveOnce("#/chat");
    expect(consumeAllowedLeave("#/tasks")).toBe(false);
    expect(consumeAllowedLeave("#/chat")).toBe(true);
    expect(consumeAllowedLeave("#/chat")).toBe(false);
  });
});
