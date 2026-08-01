/**
 * The composer's attachment machinery, owned in one place (BUG-35).
 *
 * Chat could carry files into a turn and Build could not, which was never a
 * design decision — Build is the surface where "look at this stack trace",
 * "here is the failing screenshot" and "match this spec document" are the most
 * natural things a person wants to say, and the composer simply had no way to
 * say them. Two composers that look alike and behave differently are worse than
 * one that is honest about its limits, so the answer is not a second
 * implementation: it is this one, used by both.
 *
 * Everything the client does here is a convenience. The governed decisions all
 * happen server-side and are unchanged by this file:
 *
 * * A **workspace path** is resolved inside the workspace by the prompt route;
 *   anything outside fails closed, and what is read enters context labelled
 *   untrusted.
 * * An **image** is validated fail-closed on upload — media-type allowlist,
 *   5 MB cap, magic-byte sniff — and only ever reaches a model as an image
 *   block on a vision-capable profile.
 * * A **document** is validated the same way (allowlist, 32 MB cap, per-type
 *   sniff) and its text is extracted locally; the bytes never leave the box.
 *
 * The checks below therefore exist to give an immediate, specific answer
 * instead of a round trip that ends in a reason code. The server re-validates
 * everything regardless of what the client believed.
 */

import { api, ApiError } from "./api";

/** One attachment the composer is carrying, or that a turn carried. */
export interface ComposerAttachment {
  kind: "path" | "image" | "document";
  label: string;
  detail: string;
  path?: string;
  attachmentId?: string;
  source?: "uploaded" | "generated";
  createdAt?: string;
  /** What it is and how big, so a card can say so instead of just naming it. */
  mediaType?: string;
  byteSize?: number;
  /**
   * A local object URL for an image the owner just picked, used as its
   * thumbnail. Held here so it can be revoked when the attachment is removed or
   * the composer is cleared — a leaked handle keeps the whole file in memory.
   * Never a remote URL, and never used for anything but display.
   */
  previewUrl?: string;
}

/** A human file size. Bytes for the tiny cases, then KB, then MB. */
export function formatBytes(bytes: number | undefined): string {
  if (bytes === undefined || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** The short badge a document card shows: PDF, DOCX, CSV, MD… */
export function typeLabel(attachment: ComposerAttachment): string {
  if (attachment.kind === "path") return "PATH";
  const extension = attachment.label.split(".").pop() ?? "";
  if (extension && extension !== attachment.label && extension.length <= 5) {
    return extension.toUpperCase();
  }
  const subtype = (attachment.mediaType ?? "").split("/").pop() ?? "";
  return (subtype.split(".").pop() || "FILE").slice(0, 5).toUpperCase();
}

export const MAX_ATTACHMENTS = 8;
export const IMAGE_MEDIA_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];
export const MAX_IMAGE_BYTES = 5_000_000;

const DOCX_MEDIA_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const XLSX_MEDIA_TYPE =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export const DOCUMENT_MEDIA_TYPES = [
  "text/plain",
  "text/markdown",
  "text/csv",
  "application/pdf",
  DOCX_MEDIA_TYPE,
  XLSX_MEDIA_TYPE,
];
export const DOCUMENT_EXTENSIONS = [".txt", ".md", ".markdown", ".csv", ".pdf", ".docx", ".xlsx"];
export const MAX_DOCUMENT_BYTES = 32_000_000;

/** The last path segment — chips show a name, not a whole path. */
export function fileName(path: string): string {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

/**
 * Browsers report text media types inconsistently (a .md file often arrives
 * with an empty or non-standard type), so fall back to the extension. The
 * server re-validates fail-closed regardless of what we send.
 */
export function documentMediaType(file: File): string | null {
  if (DOCUMENT_MEDIA_TYPES.includes(file.type)) return file.type;
  const lower = file.name.toLowerCase();
  if (lower.endsWith(".csv")) return "text/csv";
  if (lower.endsWith(".md") || lower.endsWith(".markdown")) return "text/markdown";
  if (lower.endsWith(".txt")) return "text/plain";
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".docx")) return DOCX_MEDIA_TYPE;
  if (lower.endsWith(".xlsx")) return XLSX_MEDIA_TYPE;
  return null;
}

function objectUrlFor(file: File): string | undefined {
  // Absent in jsdom. Its absence costs the thumbnail, not the attachment.
  if (typeof URL?.createObjectURL !== "function") return undefined;
  try {
    return URL.createObjectURL(file);
  } catch {
    return undefined;
  }
}

