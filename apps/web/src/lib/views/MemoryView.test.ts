// Reliable memory controls (backlog item 3): the Memory view lists approved
// memories with governance metadata, supports pin/bookmark, forget, and an
// incognito opt-out toggle.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import MemoryView from "./MemoryView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MemoryView", () => {
  it("shows a route-level loading state while memories are fetched", async () => {
    stubFetchPending();
    render(MemoryView);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/loading memories/i);
  });

  it("shows a route-level error state when memories cannot load", async () => {
    stubFetch({});
    render(MemoryView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load memories/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("lists memories with provenance and sensitivity", async () => {
    stubFetch({
      "GET /api/memory": [
        {
          memory_id: "mem_1",
          text: "The user prefers tabs over spaces.",
          scope: "project:alpha",
          sensitivity: "normal",
          memory_type: "project",
          created_at: "2026-07-12T00:00:00Z",
          tags: ["style"],
          source: "agent",
          provenance: { source_session_id: "sess_x" },
          confidence: 0.9,
          trust_score: 0.8,
          retention: "until_forget",
          approval_state: "approved",
          pinned: false,
          search_enabled: true,
          expires_at: null,
        },
      ],
      "GET /api/memory/settings": { incognito: false },
    });
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText("The user prefers tabs over spaces.")).toBeInTheDocument(),
    );
    expect(screen.getByText("project:alpha scope")).toBeInTheDocument();
    expect(screen.getByText(/normal sensitivity/i)).toBeInTheDocument();
    expect(screen.getByText(/confidence: 0.90/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no memories", async () => {
    stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": { incognito: false },
    });
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText(/no approved memories yet/i)).toBeInTheDocument(),
    );
  });

  it("states how recall scales without implying an unearned warm cache", async () => {
    stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": {
        incognito: false,
        vector_search_strategy: "exact_then_approximate",
        vector_search_exact_limit: 512,
      },
    });
    render(MemoryView);

    expect(await screen.findByText(/recall keeps a revision-checked index/i)).toBeInTheDocument();
    expect(screen.getByText(/exact score re-ranking/i)).toBeInTheDocument();
  });

  it("distinguishes a permission check in progress from a failed permission read", async () => {
    stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": { incognito: false },
      "GET /api/capability-gates": [{
        capability: "memory_write_execution",
        state: "disabled",
        decision_mode: "ask",
      }],
    });
    render(MemoryView);

    expect(await screen.findByText(/memory store is off/i)).toBeInTheDocument();
    expect(screen.queryByText(/could not read your memory permissions/i)).not.toBeInTheDocument();
  });

  it("reviews governed proposals directly on the Memory page", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": { incognito: false },
      "GET /api/memory/proposals": [{
        candidate_id: "memcand_1",
        source_event_id: "evt_1",
        memory_type: "project",
        scope: "project:alpha",
        text: "Prefer concise answers",
        sensitivity: "normal",
        confidence: 0.8,
        decision: "deferred",
        created_at: "2026-07-12T00:00:00Z",
      }],
      "POST /api/memory/proposals/memcand_1/decision": {
        ok: true, candidate_id: "memcand_1", decision: "approved", memory_id: "mem_1",
      },
    });
    render(MemoryView);
    await waitFor(() => expect(screen.getByText("Prefer concise answers")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: /^approve$/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/memory/proposals/memcand_1/decision",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("reviews extracted relationships with visible evidence", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": { incognito: false },
      "GET /api/memory/relationship-proposals": [{
        candidate_id: "relcand_1",
        subject_name: "Rahul",
        subject_type: "person",
        predicate: "works_on",
        object_name: "Raiker",
        object_type: "project",
        evidence_memory_id: "mem_evidence",
        evidence_text: "Rahul works on Raiker.",
        confidence: 0.97,
        extractor_version: "memory-entity-rules-v1",
        decision: "needs_user_review",
        created_at: "2026-08-21T00:00:00Z",
      }],
      "POST /api/memory/relationship-proposals/relcand_1/decision": {
        ok: true,
        candidate_id: "relcand_1",
        decision: "approved",
        relationship_id: "rel_1",
      },
    });
    render(MemoryView);

    expect(await screen.findByText("Rahul works on Raiker.")).toBeInTheDocument();
    expect(screen.getByText(/97% confidence/i)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: /approve relationship/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/memory/relationship-proposals/relcand_1/decision",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("toggles incognito and reflects the new state", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": { incognito: false },
      "PUT /api/memory/incognito": { ok: true, incognito: true },
    });
    render(MemoryView);

    await waitFor(() => expect(screen.getByRole("switch", { name: /incognito session/i })).toHaveAttribute("aria-checked", "false"));
    await fireEvent.click(screen.getByRole("switch", { name: /incognito session/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/incognito",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ incognito: true }),
        }),
      );
    });
  });

  it("pins and forgets a memory through the governed API", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = stubFetch({
      "GET /api/memory": [
        {
          memory_id: "mem_1",
          text: "remember this",
          scope: "project:alpha",
          sensitivity: "normal",
          memory_type: "project",
          created_at: "2026-07-12T00:00:00Z",
          tags: [],
          source: "agent",
          provenance: {},
          confidence: 0.5,
          trust_score: 0.5,
          retention: "until_forget",
          approval_state: "approved",
          pinned: false,
          search_enabled: true,
          expires_at: null,
        },
      ],
      "GET /api/memory/settings": { incognito: false },
      "PUT /api/memory/mem_1/pin": { ok: true, memory_id: "mem_1", pinned: true },
      "DELETE /api/memory/mem_1": { ok: true, memory_id: "mem_1" },
    });
    render(MemoryView);

    await waitFor(() => expect(screen.getByText("remember this")).toBeInTheDocument());
    const pinBtn = screen.getByRole("button", { name: /pin memory/i });
    await fireEvent.click(pinBtn);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/mem_1/pin",
        expect.objectContaining({ method: "PUT" }),
      ),
    );

    const forgetBtn = screen.getByRole("button", { name: /forget memory/i });
    await fireEvent.click(forgetBtn);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/mem_1",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });

  it("edits a memory and keeps import and export in advanced management", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory": [
        {
          memory_id: "mem_1",
          text: "remember this",
          scope: "project:alpha",
          sensitivity: "normal",
          memory_type: "project",
          created_at: "2026-07-12T00:00:00Z",
          tags: [],
          source: "agent",
          provenance: {},
          confidence: 0.5,
          trust_score: 0.5,
          retention: "until_forget",
          approval_state: "approved",
          pinned: false,
          search_enabled: true,
          expires_at: null,
        },
      ],
      "GET /api/memory/settings": { incognito: false },
      "PUT /api/memory/mem_1": { ok: true, memory_id: "mem_1" },
      "PUT /api/memory/mem_1/search": { ok: true, memory_id: "mem_1", search_enabled: false },
      "PUT /api/memory/mem_1/expiry": { ok: true, memory_id: "mem_1", expires_at: "2030-01-01T00:00:00Z" },
      "GET /api/memory/export": { ok: true, memories: [{ text: "remember this" }] },
      "POST /api/memory/import": { ok: true, count: 1 },
    });
    render(MemoryView);

    await waitFor(() => expect(screen.getByText("remember this")).toBeInTheDocument());

    await fireEvent.click(screen.getByRole("button", { name: /edit memory/i }));
    await fireEvent.input(screen.getByLabelText(/memory text/i), { target: { value: "updated" } });
    await fireEvent.click(screen.getByRole("button", { name: /^save memory$/i }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/mem_1",
        expect.objectContaining({ method: "PUT", body: JSON.stringify({ text: "updated" }) }),
      ),
    );

    expect(screen.getByText(/advanced memory management/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/memory export json/i)).not.toBeInTheDocument();
  });
});

