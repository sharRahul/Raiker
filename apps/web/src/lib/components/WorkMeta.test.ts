/**
 * VIS-14 — Threads, Tasks and Projects are three views of the same thing, and
 * they described it three different ways: "3 turns · 2h ago" with a bare tag,
 * "Runs hourly · updated 2h ago" with a Badge, "4 sessions". Same facts, three
 * orders, three spellings. A task thread read as though it belonged to a
 * different application from the chat thread beside it on Home.
 *
 * What is asserted here is the vocabulary itself: which parts exist, the order
 * they appear in, and that an object without one of them leaves no trace of it.
 */
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import WorkMeta from "./WorkMeta.svelte";

describe("work meta", () => {
  it("states project, state, detail and last activity in one order", () => {
    const { container } = render(WorkMeta, {
      project: "Quarterly note",
      state: "waiting on you",
      stateVariant: "approval-required",
      detail: "3 turns",
      activityAt: "2026-09-06T10:00:00Z",
    });

    const text = container.textContent ?? "";
    expect(text.indexOf("Quarterly note")).toBeLessThan(text.indexOf("waiting on you"));
    expect(text.indexOf("waiting on you")).toBeLessThan(text.indexOf("3 turns"));
    expect(text.indexOf("3 turns")).toBeLessThan(text.indexOf("ago"));
  });

  it("leaves out every part the object does not have", () => {
    // A project has no state and no turn count; it must not render an empty
    // chip or a dangling separator where one would be.
    const { container } = render(WorkMeta, {
      detail: "4 sessions",
      activityAt: "2026-09-06T10:00:00Z",
      activityVerb: "created",
    });

    const text = (container.textContent ?? "").trim();
    expect(text).toMatch(/^4 sessions\s+created .*ago$/);
    expect(container.querySelectorAll("span.tag")).toHaveLength(0);
  });

  it("names what last activity means rather than assuming it is an update", () => {
    render(WorkMeta, { activityAt: "2026-09-06T10:00:00Z", activityVerb: "created" });
    expect(screen.getByText(/^created /)).toBeInTheDocument();
  });

  it("renders nothing at all for an object with none of the parts", () => {
    const { container } = render(WorkMeta, {});
    expect((container.textContent ?? "").trim()).toBe("");
  });
});
