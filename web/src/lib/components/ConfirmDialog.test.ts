import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import ConfirmDialog from "./ConfirmDialog.svelte";
import { askConfirm } from "../confirm.svelte";

describe("QUI-F10 the one confirmation dialog", () => {
  it("names the action on its own button and resolves true only when confirmed", async () => {
    render(ConfirmDialog);
    const answer = askConfirm({ title: "Delete “Weekly review”?", body: "Its document is removed.", confirmLabel: "Delete", danger: true });
    const dialog = await screen.findByRole("dialog", { name: "Delete “Weekly review”?" });
    expect(dialog).toHaveTextContent("Its document is removed.");
    expect(screen.queryByRole("button", { name: "OK" })).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await expect(answer).resolves.toBe(true);
  });

  it("Enter confirms and Cancel declines", async () => {
    render(ConfirmDialog);
    const first = askConfirm({ title: "Archive this?", confirmLabel: "Archive" });
    await fireEvent.keyDown(await screen.findByRole("dialog"), { key: "Enter" });
    await expect(first).resolves.toBe(true);
    const second = askConfirm({ title: "Archive that?", confirmLabel: "Archive" });
    await fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await expect(second).resolves.toBe(false);
  });
});
