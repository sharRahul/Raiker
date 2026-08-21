import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { expect, it, vi } from "vitest";
import General from "./General.svelte";

it("offers the exact persisted speech language set and browser-processing disclosure", async () => {
  const save = vi.fn();
  render(General, { settings: { "general.speech_language": "fr" }, save });
  const select = screen.getByLabelText("Speech language");
  expect(select).toHaveValue("fr");
  expect(within(select).getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual([
    "auto", "en", "fr", "de", "hi", "it", "ja", "ko", "pt", "ru", "es", "tr", "uk",
  ]);
  expect(screen.getByText(/browser's speech service may process audio externally/)).toBeInTheDocument();
  await fireEvent.change(select, { target: { value: "ja" } });
  expect(save).toHaveBeenCalledWith({ "general.speech_language": "ja" });
});
