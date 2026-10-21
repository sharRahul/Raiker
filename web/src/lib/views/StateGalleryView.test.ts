import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import StateGalleryView from "./StateGalleryView.svelte";
import { routeFromHash } from "../nav";

describe("StateGalleryView (QUI-G03)", () => {
  it("shows every shared state and switches the theme, then restores the owner's", async () => {
    delete document.documentElement.dataset.theme;
    const view = render(StateGalleryView);
    for (const name of ["Empty", "Loading", "Working", "Needs permission", "Error", "Done"]) {
      expect(screen.getByRole("heading", { name })).toBeInTheDocument();
    }
    expect(screen.getByText("Reading 2 emails from Anna…")).toBeInTheDocument();
    expect(screen.getByTestId("gallery-decision")).toBeInTheDocument();
    await fireEvent.click(screen.getByLabelText("Dark"));
    expect(document.documentElement.dataset.theme).toBe("dark");
    view.unmount();
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("is a route in development builds", () => {
    expect(import.meta.env.DEV).toBe(true);
    expect(routeFromHash("#/state-gallery")).toBe("state-gallery");
  });
});
