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
});
