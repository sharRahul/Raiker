import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./api/core";
import { importMoveFile, moveProblem } from "./move";

describe("RU-17 move file client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends the file raw with the passphrase in its header", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true, created_at: "t", counts: { sessions: 2 }, keys_removed: 1, quarantine: "q" }), { status: 200 }),
    );
    const result = await importMoveFile(new Blob([new Uint8Array([1, 2, 3])]), "correct horse battery");
    expect(result.counts.sessions).toBe(2);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/move/import");
    const headers = new Headers(init?.headers);
    expect(headers.get("content-type")).toBe("application/octet-stream");
    expect(headers.get("x-raiker-move-passphrase")).toBe("correct horse battery");
  });

  it("turns a refusal into the owner's words", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: { reason_code: "move_passphrase_or_file_wrong" } }), { status: 422 }),
    );
    const failure = await importMoveFile(new Blob(["x"]), "wrong").catch((e: unknown) => e);
    expect(failure).toBeInstanceOf(ApiError);
    expect(moveProblem(failure)).toContain("passphrase does not open this file");
    expect(moveProblem(new ApiError(409, "move_workspace_in_use", ""))).toContain("already has an account");
  });
});
