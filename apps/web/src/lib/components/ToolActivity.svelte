<script lang="ts">
  /**
   * What a turn actually did, one call per line (BUG-206 slice D).
   *
   * Before this, a turn that listed a directory, read three files and fetched a
   * page rendered exactly like a turn that used no tools: prompt bubble, answer
   * bubble. The only call a conversation ever mentioned was one policy had
   * *refused*, which made refusal the single visible tool outcome and success
   * invisible.
   *
   * Each row is `[icon] [tool] [action]`:
   *
   * * the **icon** names the family — file, shell, web, repository, connector,
   *   memory, subagent, plan — so the kind of work reads before the words do;
   * * the **tool** is the owner's language, never the identifier;
   * * the **action** names the object it acted on.
   *
   * All three are resolved in `raiker/tools/presentation.py` and arrive on the
   * stream already redacted. Nothing here is derived from raw arguments, which
   * is the property that keeps a transcript row from being able to say more
   * than the audit log does.
   *
   * A refused call (slice E) is this same row in a refused state, in the place
   * it was refused, rather than a separate card at the bottom of the turn.
   */
  import Icon from "./Icon.svelte";
  import { familyIcon, type ToolCallRow } from "../chatPresentation";
  import { navItem } from "../nav";

  let { rows }: { rows: ToolCallRow[] } = $props();

  const STATE_LABEL: Record<ToolCallRow["state"], string> = {
    running: "running",
    waiting: "waiting for your decision",
    success: "done",
    failed: "failed",
    denied: "not permitted",
    refused: "refused",
  };

  // The states that put their own words on screen. The rest are carried by the
  // glyph, which is exactly what a screen reader needs told.
  const SPOKEN_STATES = new Set<ToolCallRow["state"]>([
    "waiting",
    "failed",
    "denied",
    "refused",
  ]);
</script>

{#if rows.length > 0}
  <ul class="tool-activity" aria-label="What Raiker did in this turn">
    {#each rows as row (row.actionId)}
      <li class="tool-row" data-state={row.state} data-family={row.family}>
        <span class="tool-glyph" aria-hidden="true">
          {#if row.state === "running"}
            <span class="tool-pulse"></span>
          {:else if row.state === "waiting"}
            <Icon name="hand" size="sm" />
          {:else}
            <Icon name={familyIcon(row.family)} size="sm" />
          {/if}
        </span>
        <span class="tool-label">{row.label}</span>
        <!-- The action and any short state share one column, so a long path
             ellipses instead of squeezing the words beside it onto their own
             lines one at a time. -->
        <span class="tool-detail">
          {#if row.action}<span class="tool-action">{row.action}</span>{/if}
          {#if row.state === "waiting"}
            <!-- Nothing is running: the turn stopped on the owner's decision,
                 and the approval card below it is where that decision is
                 made. -->
            <span class="tool-waiting">{STATE_LABEL.waiting}</span>
          {/if}
        </span>
        {#if !SPOKEN_STATES.has(row.state)}
          <!-- "running" and "done" are carried by the glyph alone, which a
               screen reader cannot see. Every other state states itself in
               visible text below, so repeating it here would announce it
               twice. -->
          <span class="sr-only">{STATE_LABEL[row.state]}</span>
        {/if}
        {#if row.state === "failed" || row.state === "denied" || row.state === "refused"}
          <span class="tool-reason">
            {row.state === "refused" ? "refused" : row.state === "denied" ? "not permitted" : "failed"}{row
              .reasons.length > 0
              ? ` — ${row.reasons.join(", ")}`
              : ""}
          </span>
          {#if row.remediationRoute}
            <a class="tool-remedy" href={`#/${row.remediationRoute}`}
              >Open {navItem(row.remediationRoute).label}</a
            >
          {/if}
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .tool-activity {
    list-style: none;
    margin: 0 0 0.4rem;
    padding: 0;
    display: grid;
    gap: 0.15rem;
  }
  /* One line per call. `auto auto 1fr` keeps the labels of a batch of reads
     aligned with each other, so three reads read as three of the same thing
     rather than as three unrelated rows. */
  .tool-row {
    display: grid;
    grid-template-columns: 1.05rem auto minmax(0, 1fr);
    align-items: baseline;
    gap: 0.45rem;
    font-size: 0.79rem;
    color: var(--text-3);
    line-height: 1.5;
  }
  .tool-glyph {
    display: grid;
    place-items: center;
    color: var(--text-3);
    align-self: center;
  }
  .tool-row[data-state="success"] .tool-glyph { color: var(--text-2); }
  .tool-row[data-state="failed"] .tool-glyph,
  .tool-row[data-state="denied"] .tool-glyph,
  .tool-row[data-state="refused"] .tool-glyph { color: var(--warn); }
  .tool-row[data-state="waiting"] .tool-glyph { color: var(--accent); }
  .tool-waiting {
    color: var(--accent);
    white-space: nowrap;
  }
  .tool-label {
    color: var(--text-2);
    font-weight: 600;
    white-space: nowrap;
  }
  .tool-detail {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    min-width: 0;
  }
  .tool-action {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  /* The reason and the remedy break onto their own line rather than pushing the
     action out of view: a failure is the row you most need to read in full. */
  .tool-reason {
    grid-column: 2 / -1;
    color: var(--warn);
  }
  .tool-remedy {
    grid-column: 2 / -1;
    justify-self: start;
    font-size: 0.76rem;
  }
  /* A call still running: the same quiet pulse the composer uses, in the
     glyph's place, so the row does not change width when it settles. */
  .tool-pulse {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
    animation: tool-pulse 1.4s ease-in-out infinite;
  }
  @keyframes tool-pulse {
    0%, 100% { opacity: 0.35; }
    50% { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .tool-pulse { animation: none; opacity: 0.8; }
  }
</style>
