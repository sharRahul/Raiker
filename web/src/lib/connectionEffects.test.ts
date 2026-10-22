import { describe, expect, it } from "vitest";
import { operationEffect } from "./connectionEffects";

describe("operationEffect (QUI-P04)", () => {
  it("says what each activity does in words", () => {
    expect(operationEffect("GET").label).toBe("Reads");
    expect(operationEffect("head").label).toBe("Reads");
    expect(operationEffect("POST").label).toBe("Changes");
    expect(operationEffect("PATCH").label).toBe("Changes");
    expect(operationEffect("DELETE").label).toBe("Can't be undone");
  });
});
