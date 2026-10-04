/**
 * UX-BUILD-01 — Build's approval review, out of BuildView.
 *
 * The decisions this conversation raised, the change each one would make (B14),
 * the hunks a reviewer narrowed it to, the reviewer's own version of a patch
 * (BUG-271), and resolving one. One owner for that state machine; the view
 * supplies the conversation and what to do when a decision lets the parked
 * turn continue.
 *
 * Moved, not changed: the preview is still the same governed read the inbox
 * performs, a lost preview never removes Accept and Reject, and a decision that
 * ran once and failed is still told apart from one governance stopped (UX-BUILD-04).
 */
import { api, ApiError } from "../../api";
import type { ApprovalView } from "../../apiTypes";
import { publishApprovalResolved } from "../../approvalResume";

export interface ApprovalDiff {
  diff: string | null;
  path: string | null;
  kind: string;
}

export class ApprovalReview {
  approvals = $state<ApprovalView[]>([]);
  /** The approval a request is in flight for; its controls wait. */
  busy = $state<string | null>(null);
  notice = $state<string | null>(null);
  /** B14 — the change itself, per approval, where it was proposed. */
  diffs = $state<Record<string, ApprovalDiff>>({});
  /**
   * B14 — per decision, the hunks the reviewer has accepted. Absent means they
   * have not narrowed this one and Accept means all of it.
   */
  hunks = $state<Record<string, string[] | undefined>>({});
  /**
   * BUG-271 — the reviewer's own version of a proposed patch, per approval,
   * while they are writing it. `undefined` is the resting state.
   */
  edits = $state<Record<string, string | undefined>>({});

  constructor(
    private readonly session: () => string | null,
    /** B2 — continue the turn a decision released. */
    private readonly resumeTurn: (approvalId: string, outcomeStatus: string) => Promise<void>,
    /** Ask the resume watcher to look now, for a decision already spent. */
    private readonly checkNow: () => void,
  ) {}

  /** A new conversation has no decisions. */
  reset = () => {
    this.approvals = [];
    this.diffs = {};
  };

  load = async () => {
    const session = this.session();
    if (session === null) return;
    try {
      const pending = await api.approvals();
      this.approvals = pending.filter((approval) => approval.session_id === session);
    } catch {
      this.approvals = [];
      this.diffs = {};
      return;
    }
    await this.loadDiffs();
  };

  private async loadDiffs() {
    const wanted = this.approvals.filter((approval) => this.diffs[approval.approval_id] === undefined);
    const loaded = await Promise.all(
      wanted.map(async (approval) => {
        try {
          const detail = await api.approval(approval.approval_id);
          const shows =
            detail.preview_kind === "file_diff" ||
            detail.preview_kind === "patch" ||
            detail.preview_kind === "git_change";
          // Only a change with a diff gets one. Everything else keeps the
          // inbox's own presentation rather than being forced into this shape.
          return shows
            ? ([
                approval.approval_id,
                // BUG-271 — `kind` decides whether the edit control is offered:
                // only a proposed patch can be corrected as text.
                { diff: detail.diff, path: detail.diff_path, kind: detail.preview_kind },
              ] as const)
            : null;
        } catch {
          // The preview is a convenience on top of the decision. Losing it must
          // not remove the Accept and Reject the turn is parked on.
          return null;
        }
      }),
    );
    this.diffs = {
      ...this.diffs,
      ...Object.fromEntries(loaded.filter((entry) => entry !== null)),
    };
  }

  /**
   * BUG-271 — propose the reviewer's own version instead of this one. The same
   * route Approvals uses: the proposal in front of the reviewer is denied and
   * theirs is raised as a new one. Nothing runs until they accept that.
   */
  proposeEdit = async (approval: ApprovalView) => {
    const patch = this.edits[approval.approval_id];
    if (patch === undefined || this.busy !== null) return;
    this.busy = approval.approval_id;
    this.notice = null;
    try {
      await api.replaceApproval(approval.approval_id, {
        patch,
        reason: "edited in the Build workspace",
      });
      this.edits = { ...this.edits, [approval.approval_id]: undefined };
      this.notice =
        "The proposed change was denied and yours is waiting for your approval. Nothing has run.";
      this.diffs = {};
      await this.load();
    } catch (error) {
      this.notice =
        error instanceof ApiError && error.reasonCode
          ? `That version was not accepted (${error.reasonCode}).`
          : "That version was not accepted.";
    } finally {
      this.busy = null;
    }
  };

  resolve = async (approval: ApprovalView, approve: boolean) => {
    this.busy = approval.approval_id;
    this.notice = null;
    try {
      const accepted = this.hunks[approval.approval_id];
      const result = await api.resolveApproval(approval.approval_id, {
        approve,
        reason: approve ? "accepted in the Build workspace" : "rejected in the Build workspace",
        // B14 — sent only when this reviewer actually narrowed this change.
        ...(approve && accepted !== undefined ? { accepted_hunks: accepted } : {}),
      });
      this.notice = !approve
        ? "Rejection recorded."
        : result.executes_action
          ? result.execution?.path
            ? `Applied once — wrote ${result.execution.path}. The previous contents were checkpointed.`
            : // BUG-62 — a capability whose result is a row, not a file, names it.
              result.execution?.receipt
              ? `Applied once — “${result.execution.receipt.title}” now exists. ${result.execution.receipt.label}.`
              : "Applied once, under a fresh capability, policy and posture check."
          : "Decision recorded. Raiker re-governs the action before anything runs.";
      await this.load();
      // BUG-24 — tell every other tab of this browser immediately, so a Chat
      // window showing the same parked turn continues without a reload. This is
      // a hint only: the receiving tab re-checks with the server before acting.
      publishApprovalResolved({
        approvalId: approval.approval_id,
        sessionId: approval.session_id ?? null,
        turnId: result.resume?.turn_id ?? null,
        approved: approve,
      });
      // B2 — the decision closed the tool call the model was waiting on, so the
      // turn it parked picks up from here instead of costing a re-prompt.
      if (result.resume?.resumable) {
        await this.resumeTurn(approval.approval_id, approve ? "success" : "rejected");
      }
    } catch (error) {
      /*
       * UX-BUILD-04 — `target_not_executed` is two different outcomes. If
       * governance stopped the action before it ran, the approval went back to
       * pending and the card stays. If it ran once and failed — a red test is
       * the ordinary case — the decision is spent, the server has handed the
       * failure to the parked turn, and the card must not go on offering
       * Accept. Re-reading the pending decisions is what tells them apart.
       */
      let spent = false;
      if (
        approve &&
        error instanceof ApiError &&
        (error.reasonCode ?? "").startsWith("target_not_executed")
      ) {
        await this.load();
        spent = !this.approvals.some((item) => item.approval_id === approval.approval_id);
      }
      if (spent && error instanceof ApiError) {
        const detail = (error.reasonCode ?? "")
          .replace(/^target_not_executed:/, "")
          .replace(/^exit_code:(\d+)$/, "exit code $1");
        this.notice = `Approved and run once — it did not succeed (${detail}). The turn continues with the output.`;
        this.checkNow();
      } else {
        this.notice =
          error instanceof ApiError
            ? `The decision was not accepted (${error.reasonCode ?? error.status}).`
            : "The decision could not be recorded.";
      }
    } finally {
      this.busy = null;
    }
  };
}
