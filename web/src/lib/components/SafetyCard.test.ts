import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, ApiError, setToken } from "../api";
import { contract } from "../generated/apiContract";
import type { ApprovalDetailView, ApprovalInfo } from "../apiTypes";
import { RESOLVED_HERE } from "../approvalResume";
import SafetyCard from "./SafetyCard.svelte";

beforeEach(() => setToken("test-token"));
afterEach(() => {
  setToken(null);
  vi.restoreAllMocks();
});

const INFO = {
  action_id: "act_1",
  approval_id: "ap_1",
  tool_name: "write_file",
  arguments: { path: "notes.md", text: "one\ntwo\n" },
  risk_level: "medium",
  reasons: [],
  message: "Raiker wants to write notes.md",
  expected_effect: "Writes one file in your workspace.",
  resumable: true,
  queue_position: 1,
  queue_total: 1,
  queued_calls: 0,
} as ApprovalInfo;

function detail(approval: Partial<ApprovalDetailView["approval"]> = {}, kind = "file_diff"): ApprovalDetailView {
  return {
    approval: {
      approval_id: "ap_1",
      status: "pending",
      capability: "file_write_execution",
      is_expired: false,
      critical: false,
      ...approval,
    },
    arguments: {},
    diff: null,
    diff_path: null,
    preview_kind: kind,
    metadata_only_notice: "",
    executes_on_approval: true,
    execution_evidence: {},
  } as unknown as ApprovalDetailView;
}

function stub(view: ApprovalDetailView, sideEffect = "reversible") {
  vi.spyOn(api, "approval").mockResolvedValue(view);
  vi.spyOn(api, "capabilityGate").mockResolvedValue({ side_effect: sideEffect } as never);
}

it("says the six things in order, and offers Decline, Change and Allow once", async () => {
  stub(detail());
  render(SafetyCard, { props: { approval: INFO } });

  expect(await screen.findByText("Can be undone afterwards.")).toBeInTheDocument();
  expect(screen.getByText("Waiting for your decision")).toBeInTheDocument();
  const labels = Array.from(document.querySelectorAll("dt")).map((node) => node.textContent);
  expect(labels).toEqual([
    "What will happen",
    "Why it needs you",
    "Affects",
    "Data involved",
    "Undo",
    "Safer alternative",
  ]);
  expect(screen.getByTestId("safety-affects")).toHaveTextContent("notes.md");
  expect(screen.getByTestId("safety-data")).toHaveTextContent("2 lines of text.");
  expect(screen.getByRole("button", { name: "Decline" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Change" })).toHaveAttribute("href", "#/approvals?item=ap_1");
  expect(screen.getByRole("button", { name: "Allow once" })).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/always allow/i);
  expect(document.querySelector("[data-raiker-safety]")).not.toBeNull();
});

it("decides in place and announces it, so every other place clears", async () => {
  stub(detail());
  const resolve = vi.spyOn(api, "resolveApproval").mockResolvedValue({
    approval_id: "ap_1",
    status: "approved",
    resume: { resumable: true, session_id: "sess_1", turn_id: "turn_1" },
  } as never);
  const heard = vi.fn();
  window.addEventListener(RESOLVED_HERE, heard);
  const onDecided = vi.fn();
  render(SafetyCard, { props: { approval: INFO, sessionId: "sess_1", onDecided } });

  await fireEvent.click(await screen.findByRole("button", { name: "Allow once" }));
  await waitFor(() => expect(onDecided).toHaveBeenCalledWith(true, true));
  expect(resolve).toHaveBeenCalledWith("ap_1", { approve: true, reason: "allowed once in the conversation" });
  expect(heard).toHaveBeenCalledTimes(1);
  window.removeEventListener(RESOLVED_HERE, heard);
});

it("marks an unanswered approval Not done, with Ask again and the time limit", async () => {
  stub(detail({ is_expired: true }));
  vi.spyOn(api, "settings").mockResolvedValue({
    settings: { "security.approval_timeout_minutes": 60 },
  } as never);
  const onAskAgain = vi.fn();
  render(SafetyCard, { props: { approval: INFO, onAskAgain } });

  expect(await screen.findByText("Not done: no decision")).toBeInTheDocument();
  expect(await screen.findByText(/Nobody answered within 1 hour/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Change the time limit" })).toHaveAttribute(
    "href",
    "#/settings?tab=security",
  );
  expect(screen.queryByRole("button", { name: "Allow once" })).not.toBeInTheDocument();
  // Nothing to change any more, so no safer alternative pointing at Change.
  expect(screen.queryByTestId("safety-alternative")).not.toBeInTheDocument();
  await fireEvent.click(screen.getByRole("button", { name: "Ask again" }));
  expect(onAskAgain).toHaveBeenCalledTimes(1);
});

it("turns a decision the server refused as expired into the Not done state", async () => {
  stub(detail());
  vi.spyOn(api, "settings").mockResolvedValue({ settings: {} } as never);
  vi.spyOn(api, "resolveApproval").mockRejectedValue(
    new ApiError(409, "approval_expired", "approval_expired"),
  );
  render(SafetyCard, { props: { approval: INFO } });

  await fireEvent.click(await screen.findByRole("button", { name: "Decline" }));
  expect(await screen.findByText("Not done: no decision")).toBeInTheDocument();
  expect(await screen.findByText(/Nobody answered within 30 minutes/)).toBeInTheDocument();
});

it("sends a critical decision to Approvals, where the password is asked", async () => {
  stub(detail({ critical: true }), "critical");
  render(SafetyCard, { props: { approval: INFO } });

  expect(await screen.findByText(/needs your password or a code/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Allow once" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Review in Approvals" })).toBeInTheDocument();
});

it("holds an allowed connector write with a countdown and Undo, and says when it was taken back (QUI-F19)", async () => {
  stub(detail({ capability: "connector_write" }, "connector_request"), "external");
  let finish: (value: unknown) => void = () => {};
  vi.spyOn(api, "resolveApproval").mockReturnValue(new Promise((resolve) => (finish = resolve)) as never);
  const undo = vi.spyOn(contract, "undoHeldSend").mockResolvedValue({ ok: true, approval_id: "ap_1", status: "undone" });
  const connectorWrite = { ...INFO, tool_name: "connector_write", arguments: { connector_id: "gmail", operation_id: "send", account: "Personal Gmail" } } as ApprovalInfo;
  render(SafetyCard, { props: { approval: connectorWrite, sessionId: "sess_1" } });

  await fireEvent.click(await screen.findByRole("button", { name: "Allow once" }));
  expect(await screen.findByText("Sending in 10 s")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Allow once" })).not.toBeInTheDocument();
  await fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(undo).toHaveBeenCalledWith("ap_1");
  finish({ approval_id: "ap_1", status: "undone", resume: { resumable: true, session_id: "sess_1", turn_id: "turn_1" } });
  expect(await screen.findByText("Not sent: you took it back")).toBeInTheDocument();
});

it("does not hold anything that is not sent through a connection", async () => {
  stub(detail());
  vi.spyOn(api, "resolveApproval").mockResolvedValue({ approval_id: "ap_1", status: "approved", resume: { resumable: false } } as never);
  render(SafetyCard, { props: { approval: INFO } });
  await fireEvent.click(await screen.findByRole("button", { name: "Allow once" }));
  expect(screen.queryByText(/Sending in/)).not.toBeInTheDocument();
});
