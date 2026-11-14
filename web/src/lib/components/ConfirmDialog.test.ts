import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import ConfirmDialog from "./ConfirmDialog.svelte";
import { askConfirm, askText } from "../confirm.svelte";

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

  it("asks for a few words in Raiker's own dialog and returns them (no window.prompt)", async () => {
    render(ConfirmDialog);
    const answer = askText({ title: "Reject this relationship?", confirmLabel: "Reject", input: { label: "Why is it incorrect?", value: "Wrong", required: true } });
    const dialog = await screen.findByRole("dialog", { name: "Reject this relationship?" });
    const field = screen.getByLabelText("Why is it incorrect?");
    expect(field).toHaveValue("Wrong");
    await fireEvent.input(field, { target: { value: "  Not the same person  " } });
    await fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    await expect(answer).resolves.toBe("Not the same person");
    expect(dialog).not.toBeInTheDocument();
  });

  it("a required field cannot be confirmed empty, and Cancel returns null", async () => {
    render(ConfirmDialog);
    const answer = askText({ title: "Attach a folder", confirmLabel: "Attach", input: { label: "Full path", required: true } });
    await screen.findByRole("dialog", { name: "Attach a folder" });
    expect(screen.getByRole("button", { name: "Attach" })).toBeDisabled();
    await fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await expect(answer).resolves.toBeNull();
  });
});
