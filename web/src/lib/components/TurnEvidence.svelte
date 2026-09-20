<script lang="ts">
  /**
   * REM-CHAT-01 — one turn's own evidence, under the turn.
   *
   * The transcript is the answer and the decisions it asked for. Everything
   * that proves *how* it got there — the turn's coordinate, each call's action
   * id, the governed events the runtime wrote down — lived on another route, so
   * checking a turn meant leaving the conversation, finding the session again
   * and matching by timestamp.
   *
   * This is the shared expandable inspector that ends that. It is collapsed
   * until asked for, so the primary reading order is unchanged: the answer, the
   * calls in the owner's language, the approval, the failure, the sources. It
   * fetches nothing until it is opened — a long conversation does not issue one
   * request per turn to show a closed disclosure.
   *
   * It shows what the runtime recorded and nothing it assembles itself. Every
   * summary below arrives redacted from `raiker/tools/presentation.py` and the
   * audit writer; this component never renders a raw argument, and the
   * full record, with its filters and its export, stays one link away.
   */
  import { api, ApiError } from "../api";
  import type { EventEntry } from "../apiTypes";
  import type { ToolCallRow } from "../chatPresentation";

  /** One governance phase of a turn, as a surface has already grouped it. */
  export type TurnPhaseRow = { phase: string; label: string; lines: string[] };
  import { evidenceLink } from "../turnAnchor";
  import Icon from "./Icon.svelte";

  let {
    sessionId,
    turnId,
    rows = [],
    phases = [],
    initiallyOpen = false,
    label = "Evidence",
  }: {
    sessionId: string | null;
    turnId: string | null;
    rows?: ToolCallRow[];
    /**
     * The governance phases a turn is producing *now*, for a surface that
     * watches a turn run. Build had its own disclosure for these; passing them
     * here is what lets one inspector serve a running turn and a settled one,
     * instead of two components that answer the same question differently.
     */
    phases?: TurnPhaseRow[];
    initiallyOpen?: boolean;
    label?: string;
  } = $props();

  let events = $state<EventEntry[] | null>(null);
  let loadError = $state<string | null>(null);
  let loading = $state(false);
  let copied = $state(false);

  async function load(): Promise<void> {
    if (turnId === null || turnId === "" || events !== null || loading) return;
    loading = true;
    loadError = null;
    try {
      const detail = await api.turn(turnId);
      events = detail.events;
    } catch (error) {
      // Said, not swallowed. An inspector that shows an empty list when the
      // record could not be read is claiming the turn did nothing.
      loadError =
        error instanceof ApiError
          ? `The record for this turn could not be read (${error.status}).`
          : "The record for this turn could not be read.";
    } finally {
      loading = false;
    }
  }

  function toggle(event: Event): void {
    if ((event.currentTarget as HTMLDetailsElement).open) void load();
  }

  async function copyCoordinate(): Promise<void> {
    if (turnId === null) return;
    try {
      await navigator.clipboard.writeText(turnId);
      copied = true;
      setTimeout(() => (copied = false), 1600);
    } catch {
      copied = false;
    }
  }

  function moment(timestamp: string): string {
    const parsed = new Date(timestamp);
    return Number.isNaN(parsed.getTime()) ? timestamp : parsed.toLocaleTimeString();
  }
</script>

