import { describe, expect, it } from "vitest";
import { mayLeave, registerLeaveGuard } from "./leaveGuard";

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
});
