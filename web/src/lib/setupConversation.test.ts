import { afterEach, describe, expect, it, vi } from "vitest";
import { answeredExchanges, HELLO_LINE, MODEL_QUESTION, saveOwnerName } from "./setupConversation";
import { stubFetch } from "./test-helpers";

afterEach(() => vi.unstubAllGlobals());

describe("answeredExchanges (QUI-W02 – W04)", () => {
  it("draws only the steps already passed, with what was chosen", () => {
    expect(answeredExchanges([], { name: "Rahul", model: null })).toEqual([]);
    expect(answeredExchanges(["welcome", "model"], { name: "Rahul", model: "Claude Haiku 4.5" })).toEqual([
      { id: "welcome", asked: HELLO_LINE, answered: "Rahul" },
      { id: "model", asked: MODEL_QUESTION, answered: "Claude Haiku 4.5" },
    ]);
  });

  it("says Skipped and Decide later rather than inventing an answer", () => {
    const [name, model] = answeredExchanges(["welcome", "model"], { name: " ", model: null });
    expect(name.answered).toBe("Skipped");
    expect(model.answered).toBe("Decide later");
  });
});

describe("saveOwnerName", () => {
  it("writes the display name back with the revision it read, keeping other settings", async () => {
    const fetchMock = stubFetch({
      "GET /api/settings": { settings: { "ui.theme": "dark" }, status: {}, revision: "r1" },
      "PUT /api/settings": { settings: {}, revision: "r2", merged_keys: [] },
    });
    await saveOwnerName("  Rahul ");
    const put = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT");
    expect(JSON.parse(String((put?.[1] as RequestInit).body))).toEqual({
      settings: { "ui.theme": "dark", "account.display_name": "Rahul" },
      expected_revision: "r1",
      base: { "account.display_name": null },
    });
  });
});
