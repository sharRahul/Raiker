<script lang="ts">
  // STOP switch (top bar). Wired to the governed stop path: it requests that all
  // work in progress stop at the next safe boundary — NOT an instant force-kill.
  //
  // Found live 2026-09-05, walking every destination at four widths.
  //
  // The control was **full-strength red on every page, at every width, forever**,
  // and it could not say whether pressing it would do anything. The owner
  // pressed it, confirmed a dialog about cancelling everything at a safe
  // boundary, waited on two API calls, and was told "No active tasks to stop."
  // On a 360px header the pill took about a third of the width to do it. A
  // permanent alarm is an alarm nobody reads, which is the opposite of what an
  // emergency control is for.
  //
  // **What did not change, and must not.** The stop stays reachable from every
  // page at every moment — that is the Security Philosophy's "instant stop", and
  // taking it away when Raiker *believes* nothing is running would make a stale
  // belief into a removed control. It is still one press away when the count is
  // zero; it is simply quiet about it.
  //
  // **What changed.** The switch reads the same task list the workbench reads
  // and counts it with the same `isActiveTask`, so the two can never disagree.
  // Nothing running: a ghost icon, no word, no colour. Something running: the
  // red pill it always was, with the number on it, announced politely. And the
  // dialog opens on a count refreshed at that moment, so an owner pressing it
  // with nothing running is told so immediately rather than after an interrupt
  // nobody needed.
  //
  // Beyond the reference set: Claude Code, Cowork and Codex all surface a stop
  // while a turn runs. None of them tells you *how much* it would reach before
  // you commit to it, because none of them has a governed queue to count.
  //
  // **GEP-02 (owner decision, 2026-09-27).** "Stop" means stop *everything*
  // currently being performed — the answer being written in Chat, a Build turn,
  // a routine, a task, a running command — whether or not it leaves the
  // machine. The switch used to read the task list alone, so the one thing an
  // owner most often wants to stop, the turn they are watching, was invisible to
  // it: a chat turn is not a task. It now counts tasks the way every surface
  // does (`isActiveTask` over `GET /api/tasks`) and adds what
  // `GET /api/work-in-flight` reports — live turns and running commands — and
  // one press sends one `POST /api/stop-all`, which applies each kind of work's
  // own existing stop at its safe boundary.
  import { onMount } from "svelte";
  import Icon from "./Icon.svelte";
  import { api, ApiError } from "../api";
  import { humanize } from "../format";
  import { isActiveTask } from "../statusMaps";
  import type { EventEntry, StopAllResult, TaskView } from "../apiTypes";

  type Phase = "checking" | "confirm" | "working" | "done" | "empty" | "error";
  type Counts = { tasks: number; turns: number; commands: number };

  const INTERRUPT_EVENT_TYPES = ["interrupt_received", "safe_boundary_reached", "task_cancelled"];
  /** How often the idle badge re-reads. The same cadence the work surfaces use. */
  const POLL_MS = 15_000;

  let open = $state(false);
  let phase = $state<Phase>("confirm");
  let counts = $state<Counts>({ tasks: 0, turns: 0, commands: 0 });
  let result = $state<StopAllResult | null>(null);
  let resultEvents = $state<EventEntry[]>([]);
  let errorText = $state<string | null>(null);
  let dialogEl: HTMLDivElement | undefined = $state();
  const activeCount = $derived(counts.tasks + counts.turns + counts.commands);
  const live = $derived(activeCount > 0);

  function plural(n: number, one: string, many: string): string {
    return `${n} ${n === 1 ? one : many}`;
  }

  /** "2 tasks, 1 answer being written and 1 command" — only the kinds present. */
  function describe(c: Counts): string {
    const parts = [
      c.turns ? plural(c.turns, "answer being written", "answers being written") : "",
      c.tasks ? plural(c.tasks, "task", "tasks") : "",
      c.commands ? plural(c.commands, "command", "commands") : "",
    ].filter(Boolean);
    if (parts.length <= 1) return parts[0] ?? "";
    return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
  }

  /** The active tasks, counted the way every other surface counts them. */
  async function activeTasks(): Promise<TaskView[]> {
    const tasks = await api.tasks();
    return tasks.filter((task) => isActiveTask(task.status));
  }

  /**
   * Tasks from the task list, turns and commands from the in-flight read. The
   * two reads fail separately: a failed in-flight read keeps the last known
   * turn and command counts rather than zeroing them, for the same reason a
   * failed task read keeps the task count.
   */
  async function readCounts(): Promise<Counts> {
    const [tasks, inFlight] = await Promise.allSettled([activeTasks(), api.workInFlight()]);
    if (tasks.status === "rejected") throw tasks.reason;
    const next: Counts = { ...counts, tasks: tasks.value.length };
    if (inFlight.status === "fulfilled") {
      next.turns = inFlight.value.turns;
      if (inFlight.value.commands !== null) next.commands = inFlight.value.commands;
    }
    return next;
  }

  async function refreshCount() {
    try {
      counts = await readCounts();
    } catch {
      // A failed read keeps the last known count. Blanking it would turn a
      // network hiccup into "nothing is running", which is the one thing this
      // control must never say wrongly.
    }
  }

  onMount(() => {
    void refreshCount();
    const timer = window.setInterval(() => void refreshCount(), POLL_MS);
    // A tab that was in the background may have been away for a long time; the
    // count it is showing is from before that.
    const onVisible = () => {
      if (document.visibilityState === "visible") void refreshCount();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  });

  async function show() {
    phase = "checking";
    result = null;
    resultEvents = [];
    errorText = null;
    open = true;
    try {
      counts = await readCounts();
      phase = activeCount === 0 ? "empty" : "confirm";
    } catch (e) {
      errorText =
        e instanceof ApiError
          ? `Could not read what is running (${e.status}).`
          : "Could not read what is running.";
      phase = "confirm";
    }
  }
  function close() {
    open = false;
  }
  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") close();
  }

  async function confirmStop() {
    phase = "working";
    errorText = null;
    try {
      result = await api.stopAll();
      const sessions = [
        ...new Set([
          ...result.turns.map((t) => t.session_id),
          ...(await activeTasks().catch(() => [] as TaskView[])).map((t) => t.session_id),
        ]),
      ];
      resultEvents = await loadInterruptEvents(sessions);
      phase = "done";
      void refreshCount();
    } catch (e) {
      errorText =
        e instanceof ApiError ? `Stop failed (${e.status}).` : "Could not reach the local runtime.";
      phase = "error";
    }
  }

  async function loadInterruptEvents(sessions: string[]): Promise<EventEntry[]> {
    const collected: EventEntry[] = [];
    for (const sessionId of sessions) {
      try {
        const evs = await api.events({ session_id: sessionId, limit: 50 });
        collected.push(...evs.filter((e) => INTERRUPT_EVENT_TYPES.includes(e.event_type)));
      } catch {
        // The stop already happened; a failed evidence read must not undo the
        // "done" the owner is owed.
      }
    }
    return collected;
  }

  $effect(() => {
    if (open) dialogEl?.focus();
  });
