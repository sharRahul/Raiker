import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeGate, stubFetch } from "../test-helpers";
import BuildView from "./BuildView.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("BuildView mode explanation", () => {
  it("explains Plan, Edit and Auto inside the mode picker and nowhere else", async () => {
    stubFetch({
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "GET /api/code/repos": { repos: [], selected_repo_id: null },
      "GET /api/tasks": [],
      "GET /api/capability-gates": [
        "file_write_execution",
        "patch_apply_execution",
        "shell_execution",
        "process_execution",
      ].map((capability) => makeGate({ capability, decision_mode: "ask" })),
    });
    render(BuildView);

    // The composer stays minimal: the three explanations are one click away in
    // the control that sets them, not three paragraphs standing above the box.
    const trigger = await screen.findByRole("button", {
      name: /^How much Raiker may do this turn:/,
    });
    expect(screen.queryByRole("menu", { name: "Mode" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Research and propose\. No changes\./i)).not.toBeInTheDocument();

    await fireEvent.click(trigger);

    const menu = screen.getByRole("menu", { name: "Mode" });
    expect(menu).toHaveTextContent(/Research and propose\. No changes\./i);
    expect(menu).toHaveTextContent(/Propose each change and wait for you\./i);
    expect(menu).toHaveTextContent(/Follow your standing permissions\./i);
    // BUG-70 — the menu has to say whose posture this is, because the chips used
    // to change the owner's standing permissions without asking.
    expect(menu).toHaveTextContent(/applies to this conversation's turns only/i);
    expect(menu).toHaveTextContent(/never widen it/i);
    expect(menu).toHaveTextContent(/raising a standing permission stays on the Permissions page/i);
  });
});
