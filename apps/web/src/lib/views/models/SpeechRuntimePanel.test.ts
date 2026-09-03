import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, expect, it, vi } from "vitest";
import SpeechRuntimePanel from "./SpeechRuntimePanel.svelte";
import { api } from "../../api";
import type { SpeechRuntimeSettings } from "../../apiTypes";

function runtime(overrides: Partial<SpeechRuntimeSettings> = {}): SpeechRuntimeSettings {
  return { endpoint: "", model: "", configured: false, effective: "browser", ...overrides };
}

beforeEach(() => vi.restoreAllMocks());

it("keeps an address typed before the read resolved", async () => {
  // FIXED-85's defect, in a new place: the row renders before the read answers,
  // so an owner can type into it first. Adopting the stored value afterwards
  // would clear what they had already entered.
  type View = { runtime: SpeechRuntimeSettings; max_audio_bytes: number };
  const pending: { settle: (view: View) => void } = { settle: () => {} };
  vi.spyOn(api, "speechRuntime").mockReturnValue(
    new Promise<View>((resolve) => { pending.settle = resolve; }),
  );
  render(SpeechRuntimePanel);
  const field = screen.getByLabelText("Speech runtime address");
  await fireEvent.input(field, { target: { value: "http://127.0.0.1:8910" } });
  pending.settle({ runtime: runtime(), max_audio_bytes: 1 });
  await waitFor(() => expect(screen.getByText("Not set up")).toBeInTheDocument());
  expect(field).toHaveValue("http://127.0.0.1:8910");
});

it("reports what answered at the address", async () => {
  vi.spyOn(api, "speechRuntime").mockResolvedValue({ runtime: runtime(), max_audio_bytes: 1 });
  vi.spyOn(api, "saveSpeechRuntime").mockResolvedValue({
    runtime: runtime({ endpoint: "http://127.0.0.1:8910", configured: true, effective: "local" }),
    max_audio_bytes: 1,
  });
  vi.spyOn(api, "probeSpeechRuntime").mockResolvedValue({
    ok: false,
    reason_code: "speech_runtime_unreachable",
    endpoint: "http://127.0.0.1:8910",
  });
  render(SpeechRuntimePanel);
  await fireEvent.input(await screen.findByLabelText("Speech runtime address"), {
    target: { value: "http://127.0.0.1:8910" },
  });
  await fireEvent.click(screen.getByRole("button", { name: "Save and test" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/Nothing answered there/);
});
