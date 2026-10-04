/**
 * UX-CHAT-01 — the file and source inspector, out of ChatView.
 *
 * One state machine with one owner: which file or cited source the right-hand
 * pane shows, its preview and the object URL behind it, the provenance read,
 * the turn source ledger the citation chips resolve against, and the two
 * download paths. ChatView used to hold all of it beside its streaming,
 * history, composer and memory state, so a change to any of those could reach
 * into this one by name.
 *
 * Moved, not changed. Every race guard is the one the view had: a second chip
 * clicked while the first is loading wins, a late answer for a file no longer
 * open is dropped, and an object URL is revoked whenever another file opens or
 * the pane closes.
 */
import { api, ApiError } from "../../api";
import type { AttachmentPreview, SourceExcerptView, TurnSourceView } from "../../apiTypes";
import { sentenceAround } from "../../citations";

export class SourceInspector {
  /** What the pane is showing; `attachmentId` is "" for a source with no file here. */
  inspecting = $state<{ attachmentId: string; filename: string } | null>(null);
  preview = $state<AttachmentPreview | null>(null);
  previewLoading = $state(false);
  previewError = $state<string | null>(null);
  /**
   * Object URL for a preview served as bytes (a PDF or an image): neither an
   * <object> nor an <img> can send the bearer token, so the bytes are fetched
   * here and handed over as a blob. Revoked on close and whenever another file
   * is opened — a stale handle keeps the whole file alive in memory.
   */
  objectUrl = $state<string | null>(null);
  /**
   * BUG-27 — where a generated file came from. Resolved on demand, because the
   * answer depends on what is still readable *now*, not on what was true when
   * the file was written.
   */
  source = $state<SourceExcerptView | null>(null);
  sourceLoading = $state(false);
  /**
   * C6/C4 — what each turn in this conversation actually read. Labels only;
   * opening a chip is what fetches the passage behind it.
   */
  turnSources = $state<TurnSourceView[]>([]);
  /**
   * Which source is open, as (turn, id): ids restart at `s1` in every turn, so
   * the id alone would mark a chip open under every turn that has one.
   */
  openSourceId = $state<string | null>(null);
  openSourceTurnId = $state<string | null>(null);
  /** BUG-28 — the pane's own download, with every outcome stated. */
  downloadState = $state<"idle" | "working" | "done">("idle");
  downloadError = $state<string | null>(null);
  /**
   * Scoped to the card that failed: a refusal on one artifact must not appear
   * under every other turn that happens to have produced a file.
   */
  artifactNotice = $state<{ attachmentId: string; text: string } | null>(null);

  constructor(
    /** The conversation the pane reads from; nothing opens without one. */
    private readonly session: () => string | null,
    /** One detail panel at a time — they share the right-hand column (B18). */
    private readonly beforeOpen: () => void,
  ) {}

  private releaseObjectUrl() {
    if (this.objectUrl === null) return;
    URL.revokeObjectURL?.(this.objectUrl);
    this.objectUrl = null;
  }

  /**
   * BUG-07 — an attachment chip opens a view-only preview of the file it names.
   * Authorized by the conversation that carried the file; no upload, edit, or
   * download control beyond the governed download.
   */
  openFile = async (attachmentId: string, filename: string) => {
    const openedSession = this.session();
    if (openedSession === null) return;
    this.beforeOpen();
    this.releaseObjectUrl();
    this.inspecting = { attachmentId, filename };
    this.preview = null;
    this.previewError = null;
    this.previewLoading = true;
    try {
      const result = await api.attachmentPreview(openedSession, attachmentId);
      // A second chip clicked while this was in flight wins; drop the late one
      // rather than overwriting the file the user is now looking at.
      if (this.inspecting?.attachmentId !== attachmentId) return;
      this.preview = result;
      // PDFs and images are the two kinds whose content is bytes rather than
      // JSON; everything else is already in the preview.
      const bytesPath = result.pdf_url ?? result.image_url;
      if (bytesPath !== null) {
        const url = await api.attachmentPreviewObjectUrl(bytesPath);
        if (this.inspecting?.attachmentId === attachmentId) {
          this.objectUrl = url;
        } else {
          URL.revokeObjectURL?.(url);
        }
      }
    } catch (e) {
      if (this.inspecting?.attachmentId !== attachmentId) return;
      this.previewError =
        e instanceof ApiError && e.status === 404
          ? "This file is no longer available in this conversation."
          : "Could not open this file.";
    } finally {
      if (this.inspecting?.attachmentId === attachmentId) this.previewLoading = false;
    }
  };

