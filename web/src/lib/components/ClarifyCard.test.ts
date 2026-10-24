import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import ClarifyCard from "./ClarifyCard.svelte";
import { clarifyBody, clarifyText, ownerQuestions } from "../clarify";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const option = (label: string) => ({ label, description: "" });
const ACCOUNT = { question: "Which account?", header: "Account", options: [option("Work Gmail"), option("Personal Gmail")], multiSelect: false };
const DAYS = { question: "Which days?", header: "Days", options: [option("Mon"), option("Tue"), option("Wed")], multiSelect: true };

function answered() {
  return { approval_id: "apr_1", status: "answered", answered: 2, resume: { resumable: true, session_id: "s1", turn_id: "t1" } };
}

describe("QUI-F02 clarifying questions as cards", () => {
  it("asks one at a time and answers through the question's own route, exactly as chosen", async () => {
    const fetchMock = stubFetch({ "POST /api/approvals/apr_1/answer": answered() });
    const onAnswered = vi.fn();
    render(ClarifyCard, { approvalId: "apr_1", questions: [ACCOUNT, DAYS], onAnswered });
    expect(screen.getByText("Waiting for your answer")).toBeInTheDocument();
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    const next = screen.getByRole("button", { name: "Next question" });
    expect(next).toBeDisabled();
    await fireEvent.click(screen.getByRole("radio", { name: "Work Gmail" }));
    await fireEvent.click(next);
    expect(screen.getByText("2 of 2")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("checkbox", { name: "Mon" }));
    await fireEvent.click(screen.getByRole("checkbox", { name: "Wed" }));
    await fireEvent.click(screen.getByRole("button", { name: "Confirm and continue" }));
    await waitFor(() => expect(onAnswered).toHaveBeenCalledWith(true));
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/answer"));
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({
      answers: { "Which account?": "Work Gmail", "Which days?": ["Mon", "Wed"] },
    });
    expect(screen.getByText("Answered")).toBeInTheDocument();
    // Never the approval card's words.
    expect(screen.queryByRole("button", { name: /Allow once|Decline/ })).not.toBeInTheDocument();
  });

  it("sends the owner's own words when anything was typed or skipped", () => {
    const replies = [
      { picked: [], typed: "", skipped: true },
      { picked: ["Tue"], typed: "and Friday", skipped: false },
    ];
    expect(clarifyText([ACCOUNT, DAYS], replies)).toBe("Which account? — Skipped\nWhich days? — Tue, and Friday");
    expect(clarifyBody([ACCOUNT, DAYS], replies)).toEqual({ response: "Which account? — Skipped\nWhich days? — Tue, and Friday" });
    expect(clarifyBody([ACCOUNT], [{ picked: [], typed: "", skipped: true }])).toEqual({ response: "Which account? — Skipped" });
  });

  it("reads its questions from the approval when the surface does not hold them", async () => {
    stubFetch({
      "GET /api/approvals/apr_2": { approval: { tool_name: "ask_owner_question", status: "pending" }, arguments: { questions: [ACCOUNT] } },
    });
    render(ClarifyCard, { approvalId: "apr_2" });
    expect(await screen.findByText("Which account?")).toBeInTheDocument();
  });

  it("only treats the question tool as a question", () => {
    expect(ownerQuestions({ tool_name: "write_file", arguments: { questions: [ACCOUNT] } })).toBeNull();
    expect(ownerQuestions({ tool_name: "ask_owner_question", arguments: { questions: [ACCOUNT] } })?.[0].options[1].label).toBe("Personal Gmail");
  });
});
