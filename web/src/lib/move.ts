/**
 * RU-17 — move Raiker to another machine.
 *
 * The move file is binary both ways, so these two calls go through `fetch`
 * directly rather than the generated JSON client: export answers with the
 * sealed file to save, and import sends the file as the raw body with the
 * passphrase in a header (first run has no session to sign it with).
 */
import { ApiError, authHeaders, reasonCodeFrom } from "./api/core";

export const MIN_PASSPHRASE = 12;

export interface MoveStatus {
  can_import: boolean;
  min_passphrase: number;
  max_bytes: number;
}

export interface MoveImported {
  ok: true;
  created_at: string;
  counts: Record<string, number>;
  keys_removed: number;
  quarantine: string;
}

async function refused(resp: Response): Promise<ApiError> {
  let code: string | null = null;
  try {
    code = reasonCodeFrom(await resp.json());
  } catch {
    /* not JSON */
  }
  return new ApiError(resp.status, code, code ?? `HTTP ${resp.status}`);
}

export async function moveStatus(): Promise<MoveStatus | null> {
  try {
    const resp = await fetch("/api/move/status");
    return resp.ok ? ((await resp.json()) as MoveStatus) : null;
  } catch {
    return null;
  }
}

/** Ask for the sealed file and hand it to the browser to save. */
export async function exportMoveFile(passphrase: string): Promise<string> {
  const headers = authHeaders(new Headers({ "Content-Type": "application/json" }), "POST");
  const resp = await fetch("/api/move/export", { method: "POST", headers, body: JSON.stringify({ passphrase }) });
  if (!resp.ok) throw await refused(resp);
  const disposition = resp.headers.get("content-disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "raiker.raikermove";
  const url = URL.createObjectURL(await resp.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return name;
}

export async function importMoveFile(file: Blob, passphrase: string): Promise<MoveImported> {
  const resp = await fetch("/api/move/import", {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream", "X-Raiker-Move-Passphrase": passphrase },
    body: file,
  });
  if (!resp.ok) throw await refused(resp);
  return (await resp.json()) as MoveImported;
}

/** What a refusal means to the owner, in the words the page uses. */
export function moveProblem(e: unknown): string {
  const code = e instanceof ApiError ? e.reasonCode : null;
  switch (code) {
    case "move_passphrase_or_file_wrong":
      return "That passphrase does not open this file, or the file was changed. Nothing here was changed.";
    case "move_not_a_move_file":
      return "This is not a Raiker move file. Choose the .raikermove file you saved on the other machine.";
    case "move_format_newer":
    case "move_schema_newer":
      return "A newer Raiker made this file. Update Raiker on this machine, then try again.";
    case "move_workspace_in_use":
      return "This Raiker already has an account, so a move file can't open here.";
    case "move_file_too_large":
      return "This file is larger than Raiker opens at once (512 MB).";
    case "move_passphrase_short":
      return `Use a passphrase of at least ${MIN_PASSPHRASE} characters.`;
    case "move_requires_step_up":
      return "Confirm your password first.";
    default:
      return "The move did not finish. Nothing was changed. Try again.";
  }
}
