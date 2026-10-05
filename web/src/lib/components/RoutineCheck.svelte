<script lang="ts">
  /**
   * DEC-12 steps 6 and 8 — "will this routine run?", asked before 03:00 rather
   * than answered by the run that failed then, and how long one run may take.
   *
   * The checks come from the server's doctor, which reads records only — the
   * scheduler's pass, the stored model check, the schedule's terms, the
   * owner's quiet hours — and starts nothing. Each line says what it found and
   * links to where it is fixed. Unknown is said as unknown.
   */
  import { api, ApiError } from "../api";
  import type { RoutineDoctor, TaskView } from "../generated/apiContract";
  import Icon from "./Icon.svelte";

  let { task, onChanged }: { task: TaskView; onChanged?: (task: TaskView) => void } = $props();

  let open = $state(false);
  let report = $state<RoutineDoctor | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);
  let limit = $state<number | null>(null);
  let limitNotice = $state<string | null>(null);
  const shownLimit = $derived(limit ?? task.max_run_minutes);

  const STATE_LABEL: Record<string, string> = {
    ok: "Fine",
    warn: "Check",
    blocked: "Will not run",
    unknown: "Unknown",
  };
  const OVERALL: Record<string, string> = {
    ok: "Nothing on record would stop its next run.",
    warn: "It should run, with something worth a look.",
    blocked: "Something on record will stop its next run.",
    unknown: "Something could not be read, so this is not an all-clear.",
  };
  const ICON: Record<string, "check" | "warning" | "x" | "info"> = {
    ok: "check",
    warn: "warning",
    blocked: "x",
    unknown: "info",
  };

  async function check() {
    open = true;
    busy = true;
    error = null;
    try {
      report = await api.taskDoctor(task.task_id);
    } catch (e) {
      report = null;
      error = e instanceof ApiError ? `Could not check it (${e.status}).` : "Could not check it.";
    } finally {
      busy = false;
    }
  }

  async function saveLimit(event: SubmitEvent) {
    event.preventDefault();
    const minutes = Number(shownLimit);
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 720) {
      limitNotice = "A run limit is a whole number of minutes from 1 to 720.";
      return;
    }
    try {
      const updated = await api.setTaskRunLimit(task.task_id, minutes);
      limitNotice = `Each run now stops after ${updated.max_run_minutes} minutes.`;
      onChanged?.(updated);
      if (report) await check();
    } catch (e) {
      limitNotice = e instanceof ApiError ? `Not saved (${e.status}).` : "Not saved.";
    }
  }
</script>

<button
  type="button"
  class="btn btn-ghost btn-sm"
  aria-expanded={open}
  onclick={() => (open ? (open = false) : void check())}
>
  <Icon name="shield" size="sm" />
  Will it run?
</button>

{#if open}
  <section class="routine-check" aria-label={`Will “${task.title}” run?`} data-testid="routine-check">
    {#if busy && report === null}
      <p class="sub">Checking…</p>
    {:else if error}
      <p class="sub" role="alert">{error}</p>
    {:else if report}
      <p class="overall" data-state={report.state}><strong>{OVERALL[report.state]}</strong></p>
      <ul>
        {#each report.checks as item (item.key)}
          <li data-state={item.state}>
            <Icon name={ICON[item.state] ?? "info"} size="sm" />
            <span class="label">{item.label}</span>
            <span class="state">{STATE_LABEL[item.state]}</span>
            <span class="detail">
              {item.detail}
              {#if item.href && item.state !== "ok"}<a href={item.href}>Fix it</a>{/if}
            </span>
          </li>
        {/each}
      </ul>
    {/if}
    <form class="limit" onsubmit={saveLimit}>
      <label>
        <span>Stop a run after</span>
        <input
          class="input"
          type="number"
          min="1"
          max="720"
          step="1"
          value={shownLimit}
          aria-label="Run limit in minutes"
          oninput={(e) => (limit = Number(e.currentTarget.value))}
        />
        <span>minutes</span>
      </label>
      <button type="submit" class="btn btn-sm">Save limit</button>
    </form>
    {#if limitNotice}<p class="sub" role="status">{limitNotice}</p>{/if}
  </section>
{/if}

<style>
  .routine-check {
    flex-basis: 100%;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    padding: var(--space-3);
    margin-top: var(--space-2);
    background: var(--surface);
  }
  .overall { margin: 0 0 var(--space-2); }
  ul { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  li {
    display: grid;
    grid-template-columns: auto minmax(7rem, auto) auto 1fr;
    gap: var(--space-2);
    align-items: baseline;
    font-size: var(--text-sm);
  }
  li[data-state="blocked"] { color: var(--danger, var(--text-1)); }
  li[data-state="warn"] .state, li[data-state="unknown"] .state { color: var(--warn, var(--text-2)); }
  .label { font-weight: 600; }
  .state { color: var(--text-2); }
  .detail { color: var(--text-2); overflow-wrap: anywhere; }
  .detail a { margin-left: 0.4rem; }
  .limit { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; margin-top: var(--space-3); }
  .limit label { display: flex; gap: var(--space-2); align-items: center; font-size: var(--text-sm); }
  .limit input { width: 5.5rem; }
  .sub { color: var(--text-2); font-size: var(--text-sm); margin: var(--space-2) 0 0; }
  @media (max-width: 640px) {
    li { grid-template-columns: auto 1fr auto; }
    .detail { grid-column: 2 / -1; }
  }
</style>
