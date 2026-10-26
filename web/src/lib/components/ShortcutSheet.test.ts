import { render, screen } from "@testing-library/svelte";
import { expect, it, vi } from "vitest";
import ShortcutSheet from "./ShortcutSheet.svelte";

it("shows only the three requested composer tips", () => {
  render(ShortcutSheet, { surface: "build", onclose: vi.fn() });
  const sheet = screen.getByRole("region", { name: "Keyboard shortcuts" });
  expect(sheet.querySelectorAll("dl > div")).toHaveLength(3);
  expect(sheet).toHaveTextContent("Shift + Enter");
  expect(sheet).toHaveTextContent("Mention a file from the code map");
  expect(sheet).toHaveTextContent("Slash commands, at the start of the prompt");
});
