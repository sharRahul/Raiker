import { render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../../test-helpers";
import DownloadsPanel from "./DownloadsPanel.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("DownloadsPanel", () => {
  it("keeps failed operations visible with an explicit retry", async () => {
    stubFetch({
      "GET /api/model-operations": {
        items: [
          {
            operation_id: "mop_1",
            owner_principal_id: "owner",
            kind: "download",
            target: "org/model@abc",
            state: "failed",
            phase: "failed",
            progress_bytes: 0,
            total_bytes: null,
            progress_percent: null,
            source_url: null,
            destination: null,
            error_code: "hugging_face_download_failed",
            error_detail: null,
            created_at: "now",
            updated_at: "now",
          },
        ],
      },
    });
    render(DownloadsPanel);
    expect(await screen.findByText("org/model@abc")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    expect(screen.getByText(/hugging face download failed/i)).toBeTruthy();
  });
});
