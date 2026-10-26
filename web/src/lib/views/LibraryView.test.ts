/*
 * QUI-F15 — the Library: one list of everything Raiker made, filtered by kind
 * and project, each row opening where it came from.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import LibraryView from "./LibraryView.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const base = {
  project_id: null,
  project_name: null,
  session_id: null,
  session_title: null,
  turn_id: null,
  external: false,
  download_url: null,
  block: null,
  pin_id: null,
  created_at: "2026-10-26T09:00:00Z",
};
const DOCUMENT = {
  ...base,
  item_id: "document:att_1",
  kind: "document",
  title: "summary.md",
  detail: "Markdown · 1 KB",
  session_id: "sess_1",
  session_title: "Q3 numbers",
  turn_id: "turn_1",
  project_id: "proj_1",
  project_name: "Quarterly",
  href: "#/new-chat?session=sess_1&turn=turn_1",
  download_url: "/api/sessions/sess_1/attachments/att_1/download",
};
const BLOCK = {
  ...base,
  item_id: "block:pin_1",
  kind: "block",
  title: "Quarter in numbers",
  detail: "Key figures",
  session_id: "sess_1",
  session_title: "Q3 numbers",
  turn_id: "turn_1",
  href: "#/new-chat?session=sess_1&turn=turn_1",
  pin_id: "pin_1",
  block: { type: "callout", data: { tone: "verdict", text: "Revenue grew." } },
};
const PROJECTS = { projects: [{ project_id: "proj_1", name: "Quarterly" }] };

describe("QUI-F15 Library", () => {
  it("lists each item with where it came from and opens it there", async () => {
    stubFetch({ "GET /api/library": { items: [DOCUMENT, BLOCK], kinds: [] }, "GET /api/projects": PROJECTS });
    render(LibraryView);
    const link = await screen.findByRole("link", { name: "summary.md" });
    expect(link).toHaveAttribute("href", "#/new-chat?session=sess_1&turn=turn_1");
    expect(screen.getByText(/Markdown · 1 KB · Quarterly · from “Q3 numbers”/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download summary.md" })).toBeInTheDocument();
  });

  it("filters by kind, and offers no filter that would empty the page", async () => {
    stubFetch({ "GET /api/library": { items: [DOCUMENT, BLOCK], kinds: [] }, "GET /api/projects": PROJECTS });
    render(LibraryView);
    await screen.findByText("summary.md");
    expect(screen.getByRole("button", { name: "Images" })).toBeDisabled();
    await fireEvent.click(screen.getByRole("button", { name: "Pinned" }));
    expect(screen.queryByText("summary.md")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quarter in numbers" })).toBeInTheDocument();
  });

  it("draws a pinned block on request, and unpins it", async () => {
    const fetchMock = stubFetch({
      "GET /api/library": { items: [BLOCK], kinds: [] },
      "GET /api/projects": PROJECTS,
      "DELETE /api/library/pins/pin_1": { ok: true, pin_id: "pin_1" },
    });
    render(LibraryView);
    const title = await screen.findByRole("button", { name: "Quarter in numbers" });
    expect(screen.queryByText("Revenue grew.")).not.toBeInTheDocument();
    await fireEvent.click(title);
    expect(await screen.findByText("Revenue grew.")).toBeInTheDocument();
    const row = title.closest("li") as HTMLElement;
    await fireEvent.click(within(row).getByRole("button", { name: "Unpin" }));
    await waitFor(() => expect(screen.queryByText("Quarter in numbers")).not.toBeInTheDocument());
    expect(
      fetchMock.mock.calls.some(([url, init]) => String(url).includes("/api/library/pins/pin_1") && (init as RequestInit).method === "DELETE"),
    ).toBe(true);
  });

  it("moves a pin to a project", async () => {
    const fetchMock = stubFetch({
      "GET /api/library": { items: [BLOCK], kinds: [] },
      "GET /api/projects": PROJECTS,
      "PUT /api/library/pins/pin_1/project": { pin_id: "pin_1", project_id: "proj_1", project_name: "Quarterly" },
    });
    render(LibraryView);
    const select = await screen.findByRole("combobox", { name: "Project for Quarter in numbers" });
    await fireEvent.change(select, { target: { value: "proj_1" } });
    expect(await screen.findByText("Moved to Quarterly")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/library/pins/pin_1/project"))).toBe(true);
  });

  it("says plainly when nothing has been made yet", async () => {
    stubFetch({ "GET /api/library": { items: [], kinds: [] }, "GET /api/projects": PROJECTS });
    render(LibraryView);
    expect(await screen.findByText("Nothing made yet")).toBeInTheDocument();
  });

  it("inside a project, reads that project's items and leaves out what the page shows itself", async () => {
    const IMAGE = { ...base, item_id: "image:img_1", kind: "image", title: "A lighthouse", detail: "Image", href: "#/design?asset=img_1" };
    const fetchMock = stubFetch({ "GET /api/library": { items: [DOCUMENT, IMAGE], kinds: [] } });
    render(LibraryView, { projectId: "proj_1", compact: true, exclude: ["image"] });
    await screen.findByText("summary.md");
    expect(screen.queryByText("A lighthouse")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Filter by project" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("project_id=proj_1"))).toBe(true);
  });
});
