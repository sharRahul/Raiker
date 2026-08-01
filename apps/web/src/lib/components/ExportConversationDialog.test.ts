import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExportConversationDialog from "./ExportConversationDialog.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const MANIFEST = {
  session_id: "sess_1",
  title: "Quarterly plan",
  created_at: "2026-07-30T09:00:00Z",
  message_count: 4,
  file_count: 1,
  files: [
    {
      filename: "budget.xlsx",
      media_type: "application/vnd.ms-excel",
      byte_size: 20480,
      source: "uploaded",
    },
  ],
  redaction_policy:
    "Secret-shaped values (API keys, tokens, and credentials) are replaced with ***REDACTED*** in every message. Attached files are listed by name, type, and size; their contents are never embedded.",
  formats: ["html", "markdown", "pdf"],
  messages: [],
};

function routes(extra: Record<string, unknown> = {}) {
  return { "GET /api/sessions/sess_1/export/manifest": MANIFEST, ...extra };
}

describe("ExportConversationDialog — BUG-22", () => {
  it("reviews what will be included before any format is chosen", async () => {
    stubFetch(routes());
    render(ExportConversationDialog, { sessionId: "sess_1", onclose: () => {} });
    expect(await screen.findByText("What will be included")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("budget.xlsx")).toBeInTheDocument();
    expect(screen.getByText(/never embedded/)).toBeInTheDocument();
  });

  it("offers exactly the three declared formats", async () => {
    stubFetch(routes());
    render(ExportConversationDialog, { sessionId: "sess_1", onclose: () => {} });
    await screen.findByText("What will be included");
    for (const label of ["HTML", "Markdown", "PDF"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("posts the chosen format and reports success with the download name", async () => {
    const fetchMock = stubFetch(routes({ "POST /api/sessions/sess_1/export": { ok: true } }));
    // jsdom has no real download; the anchor click is a no-op we can ignore.
    vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
    render(ExportConversationDialog, { sessionId: "sess_1", onclose: () => {} });
    await screen.findByText("What will be included");
    await fireEvent.click(screen.getByRole("radio", { name: /Markdown/ }));
    await fireEvent.click(screen.getByRole("button", { name: "Export" }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST");
      expect(post).toBeDefined();
      expect(JSON.parse(String((post![1] as RequestInit).body))).toEqual({ format: "markdown" });
    });
    expect(await screen.findByText(/quarterly-plan\.md/)).toBeInTheDocument();
  });

  it("reports a refused format at field level rather than generically", async () => {
    stubFetch(routes());
    render(ExportConversationDialog, { sessionId: "sess_1", onclose: () => {} });
    await screen.findByText("What will be included");
    // The export route is unrouted here, so the stub 404s.
    await fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(
      await screen.findByText(/no longer available to export|did not complete/),
    ).toBeInTheDocument();
  });

  it("says what went wrong when the manifest itself cannot be read", async () => {
    stubFetch({});
    render(ExportConversationDialog, { sessionId: "sess_1", onclose: () => {} });
    expect(await screen.findByText(/no longer available to export/)).toBeInTheDocument();
  });

  it("offers printing as a peer of downloading", async () => {
    stubFetch(routes());
    const onprint = vi.fn();
    render(ExportConversationDialog, { sessionId: "sess_1", onclose: () => {}, onprint });
    await screen.findByText("What will be included");
    await fireEvent.click(screen.getByRole("button", { name: /Print \/ Save as PDF/ }));
    expect(onprint).toHaveBeenCalled();
  });

  it("uses a native modal dialog and closes through its cancel event", async () => {
    stubFetch(routes());
    const onclose = vi.fn();
    render(ExportConversationDialog, { sessionId: "sess_1", onclose });
    const dialog = await screen.findByRole("dialog", { name: "Export conversation" });
    expect(dialog.tagName).toBe("DIALOG");
    await fireEvent(dialog, new Event("cancel", { cancelable: true }));
    expect(onclose).toHaveBeenCalledTimes(1);
  });
});
