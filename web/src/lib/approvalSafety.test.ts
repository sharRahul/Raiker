import { describe, expect, it } from "vitest";
import { safetyRows } from "./approvalSafety";

describe("QUI-F07 the Safety card names the account", () => {
  it("puts the account the server resolved first in Affects", () => {
    const rows = safetyRows({
      toolTitle: "Write through connector",
      expectedEffect: "",
      capability: null,
      sideEffect: "external",
      arguments: { connector_id: "gmail", operation_id: "send", account: "Personal Gmail", arguments: { to: "anna@example.com" } },
      changeable: false,
    });
    expect(rows.find((row) => row.key === "affects")?.value).toBe("Personal Gmail");
  });

  it("says nothing about an account when the proposal names none", () => {
    const rows = safetyRows({
      toolTitle: "Write file",
      expectedEffect: "Writes one file.",
      capability: null,
      sideEffect: null,
      arguments: { path: "notes.md", text: "x" },
      changeable: false,
    });
    expect(rows.find((row) => row.key === "affects")?.value).toBe("notes.md");
  });
});
