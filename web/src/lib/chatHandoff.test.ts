import { describe, expect, it } from "vitest";
import { COMPOSE_EVENT, handOffToChat, takeChatHandoff } from "./chatHandoff";

describe("chatHandoff", () => {
  it("tells a mounted Chat and keeps the message for one that mounts later", () => {
    const seen: unknown[] = [];
    const listen = (event: Event) => seen.push((event as CustomEvent).detail);
    window.addEventListener(COMPOSE_EVENT, listen);
    handOffToChat("  Plan my week  ");
    window.removeEventListener(COMPOSE_EVENT, listen);
    expect(seen).toEqual([{ text: "Plan my week", sessionId: null, fromHandoff: true }]);
    // Taken once: whichever side reads it first sends it, the other finds nothing.
    expect(takeChatHandoff()).toEqual({ text: "Plan my week", attachments: [] });
    expect(takeChatHandoff()).toBeNull();
  });

  it("carries files uploaded on Home with the message", () => {
    const file = { kind: "document" as const, label: "notes.pdf", detail: "PDF", attachmentId: "att_1" };
    handOffToChat("Summarise this", [file]);
    expect(takeChatHandoff()).toEqual({ text: "Summarise this", attachments: [file] });
  });

  it("ignores an empty message", () => {
    handOffToChat("   ");
    expect(takeChatHandoff()).toBeNull();
  });
});
