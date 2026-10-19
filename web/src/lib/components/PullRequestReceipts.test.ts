/**
 * BR-12 — pull requests Raiker opened are shown with what GitHub confirmed.
 */
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import PullRequestReceipts from "./PullRequestReceipts.svelte";
import { stubFetch } from "../test-helpers";

const ROUTE = "GET /api/code/repos/repo_1/pull-requests";

const receipt = (over: Record<string, unknown>) => ({
  receipt_id: "prr_1",
  repository: "github.com/octo/repo",
  number: 7,
  url: "https://github.com/octo/repo/pull/7",
  head_branch: "raiker/fix",
  base_branch: "main",
  head_sha: "a".repeat(40),
  state: "open",
  confirmation: "confirmed",
  session_id: "sess_1",
  turn_id: "turn_1",
  created_at: "2026-10-19T12:00:00Z",
  confirmed_at: "2026-10-19T12:00:01Z",
  ...over,
});

describe("PullRequestReceipts", () => {
  it("says which pull requests GitHub confirmed, and which it did not", async () => {
    stubFetch({
      [ROUTE]: {
        repository: "github.com/octo/repo",
        reason_code: null,
        receipts: [
          receipt({}),
          receipt({ receipt_id: "prr_2", number: 8, confirmation: "unconfirmed", confirmed_at: null }),
          receipt({ receipt_id: "prr_3", number: 9, confirmation: "mismatch", head_branch: "someone/else" }),
        ],
      },
    });
    render(PullRequestReceipts, { repoId: "repo_1" });
    expect(await screen.findByText("Confirmed by GitHub")).toBeInTheDocument();
    expect(screen.getByText("Not confirmed")).toBeInTheDocument();
    expect(screen.getByText("GitHub answered differently")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "#7" })).toHaveAttribute("href", "https://github.com/octo/repo/pull/7");
    expect(screen.getAllByText("aaaaaaa").length).toBe(3);
  });

  it("shows nothing for a repository with no pull requests from Raiker", async () => {
    stubFetch({ [ROUTE]: { repository: null, reason_code: "not_a_github_repository", receipts: [] } });
    render(PullRequestReceipts, { repoId: "repo_1" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByTestId("pull-request-receipts")).toBeNull();
  });
});