// BUG-244 — an import used to report the number of records in the file and
// write every one of them, so re-importing the same file made a second copy of
// every sentence and said "4 records" both times. Recall is budgeted: four
// copies of one sentence occupy four of the slots a turn has for remembering
// anything, which is how this was noticed at all.
describe("MemoryView import review (BUG-244)", () => {
  const base = {
    "GET /api/memory": [],
    "GET /api/memory/settings": { incognito: false },
  };

  /**
   * Choose a file in the Review import control.
   *
   * jsdom's `File` has no `Blob.prototype.text()`, which every browser Raiker
   * runs in has had since 2019 — so the shim is the harness catching up to the
   * platform, not the product working around it.
   */
  async function chooseFile(records: Array<{ text: string }>) {
    // Scoped to Advanced management: the document library on the same page has
    // file inputs of its own, and the first one on the page is one of those.
    const input = document.querySelector<HTMLInputElement>('.file-button input[type="file"]');
    expect(input).not.toBeNull();
    const body = JSON.stringify({ memories: records });
    const file = new File([body], "memories.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: async () => body, configurable: true });
    Object.defineProperty(input!, "files", { value: [file], configurable: true });
    await fireEvent.change(input!);
  }

  it("says how many records are new before anything is written", async () => {
    const fetchMock = stubFetch({
      ...base,
      "POST /api/memory/import/preview": {
        ok: true,
        total: 4,
        new_count: 1,
        duplicate_count: 3,
        duplicates: [{ index: 1, text: "already", scope: "project", memory_id: "mem_9" }],
      },
    });
    render(MemoryView);
    await waitFor(() => expect(screen.getByText(/advanced memory management/i)).toBeInTheDocument());

    await chooseFile([{ text: "a" }, { text: "b" }, { text: "c" }, { text: "d" }]);

    // The count that matters is stated before the button that acts on it.
    expect(await screen.findByText("1 new", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/3 already stored, and will be skipped/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Import 1 new record$/ })).toBeInTheDocument();
    // Asking is a read. Nothing was written by choosing the file.
    expect(
      fetchMock.mock.calls.some(([url]) => String(url) === "/api/memory/import"),
    ).toBe(false);
  });

  it("offers no ordinary import when every record is already stored", async () => {
    stubFetch({
      ...base,
      "POST /api/memory/import/preview": {
        ok: true,
        total: 2,
        new_count: 0,
        duplicate_count: 2,
        duplicates: [],
      },
    });
    render(MemoryView);
    await waitFor(() => expect(screen.getByText(/advanced memory management/i)).toBeInTheDocument());

    await chooseFile([{ text: "a" }, { text: "b" }]);

    expect(
      await screen.findByText(/All 2 records are already stored/),
    ).toBeInTheDocument();
    // The deliberate second copy stays available — an owner who means to hold
    // the same sentence at a second scope is doing something legitimate.
    expect(screen.getByRole("button", { name: /Import anyway/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import \d+ new record/ })).toBeNull();
  });

  it("reports what the import changed, not how many records were offered", async () => {
    const fetchMock = stubFetch({
      ...base,
      "POST /api/memory/import/preview": {
        ok: true,
        total: 4,
        new_count: 1,
        duplicate_count: 3,
        duplicates: [],
      },
      "POST /api/memory/import": {
        ok: true,
        count: 1,
        reviewed: 4,
        imported: 1,
        skipped_duplicates: 3,
        relationship_proposals: 0,
      },
    });
    render(MemoryView);
    await waitFor(() => expect(screen.getByText(/advanced memory management/i)).toBeInTheDocument());

    await chooseFile([{ text: "a" }, { text: "b" }, { text: "c" }, { text: "d" }]);
    await fireEvent.click(await screen.findByRole("button", { name: /Import 1 new record$/ }));

    expect(
      await screen.findByText("Imported 1 record; skipped 3 already stored."),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url) === "/api/memory/import" &&
          String((init as RequestInit | undefined)?.body).includes('"skip_duplicates":true'),
      ),
    ).toBe(true);
  });
});

