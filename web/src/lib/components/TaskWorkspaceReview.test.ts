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
  conflicts: [] as string[],
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
      created: ["new.py"], modified: ["main.py"], deleted: ["old.txt"], overwrite: [],
    }),
  );
});

it("holds Apply until each conflicting file is chosen for overwrite (BD-4)", async () => {
  vi.spyOn(api, "taskWorkspaces").mockResolvedValue({ workspaces: [{ ...copy, conflicts: ["main.py"] }] });
  const promote = vi.spyOn(api, "promoteTaskWorkspace").mockResolvedValue({
    ok: true, workspace_id: copy.workspace_id, created: ["new.py"], modified: ["main.py"], deleted: ["old.txt"],
  });
  const confirm = vi.fn<(message?: string) => boolean>(() => true);
  vi.stubGlobal("confirm", confirm);
  render(TaskWorkspaceReview, { sessionId: "sess_build" });

  expect(await screen.findByText(/Working in an isolated copy — nothing changes in your project until you Apply/)).toBeInTheDocument();
  expect(screen.getByText(/1 file was also changed in your project/)).toBeInTheDocument();
  const apply = screen.getByRole("button", { name: "Apply to project" });
  expect(apply).toBeDisabled();
  await fireEvent.click(screen.getByRole("checkbox", { name: /Overwrite with the copy's version/ }));
  expect(apply).toBeEnabled();
  await fireEvent.click(apply);

  await waitFor(() =>
    expect(promote).toHaveBeenCalledWith(copy.workspace_id, {
      created: ["new.py"], modified: ["main.py"], deleted: ["old.txt"], overwrite: ["main.py"],
    }),
  );
  expect(confirm.mock.calls[0][0]).toMatch(/replaces your own edits to main.py/);
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

it("rereads the copy when a turn ends", async () => {
  const list = vi.spyOn(api, "taskWorkspaces").mockResolvedValue({ workspaces: [] });
  const view = render(TaskWorkspaceReview, { sessionId: "sess_build", refresh: 0 });
  await waitFor(() => expect(list).toHaveBeenCalledTimes(1));

  list.mockResolvedValue({ workspaces: [copy] });
  await view.rerender({ sessionId: "sess_build", refresh: 1 });

  expect(await screen.findByText("Sandbox changes · app")).toBeInTheDocument();
  expect(list).toHaveBeenCalledTimes(2);
});

it("opens one changed file's diff from the review, and closes it again", async () => {
  vi.spyOn(api, "taskWorkspaces").mockResolvedValue({ workspaces: [copy] });
  const read = vi.spyOn(api, "taskWorkspaceFileDiff").mockResolvedValue({
    workspace_id: copy.workspace_id, path: "main.py", status: "modified",
    diff: "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-print('a')\n+print('b')\n",
    binary: false, truncated: false,
  });
  render(TaskWorkspaceReview, { sessionId: "sess_build" });

  const file = await screen.findByRole("button", { name: /Changed main\.py/ });
  await fireEvent.click(file);

  const diff = await screen.findByLabelText("Changes to main.py");
  expect(read).toHaveBeenCalledWith(copy.workspace_id, "main.py");
  expect(diff).toHaveTextContent("+print('b')");
  expect(file).toHaveAttribute("aria-expanded", "true");
  await fireEvent.click(file);
  expect(screen.queryByLabelText("Changes to main.py")).not.toBeInTheDocument();
});

it("says a binary file has no line-by-line view", async () => {
  vi.spyOn(api, "taskWorkspaces").mockResolvedValue({ workspaces: [copy] });
  vi.spyOn(api, "taskWorkspaceFileDiff").mockResolvedValue({
    workspace_id: copy.workspace_id, path: "new.py", status: "created", diff: "", binary: true, truncated: false,
  });
  render(TaskWorkspaceReview, { sessionId: "sess_build" });
  await fireEvent.click(await screen.findByRole("button", { name: /Added new\.py/ }));
  expect(await screen.findByText(/Not a text file/)).toBeInTheDocument();
});
