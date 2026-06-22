<script lang="ts">
  // STOP switch (top bar). Wired to the governed interrupt path in Milestone 3: it requests
  // cancellation of all active tasks at the next safe boundary — NOT an instant force-kill.
  import { api, ApiError } from "./api";
  import type { EventEntry } from "./apiTypes";

  type Phase = "confirm" | "working" | "done" | "empty" | "error";

  const INTERRUPT_EVENT_TYPES = ["interrupt_received", "safe_boundary_reached", "task_cancelled"];
  const ACTIVE_STATES = ["queued", "running", "paused"];

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
      // Interrupt is per-session and required by the backend schema; group active tasks by session
      // and issue one safe-boundary cancel-all per affected session.
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
      errorText = e instanceof ApiError ? `Interrupt failed (${e.status}).` : "Could not reach the local runtime.";
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

<button class="stop-switch" aria-label="Stop all tasks" onclick={show}>
  <span class="stop-glyph" aria-hidden="true">■</span>
  <span class="stop-text">STOP</span>
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
      <h2 id="stop-title">Stop all tasks?</h2>
      <p>
        This cancels all active tasks <strong>at the next safe boundary</strong>. It is not an
        instant force-kill; in-flight safe operations finish first.
      </p>

      {#if phase === "confirm"}
        <div class="actions">
          <button type="button" onclick={close}>Cancel</button>
          <button type="button" class="danger" onclick={confirmStop}>
            Stop at safe boundary
          </button>
        </div>
      {:else if phase === "working"}
        <p class="note" aria-live="polite">Requesting cancellation at the next safe boundary…</p>
      {:else if phase === "empty"}
        <p class="note">No active tasks to stop.</p>
        <div class="actions">
          <button type="button" onclick={close}>Close</button>
        </div>
      {:else if phase === "error"}
        <p class="error" role="alert">{errorText}</p>
        <div class="actions">
          <button type="button" onclick={close}>Close</button>
          <button type="button" class="danger" onclick={confirmStop}>Retry</button>
        </div>
      {:else if phase === "done"}
        <p class="note" aria-live="polite">
          Requested cancellation of {appliedCount} active task{appliedCount === 1 ? "" : "s"} at the
          next safe boundary.
        </p>
        {#if resultEvents.length > 0}
          <ul class="events">
            {#each resultEvents as ev (ev.event_id)}
              <li><code>{ev.event_type}</code> <span class="emono">{ev.turn_id ?? ev.session_id}</span></li>
            {/each}
          </ul>
        {/if}
        <div class="actions">
          <button type="button" onclick={close}>Close</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .stop-switch {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 3.25rem;
    height: 3.25rem;
    border-radius: 50%;
    border: 2px solid #b3261e;
    background: #2a0f0f;
    color: #ff8a80;
    cursor: pointer;
    font-weight: 700;
  }
  .stop-switch:hover {
    background: #3a1414;
  }
  .stop-switch:focus-visible {
    outline: 3px solid #ff8a80;
    outline-offset: 2px;
  }
  .stop-glyph {
    font-size: 1rem;
    line-height: 1;
  }
  .stop-text {
    font-size: 0.6rem;
    letter-spacing: 0.08em;
  }
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: grid;
    place-items: center;
    z-index: 50;
  }
  .modal {
    background: #15151a;
    border: 1px solid #3a3a40;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    max-width: 30rem;
    color: #d4d4da;
  }
  .modal:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 2px;
  }
  .modal h2 {
    margin-top: 0;
  }
  .note {
    color: #e6c66a;
    font-size: 0.85rem;
  }
  .error {
    color: #ef9a9a;
    font-size: 0.85rem;
  }
  .events {
    margin: 0.5rem 0 0;
    padding-left: 1.1rem;
    font-size: 0.8rem;
    max-height: 12rem;
    overflow: auto;
  }
  .events code {
    color: #9cc7ec;
  }
  .emono {
    font-family: ui-monospace, monospace;
    color: #9a9aa2;
  }
  .actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
    margin-top: 1rem;
  }
  .actions button {
    padding: 0.4rem 0.9rem;
    border-radius: 6px;
    border: 1px solid #4a4a52;
    background: #1f1f25;
    color: #d4d4da;
    cursor: pointer;
  }
  .actions button:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  .actions .danger {
    border-color: #8a2f2f;
    background: #2a1212;
    color: #ff8a80;
  }
  .actions .danger:hover {
    background: #3a1414;
  }
</style>
