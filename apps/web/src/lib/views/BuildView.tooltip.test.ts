import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeGate, stubFetch } from "../test-helpers";
import BuildView from "./BuildView.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("BuildView mode tooltip", () => {
  it("shows the Plan/Edit/Auto explanation on both hover and keyboard focus", async () => {
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

    const help = await screen.findByRole("button", { name: /about plan, edit, and auto modes/i });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await fireEvent.mouseEnter(help);
    expect(screen.getByRole("tooltip")).toHaveTextContent(/every file write/i);

    await fireEvent.mouseLeave(help);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await fireEvent.focus(help);
    expect(screen.getByRole("tooltip")).toHaveTextContent(/every file write/i);
  });
});
