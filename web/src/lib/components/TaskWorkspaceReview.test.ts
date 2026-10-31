import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../api";
import TaskWorkspaceReview from "./TaskWorkspaceReview.svelte";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const copy = {
  workspace_id: "a".repeat(32),
  session_id: "sess_build",
  source: "app",
  created_at: 0,
  created: ["new.py"],
  modified: ["main.py"],
  deleted: ["old.txt"],
  rejected: [{ path: "escape", reason: "link" }],
};

it("lists the session's sandbox changes and applies exactly what was shown", async () => {
  vi.spyOn(api, "taskWorkspaces").mockResolvedValue({ workspaces: [copy, { ...copy, workspace_id: "b".repeat(32), session_id: "other" }] });
  const promote = vi.spyOn(api, "promoteTaskWorkspace").mockResolvedValue({
    ok: true, workspace_id: copy.workspace_id, created: ["new.py"], modified: ["main.py"], deleted: ["old.txt"],
  });
  vi.stubGlobal("confirm", () => true);
  render(TaskWorkspaceReview, { sessionId: "sess_build" });

  expect(await screen.findByText("Sandbox changes · app")).toBeInTheDocument();
  expect(screen.getAllByRole("region", { name: "Sandbox changes" })).toHaveLength(1);
  expect(screen.getByText(/escape · link/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole("button", { name: "Apply to project" }));

  await waitFor(() =>
    expect(promote).toHaveBeenCalledWith(copy.workspace_id, {
      created: ["new.py"], modified: ["main.py"], deleted: ["old.txt"],
    }),
  );
});

it("says a stale review was refused and nothing was applied", async () => {
  vi.spyOn(api, "taskWorkspaces").mockResolvedValue({ workspaces: [copy] });
  vi.spyOn(api, "promoteTaskWorkspace").mockRejectedValue(
    new ApiError(409, "workspace_review_stale", "conflict"),
  );
  vi.stubGlobal("confirm", () => true);
  render(TaskWorkspaceReview, { sessionId: "sess_build" });

  await fireEvent.click(await screen.findByRole("button", { name: "Apply to project" }));

  expect(await screen.findByText(/The copy changed after you looked/)).toBeInTheDocument();
});

it("shows nothing when the session has no sandbox changes", async () => {
  vi.spyOn(api, "taskWorkspaces").mockResolvedValue({
    workspaces: [{ ...copy, created: [], modified: [], deleted: [], rejected: [] }],
  });
  render(TaskWorkspaceReview, { sessionId: "sess_build" });
  await waitFor(() => expect(api.taskWorkspaces).toHaveBeenCalled());
  expect(screen.queryByRole("region", { name: "Sandbox changes" })).not.toBeInTheDocument();
});
