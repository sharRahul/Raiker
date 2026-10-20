/*
 * DW-02 / DW-07 / DW-11 — the Documents workspace: open a design, edit it by
 * typed operations against the version on screen, review an agent proposal
 * before anything applies, and hand a frame to Build as context.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import DesignDocuments from "./DesignDocuments.svelte";
import { stubFetch } from "../test-helpers";
import { pendingDesignHandoff, takeDesignHandoff } from "../designHandoff.svelte";

function view(nodes: unknown[], version = 2, extra: Record<string, unknown> = {}) {
  return {
    document_id: "ddoc_1",
    title: "Launch post",
    project_id: null,
    system_id: null,
    system_version: null,
    current_version: version,
    content_hash: "h",
    frame_count: 1,
    created_at: "2026-10-19T10:00:00Z",
    updated_at: "2026-10-19T10:00:00Z",
    deleted_at: null,
    can_undo: version > 1,
    can_redo: false,
    document: {
      schema: 1,
      frames: [
        {
          id: "frame-1", name: "Frame 1", preset: "social_square", width: 1080, height: 1080,
          background: "#ffffff", grid: { size: 8, visible: false }, variant_of: null, nodes,
        },
      ],
    },
    ...extra,
  };
}

const TITLE = {
  id: "title", type: "text", name: "Headline", x: 40, y: 40, w: 600, h: 80, rotation: 0, visible: true,
  locked: false, opacity: 1, created_by: "owner", text: "Launch day", color: "#111111", font_family: "sans-serif",
  font_size: 48, font_weight: 700, align: "left", line_height: 1.2,
};

function routes(extra: Record<string, unknown> = {}) {
  return {
    "GET /api/design/documents": {
      documents: [{ ...view([TITLE]), document: undefined }],
      deleted: [],
      presets: [{ preset: "social_square", label: "Social post (square)", width: 1080, height: 1080 }],
    },
    "GET /api/design/documents/ddoc_1": view([TITLE]),
    "GET /api/images": { sizes: [], sized_providers: [], generations: [], deleted: [], operations: {} },
    "GET /api/models": {
      profiles: [
        { profile_id: "anthropic-hosted", provider: "anthropic", model: "claude-haiku-5-5", connection_configured: true, off_machine: true },
      ],
      selected_profile_id: null,
    },
    "GET /api/design/systems": { systems: [] },
    "GET /api/design/documents/ddoc_1/proposals": { proposals: [] },
    ...extra,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  takeDesignHandoff();
});

async function openLaunch() {
  render(DesignDocuments);
  await fireEvent.click(await screen.findByRole("button", { name: /Launch post/ }));
  await screen.findByRole("application", { name: /Canvas: Frame 1/ });
}

describe("the Documents workspace", () => {
  it("draws the document as layers and edits them as operations against the version on screen", async () => {
    const fetch = stubFetch(
      routes({
        "POST /api/design/documents/ddoc_1/operations": {
          ok: true, version: 3, rebased: false, summary: ["changed Headline"],
          document: view([{ ...TITLE, x: 41 }], 3),
        },
      }),
    );
    await openLaunch();
    expect(screen.getByText("Launch day")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: /^Headline/ }));
    const canvas = screen.getByRole("application", { name: /Headline selected/ });
    await fireEvent.keyDown(canvas, { key: "ArrowRight" });
    await waitFor(() => expect(screen.getByText("v3")).toBeInTheDocument());
    const sent = fetch.mock.calls.find(([url, init]) => String(url).endsWith("/operations") && init?.method === "POST");
    expect(JSON.parse(String(sent![1]!.body))).toEqual({
      base_version: 2,
      operations: [{ op: "update_node", node_id: "title", set: { x: 41, y: 40 } }],
    });
  });

  it("says a conflict in words and reloads instead of writing over later work", async () => {
    stubFetch(
      routes({
        "POST /api/design/documents/ddoc_1/operations": {
          __status: 409, detail: { reason_code: "design_version_conflict:title" },
        },
      }),
    );
    await openLaunch();
    await fireEvent.click(screen.getByRole("button", { name: /^Headline/ }));
    await fireEvent.keyDown(screen.getByRole("application"), { key: "ArrowDown" });
    expect(await screen.findByRole("alert")).toHaveTextContent(/changed since you loaded it/);
  });

  it("shows an agent proposal as a list to accept, and applies nothing on its own", async () => {
    const fetch = stubFetch(
      routes({
        "POST /api/design/documents/ddoc_1/proposals": {
          proposal_id: "dprop_1", document_id: "ddoc_1", base_version: 2, frame_id: "frame-1", brief: "Bolder",
          provider: "anthropic", model: "claude-haiku-5-5", status: "pending", result: null,
          created_at: "2026-10-19T10:00:00Z", decided_at: null,
          plan: { summary: "A bolder headline", hierarchy: [], assumptions: ["The date stays"], assets: [], validation: [] },
          operations: [
            { index: 0, operation: {}, status: "valid", reason_code: null, summary: "changed Headline", touched: ["title"] },
            { index: 1, operation: {}, status: "refused", reason_code: "outside_target_frame", summary: "add_node", touched: [] },
          ],
        },
      }),
    );
    await openLaunch();
    await fireEvent.click(screen.getByRole("tab", { name: "Agent" }));
    await fireEvent.input(screen.getByLabelText("Brief for the agent"), { target: { value: "Bolder" } });
    await fireEvent.click(screen.getByRole("button", { name: "Propose changes" }));
    expect(await screen.findByText("A bolder headline")).toBeInTheDocument();
    expect(screen.getByText(/refused: outside_target_frame/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "changed Headline" })).toBeChecked();
    expect(fetch.mock.calls.some(([url]) => String(url).includes("/decision"))).toBe(false);
  });

  it("hands a frame to Build as an attachment its composer will carry", async () => {
    stubFetch(
      routes({
        "GET /api/design/documents/ddoc_1/validation": {
          outcome: "passed", validator_version: "design-validate/1", document_hash: "h", version: 2, checks: [],
        },
        "GET /api/design/documents/ddoc_1/exports": { exports: [] },
        "GET /api/design/documents/ddoc_1/handoffs": { handoffs: [] },
        "POST /api/design/documents/ddoc_1/handoff": {
          handoff_id: "dhand_1", document_id: "ddoc_1", version: 2, frame_ids: ["frame-1"], target: "",
          attachment_id: "att_1", sha256: "s", created_at: "2026-10-19T10:00:00Z",
          filename: "design-handoff-launch-post-v2.md", media_type: "text/markdown", byte_size: 900,
        },
      }),
    );
    await openLaunch();
    await fireEvent.click(screen.getByRole("tab", { name: "Export" }));
    await fireEvent.click(await screen.findByRole("button", { name: "Hand to Build" }));
    expect(await screen.findByText(/Ready in Build's composer/)).toBeInTheDocument();
    expect(pendingDesignHandoff()).toMatchObject({ kind: "document", attachmentId: "att_1", mediaType: "text/markdown" });
  });

  it("selects several layers with Shift and aligns them as one change", async () => {
    const BOX = { ...TITLE, id: "box", type: "rect", name: "Box", x: 300, y: 500, w: 100, h: 100, fill: "#cccccc" };
    const fetch = stubFetch(
      routes({
        "GET /api/design/documents/ddoc_1": view([TITLE, BOX]),
        "POST /api/design/documents/ddoc_1/operations": {
          ok: true, version: 3, rebased: false, summary: ["changed Box"],
          document: view([TITLE, { ...BOX, x: 40 }], 3),
        },
      }),
    );
    await openLaunch();
    await fireEvent.click(screen.getByRole("button", { name: "text Headline" }));
    await fireEvent.click(screen.getByRole("button", { name: "rect Box" }), { shiftKey: true });
    const panel = await screen.findByRole("region", { name: "Selected layers" });
    expect(panel).toHaveTextContent("2 layers selected");
    expect(screen.getByRole("button", { name: "Distribute across" })).toBeDisabled();
    await fireEvent.click(screen.getByRole("button", { name: "Align left" }));
    await waitFor(() => expect(screen.getByText("v3")).toBeInTheDocument());
    const sent = fetch.mock.calls.find(([url, init]) => String(url).endsWith("/operations") && init?.method === "POST");
    expect(JSON.parse(String(sent![1]!.body)).operations).toEqual([
      { op: "update_node", node_id: "box", set: { x: 40 } },
    ]);
  });

  it("says when a proposal's outcome is unknown and offers to ask again", async () => {
    stubFetch(
      routes({
        "GET /api/design/documents/ddoc_1/proposals": {
          proposals: [{
            proposal_id: "dprop_1", document_id: "ddoc_1", base_version: 2, frame_id: "frame-1", brief: "A caption",
            provider: "anthropic-hosted", model: "claude-haiku-5-5", status: "outcome_unknown",
            result: { host_run: "old" }, created_at: "2026-10-19T10:00:00Z", decided_at: null,
            plan: {}, operations: [],
          }],
        },
      }),
    );
    await openLaunch();
    await fireEvent.click(screen.getByRole("tab", { name: "Agent" }));
    expect(await screen.findByText(/whether the provider answered is not known/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept selected" })).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "Ask again with this brief" }));
    expect(screen.getByLabelText("Brief for the agent")).toHaveValue("A caption");
  });
});
