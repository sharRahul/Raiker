import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { expect, it, vi } from "vitest";
import General from "./General.svelte";

it("keeps only the preferences that are about display and where the day begins", async () => {
  const save = vi.fn();
  render(General, { settings: { "general.language": "en-GB" }, save });
  // Speech moved to its own section when it gained a runtime to configure
  // (BUG-256); General should not carry a second copy of the same control.
  expect(screen.queryByLabelText("Speech language")).not.toBeInTheDocument();
  const startup = screen.getByLabelText("Default startup view");
  expect(within(startup).getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual([
    "workbench", "new-chat", "tasks", "projects", "approvals", "last-visited",
  ]);
  await fireEvent.change(startup, { target: { value: "tasks" } });
  expect(save).toHaveBeenCalledWith({ "general.startup_route": "tasks" });
});
