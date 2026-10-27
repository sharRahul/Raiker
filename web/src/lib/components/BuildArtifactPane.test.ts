import { render, screen } from "@testing-library/svelte";
import { expect, it } from "vitest";
import BuildArtifactPane from "./BuildArtifactPane.svelte";
import { stubFetch } from "../test-helpers";

it("explains when a changed tree cannot be diffed safely", async () => {
  stubFetch({
    "GET /api/code/repos/repo_1/changes": {
      entries: [{ path: "app.py", previous_path: "", state: "modified", unstaged: true }],
      diff: "", truncated: false, diff_truncated: false, root_missing: false,
      reason_code: "git_diff_native_sandbox_required",
    },
  });
  render(BuildArtifactPane, { repoId: "repo_1", onclose: () => {} });
  expect(await screen.findByText(/diff is unavailable until the native sandbox/i)).toBeInTheDocument();
});

it("does not present an oversized staged diff as complete", async () => {
  stubFetch({
    "GET /api/code/repos/repo_1/changes": {
      entries: [{ path: "app.py", previous_path: "", state: "modified", unstaged: false }],
      diff: "", truncated: false, diff_truncated: false, root_missing: false,
      reason_code: "git_diff_output_too_large",
    },
  });
  render(BuildArtifactPane, { repoId: "repo_1", onclose: () => {} });
  expect(await screen.findByText(/diff is too large to review safely/i)).toBeInTheDocument();
});
