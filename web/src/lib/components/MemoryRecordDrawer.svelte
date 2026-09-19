<script lang="ts">
  /**
   * REM-MEM-01 — one record drawer, instead of seven equally prominent actions.
   *
   * A memory card carried **View source**, **Edit**, **Edit scope**, **Review
   * expiry**, **Pin**, **View history** and **Forget** in one row, at one
   * weight, with **Delete permanently** in a disclosure below. Seven controls
   * of equal prominence is not a choice an owner makes quickly; it is a row
   * they have to read every time, and the three that change what Raiker
   * remembers looked exactly like the four that only show it something.
   *
   * The card keeps the two everyday actions — **Edit** and **Pin** — plus the
   * provenance and expiry summary, and one **More** that opens this. Here the
   * rest are grouped by what they do rather than laid out in a line, and the
   * three irreversible ones state their consequence separately rather than
   * sharing one sentence.
   *
   * **The revision is the drawer's, not the card's.** A card is drawn from a
   * list that was read when the page loaded, and this drawer is where scope,
   * expiry and deletion are decided — all three of which the server versions
   * against `updated_at`. So it takes the record by id from the list its
   * parent keeps refreshed, and when that record is no longer there — forgotten
   * in another tab, expired by the sweep, or reached from an old bookmark — it
   * says so and offers nothing rather than acting on a copy that has stopped
   * being true.
   */
  import Icon from "./Icon.svelte";
  import { relativeTime } from "../format";
  import type { MemoryControlView, MemoryHistoryEvent } from "../apiTypes";

  let {
    record,
    history = null,
    onClose,
    onViewSource,
    onChangeScope,
    onReviewExpiry,
    onViewHistory,
    onForget,
    onPurge,
  }: {
    /** `null` when the record this drawer was opened for is no longer listed. */
    record: MemoryControlView | null;
    history?: MemoryHistoryEvent[] | null;
    onClose: () => void;
    onViewSource: (record: MemoryControlView) => void;
    onChangeScope: (record: MemoryControlView) => void;
    onReviewExpiry: (record: MemoryControlView) => void;
    onViewHistory: (record: MemoryControlView) => void;
    onForget: (record: MemoryControlView) => void;
    onPurge: (record: MemoryControlView) => void;
  } = $props();

  let panel: HTMLElement | undefined = $state();

  // Focus lands in the drawer when it opens, and Escape closes it. Both are the
  // same contract every other panel in Raiker meets; a drawer that opens
  // behind the keyboard is a drawer a keyboard user cannot reach.
  $effect(() => {
    if (record !== null || panel !== undefined) panel?.focus();
  });

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") onClose();
  }
</script>

<!-- A region rather than a dialog: it expands in place beside the card it
     belongs to, nothing behind it is inert, and calling it a dialog would
     promise a focus trap and a modal backdrop that are not there. -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<section
  class="drawer"
  bind:this={panel}
  tabindex="-1"
  aria-label="Memory record"
  onkeydown={onKeydown}
