/**
 * Settings → Personalisation — the *Layout & type* disclosure.
 *
 * It opens by itself when density or typeface is not the default, so a tuned
 * value is never hidden. Found by the third 2026-09-28 live round: that was its
 * only rule, so choosing *Comfortable* inside it — the default — closed it under
 * the owner's pointer. Once the owner opens or closes it, their choice holds.
 */
import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Personalisation from "./Personalisation.svelte";

function disclosure(): HTMLDetailsElement {
  return screen.getByText("Layout & type").closest("details") as HTMLDetailsElement;
}

describe("Settings → Personalisation", () => {
  it("opens by itself when density is not the default", () => {
    render(Personalisation, {
      settings: { "personalisation.spacing": "compact" },
      save: vi.fn(),
      theme: "system",
      chooseTheme: vi.fn(),
    });
    expect(disclosure().open).toBe(true);
  });

  it("stays open when the owner chooses the default inside it", async () => {
    const save = vi.fn();
    const chooseTheme = vi.fn();
    const view = render(Personalisation, {
      settings: { "personalisation.spacing": "compact" },
      save,
      theme: "system",
      chooseTheme,
    });
    const details = disclosure();
    details.open = true;
    await fireEvent(details, new Event("toggle"));

    await fireEvent.click(screen.getByRole("radio", { name: /Comfortable/ }));
    expect(save).toHaveBeenCalledWith({ "personalisation.spacing": "comfortable" });
    // The parent re-renders with the saved default, which is what used to close it.
    await view.rerender({
      settings: { "personalisation.spacing": "comfortable" },
      save,
      theme: "system",
      chooseTheme,
    });
    expect(disclosure().open).toBe(true);
  });

  // DEC-21 Personalisation — theme is a draft the page holds, not a write here.
  it("hands a theme choice to the page's draft instead of storing it", async () => {
    const chooseTheme = vi.fn();
    render(Personalisation, { settings: {}, save: vi.fn(), theme: "light", chooseTheme });
    expect(screen.getByRole("radio", { name: /Light/ })).toHaveAttribute("aria-checked", "true");
    await fireEvent.click(screen.getByRole("radio", { name: /Dark/ }));
    expect(chooseTheme).toHaveBeenCalledWith("dark");
  });

  it("reads a stored value it does not offer as the default", () => {
    render(Personalisation, {
      settings: { "personalisation.spacing": "cramped", "personalisation.font": "comic" },
      save: vi.fn(),
      theme: "system",
      chooseTheme: vi.fn(),
    });
    expect(screen.getByRole("radio", { name: /Comfortable/ })).toHaveAttribute("aria-checked", "true");
    expect((screen.getByLabelText("Font") as HTMLSelectElement).value).toBe("sans");
  });

  it("says that how Raiker looks never changes what it is told or may do", () => {
    render(Personalisation, { settings: {}, save: vi.fn(), theme: "system", chooseTheme: vi.fn() });
    expect(screen.getByText(/never its instructions, its personality or what it may do/)).toBeInTheDocument();
  });
});
