<script lang="ts">
  /**
   * One task's attempts, in order, at the address the task did not have.
   *
   * BUG-299 / UX-TASK-04. Two shipped changes already promised this page:
   * [FIXED-531] deduplicated Home's rows and asked each to link to "the
   * canonical Tasks detail", and [FIXED-533] gave the Stop control an honest
   * `outcome_unknown` settlement whose remedy is *"refresh to see the run's
   * current state"*. Neither had anywhere to point.
   *
   * What it draws is not a second account of the task. Every row here is a
   * governed event the task's own lifecycle wrote, grouped on the server into
   * the runs it describes, so this panel and the audit log cannot disagree —
   * this *is* the audit log, read at the scope of one task.
   *
   * Newest attempt first, because the reason anyone opens this is the last
   * thing that happened. Inside an attempt the events stay in the order they
   * occurred, because that is the only order a run makes sense in.
   */
  import Badge from "./Badge.svelte";
  import Icon from "./Icon.svelte";
  import PageState from "./PageState.svelte";
  import { relativeTime } from "../format";
  import {
    attemptBadge,
    attemptOutcomeLabel,
    attemptTitle,
    eventHref,
    historySummary,
    newestFirst,
  } from "../taskHistory";
  import { taskBadge, taskStatusLabel } from "../statusMaps";
  import type { TaskDetailView } from "../apiTypes";

  let {
    detail = null,
    loading = false,
    error = null,
    onclose,
    onrefresh,
  }: {
    detail?: TaskDetailView | null;
    loading?: boolean;
    error?: string | null;
    onclose: () => void;
    onrefresh: () => void;
  } = $props();

  const attempts = $derived(detail ? newestFirst(detail.attempts) : []);
</script>

