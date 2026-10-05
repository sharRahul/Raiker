import { describe, expect, it, vi } from "vitest";
import type { Notification as RaikerNotification } from "./apiTypes";
import {
  NOTICES_CHANGED,
  NOTICE_RECORD,
  announceNoticesChanged,
  answeredByPage,
  noticeDestination,
  onNoticeRecord,
  shownByApprovalCard,
} from "./noticeDestination";

function notice(kind: string): RaikerNotification {
  return {
    notification_id: `ntf_${kind}`,
    kind,
    title: kind,
    body: "",
    finding_id: null,
    subject_id: null,
    read: false,
    created_at: "2026-09-28T00:00:00Z",
    in_app_presentation: null,
    desktop_presentation: null,
    quiet_until: null,
    summarised_at: null,
    repeat_count: 0,
    last_repeated_at: null,
  };
}

describe("noticeDestination", () => {
  it("sends a notice to the page that answers it, and everything else to the record", () => {
    expect(noticeDestination("approval_pending")).toBe("#/approvals");
    expect(noticeDestination("critical_approval_pending")).toBe("#/approvals");
    expect(noticeDestination("task_finished")).toBe("#/tasks");
    expect(noticeDestination("security_alert")).toBe(NOTICE_RECORD);
  });
});

// BUG-309 — the dock repeated the approval the Approvals queue was listing.
describe("answeredByPage", () => {
  it("is true only on the page a notice would open", () => {
    expect(answeredByPage(notice("approval_pending"), "#/approvals")).toBe(true);
    expect(answeredByPage(notice("critical_approval_pending"), "#/approvals?tab=pending")).toBe(true);
    expect(answeredByPage(notice("task_finished"), "#/tasks?task=t1")).toBe(true);
    expect(answeredByPage(notice("approval_pending"), "#/tasks")).toBe(false);
    expect(answeredByPage(notice("task_finished"), "#/approvals")).toBe(false);
  });

  it("never treats the record as answering a notice, so opening it marks nothing read", () => {
    expect(answeredByPage(notice("security_alert"), NOTICE_RECORD)).toBe(false);
    expect(answeredByPage(notice("security_alert"), "#/approvals")).toBe(false);
  });

  it("does not mistake a route that only starts the same way", () => {
    expect(answeredByPage(notice("task_finished"), "#/tasksboard")).toBe(false);
  });
});

describe("onNoticeRecord", () => {
  it("recognises the record, and only the record", () => {
    expect(onNoticeRecord(NOTICE_RECORD)).toBe(true);
    expect(onNoticeRecord("#/observe")).toBe(false);
    expect(onNoticeRecord("#/observe?tab=activity")).toBe(false);
  });
});

// The bell and the dock read notices on their own, so a mark made by one is
// announced to the other rather than disagreeing until the next poll.
describe("announceNoticesChanged", () => {
  it("tells every reader on the page", () => {
    const heard = vi.fn();
    window.addEventListener(NOTICES_CHANGED, heard);
    announceNoticesChanged();
    window.removeEventListener(NOTICES_CHANGED, heard);
    expect(heard).toHaveBeenCalledTimes(1);
  });
});

describe("shownByApprovalCard", () => {
  it("is true for the two approval kinds and nothing else", () => {
    expect(shownByApprovalCard(notice("approval_pending"))).toBe(true);
    expect(shownByApprovalCard(notice("critical_approval_pending"))).toBe(true);
    expect(shownByApprovalCard(notice("task_finished"))).toBe(false);
    expect(shownByApprovalCard(notice("security_alert"))).toBe(false);
  });
});
