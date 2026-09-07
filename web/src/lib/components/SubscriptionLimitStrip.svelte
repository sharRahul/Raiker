<script lang="ts">
  /**
   * What a subscription says is left, in its own words (BUG-254).
   *
   * ChatGPT reports a five-hour limit and a weekly limit and how much of each is
   * gone; Ollama Cloud reports session and weekly usage. Raiker showed neither,
   * so an owner discovered a limit by hitting it mid-turn.
   *
   * Two rules, and they are the whole component:
   *
   * * **Nothing reported means nothing shown.** No zero, no "unknown", no
   *   estimate from Raiker's own ledger dressed up as the provider's number.
   *   The caller renders this only when there is a reading, and this renders
   *   only the windows inside it.
   * * **A reading is a moment, not a fact.** A window that has not been
   *   refreshed by a recent turn says so, because "68% used" three days ago is
   *   not what is true now.
   */
  import type { SubscriptionLimits } from "../apiTypes";

  let {
    limits,
    /** Heading text; omitted entirely when the caller supplies its own. */
    label = "Subscription",
  }: { limits: SubscriptionLimits; label?: string | null } = $props();

  /** Hours and minutes, said the way a person would say them. */
  function until(resetsAt: string | null): string {
    if (resetsAt === null) return "";
    const ms = new Date(resetsAt).getTime() - Date.now();
    if (!Number.isFinite(ms) || ms <= 0) return "resets now";
    const minutes = Math.round(ms / 60000);
    if (minutes < 60) return `resets in ${minutes} min`;
    const hours = Math.round(minutes / 60);
    if (hours < 48) return `resets in ${hours} h`;
    return `resets in ${Math.round(hours / 24)} d`;
  }
</script>

<section class="limits" aria-label="Subscription limits reported by the provider">
  {#if label !== null}<p class="limits-label">{label}</p>{/if}
  {#each limits.windows as window (window.label)}
    <p class="limit">
      <span class="limit-head">
        <span class="limit-name">{window.label}</span>
        <span class="limit-left">{Math.round(100 - window.used_percent)}% left</span>
      </span>
      <span
        class="track"
        role="meter"
        aria-valuenow={Math.round(window.used_percent)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${window.label} window used`}
      >
        <span class="fill" class:high={window.used_percent >= 80} style={`width:${window.used_percent}%`}></span>
      </span>
      {#if window.resets_at !== null}<small>{until(window.resets_at)}</small>{/if}
    </p>
  {/each}
  {#if limits.stale}
    <p class="quiet">From an earlier turn — the next one updates it.</p>
  {/if}
</section>

<style>
  .limits { display: grid; gap: 0.35rem; }
  .limits-label {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-2xs);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .limit { margin: 0; display: grid; gap: 0.2rem; }
  .limit-head { display: flex; justify-content: space-between; gap: 0.5rem; font-size: var(--text-xs); }
  .limit-name { color: var(--text-2); }
  .limit-left { color: var(--text-1); font-weight: 650; }
  .track {
    display: block;
    height: 4px;
    border-radius: var(--r-pill);
    background: var(--sunken);
    overflow: hidden;
  }
  .fill { display: block; height: 100%; background: var(--accent); }
  /* Nearly spent is the one state worth a second colour: it is the moment the
     owner would want to know before starting something long. */
  .fill.high { background: var(--warn); }
  small, .quiet { color: var(--text-3); font-size: var(--text-2xs); }
  .quiet { margin: 0; }
</style>
