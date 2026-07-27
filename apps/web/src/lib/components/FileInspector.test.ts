// The file inspector is a reading surface for a file already attached to the
// chat. What has to hold: it is a complementary landmark (the transcript stays
// reachable), it renders each preview kind as inert content, it never executes
// document markup, and every failure mode says something rather than showing an
// empty pane.
import { render, screen } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { describe, expect, it, vi } from "vitest";
import type { AttachmentPreview } from "../apiTypes";
import FileInspector from "./FileInspector.svelte";

function preview(overrides: Partial<AttachmentPreview> = {}): AttachmentPreview {
  return {
    attachment_id: "att_1",
    session_id: "sess_1",
    filename: "notes.md",
    media_type: "text/markdown",
    kind: "markdown",
    byte_size: 12,
    text: "# Title",
    rows: [],
    truncated: false,
    pdf_url: null,
    unavailable_reason: null,
    ...overrides,
  };
}

function open(props: Record<string, unknown> = {}) {
  return render(FileInspector, {
    props: { preview: preview(), filename: "notes.md", onclose: () => {}, ...props },
  });
}

describe("FileInspector", () => {
  it("is a labelled complementary landmark, not a modal dialog", async () => {
    open();
    expect(await screen.findByRole("complementary", { name: /file preview/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("moves focus to its close control and closes on Escape", async () => {
    const onclose = vi.fn();
    open({ onclose });
    const close = await screen.findByRole("button", { name: /close file preview/i });
    await vi.waitFor(() => expect(document.activeElement).toBe(close));
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it("closes when the close button is pressed", async () => {
    const onclose = vi.fn();
    open({ onclose });
    await fireEvent.click(await screen.findByRole("button", { name: /close file preview/i }));
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it("renders Markdown through the escape-first renderer", async () => {
    open({
      preview: preview({ text: "# Title\n\n<script>alert(1)</script>" }),
    });
    expect(await screen.findByRole("heading", { name: "Title" })).toBeInTheDocument();
    // The document's markup is shown as characters, never executed as a tag.
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });

  it("renders plain text as text", async () => {
    open({
      preview: preview({
        filename: "notes.txt",
        media_type: "text/plain",
        kind: "text",
        text: "line one\nline two",
      }),
      filename: "notes.txt",
    });
    expect(await screen.findByText(/line one/)).toBeInTheDocument();
  });

  it("renders spreadsheet rows as a table", async () => {
    open({
      preview: preview({
        filename: "report.xlsx",
        media_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        kind: "table",
        text: "",
        rows: [
          ["Quarterly report", "Owner"],
          ["Revenue", "42"],
        ],
      }),
      filename: "report.xlsx",
    });
    expect(await screen.findByText("Quarterly report")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("shows a PDF in the browser's own viewer once its blob URL is ready", async () => {
    const { rerender } = open({
      preview: preview({
        filename: "doc.pdf",
        media_type: "application/pdf",
        kind: "pdf",
        text: "",
        pdf_url: "/api/sessions/sess_1/attachments/att_1/preview/pdf",
      }),
      filename: "doc.pdf",
    });
    expect(await screen.findByRole("status")).toHaveTextContent(/loading the pdf/i);
    await rerender({
      preview: preview({
        filename: "doc.pdf",
        media_type: "application/pdf",
        kind: "pdf",
        text: "",
        pdf_url: "/api/sessions/sess_1/attachments/att_1/preview/pdf",
      }),
      filename: "doc.pdf",
      pdfObjectUrl: "blob:doc",
      onclose: () => {},
    });
    const object = document.querySelector("object");
    expect(object).not.toBeNull();
    expect(object?.getAttribute("data")).toBe("blob:doc");
    expect(object?.getAttribute("type")).toBe("application/pdf");
  });

  it("states why an unsupported file cannot be shown, keeping the reason code", async () => {
    open({
      preview: preview({
        filename: "shot.png",
        media_type: "image/png",
        kind: "unavailable",
        text: "",
        unavailable_reason: "unsupported_for_preview",
      }),
      filename: "shot.png",
    });
    expect(await screen.findByText(/cannot preview this kind of file/i)).toBeInTheDocument();
    expect(screen.getByText("unsupported_for_preview")).toBeInTheDocument();
  });

  it("falls back to a plain statement for an unknown reason code", async () => {
    open({
      preview: preview({
        kind: "unavailable",
        text: "",
        unavailable_reason: "something_new",
      }),
    });
    expect(await screen.findByText(/cannot be previewed/i)).toBeInTheDocument();
    expect(screen.getByText("something_new")).toBeInTheDocument();
  });

  it("says it is loading before the preview arrives", async () => {
    open({ preview: null, loading: true, filename: "report.xlsx" });
    expect(await screen.findByRole("status")).toHaveTextContent(/opening report\.xlsx/i);
  });

  it("reports a failed read instead of an empty pane", async () => {
    open({ preview: null, error: "Could not open this file." });
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not open this file.");
  });

  it("says when only the beginning of a file is shown", async () => {
    open({ preview: preview({ truncated: true }) });
    expect(await screen.findByText(/beginning of this file only/i)).toBeInTheDocument();
  });

  it("offers no upload, download, or mutation control", async () => {
    open({ preview: preview({ truncated: true }) });
    await screen.findByRole("complementary", { name: /file preview/i });
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveAccessibleName(/close file preview/i);
    expect(document.querySelector("input")).toBeNull();
    expect(document.querySelector("a[download]")).toBeNull();
  });
});
