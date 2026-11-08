import { describe, expect, it } from "vitest";
import { mcpProvenance } from "./mcpProvenance";

describe("PL-5 — an MCP server says where it came from", () => {
  it("never calls a server Raiker did not ship reviewed", () => {
    expect(mcpProvenance("owner")).toEqual({
      label: "Added by you",
      detail: "Raiker has not reviewed this server. Use servers you trust.",
    });
    expect(mcpProvenance("plugin", "acme-tools").detail).toBe("Offered by the acme-tools plugin. Raiker has not reviewed this server.");
    expect(mcpProvenance("plugin").detail).toMatch(/^Offered by a plugin\./);
  });

  it("names Raiker's own sample as Raiker's", () => {
    expect(mcpProvenance("raiker_sample").label).toBe("Raiker sample");
  });

  it("never borrows the connector catalogue's verdicts", () => {
    for (const source of ["raiker_sample", "plugin", "owner"] as const) {
      expect(mcpProvenance(source).label).not.toMatch(/Supported|Experimental|Verified/);
    }
  });
});
