/**
 * Settings → Memory engine (REM-MEM-03).
 *
 * These two cases came from `MemoryView.test.ts` with the controls they cover:
 * which space recall searches, and building one. Memory keeps the sentence that
 * says whether recall is matching meaning, and the link here.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import MemoryEngine from "./MemoryEngine.svelte";
import { stubFetch } from "../../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const LOCAL_PROVIDER = {
  profile_id: "raiker-local-llama-cpp",
  provider: "llama.cpp",
  model: "local-gguf",
  space: "llama.cpp:local-gguf",
  local_only: true,
  requires_network: false,
  unindexed_memories: 4,
  unindexed_file_chunks: 2,
  pending_count: 6,
};

const HOSTED_PROVIDER = {
  profile_id: "openai-hosted",
  provider: "openai",
  model: "text-embedding-3-small",
  space: "openai:text-embedding-3-small",
  local_only: false,
  requires_network: true,
  unindexed_memories: 4,
  unindexed_file_chunks: 2,
  pending_count: 6,
};

function settings(overrides: Record<string, unknown> = {}) {
  return {
    incognito: false,
    embedding_backend: "auto",
    retrieval: {
      backend_id: "local_hash",
      kind: "lexical_fallback",
      model: "raiker-local-hash-v1",
      dimensions: 384,
      semantic: false,
      reason_code: "embedding_backend_semantic_not_configured",
    },
    spaces: [],
    embedding_providers: [LOCAL_PROVIDER, HOSTED_PROVIDER],
    unindexed_memories: 4,
    unindexed_file_chunks: 2,
    ...overrides,
  };
}

describe("Settings → Memory engine", () => {
  it("builds a meaning-based index with the model the owner named", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory/settings": settings(),
      "POST /api/memory/embedding-index": {
        ok: true,
        embedding_model: "openai:text-embedding-3-small",
        indexed_count: 4,
        indexed_file_chunk_count: 2,
        skipped_count: 0,
      },
    });
    vi.stubGlobal("confirm", () => true);
    render(MemoryEngine);

    const select = await screen.findByLabelText(/embedding model/i);
    expect(
      screen.getByRole("link", { name: /review and download it in models/i }),
    ).toHaveAttribute("href", "#/models?tab=add");
    await fireEvent.change(select, { target: { value: "openai:text-embedding-3-small" } });
    await fireEvent.click(screen.getByRole("button", { name: /embed 6/i }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/embedding-index",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ provider: "openai", model: "text-embedding-3-small" }),
        }),
      ),
    );
  });

  it("says how many records leave this machine, and where, before they do", async () => {
    const asked: string[] = [];
    stubFetch({ "GET /api/memory/settings": settings() });
    vi.stubGlobal("confirm", (question: string) => {
      asked.push(question);
      return false;
    });
    render(MemoryEngine);

    const select = await screen.findByLabelText(/embedding model/i);
    await fireEvent.change(select, { target: { value: "openai:text-embedding-3-small" } });
    await fireEvent.click(screen.getByRole("button", { name: /embed 6/i }));

    expect(asked[0]).toContain("Send 4 approved memories");
    expect(asked[0]).toContain("to openai");
    // Refused, so nothing ran.
    expect(screen.queryByText(/Embedded 4 memories/)).not.toBeInTheDocument();
  });

  it("reports the owner's chosen space to the runtime", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory/settings": settings({
        spaces: [{ model: "openai:text-embedding-3-small", dimensions: 1536 }],
      }),
      "PUT /api/memory/embedding-backend": { ok: true },
    });
    render(MemoryEngine);

    const select = await screen.findByLabelText("Recall backend");
    await fireEvent.change(select, { target: { value: "openai:text-embedding-3-small" } });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/embedding-backend",
        expect.objectContaining({ method: "PUT" }),
      ),
    );
  });

  it("says there is nothing to embed rather than offering an empty build", async () => {
    stubFetch({ "GET /api/memory/settings": settings({ embedding_providers: [] }) });
    render(MemoryEngine);

    await waitFor(() =>
      expect(screen.getByText(/Nothing is waiting to be embedded/)).toBeInTheDocument(),
    );
    expect(screen.queryByLabelText(/embedding model/i)).not.toBeInTheDocument();
  });
});