{#if (turnId !== null && turnId !== "") || phases.length > 0 || rows.length > 0}
  <details class="turn-evidence" open={initiallyOpen} ontoggle={toggle}>
    <summary>
      <Icon name="eye" size="sm" />
      <span>{label}</span>
      {#if rows.length > 0}
        <span class="count">{rows.length} {rows.length === 1 ? "call" : "calls"}</span>
      {/if}
    </summary>

    <div class="body">
      {#if turnId !== null && turnId !== ""}
      <div class="coordinate">
        <span class="key">Turn</span>
        <code>{turnId}</code>
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={() => void copyCoordinate()}
          aria-label={copied ? "Turn id copied" : "Copy turn id"}
          title={copied ? "Turn id copied" : "Copy turn id"}
        ><Icon name={copied ? "check" : "copy"} size="sm" /></button>
        {#if sessionId}
          <a class="full-record" href={evidenceLink(sessionId, turnId)}>Open the full record</a>
        {/if}
      </div>
      {/if}

      {#if rows.length > 0}
        <h4>Calls</h4>
        <ul class="calls">
          {#each rows as row (row.actionId)}
            <li>
              <span class="call-label">{row.label}</span>
              {#if row.action}<span class="call-action">{row.action}</span>{/if}
              <code class="action-id">{row.actionId}</code>
            </li>
          {/each}
        </ul>
      {/if}

      <!-- The phases and the stored record are two versions of the same thing,
           so only one is shown. The record wins once there is a coordinate to
           read it by; the phases stand in while the turn is still running, and
           again if the record turns out not to be readable. -->
      {#if phases.length > 0 && (turnId === null || turnId === "" || loadError !== null)}
        <h4>How this turn was governed</h4>
        <ol class="phases">
          {#each phases as row (row.phase)}
            <li>
              <span class="phase">{row.label}</span>
              <ul>
                {#each row.lines as line, index (index)}<li>{line}</li>{/each}
              </ul>
            </li>
          {/each}
        </ol>
      {/if}

      {#if turnId !== null && turnId !== ""}
      <h4>What the runtime recorded</h4>
      {#if loading}
        <p class="muted" role="status">Reading the record…</p>
      {:else if loadError}
        <p class="error-line" role="alert">{loadError}</p>
      {:else if events !== null && events.length === 0}
        <p class="muted">No governed events were written for this turn.</p>
      {:else if events !== null}
        <ul class="events">
          {#each events as event (event.event_id)}
            <li data-risk={event.risk_level ?? "none"}>
              <span class="event-time">{moment(event.timestamp)}</span>
              <span class="event-type">{event.event_type.replaceAll("_", " ")}</span>
              <span class="event-actor">{event.actor}</span>
              {#if event.summary}<span class="event-summary">{event.summary}</span>{/if}
            </li>
          {/each}
        </ul>
      {/if}
      {/if}
    </div>
  </details>
{/if}

<style>
  .turn-evidence { margin: 0.35rem 0 0; }
  summary {
    display: inline-flex; align-items: center; gap: 0.35rem;
    cursor: pointer; color: var(--text-3); font-size: var(--text-sm);
    list-style: none;
  }
  summary::-webkit-details-marker { display: none; }
  summary:hover { color: var(--text-2); }
  .count { color: var(--text-3); font-size: var(--text-xs); }
  .body {
    margin-top: var(--space-2); padding: var(--space-3);
    border: 1px solid var(--border); border-radius: var(--r-md); background: var(--sunken);
    display: grid; gap: var(--space-2);
  }
  h4 { margin: var(--space-2) 0 0; color: var(--text-3); font-size: var(--text-xs);
    text-transform: uppercase; letter-spacing: 0.04em; font-weight: 650; }
  .coordinate { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); }
  .key { color: var(--text-3); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.04em; }
  code { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--text-2); overflow-wrap: anywhere; }
  .full-record { margin-left: auto; font-size: var(--text-sm); }
  .calls, .events { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.25rem; }
  .calls li { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-2); font-size: var(--text-sm); }
  .call-label { color: var(--text-1); }
  .call-action { color: var(--text-2); }
  .action-id { margin-left: auto; color: var(--text-3); }
  .events li {
    display: grid; grid-template-columns: auto auto auto minmax(0, 1fr);
    gap: var(--space-2); align-items: baseline; font-size: var(--text-xs);
  }
  .event-time { color: var(--text-3); font-family: var(--font-mono); }
  .event-type { color: var(--text-1); }
  .event-actor { color: var(--text-3); }
  .event-summary { color: var(--text-2); overflow-wrap: anywhere; }
  /* Risk is the runtime's own classification of the event, so it is shown where
     the event is rather than summarised into a badge somewhere else. */
  .events li[data-risk="high"] .event-type, .events li[data-risk="critical"] .event-type { color: var(--danger); }
  .phases { margin: 0; padding-left: 1.1rem; display: grid; gap: 0.25rem; }
  .phases > li { font-size: var(--text-xs); color: var(--text-2); }
  .phases .phase { color: var(--text-1); }
  .phases ul { list-style: none; margin: 0.1rem 0 0; padding: 0; display: grid; gap: 0.1rem; }
  .muted { color: var(--text-3); font-size: var(--text-sm); margin: 0; }
  @media (max-width: 40rem) {
    .events li { grid-template-columns: auto minmax(0, 1fr); }
    .action-id { margin-left: 0; flex-basis: 100%; }
    .full-record { margin-left: 0; }
  }
</style>
