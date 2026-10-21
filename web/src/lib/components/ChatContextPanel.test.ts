import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import ChatContextPanel from "./ChatContextPanel.svelte";
import type { ToolCallRow } from "../chatPresentation";
import type { TurnSourceView } from "../apiTypes";

const FILE = { kind: "path" as const, label: "plan.md", detail: "notes/plan.md", path: "notes/plan.md" };
const ROW = { actionId: "a1", toolName: "read_file", family: "files", label: "Read a file", action: "notes/plan.md", state: "success", reasons: [] } as unknown as ToolCallRow;
const SOURCE = { source_id: "src_1", ordinal: 1, kind: "web", title: "Release notes", locator: "example.com/notes", tool_name: "web_fetch", detail: "", attachment_id: "", turn_id: "t1", openable: true } as TurnSourceView;

describe("ChatContextPanel (QUI-C07)", () => {
  it("draws only the tabs that have content and switches between them", async () => {
    const onopensource = vi.fn();
    render(ChatContextPanel, {
      props: { files: [FILE], plan: null, sources: [SOURCE], activity: [ROW], onclose: () => {}, onopensource },
    });
    const tabs = screen.getAllByRole("tab").map((tab) => tab.textContent);
    expect(tabs).toEqual(["Context", "Sources", "Activity"]);
    expect(screen.getByText("plan.md")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    expect(screen.getByText("Read a file")).toBeInTheDocument();
    expect(screen.getByText("notes/plan.md · Done")).toBeInTheDocument();
    await fireEvent.keyDown(screen.getByRole("tab", { name: "Activity" }), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Context" })).toHaveAttribute("aria-selected", "true");
    await fireEvent.click(screen.getByRole("tab", { name: "Sources" }));
    await fireEvent.click(screen.getByRole("button", { name: "Release notes" }));
    expect(onopensource).toHaveBeenCalledWith(SOURCE);
  });

  it("names plan steps in words, not only colour, and draws no tab list for one tab", () => {
    render(ChatContextPanel, {
      props: {
        files: [], sources: [], activity: [], onclose: () => {},
        plan: { session_id: "s", steps: [{ title: "Read the brief", status: "completed" }, { title: "Draft", status: "in_progress" }] },
      },
    });
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Now")).toBeInTheDocument();
  });

  it("says plainly when nothing is in use yet", () => {
    render(ChatContextPanel, { props: { files: [], plan: null, sources: [], activity: [], onclose: () => {} } });
    expect(screen.getByText(/Nothing in use yet/)).toBeInTheDocument();
  });
});
