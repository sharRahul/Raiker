import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import General from "./General.svelte";
import { stubFetch } from "../../test-helpers";

afterEach(() => vi.unstubAllGlobals());

it("offers the exact persisted speech language set", async () => {
  const save = vi.fn();
  render(General, { settings: { "general.speech_language": "fr" }, save });
  const select = screen.getByLabelText("Speech language");
  expect(select).toHaveValue("fr");
  expect(within(select).getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual([
    "auto", "en", "fr", "de", "hi", "it", "ja", "ko", "pt", "ru", "es", "tr", "uk",
  ]);
  await fireEvent.change(select, { target: { value: "ja" } });
  expect(save).toHaveBeenCalledWith({ "general.speech_language": "ja" });
});

it("does not ask the owner to choose a speech runtime", () => {
  // BUG-256 shipped a mode selector, and it was one decision too many: setting a
  // runtime up is the whole choice. Where the audio is transcribed is a fact the
  // microphone's own disclosure states, not a preference to be set here.
  render(General, { settings: {}, save: vi.fn() });
  expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/speech runtime address/i)).not.toBeInTheDocument();
});

// DEC-21 General — three languages, each doing what it says.
it("sets the date format, says it is the format, and offers no region that does nothing", async () => {
  const save = vi.fn();
  render(General, { settings: { "general.language": "de-DE", "general.region": "US" }, save });
  const format = screen.getByLabelText("Dates and times");
  expect(format).toHaveValue("de-DE");
  expect(screen.getByText(/Raiker's own text is in English/)).toBeInTheDocument();
  // The old promise of "interface text and formatting" is gone, and so is the
  // select that changed nothing.
  expect(screen.queryByText(/Interface text and formatting/)).not.toBeInTheDocument();
  expect(screen.queryByText("Country or region")).not.toBeInTheDocument();
  await fireEvent.change(format, { target: { value: "en-US" } });
  expect(save).toHaveBeenCalledWith({ "general.language": "en-US" });
});

it("says which language setting reaches a model", async () => {
  const save = vi.fn();
  render(General, { settings: {}, save });
  const answer = screen.getByLabelText("Answer in");
  expect(answer).toHaveValue("");
  expect(screen.getByText(/Every model turn is told this/)).toBeInTheDocument();
  await fireEvent.change(answer, { target: { value: "fr" } });
  expect(save).toHaveBeenCalledWith({ "general.answer_language": "fr" });
});

// QUI-W06 — setup can be run again, keeping every earlier choice.
it("reopens first-run setup on its model step, keeping what was chosen", async () => {
  const stored = {
    owner_principal_id: "prin_owner", status: "complete", stage: "finish",
    selected_profile_id: "anthropic-hosted", selected_model: "claude-haiku-4-5", model_deferred: false,
    privacy_mode: "balanced", privacy_acknowledged_at: "2026-10-01T00:00:00Z", backup_mode: "later",
    backup_target: null, backup_verified_at: null, background_service_enabled: false,
    created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  };
  const fetchMock = stubFetch({ "GET /api/setup": stored, "PUT /api/setup": { ...stored, status: "in_progress", stage: "model" } });
  window.location.hash = "#/settings";
  render(General, { settings: {}, save: vi.fn() });
  await fireEvent.click(screen.getByRole("button", { name: "Run setup again" }));
  await waitFor(() => expect(window.location.hash).toBe("#/model-setup"));
  const put = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT");
  expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({
    status: "in_progress",
    stage: "model",
    selected_profile_id: "anthropic-hosted",
    selected_model: "claude-haiku-4-5",
  });
  // The startup page is called Home, as the sidebar calls it.
  expect(screen.getByRole("option", { name: "Home" })).toBeInTheDocument();
});
