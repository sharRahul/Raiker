/**
 * BUG-305 — what Raiker can read, in one list.
 *
 * The two controllers stay two; the owner's question gets one answer. What has
 * to be true on screen is that a row says which kind it is, whether recall and
 * the Map can actually reach it, and — before anything is stopped — what
 * stopping it does to the bytes. Those are opposite for the two kinds, and
 * getting either the wrong way round is a data-loss surprise.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import KnowledgeSources from "./KnowledgeSources.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const HELD = {
  source_id: "file_1",
  kind: "managed_file" as const,
  label: "notes.md",
  location: "memory-files/notes.md",
  scope: "memory",
  held: true,
  index_state: "ready",
  recall: true,
  graph: false,
  added_at: "2026-09-20T10:00:00Z",
};

const GRANTED = {
  source_id: "root_1",
  kind: "granted_folder" as const,
  label: "Papers",
  location: "/home/owner/papers",
  scope: "folder",
  held: false,
  index_state: "granted",
  recall: false,
  graph: false,
  added_at: "2026-09-20T11:00:00Z",
};

function mount(sources = [HELD, GRANTED]) {
  return stubFetch({
    "GET /api/knowledge-sources": {
      sources,
      held_count: sources.filter((s) => s.held).length,
      granted_count: sources.filter((s) => !s.held).length,
    },
    "DELETE /api/knowledge-sources": { ok: true },
  });
}

describe("KnowledgeSources", () => {
  it("lists both kinds and says which is which", async () => {
    mount();
    render(KnowledgeSources);

    await waitFor(() => expect(screen.getByText("notes.md")).toBeInTheDocument());
    expect(screen.getByText("Papers")).toBeInTheDocument();
    expect(screen.getByText("Kept by Raiker")).toBeInTheDocument();
    expect(screen.getByText("Read where it is")).toBeInTheDocument();
  });

  it("says a granted folder is not indexed rather than implying it is read", async () => {
    mount();
    render(KnowledgeSources);

    await waitFor(() => expect(screen.getByText("Not indexed yet")).toBeInTheDocument());
    expect(screen.getByText("Recall")).toBeInTheDocument();
  });

  it("warns that stopping a kept document deletes Raiker's copy", async () => {
    const asked: string[] = [];
    vi.stubGlobal("confirm", (question: string) => {
      asked.push(question);
      return false;
    });
    mount();
    render(KnowledgeSources);

    await waitFor(() => expect(screen.getByText("notes.md")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Stop reading notes.md" }));

    expect(asked[0]).toContain("deleted with it");
    expect(asked[0]).toContain("original you imported it from is untouched");
  });

  it("promises a granted folder is left where it is", async () => {
    const asked: string[] = [];
    vi.stubGlobal("confirm", (question: string) => {
      asked.push(question);
      return false;
    });
    mount();
    render(KnowledgeSources);

    await waitFor(() => expect(screen.getByText("Papers")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Stop reading Papers" }));

    expect(asked[0]).toContain("Nothing in the folder is deleted");
  });

  it("stops reading only what the owner confirmed", async () => {
    vi.stubGlobal("confirm", () => true);
    const fetchMock = mount();
    render(KnowledgeSources);

    await waitFor(() => expect(screen.getByText("Papers")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Stop reading Papers" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).includes("kind=granted_folder") &&
            String(url).includes("source_id=root_1") &&
            (init as RequestInit | undefined)?.method === "DELETE",
        ),
      ).toBe(true),
    );
  });

  it("says there is nothing rather than showing an empty frame", async () => {
    mount([]);
    render(KnowledgeSources);

    await waitFor(() => expect(screen.getByText(/Nothing yet/)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Knowledge Map" })).toHaveAttribute("href", "#/brain");
    // And not the same fact twice: a summary of a list that is not there.
    expect(screen.queryByText(/documents Raiker keeps/)).not.toBeInTheDocument();
  });

  it("summarises the list once there is one", async () => {
    mount();
    render(KnowledgeSources);

    await waitFor(() =>
      expect(screen.getByText(/document Raiker keeps/)).toBeInTheDocument(),
    );
  });
});
