/**
 * The launcher that lets the rail be short.
 *
 * These are the properties that make it a substitute for permanent rows rather
 * than a second way to do what the sidebar already did: it finds destinations
 * the rail no longer carries, it finds settings sections by their own name, and
 * the keyboard alone gets you from the shortcut to the page.
 */
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { beforeEach, describe, expect, it } from "vitest";
import CommandPalette from "./CommandPalette.svelte";

describe("command palette", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("finds a destination that is no longer on the sidebar", async () => {
    render(CommandPalette, { open: true });
    const box = screen.getByRole("textbox", { name: /search everything/i });

    await fireEvent.input(box, { target: { value: "approvals" } });

    const results = screen.getByRole("listbox", { name: /results/i });
    expect(within(results).getByText("Open approvals")).toBeInTheDocument();
    // The page itself is offered too, and says why you could not find it.
    expect(within(results).getByText(/not on the sidebar/i)).toBeInTheDocument();
  });

  it("finds a settings section by its own name, not by 'Settings'", async () => {
    // "Where is that setting" should not require opening Settings and then
    // reading its rail.
    render(CommandPalette, { open: true });

    await fireEvent.input(screen.getByRole("textbox", { name: /search everything/i }), {
      target: { value: "privacy" },
    });

    const option = screen.getByRole("option", { name: /privacy/i });
    await fireEvent.click(option);
    expect(window.location.hash).toBe("#/settings?tab=privacy");
  });

  it("names every settings section as the rail does", async () => {
    // It kept a label table of its own, with no row for Memory engine — which
    // was therefore offered as "memory-engine". QUI-L09 — the section list
    // changed; the rule did not.
    render(CommandPalette, { open: true });

    await fireEvent.input(screen.getByRole("textbox", { name: /search everything/i }), {
      target: { value: "web access" },
    });

    const option = screen.getByRole("option", { name: /web access/i });
    expect(option).not.toHaveTextContent("web-access");
    await fireEvent.click(option);
    expect(window.location.hash).toBe("#/settings?tab=web-access");
  });

  it("navigates with the keyboard alone", async () => {
    render(CommandPalette, { open: true });
    const box = screen.getByRole("textbox", { name: /search everything/i });

    await fireEvent.input(box, { target: { value: "build" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    expect(window.location.hash).toBe("#/build");
  });

  it("moves the highlight with the arrow keys", async () => {
    render(CommandPalette, { open: true });
    const box = screen.getByRole("textbox", { name: /search everything/i });
    await fireEvent.input(box, { target: { value: "project" } });

    const first = screen.getAllByRole("option")[0];
    expect(first.getAttribute("aria-selected")).toBe("true");

    await fireEvent.keyDown(box, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[0].getAttribute("aria-selected")).toBe("false");
    expect(screen.getAllByRole("option")[1].getAttribute("aria-selected")).toBe("true");
  });

  it("says so rather than showing an empty box when nothing matches", async () => {
    render(CommandPalette, { open: true });

    await fireEvent.input(screen.getByRole("textbox", { name: /search everything/i }), {
      target: { value: "zzzzzz" },
    });

    expect(screen.getByText(/nothing matches/i)).toBeInTheDocument();
    expect(screen.queryAllByRole("option")).toHaveLength(0);
  });

  it("renders nothing at all when closed", () => {
    render(CommandPalette, { open: false });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("QUI-F22 one search for everything", () => {
  it("finds chats, tasks and memories, and filters to one type", async () => {
    const { stubFetch } = await import("../test-helpers");
    stubFetch({
      "GET /api/tasks": [{ task_id: "t1", title: "Weekly inbox tidy", objective: "Group what needs a reply", status: "queued" }],
      "GET /api/memory": [{ memory_id: "m1", text: "Anna prefers short replies." }],
      "GET /api/chat-search": [{ session_id: "s1", title: "Reply to Anna", match_snippet: "…short replies…", match_turn_id: "turn_1" }],
      "GET /api/guide": { sections: [] },
    });
    render(CommandPalette, { open: true });
    const box = screen.getByRole("textbox", { name: /search everything/i });
    await fireEvent.input(box, { target: { value: "repl" } });
    const results = screen.getByRole("listbox", { name: /results/i });
    expect(await within(results).findByText("Reply to Anna", {}, { timeout: 2000 })).toBeInTheDocument();
    expect(within(results).getByText("Weekly inbox tidy")).toBeInTheDocument();
    expect(within(results).getByText("Anna prefers short replies.")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Memories" }));
    expect(within(results).queryByText("Reply to Anna")).not.toBeInTheDocument();
    await fireEvent.click(within(results).getByRole("option", { name: /Anna prefers short replies/ }));
    expect(window.location.hash).toBe("#/memory?tab=memories&record=m1");
  });
});
