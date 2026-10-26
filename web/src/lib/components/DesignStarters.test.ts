import { fireEvent, render, screen } from "@testing-library/svelte";
import { expect, it, vi } from "vitest";
import DesignStarters from "./DesignStarters.svelte";

it("offers eight keyboard-accessible starters without submitting", async () => {
  const onchoose = vi.fn();
  render(DesignStarters, { onchoose });
  const poster = screen.getByRole("button", { name: /Poster/ });
  await fireEvent.click(poster);
  expect(onchoose).toHaveBeenCalledOnce();
  expect(onchoose.mock.calls[0][0].prompt).toContain("poster");
  expect(screen.getAllByRole("button")).toHaveLength(8);
});

it("does not offer an edit starter without declared edit support", () => {
  render(DesignStarters, { onchoose: vi.fn(), editAvailable: false });
  expect(screen.getByRole("button", { name: /Edit an image/ })).toBeDisabled();
  expect(screen.getAllByText("Requires an editing model")).toHaveLength(2);
});
