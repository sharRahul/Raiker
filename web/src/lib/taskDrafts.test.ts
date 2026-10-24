import { describe, expect, it } from "vitest";

import { SCHEDULE_TEMPLATES, firstRunValue, requestTaskDraft, routineFromTurn, takeTaskDraft } from "./taskDrafts";
import { AGENT_CADENCES } from "./agentCadence";

describe("QUI-F06 schedule templates", () => {
  it("offers the three named templates, each a repeating cadence the runtime knows", () => {
    expect(SCHEDULE_TEMPLATES.map((template) => template.label)).toEqual(["Morning brief", "Weekly inbox tidy", "Watch this page"]);
    const known = new Set(AGENT_CADENCES.map((cadence) => cadence.id));
    for (const template of SCHEDULE_TEMPLATES) expect(known.has(template.every)).toBe(true);
  });

  it("never asks a template to send, archive or delete", () => {
    const inbox = SCHEDULE_TEMPLATES.find((template) => template.id === "weekly-inbox-tidy");
    expect(inbox?.objective).toContain("Do not send, archive or delete anything");
  });

  it("puts the first run at the next matching time, never in the past", () => {
    const now = new Date(2026, 9, 24, 10, 30); // Saturday 10:30
    expect(firstRunValue({ at: "08:00" }, now)).toBe("2026-10-25T08:00");
    expect(firstRunValue({ at: "11:00" }, now)).toBe("2026-10-24T11:00");
    expect(firstRunValue({ at: "09:00", weekday: 1 }, now)).toBe("2026-10-26T09:00");
  });
});

describe("QUI-F18 save as routine", () => {
  it("hands the request that worked over once, as a daily draft", () => {
    requestTaskDraft(routineFromTurn("  Summarise my unread email  ", "Inbox summary"));
    expect(takeTaskDraft()).toMatchObject({ title: "Inbox summary", objective: "Summarise my unread email", timing: "repeating", every: "daily" });
    expect(takeTaskDraft()).toBeNull();
  });
});

describe("QUI-F18 the steps a routine repeats", () => {
  it("lists what the turn's record says it did, and nothing that failed", async () => {
    const { routineSteps } = await import("./taskDrafts");
    const steps = routineSteps([
      { label: "Read file", action: "notes.txt", state: "success", toolName: "read_file" },
      { label: "Update plan", action: "", state: "success", toolName: "update_plan" },
      { label: "Search the web", action: "flights", state: "failed", toolName: "web_search" },
    ]);
    expect(steps).toEqual(["Read file (notes.txt)"]);
    const draft = routineFromTurn("Summarise notes", "", steps);
    expect(draft.objective).toBe("Summarise notes\n\nLast time this took these steps: Read file (notes.txt).");
    expect(draft.title).toBe("Summarise notes");
  });
});
