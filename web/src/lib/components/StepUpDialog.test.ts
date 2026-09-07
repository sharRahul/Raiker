import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import StepUpDialog from "./StepUpDialog.svelte";

describe("StepUpDialog", () => {
  it("blocks confirmation until a reason is provided", async () => {
    const onConfirm = vi.fn();
    render(StepUpDialog, {
      title: "Enable Shell commands",
      principal: "prin_owner",
      onConfirm,
      onCancel: vi.fn(),
    });
    const confirm = screen.getByRole("button", { name: /confirm change/i });
    expect(confirm).toBeDisabled();
    await fireEvent.input(screen.getByLabelText(/reason/i), { target: { value: "testing" } });
    expect(confirm).toBeEnabled();
    await fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith({
      reason: "testing",
      confirmationToken: null,
      threatAck: false,
    });
  });

  it("requires the Tier-2 confirmation token and threat ack when asked", async () => {
    const onConfirm = vi.fn();
    render(StepUpDialog, {
      title: "Enable Shell commands",
      principal: "prin_owner",
      requireToken: true,
      requireThreatAck: true,
      onConfirm,
      onCancel: vi.fn(),
    });
    const confirm = screen.getByRole("button", { name: /confirm change/i });
    await fireEvent.input(screen.getByLabelText(/reason/i), { target: { value: "why" } });
    expect(confirm).toBeDisabled();
    await fireEvent.input(screen.getByLabelText(/confirmation token/i), { target: { value: "tok" } });
    expect(confirm).toBeDisabled();
    await fireEvent.click(screen.getByRole("checkbox"));
    expect(confirm).toBeEnabled();
    await fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith({ reason: "why", confirmationToken: "tok", threatAck: true });
  });

  it("explains that any phrase is a recorded intent confirmation", () => {
    render(StepUpDialog, {
      title: "Enable Shell commands",
      principal: "prin_owner",
      requireToken: true,
      onConfirm: vi.fn(),
      onCancel: vi.fn(),
    });

    expect(
      screen.getByText("Type any phrase to confirm you intend this change. It is recorded with your decision."),
    ).toBeInTheDocument();
  });

  it("names the acting principal and cancels on Escape", async () => {
    const onCancel = vi.fn();
    render(StepUpDialog, {
      title: "Disable gate",
      principal: "prin_owner",
      onConfirm: vi.fn(),
      onCancel,
    });
    expect(screen.getByText("prin_owner")).toBeInTheDocument();
    await fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onCancel).toHaveBeenCalled();
  });
});
