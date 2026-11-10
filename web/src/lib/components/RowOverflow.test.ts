import { fireEvent, render, screen } from "@testing-library/svelte";
import { expect, it, vi } from "vitest";
import RowOverflow from "./RowOverflow.svelte";

it("Escape closes the open menu without reaching an enclosing dialog", async () => {
  const parentEscape = vi.fn();
  window.addEventListener("keydown", parentEscape);
  try {
    render(RowOverflow, { label: "Ollama", items: [{ label: "Test connection", run: vi.fn() }] });
    const trigger = screen.getByRole("button", { name: "More actions for Ollama" });
    await fireEvent.click(trigger);
    expect(screen.getByRole("menu")).toBeVisible();
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(trigger).toHaveFocus();
    expect(parentEscape).not.toHaveBeenCalled();
  } finally {
    window.removeEventListener("keydown", parentEscape);
  }
});