>
  <header>
    <h4>Memory record</h4>
    <button type="button" class="btn btn-ghost btn-sm" onclick={onClose}>
      <Icon name="x" size="sm" />
      Close
    </button>
  </header>

  {#if record === null}
    <!-- An old bookmarked record, or one another tab forgot while this drawer
         was open. Saying so is the whole point of resolving by id: the
         alternative is a drawer whose buttons act on a revision that is gone. -->
    <p class="gone" role="status">
      This record is no longer in your approved memories. It may have been
      forgotten, expired, or deleted since this page was loaded. Refresh to see
      what is there now.
    </p>
  {:else}
    <p class="text">{record.text}</p>

    <dl class="facts">
      <div><dt>Scope</dt><dd>{record.scope}</dd></div>
      <div><dt>Sensitivity</dt><dd>{record.sensitivity}</dd></div>
      <div><dt>Type</dt><dd>{record.memory_type}</dd></div>
      <div><dt>Retention</dt><dd>{record.retention}</dd></div>
      <div><dt>Confidence</dt><dd>{record.confidence.toFixed(2)}</dd></div>
      <div><dt>Trust</dt><dd>{record.trust_score.toFixed(2)}</dd></div>
      <div>
        <dt>Review or expiry</dt>
        <dd>{record.expires_at ? relativeTime(record.expires_at) : "No date set"}</dd>
      </div>
      <div>
        <!-- REM-MEM-02 — inclusion, never use. Nothing records whether an
             answer relied on a record that was put in front of it. -->
        <dt>Last included in a model’s context</dt>
        <dd>{record.last_used_at ? relativeTime(record.last_used_at) : "Never"}</dd>
      </div>
      <div>
        <dt>Source record details</dt>
        <dd>
          {Object.keys(record.provenance).length
            ? Object.keys(record.provenance).join(", ")
            : "Source metadata unavailable"}
        </dd>
      </div>
    </dl>

    <section aria-labelledby="mem-drawer-inspect">
      <h5 id="mem-drawer-inspect">Look at the record</h5>
      <p class="note">Neither of these changes anything Raiker remembers.</p>
      <div class="actions">
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => onViewSource(record)}>
          View source
        </button>
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => onViewHistory(record)}>
          View history
        </button>
      </div>
      {#if history !== null}
        <ol class="history" aria-label="Memory history">
          {#each history as event (event.created_at + event.action)}
            <li>
              <strong>{event.action.replaceAll("_", " ")}</strong>
              <span>{relativeTime(event.created_at)}</span>
            </li>
          {/each}
        </ol>
      {/if}
    </section>

    <section aria-labelledby="mem-drawer-lifecycle">
      <h5 id="mem-drawer-lifecycle">Change how long it lives</h5>
      <!-- Each consequence stated on its own, because they are different
           consequences. Scope decides which work may recall the record;
           expiry decides when it comes back for review. One shared sentence
           made them read as one setting. -->
      <div class="lifecycle">
        <div>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => onChangeScope(record)}>
            Edit scope
          </button>
          <p class="note">
            Scope decides which work may recall this record. Narrowing it takes
            the fact out of the context of everything outside the new scope.
          </p>
        </div>
        <div>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => onReviewExpiry(record)}>
            Review expiry
          </button>
          <p class="note">
            An expiry date brings the record back for review on that date. With
            no date set it stays until you forget it.
          </p>
        </div>
      </div>
    </section>

    <section aria-labelledby="mem-drawer-remove">
      <h5 id="mem-drawer-remove">Remove it</h5>
      <div class="lifecycle">
        <div>
          <button type="button" class="btn btn-ghost btn-sm danger" onclick={() => onForget(record)}>
            Forget
          </button>
          <p class="note">
            Raiker stops using this record in future work. Existing responses and
            required audit records are not rewritten.
          </p>
        </div>
        <div>
          <button type="button" class="btn btn-ghost btn-sm danger" onclick={() => onPurge(record)}>
            Delete permanently
          </button>
          <p class="note">
            Removes the record and its derived artifacts. You are shown what
            would go, and asked to type the record’s id, before anything does.
          </p>
        </div>
      </div>
    </section>
  {/if}
</section>

<style>
  .drawer {
    display: grid;
    gap: var(--space-4);
    padding: var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
  }
  .drawer:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }
  h4 {
    margin: 0;
    font-size: var(--text-base);
  }
  h5 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .text {
    margin: 0;
    font-weight: 650;
  }
  .gone {
    margin: 0;
    color: var(--text-2);
  }
  .facts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: var(--space-2) var(--space-4);
    margin: 0;
  }
  .facts dt {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .facts dd {
    margin: 0;
    font-size: var(--text-sm);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .lifecycle {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    gap: var(--space-3);
  }
  .note {
    margin: var(--space-2) 0 0;
    color: var(--text-2);
    font-size: var(--text-xs);
  }
  .history {
    margin: var(--space-3) 0 0;
    padding-left: 1.1rem;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
</style>
