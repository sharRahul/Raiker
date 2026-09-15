/**
 * One run, one Stop, one Resume, one Run now — and one account of what happened.
 *
 * REM-TASK-02. Home, the Tasks page and Build's side panel each carried their
 * own copy of "stop this task". The three agreed on the request they sent and on
 * nothing else:
 *
 * | Surface | On success | On failure |
 * |---|---|---|
 * | Workbench | "Asked X to stop at its next safe boundary." | named the reason code |
 * | Tasks | "Requested a safe-boundary stop for X." | "Could not request the stop." — reason discarded |
 * | Build | "Asked X to stop at its next safe boundary." | "Could not request the stop." — reason discarded |
 *
 * Presentation may differ between surfaces; **what a control means must not**,
 * and two of the three were throwing away the one thing an owner needs when a
 * stop does not take. Worse, all three reported the same two outcomes for three
 * genuinely different situations, and the third is the one that matters:
 *
 * * **requested** — the runtime accepted it. The task is marked cancelled and
 *   the run stops at its next safe boundary. This is not "stopped": a cycle
 *   already in flight finishes its current step, by design.
 * * **completed** — the runtime refused, and said why. Nothing changed.
 * * **outcome_unknown** — the request left and no answer came back. It may have
 *   been applied. Reporting this as "Could not request the stop" is a claim
 *   nobody is in a position to make, and an owner who believes it will press
 *   Stop again, or worse, assume the work is still running when it is not.
 *
 * Nothing here renders. A surface decides where a notice goes and how loudly;
 * this decides what it says.
 */
import { ApiError, api } from "./api";
import type { TaskView } from "./apiTypes";
import { taskDetailHref } from "./taskHistory";

/** What is known about the request, which is not always what happened. */
export type TaskSettlement = "requested" | "completed" | "outcome_unknown";

export interface TaskLifecycleOutcome {
  /** True only when the runtime accepted the request. */
  ok: boolean;
  settlement: TaskSettlement;
  /** One sentence for the owner. Never a bare reason code. */
  notice: string;
  /** The governed reason code, when the runtime supplied one. */
  reasonCode?: string;
  /**
   * Where the owner can see what actually happened, when the outcome is not
   * knowable from here (BUG-299). Set only on `outcome_unknown`, because that
   * is the only settlement whose remedy is "go and look".
   */
  detailHref?: string;
}

/**
 * Why an `ApiError` is a *settled* failure and anything else is not.
 *
 * An `ApiError` is the server's own answer: it received the request, refused it,
 * and said why — so nothing was applied and that is knowable. A thrown
 * `TypeError` from `fetch` is a request that may have arrived, been applied, and
 * lost its response on the way back. The two are not the same fact and were
 * being reported with the same sentence.
 */
function settleFailure(
  error: unknown,
  verb: string,
  title: string,
  taskId: string,
): TaskLifecycleOutcome {
  if (error instanceof ApiError) {
    return {
      ok: false,
      settlement: "completed",
      reasonCode: error.reasonCode ?? undefined,
      notice: `Raiker refused to ${verb} “${title}” (${error.reasonCode ?? error.status}). Nothing changed.`,
    };
  }
  return {
    ok: false,
    settlement: "outcome_unknown",
    notice:
      `Raiker did not answer the request to ${verb} “${title}”, so it may or may ` +
      "not have been applied. Open this task's history to see the run's current " +
      "state before trying again.",
    // BUG-299 — the remedy this settlement names now has somewhere to go. It
    // was written before a task had an address, so "refresh to see the run's
    // current state" asked an owner to look at a page that did not exist.
    detailHref: taskDetailHref(taskId),
  };
}

/**
 * Ask one run to stop at its next safe boundary. Never a hard kill.
 *
 * `reason` is the audit trail's record of *where* the owner pressed it, which
 * is why it stays a per-surface argument rather than one shared string: "stopped
 * from the Workbench board" and "stopped from the Build workspace" are different
 * facts about the same decision.
 */
export async function stopRun(task: TaskView, reason: string): Promise<TaskLifecycleOutcome> {
  try {
    const result = await api.interrupt({
      session_id: task.session_id,
      task_id: task.task_id,
      action_type: "cancel",
      reason,
    });
    const applied = (result.applied ?? []).some((entry) => entry.task_id === task.task_id);
    if (!applied) {
      // The call succeeded and this task is not in what it applied to. The run
      // had probably already settled; saying "asked it to stop" would describe
      // an act that did not occur.
      return {
        ok: false,
        settlement: "outcome_unknown",
        notice:
          `Raiker accepted the request but did not apply it to “${task.title}”. ` +
          "The run may have already finished; open its history to see what it did.",
        detailHref: taskDetailHref(task.task_id),
      };
    }
    return {
      ok: true,
      settlement: "requested",
      // "Asked", not "stopped". A cycle in flight finishes its current step.
      notice: `Asked “${task.title}” to stop at its next safe boundary.`,
    };
  } catch (error) {
    return settleFailure(error, "stop", task.title, task.task_id);
  }
}

/**
 * Continue a run that parked on an approval the owner has since resolved.
 *
 * BUG-25/BUG-39 — granting the approval signals the host directly, so this is
 * the recovery path rather than the ordinary one: what to press when that could
 * not proceed. It is the same governed path, so it can never continue something
 * the automatic pass would have refused, and it never re-runs a turn that ran.
 */
export async function resumeRun(task: TaskView): Promise<TaskLifecycleOutcome> {
  try {
    const result = await api.resumeTask(task.task_id);
    if (result.ok) {
      return { ok: true, settlement: "requested", notice: `Continuing “${task.title}”.` };
    }
    return {
      ok: false,
      settlement: "completed",
      reasonCode: result.reason_code ?? undefined,
      notice:
        result.reason_code === "no_resolved_approval"
          ? "No decision has been recorded yet, so there is nothing to continue."
          : `Could not continue “${task.title}” (${result.reason_code ?? "unknown reason"}). Nothing changed.`,
    };
  } catch (error) {
    return settleFailure(error, "continue", task.title, task.task_id);
  }
}

/** Start a scheduled or idle task now, rather than at its next slot. */
export async function startRunNow(task: TaskView): Promise<TaskLifecycleOutcome> {
  try {
    await api.runTask(task.task_id);
    return { ok: true, settlement: "requested", notice: `Starting “${task.title}”.` };
  } catch (error) {
    return settleFailure(error, "run", task.title, task.task_id);
  }
}
