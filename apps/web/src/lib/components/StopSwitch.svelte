<script lang="ts">
  // STOP switch (top bar). Wired to the governed interrupt path: it requests
  // cancellation of all active tasks at the next safe boundary — NOT an instant force-kill.
  import Icon from "./Icon.svelte";
  import { api, ApiError } from "../api";
  import { humanize } from "../format";
  import { ACTIVE_TASK_STATES } from "../statusMaps";
  import type { EventEntry } from "../apiTypes";

  type Phase = "confirm" | "working" | "done" | "empty" | "error";

  const INTERRUPT_EVENT_TYPES = ["interrupt_received", "safe_boundary_reached", "task_cancelled"];
  const ACTIVE_STATES = ACTIVE_TASK_STATES;

  let open = $state(false);
  let phase = $state<Phase>("confirm");
  let appliedCount = $state(0);
  let resultEvents = $state<EventEntry[]>([]);
  let errorText = $state<string | null>(null);
  let dialogEl: HTMLDivElement | undefined = $state();

  function show() {
    phase = "confirm";
    appliedCount = 0;
    resultEvents = [];
    errorText = null;
    open = true;
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
      const tasks = await api.tasks();
      const active = tasks.filter((t) => ACTIVE_STATES.includes(t.status));
      if (active.length === 0) {
        phase = "empty";
        return;
      }
      // Interrupt is per-session and required by the backend schema; group active tasks by
      // session and issue one safe-boundary cancel-all per affected session.
      const sessions = [...new Set(active.map((t) => t.session_id))];
      let applied = 0;
      for (const sessionId of sessions) {
        const result = await api.interrupt({
          session_id: sessionId,
          all: true,
          action_type: "cancel",
          reason: "user requested stop (web UI)",
        });
        applied += result.applied.length;
      }
      appliedCount = applied;
      // Surface the resulting governed events as confirmation.
      resultEvents = await loadInterruptEvents(sessions);
      phase = "done";
    } catch (e) {
      errorText =
        e instanceof ApiError ? `Interrupt failed (${e.status}).` : "Could not reach the local runtime.";
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
        // Confirmation events are best-effort; the interrupt itself already succeeded.
      }
    }
    return collected;
  }

  $effect(() => {
    if (open) dialogEl?.focus();
  });
</script>

<button type="button" class="stop-btn" onclick={show} aria-haspopup="dialog">
  <Icon name="stop" size="md" />
  STOP
</button>

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
      <h2 id="stop-title">Stop all active tasks?</h2>

      {#if phase === "confirm"}
        <p>
          This requests cancellation of every task that is queued, running, paused, or waiting
          for your approval, at the next
          <strong>safe boundary</strong>. It is governed and audited — not a force-kill.
        </p>
        <div class="actions">
          <button type="button" class="btn" onclick={close}>Cancel</button>
          <button type="button" class="btn btn-danger" onclick={confirmStop}>Stop tasks</button>
        </div>
      {:else if phase === "working"}
        <p role="status">Requesting safe-boundary stop…</p>
      {:else if phase === "empty"}
        <p role="status">No active tasks to stop.</p>
        <div class="actions">
          <button type="button" class="btn" onclick={close}>Close</button>
        </div>
      {:else if phase === "done"}
        <p role="status" class="ok-line">
          Stop applied to {appliedCount} task{appliedCount === 1 ? "" : "s"} at the safe boundary.
        </p>
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
  .stop-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--danger);
    background: var(--danger-soft);
    border: 1px solid var(--danger-border);
    border-radius: var(--r-pill);
    padding: 0.32rem 0.85rem;
    cursor: pointer;
  }
  .stop-btn:hover {
    border-color: var(--danger);
  }
  .overlay {
    position: fixed;
    inset: 0;
    background: var(--overlay);
    display: grid;
    place-items: center;
    z-index: 60;
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
