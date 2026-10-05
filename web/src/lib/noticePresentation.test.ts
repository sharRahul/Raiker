import { describe, expect, it } from "vitest";
import type { Notification as RaikerNotification } from "./apiTypes";
import { presentationPhrase, repeatPhrase } from "./noticePresentation";

function notice(partial: Partial<RaikerNotification>): RaikerNotification {
  return {
    notification_id: "ntf_1", kind: "task_finished", title: "t", body: "b", finding_id: null, subject_id: null,
    read: false, created_at: "2026-10-05T22:00:00Z", in_app_presentation: "interrupt", desktop_presentation: "interrupt",
    quiet_until: null, summarised_at: null, repeat_count: 0, last_repeated_at: null, ...partial,
  };
}

describe("what the record says happened to a notice", () => {
  it("says nothing extra about a notice that was simply shown, or one older than the policy", () => {
    expect(presentationPhrase(notice({}))).toBeNull();
    expect(presentationPhrase(notice({ in_app_presentation: null }))).toBeNull();
  });

  it("names quiet hours, a muted kind and a security exception", () => {
    expect(presentationPhrase(notice({ in_app_presentation: "quiet_hours", quiet_until: "2026-10-06T07:00:00Z" }), () => "07:00"))
      .toBe("held for quiet hours until 07:00");
    expect(presentationPhrase(notice({ in_app_presentation: "quiet_hours", summarised_at: "2026-10-06T07:01:00Z" })))
      .toBe("held for quiet hours, then summarised");
    expect(presentationPhrase(notice({ in_app_presentation: "muted" }))).toMatch(/turned off in Notifications/);
    expect(presentationPhrase(notice({ in_app_presentation: "critical_exception" }))).toMatch(/security exception/);
  });

  it("counts a notice raised again rather than listing it again", () => {
    expect(repeatPhrase(notice({}))).toBeNull();
    expect(repeatPhrase(notice({ repeat_count: 1 }))).toBe("raised 1 more time");
    expect(repeatPhrase(notice({ repeat_count: 4 }))).toBe("raised 4 more times");
  });
});