  close = () => {
    this.releaseObjectUrl();
    this.inspecting = null;
    this.preview = null;
    this.previewError = null;
    this.previewLoading = false;
    this.source = null;
    this.sourceLoading = false;
    this.openSourceId = null;
    this.openSourceTurnId = null;
    this.downloadState = "idle";
    this.downloadError = null;
  };

  /**
   * Refreshed whenever a turn lands, so a citation the model just wrote has
   * something to resolve against by the time the answer finishes rendering.
   */
  refreshTurnSources = async (id: string) => {
    try {
      this.turnSources = (await api.sessionSources(id)).sources;
    } catch {
      // The ledger is provenance for an answer that already arrived. Losing it
      // must not cost the transcript, so the chips simply do not appear.
      this.turnSources = [];
    }
  };

  /**
   * Open one cited source at the passage the turn used (C4).
   *
   * An attachment is opened in the file pane *and* marked at its passage, so
   * "which document" and "which part of it" are the same action. Everything
   * else — a web page, an email, a connector response — has no second copy on
   * this machine, so what is shown is the exact text that reached the model.
   */
  openSource = async (source: TurnSourceView, quote = "") => {
    const opened = this.session();
    if (opened === null || !source.openable) return;
    this.openSourceId = source.source_id;
    this.openSourceTurnId = source.turn_id;
    if (source.attachment_id !== "") {
      await this.openFile(source.attachment_id, source.title);
    } else {
      this.beforeOpen();
      this.releaseObjectUrl();
      this.inspecting = { attachmentId: "", filename: source.title };
      this.preview = null;
      this.previewError = null;
      this.previewLoading = false;
    }
    this.source = null;
    this.sourceLoading = true;
    try {
      const resolved = await api.turnSourceExcerpt(opened, source.turn_id, source.source_id, quote);
      if (this.openSourceId === source.source_id) this.source = resolved;
    } catch {
      if (this.openSourceId === source.source_id) {
        this.source = {
          status: "source_deleted",
          kind: source.kind,
          title: source.title,
          excerpt: "",
          highlight_start: -1,
          highlight_length: 0,
          session_id: opened,
          turn_id: source.turn_id,
          attachment_id: source.attachment_id,
          truncated: false,
          resolution_method: "",
        };
      }
    } finally {
      if (this.openSourceId === source.source_id) this.sourceLoading = false;
    }
  };

  /**
   * A `[s1]` chip inside the answer opens the same source the strip does — and,
   * unlike the strip, it knows which sentence rests on it, so the pane can open
   * at that part of the source rather than at the whole of it.
   */
  openSourceById = (turnId: string, sourceId: string, answer: string) => {
    const match = this.turnSources.find(
      (source) => source.turn_id === turnId && source.source_id === sourceId,
    );
    if (match !== undefined) void this.openSource(match, sentenceAround(answer, sourceId));
  };

  openGeneratedFile = async (attachmentId: string, label: string) => {
    await this.openFile(attachmentId, label);
    const session = this.session();
    if (session === null || this.inspecting?.attachmentId !== attachmentId) return;
    this.sourceLoading = true;
    try {
      const resolved = await api.attachmentProvenance(session, attachmentId);
      if (this.inspecting?.attachmentId === attachmentId) this.source = resolved;
    } catch {
      // Provenance is supplementary to the file itself. A failure leaves the
      // preview intact and simply shows no source panel rather than replacing a
      // readable document with an error.
      if (this.inspecting?.attachmentId === attachmentId) this.source = null;
    } finally {
      if (this.inspecting?.attachmentId === attachmentId) this.sourceLoading = false;
    }
  };

  /** Download straight from an artifact card, without opening the pane first. */
  downloadArtifact = async (attachmentId: string, label: string) => {
    const session = this.session();
    if (session === null) return;
    try {
      const blob = await api.attachmentDownload(session, attachmentId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = label || "download";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      this.artifactNotice = null;
    } catch (e) {
      this.artifactNotice = {
        attachmentId,
        text:
          e instanceof ApiError && e.status === 404
            ? `“${label}” is no longer kept in this conversation, so it cannot be downloaded.`
            : `Could not download “${label}”.`,
      };
    }
  };

  downloadInspected = async () => {
    const session = this.session();
    if (this.inspecting === null || session === null) return;
    const { attachmentId, filename } = this.inspecting;
    this.downloadState = "working";
    this.downloadError = null;
    try {
      const blob = await api.attachmentDownload(session, attachmentId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = this.preview?.filename || filename || "download";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      this.downloadState = "done";
    } catch (e) {
      this.downloadState = "idle";
      this.downloadError =
        e instanceof ApiError && e.status === 404
          ? "This file is no longer kept in this conversation, so it cannot be downloaded."
          : e instanceof ApiError && e.status === 403
            ? "This account is not permitted to download this file."
            : "Could not download this file.";
    }
  };
}
