import { afterEach, describe, expect, it } from "vitest";
import {
  CONVERSATION_PROFILES,
  profileCapabilityModes,
  profileFromSession,
} from "./conversationProfile";
import { vi } from "vitest";
import { handOffToChat, takeChatHandoff } from "./chatHandoff";

afterEach(() => localStorage.clear());

const GATES = [
  { capability: "file_write_execution", side_effect: "reversible" },
  { capability: "web_fetch_runtime", side_effect: "read" },
  { capability: "email_send_runtime", side_effect: "external" },
  { capability: "memory_forget_execution", side_effect: "destructive" },
  { capability: "plugin_install_runtime", side_effect: "critical" },
  { capability: "inert_gate", side_effect: "" },
];

describe("conversation profile (QUI-P02)", () => {
  it("offers Careful and Standard only: no Off, no Within limits yet", () => {
    expect(CONVERSATION_PROFILES.map((item) => item.label)).toEqual(["Careful", "Standard"]);
  });

  it("sends nothing in Standard", () => {
    expect(profileCapabilityModes("standard", GATES)).toEqual({});
  });

  it("asks, and only asks, before every capability that changes something in Careful", () => {
    const modes = profileCapabilityModes("careful", GATES);
    expect(modes).toEqual({
      file_write_execution: "ask",
      email_send_runtime: "ask",
      memory_forget_execution: "ask",
      plugin_install_runtime: "ask",
    });
    // It can only tighten: the runtime accepts `ask` and `deny` and nothing wider.
    expect(new Set(Object.values(modes))).toEqual(new Set(["ask"]));
  });

  // Decided 2026-10-25: the profile is kept on the conversation, so every
  // device opens it the same way.
  it("takes the conversation's own record", () => {
    const save = vi.fn();
    expect(profileFromSession("sess_a", "careful", save)).toBe("careful");
    expect(profileFromSession("sess_b", "standard", save)).toBe("standard");
    expect(profileFromSession("sess_c", undefined, save)).toBe("standard");
    expect(save).not.toHaveBeenCalled();
  });

  it("carries a Careful choice this browser kept before over to the conversation, once", () => {
    localStorage.setItem("raiker.conversation-profile.sess_a", "careful");
    const save = vi.fn();
    expect(profileFromSession("sess_a", "standard", save)).toBe("careful");
    expect(save).toHaveBeenCalledWith("sess_a", "careful");
    expect(localStorage.length).toBe(0);
  });

  it("travels from Home's composer to the conversation it starts", () => {
    handOffToChat("Plan my week", [], undefined, "careful");
    expect(takeChatHandoff()).toMatchObject({ text: "Plan my week", profile: "careful" });
  });
});
