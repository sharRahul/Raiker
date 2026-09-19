/**
 * REM-OBSERVE — what, on this overview, is actually an exception.
 *
 * Observability's Overview asked five good operational questions and answered
 * every one of them whether or not there was anything to say. On a working
 * install that is seven tiles reading *Ready*, *0*, *0*, *0*, *Nothing
 * required is unset* — and then a whole specialist diagnostics view inline
 * below them — before the owner reaches the one line that would have told them
 * something. The page was not wrong; it was uniform, and a uniform page makes
 * the one red tile no easier to find than the six green ones beside it.
 *
 * So the order changed rather than the content: exceptions and recent changes
 * first, and the resting state of a healthy install behind a disclosure. This
 * module is the "is it an exception" half, separated out because it is the part
 * with rules in it:
 *
 * * **Healthy work is not an exception.** A queued or running task is progress.
 *   REM-HOME-02 settled this for Home when the attention rail counted every
 *   active task and a healthy nightly routine made the board permanently claim
 *   something needed the owner; the same rule holds here.
 * * **Unknown is not healthy.** A read that failed is reported as unknown, with
 *   what could not be read named. NEW-HOME-01 was the same defect from the
 *   other side: a caught diagnostics failure became `0 issues`, and `0 issues`
 *   became "nothing needs you".
 * * **Containment comes first and is never folded away.** A security signal in
 *   `alerting` is the one item on this page that must never sit below a
 *   telemetry delivery error or inside a disclosure.
 */

import type { ApprovalView, Diagnostics, SecurityHealth } from "./apiTypes";

/** How loudly one item asks, and in what order the list is read. */
export type AttentionTone = "containment" | "blocking" | "waiting" | "unknown";

export interface AttentionItem {
  /** Stable across renders so the list can be keyed. */
  id: string;
  tone: AttentionTone;
  title: string;
  /** What it means, and what happens if it is left. Never a bare count. */
  detail: string;
  href: string;
  linkLabel: string;
}

/** Read first to last. Containment before anything, unknown before nothing. */
const TONE_ORDER: Record<AttentionTone, number> = {
  containment: 0,
  blocking: 1,
  waiting: 2,
  unknown: 3,
};

export interface AttentionInputs {
  /** `null` when the read failed — which is unknown, not healthy. */
  diagnostics: Diagnostics | null;
  approvals: ApprovalView[] | null;
  security: SecurityHealth[] | null;
  unreadNotifications: number | null;
}

/**
 * The exceptions on this overview, most urgent first.
 *
 * An empty list means every input was read and none of them had anything to
 * report. It never means "a read failed and we assumed the good answer": a
 * failed read is an `unknown` item in the list, so a caller can say what it
 * does not know rather than showing an all-clear it did not earn.
 */
export function attentionItems(inputs: AttentionInputs): AttentionItem[] {
  const items: AttentionItem[] = [];

  // 1. Containment. A signal that is alerting is a boundary the runtime
  //    believes is being crossed, and it leads whatever else is true.
  const alerting = (inputs.security ?? []).filter((signal) => signal.state === "alerting");
  for (const signal of alerting) {
    items.push({
      id: `containment:${signal.source}:${signal.subject_id}:${signal.code}`,
      tone: "containment",
      title: `Containment alerting: ${signal.code.replaceAll("_", " ")}`,
      detail: `${signal.source} raised this for ${signal.subject_id} and it has not recovered.`,
      href: "#/settings?tab=security",
      linkLabel: "Review security",
    });
  }
  if (inputs.security === null) {
    items.push({
      id: "unknown:security",
      tone: "unknown",
      title: "Security signals could not be read",
      detail: "Containment state is unknown for now. This is not an all-clear.",
      href: "#/settings?tab=security",
      linkLabel: "Open security",
    });
  }

  // 2. The runtime itself.
  if (inputs.diagnostics === null) {
    items.push({
      id: "unknown:diagnostics",
      tone: "unknown",
      title: "Runtime health could not be read",
      detail:
        "Readiness and configuration are unknown for now. Nothing was started or changed.",
      href: "#/observe?tab=overview",
      linkLabel: "Try again",
    });
  } else {
    if (!inputs.diagnostics.production_ready_local_single_user_runtime) {
      items.push({
        id: "readiness",
        tone: "blocking",
        title: "Readiness checks are unmet",
        detail: "Some governed work will fail closed until they pass.",
        href: "#/observe?tab=overview",
        linkLabel: "See which checks failed",
      });
    }
    if (inputs.diagnostics.missing_config.length > 0) {
      items.push({
        id: "missing-config",
        tone: "blocking",
        title: `${inputs.diagnostics.missing_config.length} required setting${
          inputs.diagnostics.missing_config.length === 1 ? " is" : "s are"
        } unset`,
        detail: inputs.diagnostics.missing_config.join(", "),
        href: "#/settings",
        linkLabel: "Open settings",
      });
    }
  }

  // 3. Decisions the owner owes. Expired first: an expired request cannot be
  //    approved at all, so it is a different job from deciding a live one.
  if (inputs.approvals === null) {
    items.push({
      id: "unknown:approvals",
      tone: "unknown",
      title: "Pending decisions could not be read",
      detail: "Whether anything is waiting on you is unknown for now.",
      href: "#/approvals",
      linkLabel: "Open the decision queue",
    });
  } else {
    const expired = inputs.approvals.filter((approval) => approval.is_expired);
    const live = inputs.approvals.length - expired.length;
    if (expired.length > 0) {
      items.push({
        id: "approvals-expired",
        tone: "blocking",
        title: `${expired.length} approval${expired.length === 1 ? "" : "s"} expired`,
        detail: "These can no longer be approved; the action must be requested again.",
        href: "#/approvals",
        linkLabel: "Review expiries",
      });
    }
    if (live > 0) {
      items.push({
        id: "approvals-pending",
        tone: "waiting",
        title: `${live} decision${live === 1 ? "" : "s"} waiting on you`,
        detail: "Each one blocks a governed action until you decide.",
        href: "#/approvals",
        linkLabel: "Open the decision queue",
      });
    }
  }

  // 4. Notifications. Something asked for the owner's eye and has not had it.
  if ((inputs.unreadNotifications ?? 0) > 0) {
    const unread = inputs.unreadNotifications ?? 0;
    items.push({
      id: "notifications",
      tone: "waiting",
      title: `${unread} unread notification${unread === 1 ? "" : "s"}`,
      detail: "The same record the bell in the context bar reads from.",
      href: "#/observe?tab=notifications",
      linkLabel: "Open notification history",
    });
  }

  return items.sort((a, b) => TONE_ORDER[a.tone] - TONE_ORDER[b.tone]);
}

/**
 * What an empty attention list is allowed to claim.
 *
 * Only the inputs that were actually read. A page that says "nothing needs you"
 * over a failed read is the NEW-HOME-01 defect, and the honest sentence names
 * the scope of the all-clear rather than implying a whole-runtime one.
 */
export function allClearSentence(inputs: AttentionInputs): string {
  const checked: string[] = [];
  if (inputs.security !== null) checked.push("containment");
  if (inputs.diagnostics !== null) checked.push("readiness and configuration");
  if (inputs.approvals !== null) checked.push("pending decisions");
  if (inputs.unreadNotifications !== null) checked.push("notifications");
  if (checked.length === 0) return "Nothing could be read, so nothing can be said about it yet.";
  const last = checked.pop() as string;
  const list = checked.length === 0 ? last : `${checked.join(", ")} and ${last}`;
  return `Nothing needs you. Checked: ${list}.`;
}
