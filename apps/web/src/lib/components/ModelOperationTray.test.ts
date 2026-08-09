import { render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../test-helpers";
import ModelOperationTray from "./ModelOperationTray.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("ModelOperationTray", () => {
  it("appears only for active model work", async () => {
    stubFetch({
      "GET /api/model-operations": {
        items: [
          {
            operation_id: "mop_1",
            owner_principal_id: "owner",
            kind: "pull",
            target: "gemma4",
            state: "running",
            phase: "downloading",
            progress_bytes: 1,
            total_bytes: 2,
            progress_percent: 50,
            source_url: null,
            destination: null,
            error_code: null,
            error_detail: null,
            created_at: "now",
            updated_at: "now",
          },
        ],
      },
    });
    render(ModelOperationTray);
    expect(await screen.findByText("1 model job")).toBeTruthy();
  });
});
