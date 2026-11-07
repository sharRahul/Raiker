import { describe, expect, it } from "vitest";
import { isSendKeystroke, sendHint, sendKeyFrom } from "./sendKey";
import { shortcuts } from "./composerCommands";

const key = (init: KeyboardEventInit) => new KeyboardEvent("keydown", { key: "Enter", ...init });

describe("send key (QUI-C04)", () => {
  it("defaults to Enter and ignores unknown values", () => {
    expect(sendKeyFrom({})).toBe("enter");
    expect(sendKeyFrom({ "personalisation.send_key": "space" })).toBe("enter");
    expect(sendKeyFrom({ "personalisation.send_key": "mod_enter" })).toBe("mod_enter");
  });
  it("sends on Enter, never on Shift + Enter, in the default mode", () => {
    expect(isSendKeystroke(key({}), "enter")).toBe(true);
    expect(isSendKeystroke(key({ shiftKey: true }), "enter")).toBe(false);
  });
  it("needs Ctrl or ⌘ in the long-instructions mode; plain Enter is a new line", () => {
    expect(isSendKeystroke(key({}), "mod_enter")).toBe(false);
    expect(isSendKeystroke(key({ ctrlKey: true }), "mod_enter")).toBe(true);
    expect(isSendKeystroke(key({ metaKey: true }), "mod_enter")).toBe(true);
  });
  it("never sends mid-composition", () => {
    expect(isSendKeystroke(key({ isComposing: true }), "enter")).toBe(false);
  });
  it("names the keys in the hint and the shortcut map", () => {
    expect(sendHint("enter")).toBe("Enter to send · Shift + Enter for a new line");
    expect(sendHint("mod_enter")).toMatch(/\+ Enter to send · Enter for a new line$/);
    expect(shortcuts("chat", "mod_enter").find((row) => row.what === "New line")?.keys).toBe("Enter");
  });
});

import { contextWarning, estimateDraftTokens, formatTokenEstimate } from "./tokenEstimate";

describe("context guardrail (QUI-C04)", () => {
  it("warns only above 80% of a known window, and says it counts what is being added", () => {
    expect(contextWarning(160_000, 200_000)).toBeNull();
    expect(contextWarning(176_000, 200_000)).toMatch(/^With what you are adding, this prompt is about 88%/);
    expect(contextWarning(250_000, 200_000)).toMatch(/larger than the model's context window/);
    expect(contextWarning(999_999, null)).toBeNull();
  });
  it("estimates text and text files, never a PDF", () => {
    expect(estimateDraftTokens("abcd".repeat(10), [
      { kind: "document", label: "a.csv", detail: "", mediaType: "text/csv", byteSize: 400 },
      { kind: "document", label: "b.pdf", detail: "", mediaType: "application/pdf", byteSize: 400_000 },
    ])).toBe(110);
    expect(formatTokenEstimate(1234)).toBe("≈ 1.2k tokens");
  });
});
