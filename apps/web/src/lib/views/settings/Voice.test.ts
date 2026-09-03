import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { beforeEach, expect, it, vi } from "vitest";
import Voice from "./Voice.svelte";
import { api, ApiError } from "../../api";
import type { SpeechRuntimeSettings } from "../../apiTypes";

function runtime(overrides: Partial<SpeechRuntimeSettings> = {}): SpeechRuntimeSettings {
  return {
    mode: "auto",
    endpoint: "",
    model: "",
    configured: false,
    effective: "browser",
    ...overrides,
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

it("says which runtime dictation will actually use", async () => {
  vi.spyOn(api, "speechRuntime").mockResolvedValue({
    runtime: runtime({ endpoint: "http://127.0.0.1:8910", configured: true, effective: "local" }),
    max_audio_bytes: 1,
  });
  render(Voice, { settings: {}, save: vi.fn() });
  expect(await screen.findByText("Dictation runs on this device.")).toBeInTheDocument();
});

it("tells an owner who asked for on-device that nothing is set up yet", async () => {
  vi.spyOn(api, "speechRuntime").mockResolvedValue({
    runtime: runtime({ mode: "local", effective: "local" }),
    max_audio_bytes: 1,
  });
  render(Voice, { settings: {}, save: vi.fn() });
  expect(
    await screen.findByText("Dictation is off until you add a runtime below."),
  ).toBeInTheDocument();
});

it("records the choice as soon as it is made", async () => {
  vi.spyOn(api, "speechRuntime").mockResolvedValue({ runtime: runtime(), max_audio_bytes: 1 });
  const save = vi
    .spyOn(api, "saveSpeechRuntime")
    .mockResolvedValue({ runtime: runtime({ mode: "browser" }), max_audio_bytes: 1 });
  render(Voice, { settings: {}, save: vi.fn() });
  await fireEvent.click(await screen.findByRole("radio", { name: /Browser speech/ }));
  await waitFor(() => expect(save).toHaveBeenCalledWith({ mode: "browser" }));
});

it("saves the address and reports what answered", async () => {
  vi.spyOn(api, "speechRuntime").mockResolvedValue({ runtime: runtime(), max_audio_bytes: 1 });
  vi.spyOn(api, "saveSpeechRuntime").mockResolvedValue({
    runtime: runtime({ endpoint: "http://127.0.0.1:8910", configured: true, effective: "local" }),
    max_audio_bytes: 1,
  });
  vi.spyOn(api, "probeSpeechRuntime").mockResolvedValue({
    ok: true,
    reason_code: null,
    endpoint: "http://127.0.0.1:8910",
  });
  render(Voice, { settings: {}, save: vi.fn() });
  await fireEvent.input(await screen.findByLabelText("Speech runtime address"), {
    target: { value: "http://127.0.0.1:8910" },
  });
  await fireEvent.click(screen.getByRole("button", { name: "Save and test" }));
  expect(await screen.findByText("Saved. The runtime answered.")).toBeInTheDocument();
});

it("says what is wrong with an address that is not on this machine", async () => {
  vi.spyOn(api, "speechRuntime").mockResolvedValue({ runtime: runtime(), max_audio_bytes: 1 });
  vi.spyOn(api, "saveSpeechRuntime").mockRejectedValue(
    new ApiError(422, "speech_endpoint_not_local", "refused"),
  );
  render(Voice, { settings: {}, save: vi.fn() });
  await fireEvent.input(await screen.findByLabelText("Speech runtime address"), {
    target: { value: "https://speech.example.com" },
  });
  await fireEvent.click(screen.getByRole("button", { name: "Save and test" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/not on this machine/);
});

it("keeps the speech language on the settings save queue", async () => {
  vi.spyOn(api, "speechRuntime").mockResolvedValue({ runtime: runtime(), max_audio_bytes: 1 });
  const save = vi.fn();
  render(Voice, { settings: { "general.speech_language": "fr" }, save });
  const select = await screen.findByLabelText("Speech language");
  expect(select).toHaveValue("fr");
  expect(
    within(select).getAllByRole("option").map((option) => option.getAttribute("value")),
  ).toEqual(["auto", "en", "fr", "de", "hi", "it", "ja", "ko", "pt", "ru", "es", "tr", "uk"]);
  await fireEvent.change(select, { target: { value: "ja" } });
  expect(save).toHaveBeenCalledWith({ "general.speech_language": "ja" });
});
