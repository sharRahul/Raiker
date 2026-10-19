/**
 * BR-D04 — the Changes pane reviews the exact patch once, and shows the stored
 * review of the same patch instead of a second set of findings.
 */
import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import PatchReview from "./PatchReview.svelte";
import { stubFetch } from "../test-helpers";

const ROUTE = "/api/code/repos/repo_1/review";
const FINGERPRINT = "0123456789abcdef".repeat(4);

const review = {
  fingerprint: FINGERPRINT,
  files: 2,
  added_lines: 3,
  truncated: false,
  reviewed_at: "2026-10-19T12:00:00Z",
  counts: { high: 1, medium: 1, low: 0, info: 0 },
  findings: [
    {
      finding_id: "f1",
      rule: "possible_credential",
      severity: "high",
      category: "security",
      title: "Possible credential added",
      evidence: "This line matches a credential pattern. The value is withheld.",
      next_step: "Remove it from the change, rotate it, and read it from the environment or a secret store instead.",
      confidence: "medium",
      path: "app/config.py",
      line: 2,
    },
    {
      finding_id: "f2",
      rule: "source_without_tests",
      severity: "medium",
      category: "tests",
      title: "Source changed without a test change",
      evidence: "1 source file(s) changed and no test file did.",
      next_step: "Add or update a test that fails without this change.",
      confidence: "medium",
      path: null,
      line: null,
    },
  ],
};

describe("PatchReview", () => {
  it("offers a review of an unreviewed patch and shows its findings with their lines", async () => {
    const fetch = stubFetch({
      [`GET ${ROUTE}`]: { fingerprint: FINGERPRINT, has_changes: true, review: null, reused: false, reason_code: null },
      [`POST ${ROUTE}`]: { fingerprint: FINGERPRINT, has_changes: true, review, reused: false, reason_code: null },
    });
    render(PatchReview, { repoId: "repo_1" });
    const button = await screen.findByRole("button", { name: "Review this patch" });
    await fireEvent.click(button);
    expect(await screen.findByText("2 findings: 1 high, 1 medium.")).toBeInTheDocument();
    expect(screen.getByText("app/config.py:2")).toBeInTheDocument();
    expect(screen.getByText("Reviewed just now · 01234567")).toBeInTheDocument();
    expect(fetch.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST")).toBe(true);
    // The value of a credential is never part of what is shown.
    expect(screen.getByText(/The value is withheld/)).toBeInTheDocument();
  });

  it("shows the stored review of the same patch without asking again", async () => {
    stubFetch({ [`GET ${ROUTE}`]: { fingerprint: FINGERPRINT, has_changes: true, review, reused: true, reason_code: null } });
    render(PatchReview, { repoId: "repo_1" });
    expect(await screen.findByText("Reviewed · 01234567")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Review this patch" })).toBeNull();
  });

  it("says nothing when there is no patch to review", async () => {
    stubFetch({ [`GET ${ROUTE}`]: { fingerprint: "", has_changes: false, review: null, reused: false, reason_code: null } });
    render(PatchReview, { repoId: "repo_1" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByTestId("patch-review")).toBeNull();
  });

  it("marks new findings, lists what was fixed, and offers a scoped repair it never sends", async () => {
    const reviewed = {
      ...review,
      findings: [{ ...review.findings[0], since: "new" }, { ...review.findings[1], since: "still_present" }],
      previous_fingerprint: "f".repeat(64),
      resolved: [{ rule: "debug_left_in", title: "Debugging statement left in", severity: "low", path: "app/config.py", line: 3 }],
    };
    const fetch = stubFetch({
      [`GET ${ROUTE}`]: { fingerprint: FINGERPRINT, has_changes: true, review: reviewed, reused: true, reason_code: null, previous: null },
    });
    const asked: string[] = [];
    render(PatchReview, { repoId: "repo_1", onrepair: (text: string) => asked.push(text) });
    expect(await screen.findByText("New")).toBeInTheDocument();
    const resolved = screen.getByTestId("patch-review-resolved");
    expect(resolved).toHaveTextContent("Debugging statement left in");
    expect(resolved.querySelector("code.resolved-path")).toHaveTextContent("app/config.py");
    const callsBefore = fetch.mock.calls.length;
    await fireEvent.click(screen.getAllByRole("button", { name: "Ask Raiker to fix" })[0]);
    expect(asked[0]).toContain("in app/config.py at line 2: Possible credential added.");
    expect(asked[0]).toContain("Do not commit, push or merge.");
    // Asking writes the request into the composer; it calls nothing.
    expect(fetch.mock.calls.length).toBe(callsBefore);
  });

  it("says when the last review was of an earlier version of the patch", async () => {
    stubFetch({
      [`GET ${ROUTE}`]: {
        fingerprint: FINGERPRINT,
        has_changes: true,
        review: null,
        reused: false,
        reason_code: null,
        previous: { fingerprint: "e".repeat(64), reviewed_at: "2026-10-19T11:00:00Z", findings: 2, counts: { high: 1 } },
      },
    });
    render(PatchReview, { repoId: "repo_1" });
    expect(await screen.findByTestId("patch-review-stale")).toHaveTextContent("earlier version of this patch (2 findings)");
    expect(screen.getByRole("button", { name: "Review this patch" })).toBeInTheDocument();
  });
});
