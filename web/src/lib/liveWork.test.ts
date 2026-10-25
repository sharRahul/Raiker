import { describe, expect, it } from "vitest";

import { liveWorkItems, liveWorkLine, type LiveWorkItem } from "./liveWork.svelte";

const task = (task_id: string, status: string, title = "Tidy inbox", current_step: string | null = null) => ({
  task_id,
  status,
  title,
  current_step,
});

const turn: LiveWorkItem = {
  id: "turn:chat",
  label: "Reply to Anna",
  step: "Drafting reply",
  href: "#/new-chat?session=s1",
  waiting: false,
};

describe("QUI-F04 live work line", () => {
  it("is empty when nothing runs", () => {
    expect(liveWorkLine(liveWorkItems([task("t1", "completed")], {}))).toBe("");
  });

  it("names the one thing running and its real step", () => {
    const items = liveWorkItems([task("t1", "running", "Morning brief", "Reading calendar")], {});
    expect(liveWorkLine(items)).toBe("Morning brief · Reading calendar");
    expect(items[0].href).toBe("#/tasks?task=t1");
  });

  it("says a task without a step is running, never a percentage", () => {
    expect(liveWorkLine(liveWorkItems([task("t1", "running")], {}))).toBe("Tidy inbox · running");
  });

  it("says a parked task waits for the owner even when it reported a step", () => {
    const items = liveWorkItems([task("t1", "waiting_for_approval", "Send reply", "Sending email")], {});
    expect(liveWorkLine(items)).toBe("Send reply · waiting for you");
    expect(items[0].waiting).toBe(true);
  });

  it("counts several, and how many wait", () => {
    const items = liveWorkItems([task("t1", "running"), task("t2", "paused")], {});
    expect(liveWorkLine(items)).toBe("2 tasks running · 1 waiting for you");
  });

  it("puts this window's turn first and stops calling everything a task", () => {
    const items = liveWorkItems([task("t1", "running")], { chat: turn });
    expect(items[0].id).toBe("turn:chat");
    expect(liveWorkLine(items)).toBe("2 things running");
  });

  it("does not count a routine queued for later as running", () => {
    const now = Date.parse("2026-10-25T12:00:00Z");
    const later = { ...task("t1", "queued"), scheduled_at: "2030-01-01T08:00:00Z" };
    const due = { ...task("t2", "queued", "Due now"), scheduled_at: "2026-10-25T11:00:00Z" };
    const items = liveWorkItems([later, due], {}, now);
    expect(items.map((item) => item.id)).toEqual(["task:t2"]);
  });
});
