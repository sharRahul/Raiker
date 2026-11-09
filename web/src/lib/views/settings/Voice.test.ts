import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Voice from "./Voice.svelte";
import { stubFetch } from "../../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const component = (role: string, item_id: string, name: string, extra: Record<string, unknown> = {}) => ({
  role, item_id, name, licence: "MIT", size_bytes: 92_361_271, installed: false, installable: true,
  refusal: null, pending_reason: null, source_page: "https://github.com", ...extra,
});

function status(profile = "balanced", overrides: Record<string, unknown> = {}) {
  return {
    settings: {
      profile, english_only: false, whisper_model: null, voice: null, speed: 1, idle_unload_minutes: 10, run_on: "auto",
      conversation: { mode: "push_to_talk", end_silence_ms: 500, barge_in: true, speak_tool_progress: false,
                      keep_recordings: false, labs_hands_free: false },
    },
    recommended_profile: "balanced",
    recommendation: "Your NVIDIA RTX 4060 can run speech recognition next to a local model.",
    profiles: [
      { profile_id: "lite", name: "Lite", audience: "8 GB", speaking: "kokoro", download_bytes: 1, memory_bytes: 1,
        listening_available: false, speaking_available: false, recommended: false },
      { profile_id: "balanced", name: "Balanced", audience: "16 GB", speaking: "kokoro", download_bytes: 600_000_000,
        memory_bytes: 1, listening_available: false, speaking_available: true, recommended: true },
    ],
    listening: {
      state: "unavailable", device: null,
      components: [component("whisper_model", "whisper-small-q5_1", "Whisper small (q5_1)",
        { installable: false, refusal: "voice_item_pending" })],
    },
    speaking: {
      state: "not_installed", engine: "kokoro", voices: ["af_heart", "bf_emma"],
      components: [component("kokoro_model", "kokoro-82m-int8", "Kokoro-82M (int8)")],
    },
    plan: { fits: true, sentence: "Speech recognition runs on the processor with 4 threads.", smaller_profile: null, placements: [] },
    disk_bytes: 0,
    hardware: { os: "windows", arch: "x64", total_memory_bytes: 1, gpu: null },
    ...overrides,
  };
}

describe("Settings › Voice", () => {
  it("names the recommended profile and says why a component is not offered yet", async () => {
    stubFetch({ "GET /api/voice/status": status() });
    render(Voice);
    expect(await screen.findByText("Recommended for this computer")).toBeInTheDocument();
    expect(screen.getByText(/RTX 4060 can run speech recognition/)).toBeInTheDocument();
    expect(screen.getByText(/waiting for a verified digest/)).toBeInTheDocument();
    expect(screen.getByText(/speaking only for now/)).toBeInTheDocument();
    expect(screen.getByTestId("voice-plan")).toHaveTextContent("processor with 4 threads");
  });

  it("starts an install and reports the test round trip", async () => {
    const fetchMock = stubFetch({
      "GET /api/voice/status": status(),
      "POST /api/voice/install": { operation_id: "op_1", state: "queued", progress_percent: null },
      "POST /api/voice/test": { spoke: true, heard: false, transcript: null, word_error_rate: null, seconds: 1.4,
                                reason_code: "voice_listening_not_installed" },
    });
    render(Voice);
    await fireEvent.click(await screen.findByRole("button", { name: "Install" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/api/voice/install") && init?.method === "POST")).toBe(true),
    );
    vi.unstubAllGlobals();
    stubFetch({
      "GET /api/voice/status": status("balanced", { disk_bytes: 120_000_000 }),
      "POST /api/voice/test": { spoke: true, heard: true, transcript: "raiker can hear", word_error_rate: 0.1, seconds: 2.5,
                                reason_code: null },
    });
    render(Voice);
    const tests = await screen.findAllByRole("button", { name: "Test" });
    await fireEvent.click(tests[tests.length - 1]);
    expect(await screen.findByTestId("voice-test-result")).toHaveTextContent("90% of the words matched");
  });

  it("removes voice only after confirming, and says how much was freed", async () => {
    stubFetch({
      "GET /api/voice/status": status("balanced", { disk_bytes: 120_000_000 }),
      "DELETE /api/voice": { freed_bytes: 120_000_000 },
    });
    render(Voice);
    await fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
    expect(screen.getByText(/Remove every voice file/)).toBeInTheDocument();
    const confirm = screen.getAllByRole("button", { name: "Remove" }).at(-1)!;
    await fireEvent.click(confirm);
    expect(await screen.findByText(/Voice removed/)).toBeInTheDocument();
  });

  it("shows only the profile choice while voice is off", async () => {
    stubFetch({ "GET /api/voice/status": status("off") });
    render(Voice);
    expect(await screen.findByRole("radio", { name: /Off/ })).toBeChecked();
    expect(screen.queryByRole("heading", { name: "Engines" })).toBeNull();
  });
});
