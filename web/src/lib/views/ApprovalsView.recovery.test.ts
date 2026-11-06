/**
 * QUI-G06 — Approvals errors name what failed, what it affected and one safe
 * next step. A decision whose answer was lost may have been recorded, so the
 * step is always "check before deciding again", never "try again".
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ApprovalsView from "./ApprovalsView.svelte";
import { stubFetch } from "../test-helpers";
import { publishPendingApprovalCount } from "../approvalResume";

const PENDING = {
  approval_id: "appr_1",
  action_id: "act_1",
  status: "pending",
  tool_name: "write_file",
  capability: "file_write_execution",
  risk_level: "medium",
  session_id: "sess_abcdef123456",
  turn_id: "turn_1",
  created_at: "2026-07-07T00:00:00Z",
  age_seconds: 60,
  requires_approval: true,
  executes_action: false,
};

const DETAIL = {
  approval: PENDING,
  arguments: { path: "notes.txt" },
  diff: "--- a/notes.txt\n+++ b/notes.txt\n+hello\n",
  diff_path: "notes.txt",
  preview_kind: "file_diff",
  metadata_only_notice: "Approving this performs the change shown above, once, in your workspace.",
  executes_on_approval: true,
};

const CRITICAL = { ...PENDING, approval_id: "appr_critical", tool_name: "shell_exec", risk_level: "critical", critical: true };

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  window.location.hash = "";
});

async function openFirst() {
  const [first] = within(await screen.findByRole("listbox")).getAllByRole("option");
  await fireEvent.click(first);
}

describe("ApprovalsView recovery (QUI-G06)", () => {
  it("retries a failed read and keeps rows already read when a refresh fails", async () => {
    const routes: Record<string, unknown> = { "GET /api/approvals": { __status: 503 } };
    stubFetch(routes);
    render(ApprovalsView);
    expect(await screen.findByText(/approvals could not be read \(HTTP 503\)\. Which decisions are waiting is unknown/i)).toBeInTheDocument();

    routes["GET /api/approvals"] = [PENDING];
    await fireEvent.click(screen.getByRole("button", { name: "Retry approvals" }));
    expect(await screen.findByRole("listbox")).toBeInTheDocument();
    expect(screen.queryByText(/approvals could not be read/i)).toBeNull();

    routes["GET /api/approvals"] = { __status: 500 };
    await fireEvent.click(screen.getByRole("button", { name: "Refresh approvals" }));
    expect(await screen.findByText(/the list below may be out of date/i)).toBeInTheDocument();
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("names a decision that could not be opened and opens it again", async () => {
    const routes: Record<string, unknown> = {
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": { __status: 500 },
    };
    stubFetch(routes);
    render(ApprovalsView);
    await openFirst();
    expect(await screen.findByText(/this approval could not be opened \(HTTP 500\)\. .*nothing was decided/i)).toBeInTheDocument();

    routes["GET /api/approvals/appr_1"] = DETAIL;
    await fireEvent.click(screen.getByRole("button", { name: "Open it again" }));
    expect(await screen.findByRole("button", { name: /^allow once$/i })).toBeInTheDocument();
  });

  it("says a lost decision may have run and to check History before deciding again", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": DETAIL,
      "POST /api/approvals/appr_1/resolve": { __status: 502 },
    });
    render(ApprovalsView);
    await openFirst();
    await fireEvent.click(await screen.findByRole("button", { name: /^allow once$/i }));
    const notice = await screen.findByText(/allowing this was not confirmed \(HTTP 502\)/i);
    expect(notice).toHaveTextContent(/may have been recorded/i);
    expect(notice).toHaveTextContent(/check History for this approval before deciding again/i);
    expect(notice).not.toHaveTextContent(/rejected/i);
  });

  it("keeps a governed refusal in words, not the generic unconfirmed sentence", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": DETAIL,
      "POST /api/approvals/appr_1/resolve": { __status: 409, detail: { reason_code: "denied_by_policy" } },
    });
    render(ApprovalsView);
    await openFirst();
    await fireEvent.click(await screen.findByRole("button", { name: /^allow once$/i }));
    await waitFor(() => expect(document.querySelector(".notice-danger")).not.toBeNull());
    expect(document.querySelector(".notice-danger")?.textContent).not.toMatch(/was not confirmed/i);
  });

  it("tells a refused step-up apart from a critical decision whose answer was lost", async () => {
    const routes: Record<string, unknown> = {
      "GET /api/approvals": [CRITICAL],
      "GET /api/approvals/appr_critical": { ...DETAIL, approval: CRITICAL },
      "POST /api/auth/elevate": { __status: 500 },
      "POST /api/approvals/appr_critical/resolve-critical": { __status: 502 },
    };
    stubFetch(routes);
    render(ApprovalsView);
    await openFirst();
    await fireEvent.click(await screen.findByRole("button", { name: "Begin critical denial" }));
    await fireEvent.input(screen.getByLabelText("Decision note"), { target: { value: "Too risky" } });
    await fireEvent.input(screen.getByLabelText("Password"), { target: { value: "secret" } });
    await fireEvent.click(screen.getByRole("button", { name: "Deny critical action" }));
    expect(await screen.findByText(/step-up verification was not completed \(HTTP 500\)\. Nothing was decided/i)).toBeInTheDocument();

    routes["POST /api/auth/elevate"] = { token: "elevated" };
    await fireEvent.click(screen.getByRole("button", { name: "Deny critical action" }));
    expect(await screen.findByText(/the critical decision was not confirmed \(HTTP 502\)\. Verification succeeded/i)).toBeInTheDocument();
  });

  it("says a lost answer to a question may have reached the turn", async () => {
    const QUESTION = { ...PENDING, approval_id: "appr_q", tool_name: "ask_owner_question", capability: null, risk_level: "low" };
    stubFetch({
      "GET /api/approvals": [QUESTION],
      "GET /api/approvals/appr_q": {
        approval: QUESTION,
        arguments: { questions: [{ question: "Which one?", header: "Pick", options: [{ label: "A", description: "a" }, { label: "B", description: "b" }] }] },
        diff: null,
        diff_path: null,
        preview_kind: "arguments",
        metadata_only_notice: "",
        executes_on_approval: false,
      },
      "POST /api/approvals/appr_q/answer": { __status: 504 },
    });
    render(ApprovalsView);
    await openFirst();
    await fireEvent.click(await screen.findByRole("radio", { name: /^A/ }));
    await fireEvent.click(screen.getByRole("button", { name: /send answer/i }));
    expect(await screen.findByText(/the answer was not confirmed \(HTTP 504\)\. It may have reached the turn/i)).toBeInTheDocument();
  });

  it("re-reads an open queue when the top bar's pending count changes", async () => {
    const routes: Record<string, unknown> = { "GET /api/approvals": [] };
    stubFetch(routes);
    render(ApprovalsView);
    expect(await screen.findByText("Nothing waiting on you")).toBeInTheDocument();
    routes["GET /api/approvals"] = [PENDING];
    publishPendingApprovalCount(1);
    expect(await screen.findByRole("listbox")).toBeInTheDocument();
  });

  it("does not let an unknown refusal code hide that the decision may have run", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": DETAIL,
      "POST /api/approvals/appr_1/resolve": { __status: 503, detail: { reason_code: "injected_failure" } },
    });
    render(ApprovalsView);
    await openFirst();
    await fireEvent.click(await screen.findByRole("button", { name: /^allow once$/i }));
    const notice = await screen.findByText(/allowing this was not confirmed \(HTTP 503, injected_failure\)/i);
    expect(notice).toHaveTextContent(/check History/i);
  });
});
