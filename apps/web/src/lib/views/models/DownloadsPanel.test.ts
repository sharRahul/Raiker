import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../../test-helpers";
import DownloadsPanel from "./DownloadsPanel.svelte";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

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
            retryable: true,
            partial_files_present: false,
          },
        ],
      },
    });
    render(DownloadsPanel);
    expect(await screen.findByText("org/model@abc")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    expect(screen.getByText(/hugging face download failed/i)).toBeTruthy();
  });

  it("says a job with no recorded parameters cannot be started again", async () => {
    // BUG-75 — Retry used to be offered for every failure and then only reset
    // the row. A job that cannot really be dispatched now says so instead.
    stubFetch({
      "GET /api/model-operations": {
        items: [
          {
            operation_id: "mop_2",
            owner_principal_id: "owner",
            kind: "install",
            target: "ollama",
            state: "failed",
            phase: "failed",
            progress_bytes: 0,
            total_bytes: null,
            progress_percent: null,
            source_url: null,
            destination: null,
            error_code: "runtime_install_failed",
            error_detail: null,
            created_at: "now",
            updated_at: "now",
            retryable: false,
            partial_files_present: false,
          },
        ],
      },
    });
    render(DownloadsPanel);
    expect(await screen.findByText("ollama")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByText(/cannot be started again/i)).toBeTruthy();
  });

  it("names the exact path and size before deleting partial files", async () => {
    stubFetch({
      "GET /api/model-operations": {
        items: [
          {
            operation_id: "mop_3",
            owner_principal_id: "owner",
            kind: "download",
            target: "org/model@abc",
            state: "failed",
            phase: "failed",
            progress_bytes: 0,
            total_bytes: null,
            progress_percent: null,
            source_url: null,
            destination: "<model-library>/model.gguf",
            error_code: "hugging_face_download_failed",
            error_detail: null,
            created_at: "now",
            updated_at: "now",
            retryable: true,
            partial_files_present: true,
          },
        ],
      },
      "GET /api/model-operations/mop_3/partial-files": {
        path: "/models/library/snapshot",
        paths: ["/models/library/snapshot"],
        exists: true,
        bytes: 2048,
        file_count: 2,
      },
    });
    render(DownloadsPanel);
    const button = await screen.findByRole("button", { name: "Delete partial files" });
    await fireEvent.click(button);
    expect(await screen.findByText("/models/library/snapshot", { exact: false })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Delete files" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Keep them" })).toBeTruthy();
  });

  it("names every file a failed conversion owns, and never its library folder", async () => {
    // GCR-19 — the confirmation used to name `payload.destination`, which for a
    // conversion is the model-library output *folder* the owner chose. That
    // folder holds the models earlier conversions succeeded at, so confirming
    // it was confirming their deletion. The dialog names the operation's own
    // artifacts instead, and the folder is not one of them.
    stubFetch({
      "GET /api/model-operations": {
        items: [
          {
            operation_id: "mop_convert",
            owner_principal_id: "owner",
            kind: "convert",
            target: "mistral@abc",
            state: "failed",
            phase: "failed",
            progress_bytes: 0,
            total_bytes: null,
            progress_percent: null,
            source_url: null,
            destination: "<model-library>/converted",
            error_code: "model_conversion_failed",
            error_detail: null,
            created_at: "now",
            updated_at: "now",
            retryable: true,
            partial_files_present: true,
          },
        ],
      },
      "GET /api/model-operations/mop_convert/partial-files": {
        path: null,
        paths: [
          "/models/converted/mistral-abcdef123456.bf16.gguf",
          "/models/converted/mistral-abcdef123456.Q4_K_M.gguf",
        ],
        exists: true,
        bytes: 4096,
        file_count: 2,
      },
    });
    render(DownloadsPanel);
    await fireEvent.click(
      await screen.findByRole("button", { name: "Delete partial files" }),
    );
    expect(
      await screen.findByText("/models/converted/mistral-abcdef123456.bf16.gguf"),
    ).toBeTruthy();
    expect(
      screen.getByText("/models/converted/mistral-abcdef123456.Q4_K_M.gguf"),
    ).toBeTruthy();
    // The shared output folder is never offered as something to delete.
    expect(screen.queryByText("/models/converted")).toBeNull();
  });

  it("offers Retry for a cancelled job, not only a failed one", async () => {
    // GCR-21 — Retry was drawn on `failed` alone while the API accepted it from
    // any state, so the one job an owner most wants to start again could not be
    // started from here and a running one could be started twice from anywhere
    // else. Both halves say the same thing now.
    stubFetch({
      "GET /api/model-operations": {
        items: [
          {
            operation_id: "mop_cancelled",
            owner_principal_id: "owner",
            kind: "pull",
            target: "tiny",
            state: "cancelled",
            phase: "cancelled",
            progress_bytes: 0,
            total_bytes: null,
            progress_percent: null,
            source_url: null,
            destination: null,
            error_code: null,
            error_detail: null,
            created_at: "now",
            updated_at: "now",
            retryable: true,
            partial_files_present: false,
          },
        ],
      },
    });
    render(DownloadsPanel);
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("refreshes background operation state while the panel is mounted", async () => {
    vi.useFakeTimers();
    const fetch = stubFetch({ "GET /api/model-operations": { items: [] } });
    render(DownloadsPanel);
    // Nothing is running, so the idle cadence applies rather than the active one.
    await vi.advanceTimersByTimeAsync(16_000);
    expect(fetch.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("polls quickly only while a job is actually running", async () => {
    // A once-a-second poll on an idle panel spends half the API's per-minute
    // rate budget and gets unrelated reads throttled.
    vi.useFakeTimers();
    const running = {
      operation_id: "mop_running",
      owner_principal_id: "owner",
      kind: "pull",
      target: "tiny",
      state: "running",
      phase: "pulling",
      progress_bytes: 1,
      total_bytes: 10,
      progress_percent: 10,
      source_url: null,
      destination: null,
      error_code: null,
      error_detail: null,
      created_at: "now",
      updated_at: "now",
      retryable: true,
      partial_files_present: false,
    };
    const fetch = stubFetch({ "GET /api/model-operations": { items: [running] } });
    render(DownloadsPanel);
    await vi.advanceTimersByTimeAsync(2_100);
    const whileRunning = fetch.mock.calls.length;
    expect(whileRunning).toBeGreaterThanOrEqual(2);
  });
});
