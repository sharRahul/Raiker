import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import App from "./App.svelte";
import StepUpAuthDialog from "./lib/StepUpAuthDialog.svelte";

// Accessibility baseline: roles, labels, and focus behaviour for the chrome and the step-up dialog.
describe("a11y baseline", () => {
  it("exposes a skip link and a focusable main landmark", () => {
    const { container } = render(App);
    const skip = container.querySelector("a.skip-link");
    expect(skip).not.toBeNull();
    expect(skip?.getAttribute("href")).toBe("#main");
    const main = container.querySelector("main#main");
    expect(main).not.toBeNull();
    // Main is programmatically focusable for skip-link navigation.
    expect(main?.getAttribute("tabindex")).toBe("-1");
  });

  it("labels the STOP control for assistive tech", () => {
    render(App);
    expect(screen.getByRole("button", { name: /stop all tasks/i })).toBeInTheDocument();
  });

  it("StepUpAuthDialog is a labelled modal with an associated reason field and initial focus", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(StepUpAuthDialog, {
      props: {
        title: "Enable web_fetch",
        principal: "principal_rahul",
        requireToken: true,
        requireThreatAck: true,
        onConfirm,
        onCancel,
      },
    });

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby");
    // The reason field is reachable by its label.
    expect(screen.getByLabelText(/reason/i)).toBeInTheDocument();
    // Tier-2 inputs are present and labelled.
    expect(screen.getByLabelText(/confirmation token/i)).toBeInTheDocument();
    // The modal receives focus when opened (focus trap entry point).
    expect(document.activeElement).toBe(dialog);

    // Confirm stays disabled until all required inputs are satisfied; Cancel is always reachable.
    expect(screen.getByRole("button", { name: /confirm change/i })).toBeDisabled();
    await fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();
  });
});
