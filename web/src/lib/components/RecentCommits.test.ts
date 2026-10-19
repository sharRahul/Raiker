/**
 * BR-D05 — recent commits say which Raiker made, from what the server proved.
 */
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import RecentCommits from "./RecentCommits.svelte";
import { stubFetch } from "../test-helpers";

const ROUTE = "GET /api/code/repos/repo_1/provenance";

describe("RecentCommits", () => {
  it("labels a recorded Raiker commit, a bare claim, and a plain commit differently", async () => {
    stubFetch({
      [ROUTE]: {
        reason_code: null,
        commits: [
          { commit: "a1b2c3d", subject: "Raise x", committed_at: "2026-10-19T12:00:00Z", provenance: "recorded", session_id: "sess_1", turn_id: "turn_1" },
          { commit: "d4e5f6a", subject: "Hand made", committed_at: "2026-10-19T11:00:00Z", provenance: "unrecorded", session_id: "sess_2", turn_id: null },
          { commit: "0f9e8d7", subject: "init", committed_at: "2026-10-19T10:00:00Z", provenance: "none", session_id: null, turn_id: null },
        ],
      },
    });
    render(RecentCommits, { repoId: "repo_1" });
    expect(await screen.findByText("Raise x")).toBeInTheDocument();
    expect(screen.getByText("Made in Raiker")).toHaveAttribute("title", "Turn turn_1");
    expect(screen.getByText("Says Raiker — no record here")).toBeInTheDocument();
    const plain = screen.getByText("init").closest("li");
    expect(plain).toHaveAttribute("data-provenance", "none");
    expect(plain?.querySelector(".badge")).toBeNull();
  });

  it("shows nothing for a repository with no history to read", async () => {
    stubFetch({ [ROUTE]: { reason_code: "not_a_git_repository", commits: [] } });
    render(RecentCommits, { repoId: "repo_1" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByTestId("recent-commits")).toBeNull();
  });

  it("shows Git's verdict on a commit the owner signed, and nothing for an unsigned one", async () => {
    stubFetch({
      [ROUTE]: {
        reason_code: null,
        commits: [
          { commit: "1111111", subject: "Signed by me", committed_at: "2026-10-19T12:00:00Z", provenance: "none", session_id: null, turn_id: null, signature: "good" },
          { commit: "2222222", subject: "Tampered", committed_at: "2026-10-19T11:00:00Z", provenance: "none", session_id: null, turn_id: null, signature: "bad" },
          { commit: "3333333", subject: "Plain", committed_at: "2026-10-19T10:00:00Z", provenance: "none", session_id: null, turn_id: null, signature: "none" },
        ],
      },
    });
    render(RecentCommits, { repoId: "repo_1" });
    expect(await screen.findByText("Signed")).toBeInTheDocument();
    expect(screen.getByText("Bad signature")).toHaveAttribute("data-signature", "bad");
    expect(screen.getByText("Plain").closest("li")?.querySelector(".signature")).toBeNull();
  });
});
