import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import NotesView from "./NotesView.svelte";
import { stubFetch } from "../test-helpers";

const note = {
  path: "Alpha.md", name: "Alpha", content: "# Alpha\n\nSee [[Beta]] #idea", mtime: 1,
  properties: { status: "draft" }, tags: ["idea"], aliases: [],
  headings: [{ level: 1, text: "Alpha", line: 0 }], tasks: [], links: [], links_updated: 0,
};
function routes(extra: Record<string, unknown> = {}) {
  return stubFetch({
    "GET /api/notes": { root: "/workspace/Notes", notes: [
      { path: "Alpha.md", name: "Alpha", mtime: 1, size: 20 },
      { path: "Beta.md", name: "Beta", mtime: 1, size: 20 },
    ], tags: [{ tag: "idea", count: 1 }] },
    "GET /api/notes/note": note,
    "GET /api/notes/backlinks": { path: "Alpha.md", linked: [], unlinked: [] },
    "GET /api/notes/graph": { nodes: [], edges: [], unresolved: [] }, ...extra,
  });
}
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState(null, "", "#/notes"); });

describe("Notes", () => {
  it("opens a note with Markdown, properties and link navigation", async () => {
    routes(); window.history.replaceState(null, "", "#/notes?note=Alpha.md");
    render(NotesView);
    expect(await screen.findByRole("button", { name: "Alpha" })).toBeInTheDocument();
    expect(screen.getByRole("definition")).toHaveTextContent("draft");
    expect(within(screen.getByRole("article")).getByRole("link", { name: "Beta" })).toHaveAttribute("href", "#/notes?note=Beta");
    expect(within(screen.getByRole("article")).getByRole("link", { name: "#idea" })).toHaveAttribute("href", "#/notes?search=tag%3Aidea");
    await fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("textbox", { name: "Note text" })).toHaveValue(note.content);
  });

  it("saves with the opened version and keeps the newer draft after a save failure", async () => {
    const fetch = routes({ "PUT /api/notes/note": { __status: 409, detail: { reason_code: "note_changed_elsewhere" } } });
    window.history.replaceState(null, "", "#/notes?note=Alpha.md"); render(NotesView);
    await screen.findByRole("button", { name: "Alpha" });
    await fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const editor = screen.getByRole("textbox", { name: "Note text" });
    await fireEvent.input(editor, { target: { value: "My unsaved draft" } });
    await fireEvent.keyDown(editor, { key: "s", ctrlKey: true });
    expect(await screen.findByRole("alert")).toHaveTextContent("changed somewhere else");
    expect(fetch).toHaveBeenCalledWith("/api/notes/note", expect.objectContaining({
      method: "PUT", body: JSON.stringify({ path: "Alpha.md", content: "My unsaved draft", expected_mtime: 1 }),
    }));
    window.location.hash = "#/notes?note=Beta.md";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    await waitFor(() => expect(window.location.hash).toBe("#/notes?note=Alpha.md"));
    expect(editor).toHaveValue("My unsaved draft");
    expect(screen.getByRole("alert")).toHaveTextContent("changed somewhere else");
  });

  it("reports an unreadable folder without an invented empty notebook", async () => {
    routes({ "GET /api/notes": { __status: 403, detail: { reason_code: "folder_unavailable" } } });
    render(NotesView);
    expect(await screen.findByRole("alert")).toHaveTextContent("Notes could not be read");
    expect(screen.queryByText("No notes yet. Make one, or open today's.")).toBeNull();
  });
});