<section class="card history" aria-labelledby="task-history-h">
  <header>
    <div class="lead">
      <h3 id="task-history-h">{detail ? detail.task.title : "Task history"}</h3>
      {#if detail}
        <p class="sub">
          <Badge
            variant={taskBadge(detail.task.status)}
            label={taskStatusLabel(detail.task.status)}
          />
          <span>{historySummary(detail.attempts)}</span>
        </p>
      {/if}
    </div>
    <div class="head-actions">
      <!-- The control the `outcome_unknown` settlement tells an owner to use.
           It is here, on the page that answers it, rather than only as a
           browser reload, because the sentence says "refresh to see the run's
           current state" and this is that state. -->
      <button type="button" class="btn btn-ghost btn-sm" onclick={onrefresh} disabled={loading}>
        <Icon name="refresh" size="sm" />
        {loading ? "Refreshing…" : "Refresh"}
      </button>
      <a class="btn btn-ghost btn-sm" href="#/tasks" onclick={onclose}>Back to all tasks</a>
    </div>
  </header>

  {#if error}
    <PageState state="error" title="Couldn't load this task's history" detail={error} />
  {:else if detail === null}
    <PageState state="loading" title="Reading this task's attempts…" lines={3} />
  {:else}
    <dl class="facts">
      <div><dt>Objective</dt><dd>{detail.task.objective || "No additional instructions."}</dd></div>
      {#if detail.task.current_step}
        <div><dt>Now</dt><dd>{detail.task.current_step}</dd></div>
      {/if}
      {#if detail.task.summary}
        <div><dt>Last stated outcome</dt><dd>{detail.task.summary}</dd></div>
      {/if}
    </dl>

    {#if detail.approvals.length > 0}
      <p class="blocked" role="status">
        <Icon name="approvals" size="sm" />
        {detail.approvals.length === 1
          ? "One decision is open on this task."
          : `${detail.approvals.length} decisions are open on this task.`}
        <a href={`#/approvals?session=${encodeURIComponent(detail.task.session_id)}`}
          >Review {detail.approvals.length === 1 ? "it" : "them"}</a
        >
      </p>
    {/if}

    {#if detail.truncated}
      <!-- A bound, stated. Silently showing the most recent 400 transitions as
           though they were all of them is the kind of quiet shortening this
           record exists to stop. -->
      <p class="truncated" role="status">
        Showing this task's most recent transitions. The complete trail is in the
        <a href="#/observe?tab=activity">audit log</a>.
      </p>
    {/if}

    {#if attempts.length === 0}
      <PageState
        state="empty"
        title="Nothing has happened yet"
        detail="This task has not started, so it has no attempts to show."
      />
    {:else}
      <ol class="attempts">
        {#each attempts as attempt (`${attempt.kind}-${attempt.index}-${attempt.started_at}`)}
          {@const href = eventHref(detail.task, attempt)}
          <li class="attempt">
            <div class="attempt-head">
              <div>
                <h4>{attemptTitle(attempt)}</h4>
                <p class="when">
                  started {relativeTime(attempt.started_at)}
                  {#if attempt.ended_at}· ended {relativeTime(attempt.ended_at)}{/if}
                </p>
              </div>
              <Badge
                variant={attemptBadge(attempt.outcome)}
                label={attemptOutcomeLabel(attempt.outcome)}
              />
            </div>
            {#if attempt.summary}<p class="outcome">{attempt.summary}</p>{/if}
            <ul class="steps">
              {#each attempt.events as event (event.event_id)}
                <li>
                  <span class="tick" aria-hidden="true"></span>
                  <span class="step-detail">{event.detail}</span>
                  <span class="step-when">{relativeTime(event.timestamp)}</span>
                </li>
              {/each}
            </ul>
            {#if href}
              <a class="btn btn-ghost btn-sm evidence" {href}>
                <Icon name={attempt.approval_id ? "approvals" : "chat"} size="sm" />
                {attempt.approval_id ? "Open the decision" : "Open the conversation"}
              </a>
            {/if}
          </li>
        {/each}
      </ol>
    {/if}
  {/if}
</section>

<style>
  .history { margin-bottom: var(--space-4); }
  header { align-items: flex-start; display: flex; gap: var(--space-3); justify-content: space-between; flex-wrap: wrap; }
  h3, h4 { margin: 0; }
  .sub { align-items: center; color: var(--text-2); display: flex; flex-wrap: wrap; font-size: var(--text-sm); gap: var(--space-2); margin: .4rem 0 0; }
  .head-actions { align-items: center; display: flex; gap: .4rem; flex-wrap: wrap; }
  .facts { display: grid; gap: var(--space-2); margin: var(--space-4) 0 0; }
  .facts div { display: grid; gap: .15rem; }
  dt { color: var(--text-3); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: .04em; }
  dd { color: var(--text-1); font-size: var(--text-sm); margin: 0; overflow-wrap: anywhere; }
  .blocked, .truncated { align-items: center; border-radius: var(--r-sm); display: flex; flex-wrap: wrap; font-size: var(--text-sm); gap: .4rem; margin: var(--space-3) 0 0; padding: .4rem .6rem; }
  .blocked { background: var(--warn-soft); border: 1px solid var(--warn-border); color: var(--text-1); }
  .truncated { background: var(--sunken); border: 1px solid var(--border); color: var(--text-2); }
  .attempts { display: grid; gap: var(--space-3); list-style: none; margin: var(--space-4) 0 0; padding: 0; }
  .attempt { border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--space-3); }
  .attempt-head { align-items: flex-start; display: flex; gap: var(--space-3); justify-content: space-between; }
  .when { color: var(--text-3); font-size: var(--text-xs); margin: .2rem 0 0; }
  .outcome { color: var(--text-2); font-size: var(--text-sm); margin: .6rem 0 0; }
  .steps { display: grid; gap: .3rem; list-style: none; margin: var(--space-3) 0 0; padding: 0; }
  .steps li { align-items: baseline; color: var(--text-2); display: grid; font-size: var(--text-sm); gap: .5rem; grid-template-columns: auto 1fr auto; }
  .tick { background: var(--accent); border-radius: 50%; height: .4rem; width: .4rem; }
  .step-detail { overflow-wrap: anywhere; }
  .step-when { color: var(--text-3); font-size: var(--text-xs); white-space: nowrap; }
  .evidence { align-items: center; display: inline-flex; gap: .3rem; margin-top: var(--space-3); text-decoration: none; }
  @media (max-width: 42rem) {
    header { flex-direction: column; }
    .steps li { grid-template-columns: auto 1fr; }
    .step-when { grid-column: 2; }
  }
</style>
