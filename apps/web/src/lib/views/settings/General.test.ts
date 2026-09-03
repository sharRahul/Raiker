import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { expect, it, vi } from "vitest";
import General from "./General.svelte";

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
