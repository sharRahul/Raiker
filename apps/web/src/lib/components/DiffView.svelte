<script lang="ts">
  /**
   * B14 — a proposed change, read as a diff rather than as a block of text.
   *
   * The unified diff the server already produces is what an owner has to read
   * before approving a write, so it is rendered as one: per file, with the line
   * numbers the hunk headers state, added and removed lines told apart by more
   * than colour, and the whole thing scrolling inside itself so a long line
   * never widens the page.
   *
   * It adds no authority. Nothing here resolves an approval, edits a hunk, or
   * changes what will run — this is the reading surface, and the decision stays
   * with the buttons the approval already owns.
   */
  import { diffStat, diffSummary, parseUnifiedDiff } from "../diff";
  import Icon from "./Icon.svelte";

  let {
    diff,
    path = null,
    /** Collapsed by default in a transcript; open where the diff is the page. */
    open = true,
    emptyLabel = "(empty diff)",
  }: {
    diff: string | null;
    path?: string | null;
    open?: boolean;
    emptyLabel?: string;
  } = $props();

  const files = $derived(parseUnifiedDiff(diff ?? ""));
  const stat = $derived(diffStat(files));
  // Null until the reader has an opinion, so `open` stays the default rather
  // than a value captured once at construction.
  let opened = $state<boolean | null>(null);
  const expanded = $derived(opened ?? open);
</script>

{#if files.length === 0}
  <p class="diff-empty">{emptyLabel}</p>
{:else}
  <section class="diff-view" aria-label={`Proposed change — ${diffSummary(stat)}`}>
    <button
      type="button"
      class="diff-head"
      aria-expanded={expanded}
      onclick={() => (opened = !expanded)}
    >
      <Icon name={expanded ? "chevron-down" : "chevron-right"} size={13} />
      <span class="diff-title mono">{path ?? files[0].path ?? "Proposed change"}</span>
      <span class="diff-stat">
        <span class="stat-add">+{stat.added}</span>
        <span class="stat-remove">−{stat.removed}</span>
      </span>
    </button>

    {#if expanded}
      {#each files as file, index (file.path + index)}
        <div class="diff-file">
          {#if files.length > 1 || (path !== null && file.path !== "" && file.path !== path)}
            <p class="diff-file-path mono">{file.path === "" ? "(unnamed file)" : file.path}</p>
          {/if}
          <!-- Focusable so the diff can be scrolled from the keyboard: a long
               line is unreachable otherwise. It holds a table, not a control. -->
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <div
            class="diff-scroll"
            tabindex="0"
            role="group"
            aria-label={`Diff for ${file.path === "" ? "the proposed change" : file.path}`}
          >
            <table class="diff-table">
              <tbody>
                {#each file.lines as line, i (i)}
                  <tr class={`row-${line.kind}`}>
                    <td class="gutter" aria-hidden="true">{line.oldLine ?? ""}</td>
                    <td class="gutter" aria-hidden="true">{line.newLine ?? ""}</td>
                    <td class="sign" aria-hidden="true"
                      >{line.kind === "add" ? "+" : line.kind === "remove" ? "−" : ""}</td
                    >
                    <td class="code">
                      {#if line.kind === "add" || line.kind === "remove"}
                        <span class="sr-only">{line.kind === "add" ? "Added:" : "Removed:"}</span>
                      {/if}{line.text}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/each}
    {/if}
  </section>
{/if}

<style>
  .diff-view {
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    overflow: hidden;
  }
  .diff-head {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    width: 100%;
    padding: 0.4rem 0.55rem;
    border: 0;
    background: var(--sunken);
    color: var(--text-2);
    font: inherit;
    font-size: var(--text-xs);
    cursor: pointer;
    text-align: left;
  }
  .diff-head:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }
  .diff-title {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .diff-stat { display: inline-flex; gap: 0.4rem; font-variant-numeric: tabular-nums; }
  .stat-add { color: var(--ok); }
  .stat-remove { color: var(--danger); }
  .diff-file + .diff-file { border-top: 1px solid var(--border); }
  .diff-file-path {
    margin: 0;
    padding: 0.35rem 0.55rem;
    font-size: var(--text-2xs);
    color: var(--text-3);
    background: var(--sunken);
    border-bottom: 1px solid var(--border);
  }
  /* The diff scrolls inside itself: a 200-column line must never widen the
     transcript it sits in. */
  .diff-scroll { overflow-x: auto; max-height: 26rem; overflow-y: auto; }
  .diff-scroll:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }
  .diff-table {
    border-collapse: collapse;
    width: 100%;
    font-family: var(--font-mono);
    font-size: var(--text-2xs);
    line-height: 1.55;
  }
  .gutter {
    width: 1px;
    padding: 0 0.4rem;
    text-align: right;
    color: var(--text-3);
    opacity: 0.7;
    user-select: none;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .sign { width: 1px; padding: 0 0.2rem; user-select: none; }
  .code { padding: 0 0.5rem 0 0.2rem; white-space: pre; }
  .row-add { background: var(--ok-soft); }
  .row-add .sign, .row-add .code { color: var(--ok); }
  .row-remove { background: var(--danger-soft); }
  .row-remove .sign, .row-remove .code { color: var(--danger); }
  .row-hunk .code { color: var(--info); background: var(--sunken); }
  .row-hunk, .row-meta { background: var(--sunken); }
  .row-meta .code { color: var(--text-3); }
  .diff-empty {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
</style>
