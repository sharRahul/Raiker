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
});