</script>

<!-- One control, two voices. The word and the colour are what a running queue
     earns; an idle one gets the icon, which is still the same button in the same
     place, one press from the same dialog. -->
<button
  type="button"
  class="stop-btn"
  class:live
  onclick={show}
  aria-haspopup="dialog"
  aria-label={live
    ? `Stop all work (${activeCount} active)`
    : "Stop all work (nothing is running)"}
  title={live ? `Stop ${describe(counts)}` : "Nothing is running"}
>
  <Icon name="stop" size="md" />
  {#if live}<span class="stop-label">STOP</span><span class="stop-count">{activeCount}</span>{/if}
</button>
<!-- Polite, and outside the button, so a screen reader hears work starting
     without the button's own label being re-announced on every poll. -->
<span class="sr-only" role="status" aria-live="polite">
  {live ? `${activeCount} active` : ""}
</span>

{#if open}
  <div class="overlay">
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="stop-title"
      tabindex="-1"
      bind:this={dialogEl}
      onkeydown={onKeydown}
    >
      <h2 id="stop-title">
        {phase === "empty" ? "Nothing is running" : "Stop all work in progress?"}
      </h2>

      {#if phase === "checking"}
        <p role="status">Reading what is running…</p>
      {:else if phase === "confirm"}
        <p>
          {#if activeCount > 0}
            This stops <strong>{describe(counts)}</strong> — every answer being written, task,
            routine and command, whether or not it reaches outside this machine — at the next
          {:else}
            This stops every answer being written, task, routine and command, whether or not it
            reaches outside this machine, at the next
          {/if}
          <strong>safe boundary</strong>. It is governed and audited — not a force-kill.
        </p>
        {#if errorText}<p class="error-line" role="alert">{errorText}</p>{/if}
        <div class="actions">
          <button type="button" class="btn" onclick={close}>Cancel</button>
          <button type="button" class="btn btn-danger" onclick={confirmStop}>Stop all</button>
        </div>
      {:else if phase === "working"}
        <p role="status">Requesting safe-boundary stop…</p>
      {:else if phase === "empty"}
        <!-- Reached from the count taken when this opened, so it costs the owner
             a press rather than a press plus a confirmation plus an interrupt. -->
        <p role="status">
          No answer is being written, and no task, routine or command is queued, running, paused
          or waiting for approval.
        </p>
        <div class="actions">
          <button type="button" class="btn" onclick={() => void show()}>Check again</button>
          <button type="button" class="btn" onclick={close}>Close</button>
        </div>
      {:else if phase === "done"}
        <p role="status" class="ok-line">
          {#if result}
            Stop applied at the safe boundary to {describe({
              tasks: result.tasks.length,
              turns: result.turns.length,
              commands: result.commands.length,
            }) || "nothing — it had already finished"}.
          {/if}
        </p>
        {#if result && result.failed.length > 0}
          <p role="alert" class="error-line">
            {plural(result.failed.length, "item", "items")} could not be stopped:
            {result.failed.map((f) => humanize(f.reason_code)).join(", ")}.
          </p>
        {/if}
        {#if resultEvents.length > 0}
          <ul class="events">
            {#each resultEvents as ev (ev.event_id)}
              <li><strong>{humanize(ev.event_type)}</strong> {ev.summary ?? ""}</li>
            {/each}
          </ul>
        {/if}
        <div class="actions">
          <button type="button" class="btn" onclick={close}>Close</button>
        </div>
      {:else}
        <p role="alert" class="error-line">{errorText}</p>
        <div class="actions">
          <button type="button" class="btn" onclick={close}>Close</button>
          <button type="button" class="btn btn-danger" onclick={confirmStop}>Retry</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  /* Idle: the same button, drawn like every other icon control in the bar. */
  .stop-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--text-2);
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--r-pill);
    padding: 0.35rem 0.5rem;
    cursor: pointer;
    transition:
      color var(--motion-fast) var(--ease),
      background var(--motion-fast) var(--ease),
      border-color var(--motion-fast) var(--ease);
  }
  .stop-btn:hover {
    color: var(--danger);
    border-color: var(--danger-border);
    background: var(--danger-soft);
  }
  /* Running: exactly what it always looked like, plus the number. */
  .stop-btn.live {
    color: var(--danger);
    background: var(--danger-soft);
    border-color: var(--danger-border);
    padding: 0.32rem 0.75rem;
  }
  .stop-btn.live:hover {
    border-color: var(--danger);
  }
  .stop-count {
    min-width: 1.15rem;
    padding: 0 0.3rem;
    border-radius: var(--r-pill);
    background: var(--danger);
    color: var(--text-inverse);
    font-size: var(--text-2xs);
    line-height: 1.15rem;
    text-align: center;
  }
  /* The word is the first thing to go when the header is tight; the icon and the
     count still say what the control is and how much it would reach. */
  @media (max-width: 480px) {
    .stop-label {
      display: none;
    }
  }
  .overlay {
    position: fixed;
    inset: 0;
    background: var(--overlay);
    display: grid;
    place-items: center;
    z-index: var(--z-alert);
  }
  .modal {
    background: var(--raised);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-md);
    box-shadow: var(--shadow-2);
    padding: var(--space-5);
    max-width: 30rem;
    width: calc(100% - 2rem);
  }
  .actions {
    display: flex;
    gap: 0.6rem;
    justify-content: flex-end;
    margin-top: var(--space-4);
  }
  .events {
    font-size: var(--text-sm);
    color: var(--text-2);
    padding-left: 1.1rem;
    margin: 0.4rem 0 0;
  }
  .ok-line {
    color: var(--ok);
  }
  .error-line {
    color: var(--danger);
  }
</style>
