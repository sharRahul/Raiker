/**
 * VIS-08 — progressive disclosure only counts if nothing became unreachable.
 *
 * The composer used to carry the approval-mode control and the execution
 * environment badge open, permanently, under every message the owner typed.
 * Collapsing them into one chip is only an improvement if the chip tells the
 * truth about the state it is hiding and gives it all back on one click. Both
 * halves are asserted here.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PostureControl from "./PostureControl.svelte";
import { stubFetch } from "../test-helpers";

const ENVIRONMENTS = {
  environments: [
    { id: "local", name: "Local strict", kind: "local", selected: true, available: true, runtime: null },
  ],
};

describe("posture control", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("summarizes where work runs and what happens when a decision is needed", async () => {
    stubFetch({
      "GET /api/settings/composer-approval-mode": { approval_mode: "manual" },
      "GET /api/execution-environments": ENVIRONMENTS,
    });

    render(PostureControl);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Local · Asks first/i }),
      ).toBeInTheDocument();
    });
  });

  it("gives back the approval control and the environment on one click", async () => {
    stubFetch({
      "GET /api/settings/composer-approval-mode": { approval_mode: "manual" },
      "GET /api/execution-environments": ENVIRONMENTS,
    });
    render(PostureControl);
    const chip = await screen.findByRole("button", { name: /governance posture/i });

    // Collapsed: neither control is in the document at all.
    expect(screen.queryByLabelText("Execution environment")).not.toBeInTheDocument();

    await fireEvent.click(chip);

    expect(await screen.findByRole("dialog", { name: /governance posture/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approval mode/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Execution environment")).toBeInTheDocument();
    // The full matrix is not repeated here; it is linked.
    expect(
      screen.getByRole("link", { name: /every capability and how it must ask/i }),
    ).toBeInTheDocument();
  });

  it("omits the environment entirely where there is none to report", async () => {
    // Chat has no execution environment of its own, so the summary must not
    // invent one or leave a dangling separator.
    stubFetch({ "GET /api/settings/composer-approval-mode": { approval_mode: "manual" } });

    render(PostureControl, { showEnvironment: false });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Asks first/i })).toBeInTheDocument();
    });
    expect(screen.queryByText(/Local/)).not.toBeInTheDocument();
  });

  it("colours the chip only for a posture less careful than the default", async () => {
    // VIS-15 — every normal state neutral, so the one coloured state means
    // something. "Ask first" is the careful default and stays plain.
    stubFetch({
      "GET /api/settings/composer-approval-mode": { approval_mode: "auto" },
      "GET /api/execution-environments": ENVIRONMENTS,
    });

    render(PostureControl);

    const chip = await screen.findByRole("button", { name: /Approves automatically/i });
    expect(chip.className).toContain("relaxed");
    // VIS2-07 — and it does not simultaneously call itself protected. A chip
    // that reads "Protected · Auto-approve" in amber is telling the owner two
    // contradictory things about one setting.
    expect(chip.textContent).not.toMatch(/Protected/i);
  });

  // VIS2-07 — what does not depend on the approval mode is stated in the
  // popover, in the specific, so relaxing the mode does not read as switching
  // every protection off.
  it("names the protections that hold in every posture", async () => {
    stubFetch({
      "GET /api/settings/composer-approval-mode": { approval_mode: "skip" },
      "GET /api/execution-environments": ENVIRONMENTS,
    });
    render(PostureControl);
    await fireEvent.click(await screen.findByRole("button", { name: /governance posture/i }));
    expect(screen.getByText("Regardless of this setting")).toBeInTheDocument();
    expect(screen.getByText(/Capability gates and policy still apply/i)).toBeInTheDocument();
  });

  it("stays readable when the approval mode cannot be read", async () => {
    stubFetch({});
    render(PostureControl, { showEnvironment: false });

    // Never a chip that says nothing, and never a crash.
    expect(
      await screen.findByRole("button", { name: /governance posture: Not readable/i }),
    ).toBeInTheDocument();
  });
});
