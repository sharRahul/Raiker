import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../../test-helpers";
import HuggingFacePanel from "./HuggingFacePanel.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("HuggingFacePanel", () => {
  // The Hub cannot be browsed exhaustively, so the panel stays search-first —
  // but opening it to an empty box left an owner who does not already know a
  // repository id with nowhere to start.
  it("opens on the most downloaded GGUF models instead of an empty box", async () => {
    stubFetch({
      "GET /api/hugging-face/trending": {
        items: [
          { repo_id: "org/popular-GGUF", downloads: 9001, likes: 42, gated: false },
        ],
      },
    });
    render(HuggingFacePanel);

    expect(await screen.findByText("org/popular-GGUF")).toBeInTheDocument();
    expect(
      screen.getByText(/Most downloaded GGUF models/),
    ).toBeInTheDocument();
  });

  // This test used to assert that an unreachable Hub leaves "Search the Hub
  // catalogue" on screen, and it was pinning the defect FIXED-414 records: that
  // copy is what the panel says when *nothing has been asked for yet*, so the
  // surface read identically whether the Hub had answered with nothing or could
  // not be reached at all. An owner on a host with no route to huggingface.co
  // saw a panel that looked ready and found out from a search that timed out.
  //
  // The half of it that was right is kept and still asserted: this is not an
  // alert. Nothing in Raiker is broken and nothing was lost. Not interrupting is
  // simply not the same as not saying.
  it("names the unreachable Hub, where the results would have been", async () => {
    stubFetch({});
    render(HuggingFacePanel);

    expect(
      await screen.findByText("Hugging Face could not be reached"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Search the Hub catalogue")).toBeNull();
    // An unreachable Hub before the owner asked for anything is not an alert.
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says what still works, so the failure is scoped rather than total", async () => {
    stubFetch({});
    render(HuggingFacePanel);

    expect(await screen.findByText(/local library/)).toBeInTheDocument();
  });

  it("offers a retry, because a route to the Hub is the kind of thing that comes back", async () => {
    const fetchMock = stubFetch({});
    render(HuggingFacePanel);

    const retry = await screen.findByRole("button", { name: "Try again" });
    const before = fetchMock.mock.calls.length;
    await fireEvent.click(retry);

    expect(fetchMock.mock.calls.length).toBeGreaterThan(before);
  });

  // An empty catalogue is not an unreachable one. The Hub answered; it just had
  // nothing to volunteer, and the search box is still the way forward.
  it("keeps the search-first empty state when the Hub volunteers nothing", async () => {
    stubFetch({ "GET /api/hugging-face/trending": { items: [] } });
    render(HuggingFacePanel);

    expect(
      await screen.findByText("Search the Hub catalogue"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Hugging Face could not be reached")).toBeNull();
  });

  it("offers the curated local semantic-recall model without requiring a search", async () => {
    stubFetch({
      "GET /api/hugging-face/nomic-ai/nomic-embed-text-v1.5-GGUF/variants": {
        items: [
          {
            repo_id: "nomic-ai/nomic-embed-text-v1.5-GGUF",
            revision: "a".repeat(40),
            files: ["nomic-embed-text-v1.5.Q4_K_M.gguf"],
            format: "gguf",
            quantization: "Q4_K_M",
            total_bytes: 84_100_000,
            cached_bytes: 0,
            gated: false,
            license_id: "apache-2.0",
            complete: true,
          },
        ],
      },
      "GET /api/model-library": { roots: [{ path: "/models" }], models: [] },
    });
    render(HuggingFacePanel);

    await fireEvent.click(screen.getByRole("button", { name: "Review variants" }));

    expect(await screen.findByText("Q4_K_M")).toBeInTheDocument();
    expect(screen.getByText("Ready to deploy")).toBeInTheDocument();
  });

  it("searches and labels ready GGUF separately from conversion sources", async () => {
    stubFetch({
      "GET /api/hugging-face/search": {
        items: [
          { repo_id: "org/model-GGUF", downloads: 42, likes: 3, gated: false },
        ],
      },
      "GET /api/hugging-face/org/model-GGUF/variants": {
        items: [
          {
            repo_id: "org/model-GGUF",
            revision: "a".repeat(40),
            files: ["model-Q4_K_M.gguf"],
            format: "gguf",
            quantization: "Q4_K_M",
            total_bytes: 100,
            cached_bytes: 0,
            gated: false,
            license_id: "apache-2.0",
            complete: true,
          },
          {
            repo_id: "org/model-GGUF",
            revision: "a".repeat(40),
            files: ["config.json", "model.safetensors"],
            format: "safetensors",
            quantization: null,
            total_bytes: 200,
            cached_bytes: 0,
            gated: false,
            license_id: "apache-2.0",
            complete: true,
          },
        ],
      },
      "GET /api/model-library": { roots: [{ path: "D:\\Models" }], models: [] },
    });
    render(HuggingFacePanel);
    await fireEvent.input(screen.getByLabelText("Search Hugging Face models"), {
      target: { value: "gemma" },
    });
    await fireEvent.click(
      screen.getByRole("button", { name: "Search models" }),
    );
    await fireEvent.click(await screen.findByText("org/model-GGUF"));
    expect(await screen.findByText("Q4_K_M")).toBeTruthy();
    expect(screen.getByText("Ready to deploy")).toBeTruthy();
    expect(screen.getByText("Requires isolated conversion")).toBeTruthy();
  });
  it("queues the download and follows it instead of blocking on it", async () => {
    // GCR-22/GCR-23 — the snapshot download used to run inside the request, so
    // a multi-gigabyte pull held a request worker for its whole duration and
    // the completion written at the end could not see a Cancel pressed in
    // between. It is a durable background operation now: the panel gets the
    // operation back straight away and follows it.
    const revision = "a".repeat(40);
    stubFetch({
      "GET /api/hugging-face/search": {
        items: [{ repo_id: "org/model-GGUF", downloads: 42, likes: 3, gated: false }],
      },
      "GET /api/hugging-face/org/model-GGUF/variants": {
        items: [
          {
            repo_id: "org/model-GGUF",
            revision,
            files: ["model-Q4_K_M.gguf"],
            format: "gguf",
            quantization: "Q4_K_M",
            total_bytes: 100,
            cached_bytes: 0,
            gated: false,
            license_id: "apache-2.0",
            complete: true,
          },
        ],
      },
      "GET /api/model-library": { roots: [{ path: "/models" }], models: [] },
      "POST /api/hugging-face/download/preview": {
        repo_id: "org/model-GGUF",
        revision,
        files: ["model-Q4_K_M.gguf"],
        total_bytes: 100,
        cached_bytes: 0,
        download_bytes: 100,
      },
      "POST /api/hugging-face/download": {
        operation_id: "mop_dl",
        owner_principal_id: "owner",
        kind: "download",
        target: "org/model-GGUF@aaaaaaaaaaaa",
        state: "queued",
        phase: "queued",
        progress_bytes: 0,
        total_bytes: null,
        progress_percent: null,
        source_url: "https://huggingface.co/org/model-GGUF",
        destination: "<model-library>/snapshot",
        error_code: null,
        error_detail: null,
        created_at: "now",
        updated_at: "now",
        retryable: true,
        partial_files_present: false,
        snapshot_path: "/models/.raiker-hf/org--model-GGUF/aaaaaaaaaa",
        conversion_output_path: "/models/converted",
      },
      "GET /api/model-operations": {
        items: [
          {
            operation_id: "mop_dl",
            owner_principal_id: "owner",
            kind: "download",
            target: "org/model-GGUF@aaaaaaaaaaaa",
            state: "running",
            phase: "downloading",
            progress_bytes: 40,
            total_bytes: 100,
            progress_percent: 40,
            source_url: "https://huggingface.co/org/model-GGUF",
            destination: "<model-library>/snapshot",
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
    render(HuggingFacePanel);
    await fireEvent.input(screen.getByLabelText("Search Hugging Face models"), {
      target: { value: "gemma" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Search models" }));
    await fireEvent.click(await screen.findByText("org/model-GGUF"));
    await fireEvent.click(await screen.findByText("Q4_K_M"));
    await fireEvent.click(await screen.findByRole("button", { name: "Confirm download" }));

    expect(await screen.findByText(/Download queued/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cancel download" })).toBeTruthy();
  });
});
