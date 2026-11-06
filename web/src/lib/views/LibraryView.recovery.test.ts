/** QUI-G06 — Library errors name the item, what it affected and one safe next step. */
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import LibraryView from "./LibraryView.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const BLOCK = {
  item_id: "block:pin_1",
  kind: "block",
  title: "Quarter in numbers",
  detail: "Key figures",
  project_id: null,
  project_name: null,
  session_id: "sess_1",
  session_title: "Q3 numbers",
  turn_id: "turn_1",
  external: false,
  href: "#/new-chat?session=sess_1&turn=turn_1",
  download_url: null,
  pin_id: "pin_1",
  block: { type: "callout", data: { tone: "verdict", text: "Revenue grew." } },
  created_at: "2026-10-26T09:00:00Z",
};
const DOCUMENT = {
  ...BLOCK,
  item_id: "document:att_1",
  kind: "document",
  title: "summary.md",
  detail: "Markdown · 1 KB",
  pin_id: null,
  block: null,
  download_url: "/api/sessions/sess_1/attachments/att_1/download",
};
const PROJECTS = { projects: [{ project_id: "proj_1", name: "Quarterly" }] };

describe("Library recovery (QUI-G06)", () => {
  it("retries a failed read and says what is unknown", async () => {
    const routes: Record<string, unknown> = { "GET /api/library": { __status: 503 }, "GET /api/projects": PROJECTS };
    stubFetch(routes);
    render(LibraryView);
    expect(await screen.findByText(/the library could not be read \(HTTP 503\)\. What Raiker has made is unknown, and nothing was removed/i)).toBeInTheDocument();
    routes["GET /api/library"] = { items: [BLOCK], kinds: [] };
    await fireEvent.click(screen.getByRole("button", { name: "Retry Library" }));
    expect(await screen.findByRole("button", { name: "Quarter in numbers" })).toBeInTheDocument();
  });

  it("keeps an unconfirmed unpin on screen with a check-first step", async () => {
    stubFetch({
      "GET /api/library": { items: [BLOCK], kinds: [] },
      "GET /api/projects": PROJECTS,
      "DELETE /api/library/pins/pin_1": { __status: 500 },
    });
    render(LibraryView);
    const title = await screen.findByRole("button", { name: "Quarter in numbers" });
    await fireEvent.click(within(title.closest("li") as HTMLElement).getByRole("button", { name: "Unpin" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/unpinning quarter in numbers was not confirmed \(HTTP 500\)/i);
    expect(alert).toHaveTextContent(/check whether it is still pinned before unpinning again/i);
    expect(screen.getByRole("button", { name: "Quarter in numbers" })).toBeInTheDocument();
  });

  it("puts the project picker back when a move is not confirmed", async () => {
    stubFetch({
      "GET /api/library": { items: [BLOCK], kinds: [] },
      "GET /api/projects": PROJECTS,
      "PUT /api/library/pins/pin_1/project": { __status: 502 },
    });
    render(LibraryView);
    const select = (await screen.findByRole("combobox", { name: "Project for Quarter in numbers" })) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "proj_1" } });
    expect(await screen.findByText(/moving quarter in numbers was not confirmed \(HTTP 502\)\. Its saved project may have changed/i)).toBeInTheDocument();
    expect(select.value).toBe("");
  });

  it("does not blame deletion for a download that failed for another reason", async () => {
    stubFetch({
      "GET /api/library": { items: [DOCUMENT], kinds: [] },
      "GET /api/projects": PROJECTS,
      "GET /api/sessions/sess_1/attachments/att_1/download": { __status: 500 },
    });
    render(LibraryView);
    await fireEvent.click(await screen.findByRole("button", { name: "Download summary.md" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/summary\.md could not be downloaded \(HTTP 500\)\. No file was saved/i);
    expect(alert).not.toHaveTextContent(/deleted/i);
  });

  it("says a missing download may have been deleted where it was made", async () => {
    stubFetch({ "GET /api/library": { items: [DOCUMENT], kinds: [] }, "GET /api/projects": PROJECTS });
    render(LibraryView);
    await fireEvent.click(await screen.findByRole("button", { name: "Download summary.md" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/HTTP 404.*may have been deleted where it was made/i);
  });
});