function revoke(attachment: ComposerAttachment | undefined): void {
  if (attachment?.previewUrl === undefined) return;
  URL.revokeObjectURL?.(attachment.previewUrl);
}

function readBase64(file: File): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      resolve(dataUrl.slice(dataUrl.indexOf(",") + 1));
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export interface AttachmentStore {
  readonly items: ComposerAttachment[];
  readonly full: boolean;
  readonly uploading: boolean;
  readonly error: string | null;
  clearError(): void;
  /** Add a workspace path. Returns false when it was a duplicate or over cap. */
  addPath(path: string): boolean;
  remove(index: number): void;
  /** Replace the whole set — used to restore a draft or clear after a send. */
  set(items: ComposerAttachment[]): void;
  clear(): void;
  /** Snapshot for the turn being sent, before the composer is emptied. */
  take(): ComposerAttachment[];
  uploadImage(file: File): Promise<void>;
  uploadDocument(file: File): Promise<void>;
}

/** One composer's attachments. Each composer owns its own instance. */
export function createAttachmentStore(): AttachmentStore {
  let items = $state<ComposerAttachment[]>([]);
  let uploading = $state(false);
  let error = $state<string | null>(null);

  async function upload(
    file: File,
    kind: "image" | "document",
    mediaType: string,
  ): Promise<void> {
    uploading = true;
    try {
      const stored = await api.uploadAttachment({
        filename: file.name,
        media_type: mediaType,
        data_base64: await readBase64(file),
      });
      items = [
        ...items,
        {
          kind,
          label: file.name,
          detail: `${file.name} (${stored.media_type}, ${stored.byte_size} bytes)`,
          attachmentId: stored.attachment_id,
          mediaType: stored.media_type,
          byteSize: stored.byte_size,
          // The picture the owner just chose is already in the browser, so its
          // thumbnail costs no request: it is the local file, shown back.
          previewUrl: kind === "image" ? objectUrlFor(file) : undefined,
        },
      ];
    } catch (e) {
      error =
        e instanceof ApiError
          ? `Upload rejected (${e.reasonCode ?? e.status}).`
          : "Upload failed — could not reach the local runtime.";
    } finally {
      uploading = false;
    }
  }

  return {
    get items() { return items; },
    get full() { return items.length >= MAX_ATTACHMENTS; },
    get uploading() { return uploading; },
    get error() { return error; },
    clearError() { error = null; },
    addPath(path: string): boolean {
      const trimmed = path.trim();
      if (trimmed === "" || items.some((a) => a.path === trimmed) || items.length >= MAX_ATTACHMENTS) {
        return false;
      }
      items = [...items, { kind: "path", label: fileName(trimmed), detail: trimmed, path: trimmed }];
      return true;
    },
    remove(index: number) {
      revoke(items[index]);
      items = items.filter((_, i) => i !== index);
    },
    set(next: ComposerAttachment[]) {
      // Handed over rather than copied: the receiving composer now owns these
      // and will revoke them, so revoking here would blank its thumbnails.
      items = next;
    },
    clear() {
      // `take()` hands ownership of the thumbnails to the turn that is being
      // sent, so clearing after a send must not revoke them — the transcript is
      // still showing them. Only attachments still held here are released.
      items = [];
      error = null;
    },
    take(): ComposerAttachment[] {
      return [...items];
    },
    async uploadImage(file: File) {
      if (items.length >= MAX_ATTACHMENTS) return;
      error = null;
      if (!IMAGE_MEDIA_TYPES.includes(file.type)) {
        error = "Only PNG, JPEG, WebP, or GIF images can be attached.";
        return;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        error = "Image is too large (5 MB max).";
        return;
      }
      await upload(file, "image", file.type);
    },
    async uploadDocument(file: File) {
      if (items.length >= MAX_ATTACHMENTS) return;
      error = null;
      const mediaType = documentMediaType(file);
      if (mediaType === null) {
        error =
          "Only plain-text, Markdown, CSV, PDF, Word (.docx), or Excel (.xlsx) documents can be attached.";
        return;
      }
      if (file.size > MAX_DOCUMENT_BYTES) {
        error = "Document is too large (32 MB max).";
        return;
      }
      await upload(file, "document", mediaType);
    },
  };
}
