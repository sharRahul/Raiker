/*
 * QUI-P05 — Allow for this task: the limits are required, start from the
 * server's draft, and the form sends only limits (the shape is the server's).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import LimitRuleForm from "./LimitRuleForm.svelte";
import { stubFetch } from "../test-helpers";

const DRAFT = {
  approval_id: "appr_1",
  tool_name: "connector_write",
  risk_level: "medium",
  project_id: null,
  limits: { scope: "conversation", targets: ["launch"], max_uses: 10, expires_hours: 8, attachments: false, sensitive_asks: true },
};

afterEach(() => vi.unstubAllGlobals());

describe("LimitRuleForm", () => {
  it("starts from the draft and offers no project when the conversation has none", async () => {
    stubFetch({ "GET /api/approvals/appr_1/limit-rule": DRAFT });
    render(LimitRuleForm, { props: { approvalId: "appr_1", onallow: vi.fn(), oncancel: vi.fn() } });
    expect(await screen.findByRole("radio", { name: "This conversation" })).toBeChecked();
    expect(screen.queryByRole("radio", { name: "This project" })).toBeNull();
    expect(screen.getByLabelText("Only to")).toHaveValue("launch");
    expect(screen.getByLabelText("Sensitive content still asks")).toBeChecked();
    expect(screen.getByLabelText("Attachments still ask")).toBeChecked();
    expect(screen.queryByText(/Always allow/)).toBeNull();
  });

  it("refuses future work with nowhere named, and sends only limits", async () => {
    stubFetch({ "GET /api/approvals/appr_1/limit-rule": DRAFT });
    const onallow = vi.fn();
    render(LimitRuleForm, { props: { approvalId: "appr_1", onallow, oncancel: vi.fn() } });
    await fireEvent.click(await screen.findByRole("radio", { name: "Future work" }));
    expect(screen.getByText(/conversations set to/)).toBeInTheDocument();
    await fireEvent.input(screen.getByLabelText("Only to"), { target: { value: "" } });
    await fireEvent.click(screen.getByRole("button", { name: "Allow and keep these limits" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/name who or where/);
    expect(onallow).not.toHaveBeenCalled();
    await fireEvent.input(screen.getByLabelText("Only to"), { target: { value: "launch, example.com" } });
    await fireEvent.click(screen.getByRole("button", { name: "Allow and keep these limits" }));
    await waitFor(() => expect(onallow).toHaveBeenCalledTimes(1));
    expect(onallow.mock.calls[0][0]).toEqual({
      scope: "future", targets: ["launch", "example.com"], max_uses: 10, expires_hours: 8,
      attachments: false, sensitive_asks: true,
    });
  });

  it("says why a rule cannot be made from this approval", async () => {
    stubFetch({ "GET /api/approvals/appr_1/limit-rule": { __status: 409, detail: { reason_code: "grant_target_is_critical" } } });
    render(LimitRuleForm, { props: { approvalId: "appr_1", onallow: vi.fn(), oncancel: vi.fn() } });
    expect(await screen.findByRole("alert")).toHaveTextContent(/decided by you, every time/);
  });
});
