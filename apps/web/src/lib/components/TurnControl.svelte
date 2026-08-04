<script lang="ts">
  /*
   * B17 / C13 — the two controls an owner needs over a turn that is *already
   * running*, in the place the turn is running: the composer.
   *
   * Stop asks the runtime to end the turn at its next safe boundary. It is the
   * same governed `POST /api/interrupts` the STOP switch in the top bar uses —
   * not a force-kill, not a closed browser tab — so the turn ends with what it
   * has, records why it ended, and keeps the text the owner already read.
   *
   * Steer queues the owner's own words into the running turn. They arrive as a
   * user message at the same boundary, before the model is asked anything else,
   * so a turn heading the wrong way is corrected rather than waited out and
   * re-prompted. Steering grants nothing: every call the model makes after
   * reading it is governed exactly as it was before.
   *
   * Both need the session id, which a brand-new chat only learns from its first
   * streamed event — until then the controls say so rather than pretending to
   * work.
   */
  import Icon from "./Icon.svelte";
  import { api, ApiError } from "../api";

  let {
    sessionId,
    stopping = $bindable(false),
  }: { sessionId: string | null; stopping?: boolean } = $props();

  let steerText = $state("");
  let steerCount = $state(0);
  let busy = $state(false);
  let error = $state<string | null>(null);

  const ready = $derived(sessionId !== null && sessionId !== "");

  async function stop() {
    if (!ready || busy) return;
    busy = true;
    error = null;
    try {
      await api.interrupt({
        session_id: sessionId as string,
        all: true,
        action_type: "cancel",
        reason: "user stopped this turn (composer)",
      });
      stopping = true;
    } catch (e) {
      error = e instanceof ApiError ? `Stop failed (${e.status}).` : "Could not reach the local runtime.";
    } finally {
      busy = false;
    }
  }

  async function steer(event: Event) {
    event.preventDefault();
    const text = steerText.trim();
    if (!ready || busy || text === "") return;
    busy = true;
    error = null;
    try {
      const result = await api.interrupt({
        session_id: sessionId as string,
        all: true,
        action_type: "steer",
        reason: "user steered this turn (composer)",
        steer_text: text,
      });
      steerCount = result.turn_control?.queued ?? steerCount + 1;
      steerText = "";
    } catch (e) {
      error = e instanceof ApiError ? `Steer failed (${e.status}).` : "Could not reach the local runtime.";
    } finally {
      busy = false;
    }
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void steer(event);
    }
  }
</script>

<div class="turn-control" data-testid="turn-control">
  <form class="steer" onsubmit={steer}>
    <label class="sr-only" for="steer-input">Add to this turn</label>
    <input
      id="steer-input"
      class="steer-input"
      type="text"
      bind:value={steerText}
      onkeydown={onKeydown}
      placeholder={ready ? "Add to this turn — it arrives at the next safe boundary" : "Starting…"}
      disabled={!ready || busy}
      autocomplete="off"
    />
    <button
      type="submit"
      class="btn btn-ghost steer-send"
      disabled={!ready || busy || steerText.trim() === ""}
      title="Queue this for the running turn"
    >
      <Icon name="send" size={14} />
      Steer
    </button>
  </form>

  <button
    type="button"
    class="btn btn-danger stop"
    onclick={stop}
    disabled={!ready || busy || stopping}
    aria-label={stopping ? "Stopping at the next safe boundary" : "Stop this turn"}
  >
    <Icon name="stop" size={14} />
    {stopping ? "Stopping…" : "Stop"}
  </button>
</div>

{#if steerCount > 0}
  <p class="control-note" role="status">
    {steerCount} instruction{steerCount === 1 ? "" : "s"} queued for this turn — the model reads
    {steerCount === 1 ? "it" : "them"} at the next safe boundary.
  </p>
{/if}
{#if stopping}
  <p class="control-note" role="status">
    Stop requested. The turn ends at its next safe boundary and keeps what it has already done.
  </p>
{/if}
{#if error}
  <p class="control-note error" role="alert">{error}</p>
{/if}

<style>
  .turn-control {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
  }
  .steer {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex: 1 1 auto;
    min-width: 0;
  }
  .steer-input {
    flex: 1 1 auto;
    min-width: 0;
    font: inherit;
    font-size: 0.85rem;
    color: var(--text-1);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 0.4rem 0.8rem;
  }
  .steer-input:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  .steer-send {
    flex: 0 0 auto;
  }
  .stop {
    flex: 0 0 auto;
  }
  .control-note {
    margin: 0.35rem 0 0;
    font-size: 0.78rem;
    color: var(--text-2);
  }
  .control-note.error {
    color: var(--danger);
  }
</style>
