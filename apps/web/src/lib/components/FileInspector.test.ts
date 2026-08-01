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
    image_url: null,
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
      objectUrl: "blob:doc",
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
        filename: "archive.zip",
        media_type: "application/zip",
        kind: "unavailable",
        text: "",
        unavailable_reason: "unsupported_for_preview",
      }),
      filename: "archive.zip",
    });
    expect(await screen.findByText(/cannot preview this kind of file/i)).toBeInTheDocument();
    expect(screen.getByText("unsupported_for_preview")).toBeInTheDocument();
  });

  it("refuses to display a picture whose bytes do not match its type", async () => {
    // The server sends this rather than image bytes; the pane must explain it
    // instead of rendering a broken-image icon.
    open({
      preview: preview({
        filename: "shot.png",
        media_type: "image/png",
        kind: "unavailable",
        text: "",
        unavailable_reason: "content_does_not_match_media_type",
      }),
      filename: "shot.png",
    });
    expect(await screen.findByText(/contents do not match the type/i)).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
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

  it("shows an image once its blob URL is ready, described by its filename", async () => {
    const imagePreview = preview({
      filename: "shot.png",
      media_type: "image/png",
      kind: "image",
      text: "",
      image_url: "/api/sessions/sess_1/attachments/att_1/preview/image",
    });
    const { rerender } = open({ preview: imagePreview, filename: "shot.png" });
    expect(await screen.findByRole("status")).toHaveTextContent(/loading the image/i);
    await rerender({
      preview: imagePreview,
      filename: "shot.png",
      objectUrl: "blob:shot",
      onclose: () => {},
    });
    const image = await screen.findByRole("img", { name: "shot.png" });
    expect(image).toHaveAttribute("src", "blob:shot");
  });

  it("offers no upload or mutation control, and no download unless one is wired", async () => {
    open({ preview: preview({ truncated: true }) });
    await screen.findByRole("complementary", { name: /file preview/i });
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveAccessibleName(/close file preview/i);
    expect(document.querySelector("input")).toBeNull();
    expect(document.querySelector("a[download]")).toBeNull();
  });

  // ── BUG-26: looking at a picture, not just seeing it ─────────────────────

  describe("image inspection", () => {
    function openImage(props: Record<string, unknown> = {}) {
      return open({
        preview: preview({
          filename: "shot.png",
          media_type: "image/png",
          kind: "image",
          text: "",
          image_url: "/api/sessions/sess_1/attachments/att_1/preview/image",
        }),
        filename: "shot.png",
        objectUrl: "blob:shot",
        ...props,
      });
    }

    it("exposes labelled zoom, fit, rotate and reset controls with the current level", async () => {
      openImage();
      for (const name of [/zoom in/i, /zoom out/i, /fit to pane/i, /rotate right/i, /reset the view/i]) {
        expect(await screen.findByRole("button", { name })).toBeInTheDocument();
      }
      expect(screen.getByText("100%")).toBeInTheDocument();
    });

    it("zooms the picture without touching the stored file", async () => {
      openImage();
      const image = await screen.findByRole("img", { name: "shot.png" });
      const before = image.getAttribute("src");
      await fireEvent.click(screen.getByRole("button", { name: /zoom in/i }));
      expect(screen.getByText("125%")).toBeInTheDocument();
      expect(image.getAttribute("style")).toContain("scale(1.25)");
      // The bytes on screen are the same bytes: this is a way of looking.
      expect(image.getAttribute("src")).toBe(before);
    });

    it("resets back to the picture as it arrived", async () => {
      openImage();
      await fireEvent.click(screen.getByRole("button", { name: /zoom in/i }));
      await fireEvent.click(screen.getByRole("button", { name: /rotate right/i }));
      await fireEvent.click(screen.getByRole("button", { name: /reset the view/i }));
      expect(screen.getByText("100%")).toBeInTheDocument();
      const image = await screen.findByRole("img", { name: "shot.png" });
      expect(image.getAttribute("style")).toContain("scale(1) rotate(0deg)");
    });

    it("is operable from the keyboard on the picture itself", async () => {
      openImage();
      const frame = await screen.findByRole("application");
      await fireEvent.keyDown(frame, { key: "+" });
      expect(screen.getByText("125%")).toBeInTheDocument();
      await fireEvent.keyDown(frame, { key: "-" });
      expect(screen.getByText("100%")).toBeInTheDocument();
      await fireEvent.keyDown(frame, { key: "r" });
      const image = screen.getByRole("img", { name: "shot.png" });
      expect(image.getAttribute("style")).toContain("rotate(90deg)");
    });
  });

  // ── BUG-27: opening a record at the passage it came from ─────────────────

  describe("source passage", () => {
    const source = (overrides: Record<string, unknown> = {}) => ({
      status: "resolved" as const,
      kind: "conversation",
      title: "Weekly planning",
      excerpt: "before the passage and after",
      highlight_start: 7,
      highlight_length: 11,
      session_id: "sess_9",
      turn_id: "turn_9",
      attachment_id: "",
      truncated: false,
      resolution_method: "stored_coordinates",
      ...overrides,
    });

    it("marks the passage inside its surrounding text and links to the conversation", async () => {
      open({ preview: null, source: source() });
      const mark = document.querySelector("mark");
      expect(mark).not.toBeNull();
      expect(mark?.textContent).toBe("the passage");
      expect(await screen.findByRole("link", { name: /open conversation/i })).toHaveAttribute(
        "href",
        "#/new-chat?session=sess_9",
      );
      expect(screen.getByText("Verified from stored coordinates")).toBeInTheDocument();
    });

    it("labels a legacy best-effort text match", async () => {
      open({ preview: null, source: source({ resolution_method: "matching_text" }) });
      expect(await screen.findByText("Located by matching text")).toBeInTheDocument();
    });

    it("says a source was deleted rather than showing an empty pane", async () => {
      open({ preview: null, source: source({ status: "source_deleted", excerpt: "" }) });
      expect(await screen.findByText(/has been deleted/i)).toBeInTheDocument();
      expect(document.querySelector("mark")).toBeNull();
    });

    it("shows a changed source without pretending to have found the passage", async () => {
      open({
        preview: null,
        source: source({ status: "source_changed", highlight_start: -1, highlight_length: 0 }),
      });
      expect(await screen.findByText(/no longer contains this passage/i)).toBeInTheDocument();
      expect(document.querySelector("mark")?.textContent).toBe("");
    });

    it("states a record that never stored where it came from", async () => {
      open({ preview: null, source: source({ status: "no_provenance", excerpt: "", title: "" }) });
      expect(await screen.findByText(/did not store where it came from/i)).toBeInTheDocument();
    });

    it("states a source this account may not read", async () => {
      open({ preview: null, source: source({ status: "not_authorized", excerpt: "", title: "" }) });
      expect(await screen.findByText(/cannot read the source/i)).toBeInTheDocument();
    });
  });

  // ── BUG-28: taking the file away ─────────────────────────────────────────

  describe("download", () => {
    it("offers Download beside Close when a download is wired, and calls it", async () => {
      const ondownload = vi.fn();
      open({ preview: preview(), ondownload });
      const button = await screen.findByRole("button", { name: /download notes\.md/i });
      await fireEvent.click(button);
      expect(ondownload).toHaveBeenCalledTimes(1);
    });

    it("reports its progress and never claims a refused download succeeded", async () => {
      const { rerender } = open({ preview: preview(), ondownload: () => {}, downloadState: "working" });
      expect(await screen.findByText(/downloading/i)).toBeInTheDocument();
      await rerender({
        preview: preview(),
        filename: "notes.md",
        onclose: () => {},
        ondownload: () => {},
        downloadState: "idle",
        downloadError: "This account is not permitted to download this file.",
      });
      expect(await screen.findByRole("alert")).toHaveTextContent(/not permitted/i);
      expect(screen.queryByText(/downloaded$/i)).not.toBeInTheDocument();
    });
  });
});