// MEM-04 — the Observations section. The assertions worth having are the three
// that make an empty list readable: a refusal that says so, a failed read that
// is told apart from "nothing captured", and a delete that reaches the server.
describe("MemoryView observations (MEM-04)", () => {
  const memoryFixtures = {
    "GET /api/memory": [],
    "GET /api/memory/settings": { incognito: false },
  };

  it("lists what was captured, with its retention and expiry", async () => {
    stubFetch({
      ...memoryFixtures,
      "GET /api/memory/observations": {
        ok: true,
        captured: 1,
        skipped: 0,
        gists_pending: 0,
        observations: [
          {
            observation_id: "obs_1",
            session_id: "sess_1",
            turn_id: "turn_1",
            tool_name: "read_file",
            source_type: "workspace_file",
            summary: "read_file — docs/runbook.md",
            sensitivity: "project",
            retention: "short_term_30_days",
            capture_status: "captured",
            skip_reason: "",
            promotable_to_memory: true,
            content_sha256: "a".repeat(64),
            content_bytes: 4096,
            artifact_ref: null,
            source_event_id: "evt_1",
            created_at: "2026-08-17T00:00:00Z",
            expires_at: "2026-09-16T00:00:00Z",
            gist_status: "",
            gist_summary: "",
            gist_id: "",
          },
        ],
      },
    });
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText("read_file — docs/runbook.md")).toBeInTheDocument(),
    );
    expect(screen.getAllByText("workspace file").length).toBeGreaterThan(0);
    expect(screen.getByText("Kept 30 days")).toBeInTheDocument();
    expect(screen.getByText(/1 captured · 0 not captured/)).toBeInTheDocument();
    expect(screen.getByText(/aaaaaaaaaaaa… · 4096 bytes/)).toBeInTheDocument();
  });

  it("says when a capture was refused on sensitivity, and keeps no checksum", async () => {
    stubFetch({
      ...memoryFixtures,
      "GET /api/memory/observations": {
        ok: true,
        captured: 0,
        skipped: 1,
        gists_pending: 0,
        observations: [
          {
            observation_id: "obs_2",
            session_id: "sess_1",
            turn_id: "turn_1",
            tool_name: "read_file",
            source_type: "workspace_file",
            summary: "read_file — .env",
            sensitivity: "credential_like",
            retention: "short_term_30_days",
            capture_status: "skipped",
            skip_reason: "observation_sensitivity_credential_like",
            promotable_to_memory: false,
            content_sha256: "",
            content_bytes: 0,
            artifact_ref: null,
            source_event_id: "evt_2",
            created_at: "2026-08-17T00:00:00Z",
            expires_at: "2026-09-16T00:00:00Z",
            gist_status: "",
            gist_summary: "",
            gist_id: "",
          },
        ],
      },
    });
    render(MemoryView);

    await waitFor(() => expect(screen.getByText("Not captured")).toBeInTheDocument());
    expect(screen.getByText(/refused on sensitivity \(credential like\)/i)).toBeInTheDocument();
    expect(screen.getByText("None kept")).toBeInTheDocument();
  });

  it("tells a failed observation read apart from having captured nothing", async () => {
    stubFetch(memoryFixtures);
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText(/observation capture is not reporting/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/no observations yet/i)).not.toBeInTheDocument();
  });

  it("says plainly when nothing has been captured yet", async () => {
    stubFetch({
      ...memoryFixtures,
      "GET /api/memory/observations": {
        ok: true,
        captured: 0,
        skipped: 0,
        gists_pending: 0,
        observations: [],
      },
    });
    render(MemoryView);

    await waitFor(() => expect(screen.getByText(/no observations yet/i)).toBeInTheDocument());
  });

  it("deletes one observation through the governed route", async () => {
    const fetchMock = stubFetch({
      ...memoryFixtures,
      "GET /api/memory/observations": {
        ok: true,
        captured: 1,
        skipped: 0,
        gists_pending: 0,
        observations: [
          {
            observation_id: "obs_3",
            session_id: "sess_1",
            turn_id: "turn_1",
            tool_name: "create_document",
            source_type: "generated_artifact",
            summary: "create_document — report.md",
            sensitivity: "project",
            retention: "short_term_30_days",
            capture_status: "captured",
            skip_reason: "",
            promotable_to_memory: true,
            content_sha256: "b".repeat(64),
            content_bytes: 200,
            artifact_ref: null,
            source_event_id: "evt_3",
            created_at: "2026-08-17T00:00:00Z",
            expires_at: "2026-09-16T00:00:00Z",
            gist_status: "pending_review",
            gist_summary: "create_document — report.md",
            gist_id: "mem_gist",
          },
        ],
      },
      "POST /api/memory/observations/delete": { ok: true, deleted_observation_ids: ["obs_3"] },
    });
    vi.stubGlobal("confirm", () => true);
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText(/gist proposed and pending review/i)).toBeInTheDocument(),
    );
    await fireEvent.click(screen.getByRole("button", { name: /delete observation obs_3/i }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/observations/delete",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ observation_ids: ["obs_3"] }),
        }),
      ),
    );
  });
  // MEM-10 — the select opposite lists the spaces that already hold vectors, so
  // on a default install the only honest answer it has is the fallback. These
  // two pin the way out of that: the page says what could build a real space,
  // and says how many memories the run would send.
  it("offers to build a meaning-based index when recall is on the fallback", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": {
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
        embedding_providers: [
          {
            profile_id: "raiker-local-llama-cpp",
            provider: "llama.cpp",
            model: "local-gguf",
            space: "llama.cpp:local-gguf",
            local_only: true,
            requires_network: false,
            unindexed_memories: 4,
            unindexed_file_chunks: 2,
            pending_count: 6,
          },
          {
            profile_id: "openai-hosted",
            provider: "openai",
            model: "text-embedding-3-small",
            space: "openai:text-embedding-3-small",
            local_only: false,
            requires_network: true,
            unindexed_memories: 4,
            unindexed_file_chunks: 2,
            pending_count: 6,
          },
        ],
        unindexed_memories: 4,
        unindexed_file_chunks: 2,
      },
      "POST /api/memory/embedding-index": {
        ok: true,
        embedding_model: "openai:text-embedding-3-small",
        indexed_count: 4,
        indexed_file_chunk_count: 2,
        skipped_count: 0,
      },
    });
    vi.stubGlobal("confirm", () => true);
    render(MemoryView);

    const select = await screen.findByLabelText(/embedding model/i);
    expect(
      screen.getByRole("link", { name: /review and download it in models/i }),
    ).toHaveAttribute("href", "#/models?tab=huggingface");
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

  // A semantic *space* and semantic *recall* are two claims. The card said
  // "matches meaning" for the first, which is a recall the runtime does not
  // perform yet — the same defect MEM-03 was raised to remove, one layer in.
  it("says so when the vectors are semantic and the question is not embedded", async () => {
    stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": {
        incognito: false,
        embedding_backend: "auto",
        retrieval: {
          backend_id: "provider",
          kind: "provider",
          model: "openai:text-embedding-3-small",
          dimensions: 1536,
          semantic: true,
          reason_code: "",
          query_embeddable: false,
        },
        spaces: [],
        embedding_providers: [],
        unindexed_memories: 0,
      },
    });
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText(/recall still matches words/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/matches meaning/i)).not.toBeInTheDocument();
  });

  it("offers to refresh an index when semantic recall has new content", async () => {
    stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": {
        incognito: false,
        embedding_backend: "auto",
        retrieval: {
          backend_id: "provider",
          kind: "provider",
          model: "openai:text-embedding-3-small",
          dimensions: 1536,
          semantic: true,
          reason_code: "",
          query_embeddable: true,
        },
        spaces: [],
        embedding_providers: [
          {
            profile_id: "openai-hosted",
            provider: "openai",
            model: "text-embedding-3-small",
            space: "openai:text-embedding-3-small",
            local_only: false,
            requires_network: true,
            unindexed_memories: 1,
            unindexed_file_chunks: 1,
            pending_count: 2,
          },
        ],
        unindexed_memories: 1,
        unindexed_file_chunks: 1,
      },
    });
    render(MemoryView);

    await waitFor(() => expect(screen.getByText(/matches meaning/i)).toBeInTheDocument());
    expect(screen.getByLabelText(/embedding model/i)).toBeInTheDocument();
  });
  // MEM-07 — six retention classes were stored and stated on every row, and
  // nothing ever swept them. There is still no daemon; this is the confirmed
  // sweep that was meant to stand in for one and never got a surface.
  it("says what is due for expiry and runs the confirmed sweep", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": { incognito: false },
      "GET /api/memory/observations": {
        ok: true,
        captured: 1,
        skipped: 0,
        gists_pending: 0,
        due_for_expiry: ["obs_due"],
        observations: [
          {
            observation_id: "obs_due",
            session_id: "sess_1",
            turn_id: "turn_1",
            tool_name: "read_file",
            source_type: "tool_result",
            summary: "read_file — notes.md",
            sensitivity: "normal",
            retention: "short_term_7_days",
            capture_status: "captured",
            skip_reason: "",
            promotable_to_memory: false,
            content_sha256: "c".repeat(64),
            content_bytes: 120,
            artifact_ref: null,
            source_event_id: "evt_1",
            created_at: "2026-01-01T00:00:00Z",
            expires_at: "2026-01-08T00:00:00Z",
            gist_status: "",
            gist_summary: "",
            gist_id: "",
          },
        ],
      },
      "POST /api/memory/eidetic/cleanup": { ok: true, deleted_observation_ids: ["obs_due"] },
    });
    vi.stubGlobal("confirm", () => true);
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText(/1 past their retention class/i)).toBeInTheDocument(),
    );
    await fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/eidetic/cleanup",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ observation_ids: ["obs_due"] }),
        }),
      ),
    );
  });
});
