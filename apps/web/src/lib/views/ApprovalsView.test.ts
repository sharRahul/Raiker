import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ApprovalsView from "./ApprovalsView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

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
  metadata_only_notice:
    "Approval resolution is metadata-only. Recording a decision does NOT execute the action.",
  executes_on_approval: false,
};

// ADD-02 — the same approval as part of a three-call batch the turn parked on.
const BATCHED = {
  ...PENDING,
  approval_id: "appr_batched",
  queue_position: 2,
  queue_total: 3,
};

const EXPIRED = {
  ...PENDING,
  expires_at: "2000-01-01T00:00:00Z",
  is_expired: true,
};

const CRITICAL = {
  ...PENDING,
  approval_id: "appr_critical",
  tool_name: "shell_exec",
  risk_level: "critical",
  critical: true,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApprovalsView", () => {
  it("shows a route-level loading state while approvals are fetched", async () => {
    stubFetchPending();
    render(ApprovalsView);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/loading approvals/i);
  });

  it("shows a route-level error state when approvals cannot load", async () => {
    stubFetch({});
    render(ApprovalsView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load approvals/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("lists pending approvals with their capability and risk", async () => {
    stubFetch({ "GET /api/approvals": [PENDING] });
    render(ApprovalsView);
    // The raw tool identifier "write_file" is shown as a plain-English name, not a code.
    await waitFor(() => {
      expect(screen.getByText("Write file")).toBeInTheDocument();
    });
    expect(screen.queryByText("write_file")).not.toBeInTheDocument();
    expect(screen.getByText("File writes")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
  });

  it("names the machine proposer separately from the human authorizer", async () => {
    const proposed = {
      principal_id: "principal_turn_agent_1",
      principal_type: "ai_agent",
      display_name: "Raiker agent · turn_1",
      subject: "spiffe://raiker/ws/agent/turn/turn_1",
      turn_id: "turn_1",
      key_id: "mkey_1",
      issued_at: "2026-07-07T00:00:00Z",
      expires_at: "2026-07-07T00:15:00Z",
      state: "inactive",
    };
    const approved = {
      ...proposed,
      principal_id: "principal_owner",
      principal_type: "human",
      display_name: "Owner",
      subject: null,
      turn_id: null,
      key_id: null,
      issued_at: null,
      expires_at: null,
      state: "active",
    };
    const attributed = { ...PENDING, proposed_by: proposed, approved_by: approved };
    stubFetch({
      "GET /api/approvals": [attributed],
      "GET /api/approvals/appr_1": { ...DETAIL, approval: attributed },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));

    expect(screen.getAllByText("Raiker agent · turn_1").length).toBeGreaterThan(0);
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText("Authorized by")).toBeInTheDocument();
  });

  it("triages approvals by risk by default and can switch to newest first", async () => {
    const critical = {
      ...PENDING,
      approval_id: "appr_critical",
      tool_name: "shell_exec",
      risk_level: "critical",
      created_at: "2026-07-06T00:00:00Z",
    };
    const low = {
      ...PENDING,
      approval_id: "appr_low",
      tool_name: "http_request",
      risk_level: "low",
      created_at: "2026-07-08T00:00:00Z",
    };
    const newerMedium = {
      ...PENDING,
      approval_id: "appr_newer_medium",
      tool_name: "read_file",
      created_at: "2026-07-09T00:00:00Z",
    };
    stubFetch({ "GET /api/approvals": [PENDING, low, critical, newerMedium] });
    render(ApprovalsView);

    await screen.findByText("Shell exec");
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining("Shell exec"),
      expect.stringContaining("Read file"),
      expect.stringContaining("Write file"),
      expect.stringContaining("Http request"),
    ]);

    await fireEvent.change(screen.getByLabelText("Sort approvals"), { target: { value: "newest" } });
    expect(screen.getAllByRole("row").slice(1).map((row) => row.textContent)).toEqual([
      expect.stringContaining("Read file"),
      expect.stringContaining("Http request"),
      expect.stringContaining("Write file"),
      expect.stringContaining("Shell exec"),
    ]);
  });

  it("shows the metadata-only notice and diff preview in the review panel", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": DETAIL,
    });
    render(ApprovalsView);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /review/i })).toBeInTheDocument();
    });
    await fireEvent.click(screen.getByRole("button", { name: /review/i }));
    await waitFor(() => {
      expect(screen.getByText(/metadata-only/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/\+hello/)).toBeInTheDocument();
    // Approve is explicit about not executing.
    expect(screen.getByRole("button", { name: /approve \(record only\)/i })).toBeInTheDocument();
  });

  it("shows a server-reported expiry warning and withholds decision controls", async () => {
    stubFetch({
      "GET /api/approvals": [EXPIRED],
      "GET /api/approvals/appr_1": { ...DETAIL, approval: EXPIRED },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));

    expect(await screen.findByText(/expired at/i)).toBeInTheDocument();
    expect(screen.getByText(/the server will not accept a decision/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deny" })).not.toBeInTheDocument();
    expect(
      screen.queryByText((_, element) => element?.textContent?.includes("Already resolved: pending") ?? false),
    ).not.toBeInTheDocument();
  });

  // BUG-06 — a file write the owner approves is really performed. The view must
  // label the button and report the outcome from what the *server* says it will
  // do, never from a hardcoded assumption about metadata-only resolution.
  it("offers to execute, and names the written file, when the server says approving performs the write", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": {
        ...DETAIL,
        executes_on_approval: true,
        metadata_only_notice:
          "Approving this performs the change shown above, once, in your workspace.",
      },
      "POST /api/approvals/appr_1/resolve": {
        approval_id: "appr_1",
        action_id: "act_1",
        status: "executed",
        executes_action: true,
        reason: "approved via web UI",
        execution: { capability: "file_write_execution", path: "notes.txt" },
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    expect(
      await screen.findByText(/approving this performs the change shown above/i),
    ).toBeInTheDocument();
    await fireEvent.click(await screen.findByRole("button", { name: /approve and execute once/i }));

    expect(await screen.findByText(/executed once — wrote notes\.txt/i)).toBeInTheDocument();
  });

  it("names a completed write as not reversible when checkpoint capture failed", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": { ...DETAIL, executes_on_approval: true },
      "POST /api/approvals/appr_1/resolve": {
        approval_id: "appr_1",
        action_id: "act_1",
        status: "executed",
        executes_action: true,
        reason: "approved via web UI",
        execution: {
          capability: "file_write_execution",
          path: "notes.txt",
          checkpoint_capture: {
            ok: false,
            stage: "snapshot",
            reason_code: "checkpoint_snapshot_os_error",
            display_path: "notes.txt",
            checked_at: "2026-08-21T00:00:00Z",
            remediation: "Check workspace permissions and enable Windows long-path support.",
          },
        },
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    await fireEvent.click(await screen.findByRole("button", { name: /approve and execute once/i }));

    const notice = await screen.findByText(/change completed — not reversible/i);
    expect(notice).toHaveTextContent(/checkpoint_snapshot_os_error/i);
    expect(notice).toHaveTextContent(/enable Windows long-path support/i);
    expect(notice).not.toHaveTextContent(/previous contents were checkpointed/i);
  });

  it("keeps the record-only label and message when the server says the capability is gated off", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": DETAIL,
      "POST /api/approvals/appr_1/resolve": {
        approval_id: "appr_1",
        action_id: "act_1",
        status: "approved",
        executes_action: false,
        reason: "approved via web UI",
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    await fireEvent.click(await screen.findByRole("button", { name: /approve \(record only\)/i }));

    expect(await screen.findByText(/was NOT executed \(metadata-only\)/i)).toBeInTheDocument();
  });

  it("shows the terminal principal and bounded execution evidence in history", async () => {
    const resolved = {
      ...PENDING,
      status: "executed",
      requires_approval: false,
      resolved_by: "principal_owner",
    };
    stubFetch({
      "GET /api/approvals": [resolved],
      "GET /api/approvals/appr_1": {
        ...DETAIL,
        approval: resolved,
        execution_evidence: {
          principal_id: "principal_owner",
          returncode: 0,
          stdout_bytes: 15,
          stderr_bytes: 0,
          stdout: "terminal relay\n",
          stderr: "",
          truncated: false,
        },
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));

    expect(await screen.findByText("Execution evidence")).toBeInTheDocument();
    expect(screen.getAllByText("principal_owner").length).toBeGreaterThan(0);
    expect(screen.getByText("terminal relay")).toBeInTheDocument();
    expect(screen.getByText(/15 B stdout/)).toBeInTheDocument();
  });

  // B2 — resolving an approval closes the tool call the model was waiting on,
  // so the turn it parked can continue instead of costing the owner a re-prompt.
  it("offers to continue the parked turn when the server says one is waiting", async () => {
    const fetchMock = stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": { ...DETAIL, executes_on_approval: true },
      "POST /api/approvals/appr_1/resolve": {
        approval_id: "appr_1",
        action_id: "act_1",
        status: "executed",
        executes_action: true,
        reason: "approved via web UI",
        execution: { capability: "file_write_execution", path: "notes.txt" },
        resume: { resumable: true, session_id: "sess_abcdef123456", turn_id: "turn_1" },
      },
      "POST /api/approvals/appr_1/resume": {
        request_id: "req_1",
        session_id: "sess_abcdef123456",
        turn_id: "turn_1",
        status: "completed",
        message: "Done — notes.txt is written.",
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    await fireEvent.click(await screen.findByRole("button", { name: /approve and execute once/i }));

    await fireEvent.click(await screen.findByRole("button", { name: /continue the turn/i }));

    expect(await screen.findByText(/done — notes\.txt is written/i)).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some((call) => String(call[0]) === "/api/approvals/appr_1/resume"),
    ).toBe(true);
  });

  it("does not offer to continue when no turn was parked on the approval", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": DETAIL,
      "POST /api/approvals/appr_1/resolve": {
        approval_id: "appr_1",
        action_id: "act_1",
        status: "approved",
        executes_action: false,
        reason: "approved via web UI",
        resume: { resumable: false },
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    await fireEvent.click(await screen.findByRole("button", { name: /approve \(record only\)/i }));

    await screen.findByText(/was NOT executed/i);
    expect(screen.queryByRole("button", { name: /continue the turn/i })).not.toBeInTheDocument();
  });

  it("keeps executed approvals reachable through their own filter tab", async () => {
    // `executed` is the terminal status the relay writes, so without this tab
    // every approval the owner actually carried out would vanish from the queue.
    const executed = { ...PENDING, approval_id: "appr_done", status: "executed", requires_approval: false };
    const fetchMock = stubFetch({ "GET /api/approvals": [executed] });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("tab", { name: /executed/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some((call) => String(call[0]).includes("status_filter=executed")),
      ).toBe(true);
    });
    expect(await screen.findByRole("button", { name: /review/i })).toBeInTheDocument();
  });

  it("reports the connector-write exception after server-confirmed execution", async () => {
    const connectorApproval = {
      ...PENDING,
      approval_id: "appr_connector",
      tool_name: "connector_write",
      executes_action: true,
    };
    stubFetch({
      "GET /api/approvals": [connectorApproval],
      "GET /api/approvals/appr_connector": {
        ...DETAIL,
        approval: connectorApproval,
        preview_kind: "arguments",
        diff: null,
        diff_path: null,
        metadata_only_notice: "Approving this connector write executes this exact action once.",
        executes_on_approval: true,
      },
      "POST /api/approvals/appr_connector/resolve": {
        approval_id: "appr_connector",
        action_id: "act_1",
        status: "executed",
        executes_action: true,
        reason: "approved via web UI",
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    await fireEvent.click(await screen.findByRole("button", { name: /approve and execute once/i }));

    expect(await screen.findByText(/executed once: executed/i)).toBeInTheDocument();
  });

  it("shows a friendly empty state when nothing is pending", async () => {
    stubFetch({ "GET /api/approvals": [] });
    render(ApprovalsView);
    await waitFor(() => {
      expect(screen.getByText(/nothing waiting on you/i)).toBeInTheDocument();
    });
  });

  it("filters the queue to the linked session and links back to its detail", async () => {
    const anotherSession = { ...PENDING, approval_id: "appr_other", session_id: "sess_other" };
    stubFetch({
      "GET /api/approvals": [PENDING, anotherSession],
      "GET /api/approvals/appr_1": DETAIL,
    });
    render(ApprovalsView, { sessionId: PENDING.session_id });

    await screen.findByText("Write file");
    expect(screen.queryByText("appr_other")).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: /review/i }));
    expect(await screen.findByRole("link", { name: "View session" })).toHaveAttribute(
      "href",
      `#/sessions?session=${PENDING.session_id}`,
    );
  });

  // ADD-02 — a batched turn asks for several decisions on one turn. Without this
  // the inbox shows three near-identical rows and the owner cannot tell whether
  // the agent is proposing three things or proposing one thing three times.
  it("says which decision of a batch each approval is", async () => {
    stubFetch({ "GET /api/approvals": [BATCHED] });
    render(ApprovalsView);

    expect(await screen.findByText(/decision 2 of 3/i)).toBeInTheDocument();
  });

  it("does not label an ordinary single-call approval as part of a batch", async () => {
    stubFetch({ "GET /api/approvals": [{ ...PENDING, queue_position: 1, queue_total: 1 }] });
    render(ApprovalsView);

    await screen.findByText("Write file");
    expect(screen.queryByText(/decision 1 of 1/i)).not.toBeInTheDocument();
  });

  it("tells the owner how many calls the continuation still owes a decision", async () => {
    stubFetch({
      "GET /api/approvals": [BATCHED],
      "GET /api/approvals/appr_batched": { ...DETAIL, approval: BATCHED },
      "POST /api/approvals/appr_batched/resolve": {
        approval_id: "appr_batched",
        action_id: "act_1",
        status: "approved",
        executes_action: false,
        reason: "approved via web UI",
        resume: {
          resumable: true,
          session_id: "sess_abcdef123456",
          turn_id: "turn_1",
          queue_position: 2,
          queue_total: 3,
          queued_calls: 1,
        },
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    // Both the list row and the open detail pane place the decision inside its
    // batch, so the owner sees it whether or not they opened the review.
    expect(screen.getAllByText(/decision 2 of 3/i)).toHaveLength(2);
    await fireEvent.click(await screen.findByRole("button", { name: /approve \(record only\)/i }));

    expect(
      await screen.findByText(/1 more call from the same batch/i),
    ).toBeInTheDocument();
  });

  // BUG-24 / ADD-02 — walking a batch means resolving and continuing over and
  // over, so losing the race to the conversation's own watcher is routine. It is
  // still a success: the turn ran.
  it("reports a continuation that another tab already ran as a success", async () => {
    stubFetch({
      "GET /api/approvals": [BATCHED],
      "GET /api/approvals/appr_batched": { ...DETAIL, approval: BATCHED },
      "POST /api/approvals/appr_batched/resolve": {
        approval_id: "appr_batched",
        action_id: "act_1",
        status: "approved",
        executes_action: false,
        reason: "approved via web UI",
        resume: { resumable: true, session_id: "sess_abcdef123456", queued_calls: 1 },
      },
    });
    // The resume is the one route that must fail: `stubFetch` only answers 200,
    // so the conflict is layered on top of it.
    const routed = globalThis.fetch as unknown as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.endsWith("/api/approvals/appr_batched/resume")) {
        return {
          ok: false,
          status: 409,
          json: async () => ({ detail: { reason_code: "suspended_turn_already_resumed" } }),
        } as Response;
      }
      return routed(input, init);
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    await fireEvent.click(await screen.findByRole("button", { name: /approve \(record only\)/i }));
    await fireEvent.click(await screen.findByRole("button", { name: /continue the turn/i }));

    expect(await screen.findByText(/continued in another tab/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /continue the turn/i })).not.toBeInTheDocument();
  });

  it("requires fresh server-backed step-up before resolving a critical approval", async () => {
    const fetchMock = stubFetch({
      "GET /api/approvals": [CRITICAL],
      "GET /api/approvals/appr_critical": { ...DETAIL, approval: CRITICAL },
      "POST /api/auth/elevate": { token: "elevated-token" },
      "POST /api/approvals/appr_critical/resolve-critical": {
        approval_id: "appr_critical",
        status: "denied",
        decision: "deny",
        message: "critical_action_rejected",
        executes_action: false,
      },
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));
    await fireEvent.click(screen.getByRole("button", { name: "Begin critical denial" }));
    await fireEvent.input(screen.getByLabelText("Decision note"), { target: { value: "Risk is too high" } });
    await fireEvent.input(screen.getByLabelText("Password"), { target: { value: "secret" } });
    await fireEvent.click(screen.getByRole("button", { name: "Deny critical action" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/approvals/appr_critical/resolve-critical",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const call = fetchMock.mock.calls.find((item) => String(item[0]) === "/api/approvals/appr_critical/resolve-critical");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ approve: false, reason: "Risk is too high" });
    expect(await screen.findByText(/critical action was denied/i)).toBeInTheDocument();
  });

  // ADD-22 — a question rides the approval transport and must never look like an
  // approval. These assert the two halves that keep them apart on screen: the
  // approve/deny controls are *absent*, and the card says what answering does.
  const QUESTION = {
    ...PENDING,
    approval_id: "appr_question",
    tool_name: "ask_owner_question",
    capability: null,
    risk_level: "low",
  };

  const QUESTION_DETAIL = {
    approval: QUESTION,
    arguments: {
      questions: [
        {
          question: "Which database should the new service use?",
          header: "Database",
          options: [
            { label: "Postgres", description: "Relational, like the other services" },
            { label: "SQLite", description: "Embedded, no server to run" },
          ],
        },
      ],
    },
    diff: null,
    diff_path: null,
    preview_kind: "arguments",
    metadata_only_notice: "",
    executes_on_approval: false,
  };

  it("offers a question as a question, with no way to approve it", async () => {
    stubFetch({
      "GET /api/approvals": [QUESTION],
      "GET /api/approvals/appr_question": QUESTION_DETAIL,
    });
    render(ApprovalsView);

    await fireEvent.click(await screen.findByRole("button", { name: "Answer" }));

    expect(await screen.findByText(/Which database should the new service use\?/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Answer a question/i })).toBeTruthy();
    // The controls that must not exist here. An owner who can "approve" a
    // question has been shown a decision they were never asked to make.
    expect(screen.queryByRole("button", { name: /^Approve/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Deny$/ })).toBeNull();
    expect(screen.getByText(/grants nothing and\s+runs nothing/i)).toBeTruthy();
  });

  it("will not send an answer until every question has one", async () => {
    stubFetch({
      "GET /api/approvals": [QUESTION],
      "GET /api/approvals/appr_question": QUESTION_DETAIL,
    });
    render(ApprovalsView);
    await fireEvent.click(await screen.findByRole("button", { name: "Answer" }));

    const send = await screen.findByRole("button", { name: "Send answer" });
    expect(send).toBeDisabled();

    await fireEvent.click(screen.getByRole("radio", { name: /Postgres/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Send answer" })).toBeEnabled());
  });

  it("answers through the question route, never the resolve route", async () => {
    const fetchMock = stubFetch({
      "GET /api/approvals": [QUESTION],
      "GET /api/approvals/appr_question": QUESTION_DETAIL,
      "POST /api/approvals/appr_question/answer": {
        approval_id: "appr_question",
        status: "answered",
        answered: 1,
      },
    });
    render(ApprovalsView);
    await fireEvent.click(await screen.findByRole("button", { name: "Answer" }));
    await fireEvent.click(await screen.findByRole("radio", { name: /SQLite/ }));
    await fireEvent.click(screen.getByRole("button", { name: "Send answer" }));

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.endsWith("/answer"))).toBe(true);
      expect(calls.some((url) => url.endsWith("/resolve"))).toBe(false);
    });
  });
});
