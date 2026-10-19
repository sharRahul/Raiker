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

  it("asks the composer's model to read the patch and labels its findings as the model's", async () => {
    const reading = {
      fingerprint: FINGERPRINT,
      provider: "anthropic",
      model: "claude-haiku-5-5",
      truncated: false,
      reviewed_at: "2026-10-19T12:00:00Z",
      counts: { high: 0, medium: 1, low: 0, info: 0 },
      findings: [
        {
          finding_id: "m1",
          rule: "model_review",
          severity: "medium",
          category: "model_review",
          title: "Division by zero",
          evidence: "`1 / 0` always raises.",
          next_step: "Return 1.",
          confidence: "medium",
          path: "app/calc.py",
          line: 4,
          source: "model",
        },
      ],
    };
    const fetch = stubFetch({
      [`GET ${ROUTE}`]: { fingerprint: FINGERPRINT, has_changes: true, review: null, reused: false, reason_code: null },
      [`POST ${ROUTE}/model`]: { fingerprint: FINGERPRINT, has_changes: true, model_review: reading, reused: false, reason_code: null },
    });
    const requests: string[] = [];
    render(PatchReview, {
      repoId: "repo_1",
      reviewModel: { profile: "anthropic-default", model: "claude-haiku-5-5" },
      onrepair: (request: string) => requests.push(request),
    });
    await fireEvent.click(await screen.findByRole("button", { name: /^Ask .+ to review$/ }));
    expect(await screen.findByText("Division by zero")).toBeInTheDocument();
    expect(screen.getByText(/These are its reading, not checks/)).toBeInTheDocument();
    // The model's `code` spans read as code, not as literal backticks.
    expect(screen.getByText("1 / 0").tagName).toBe("CODE");
    const post = fetch.mock.calls.find(([url]) => String(url).endsWith("/review/model"));
    expect(JSON.parse(String((post?.[1] as RequestInit).body))).toEqual({
      model_profile: "anthropic-default",
      model: "claude-haiku-5-5",
    });
    await fireEvent.click(screen.getByRole("button", { name: "Ask Raiker to fix" }));
    expect(requests[0]).toContain("app/calc.py at line 4: Division by zero");
  });

  it("says when the model's answer could not be read, and stores nothing", async () => {
    stubFetch({
      [`GET ${ROUTE}`]: { fingerprint: FINGERPRINT, has_changes: true, review: null, reused: false, reason_code: null },
      [`POST ${ROUTE}/model`]: { __status: 502, detail: { reason_code: "model_review_unreadable" } },
    });
    render(PatchReview, { repoId: "repo_1" });
    await fireEvent.click(await screen.findByRole("button", { name: "Ask the model to review" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not with findings Raiker could read");
  });

  it("says a stored review is signed here, and warns when it no longer matches its signature", async () => {
    stubFetch({
      [`GET ${ROUTE}`]: {
        fingerprint: FINGERPRINT, has_changes: true, review, reused: true, reason_code: null,
        attestation: { state: "verified", key_id: "mkey_1", signed_at: "2026-10-19T12:00:00Z" },
      },
    });
    const { unmount } = render(PatchReview, { repoId: "repo_1" });
    const signed = await screen.findByText("Signed here");
    expect(signed).toHaveAttribute("title", expect.stringContaining("mkey_1"));
    expect(screen.queryByTestId("patch-review-tampered")).toBeNull();
    unmount();

    stubFetch({
      [`GET ${ROUTE}`]: {
        fingerprint: FINGERPRINT, has_changes: true, review, reused: true, reason_code: null,
        attestation: { state: "invalid", key_id: "mkey_1", signed_at: "2026-10-19T12:00:00Z" },
      },
    });
    render(PatchReview, { repoId: "repo_1" });
    expect(await screen.findByTestId("patch-review-tampered")).toHaveTextContent("don't rely on these findings");
  });

  it("reviews the patch again once after a repair turn settles, and counts a finding that persists", async () => {
    const persisting = {
      ...review,
      findings: [{ ...review.findings[0], since: "still_present", reviews_present: 3 }],
      counts: { high: 1, medium: 0, low: 0, info: 0 },
    };
    const fetch = stubFetch({
      [`GET ${ROUTE}`]: { fingerprint: FINGERPRINT, has_changes: true, review: persisting, reused: true, reason_code: null },
      [`POST ${ROUTE}`]: { fingerprint: FINGERPRINT, has_changes: true, review, reused: false, reason_code: null },
    });
    const requests: string[] = [];
    const { rerender } = render(PatchReview, {
      repoId: "repo_1",
      revision: 1,
      onrepair: (request: string) => requests.push(request),
    });
    expect(await screen.findByText("In 3 reviews in a row")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Ask Raiker to fix" }));
    expect(requests).toHaveLength(1);
    const posts = () => fetch.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST").length;
    expect(posts()).toBe(0);

    // The repair turn settles: the patch moved, so the next read has no review yet.
    stubFetch({
      [`GET ${ROUTE}`]: { fingerprint: "f2", has_changes: true, review: null, reused: false, reason_code: null },
      [`POST ${ROUTE}`]: { fingerprint: "f2", has_changes: true, review, reused: false, reason_code: null },
    });
    await rerender({ repoId: "repo_1", revision: 2, onrepair: (request: string) => requests.push(request) });
    expect(await screen.findByTestId("patch-review-rereviewed")).toBeInTheDocument();

    // A later settle without a new repair request reviews nothing by itself.
    const quiet = stubFetch({
      [`GET ${ROUTE}`]: { fingerprint: "f3", has_changes: true, review: null, reused: false, reason_code: null },
    });
    await rerender({ repoId: "repo_1", revision: 3, onrepair: (request: string) => requests.push(request) });
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(quiet.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST")).toBe(false);
  });
});
