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
   * It adds no authority. Nothing here edits a hunk or changes what a change
   * *says*; the decision still belongs to the buttons the approval owns.
   *
   * B14 — what it does now carry is the reviewer's own narrowing. With
   * `selection` bound, each hunk gets a checkbox and the caller sends the
   * accepted ids alongside Accept. That is a smaller decision, never a
   * different one: the ids are positions in this diff, the server validates
   * every one against the approved patch, and a selection can only ever remove
   * hunks from what runs.
   */
  import { diffSelectable, diffStat, diffSummary, hunkId, hunkIds, parseUnifiedDiff } from "../diff";
  import Icon from "./Icon.svelte";

  let {
    diff,
    path = null,
    /** Collapsed by default in a transcript; open where the diff is the page. */
    open = true,
    emptyLabel = "(empty diff)",
    /**
     * Turn on per-hunk acceptance. Off by default, so every surface that only
     * displays a diff stays purely a reader.
     */
    selectable: allowSelection = false,
    /**
     * The hunks the reviewer has accepted, bindable. `undefined` means they
     * have not narrowed anything, which is not the same as having accepted
     * every hunk explicitly — the caller uses that difference to decide whether
     * to record a scope at all.
     */
    selection = $bindable(undefined),
  }: {
    diff: string | null;
    path?: string | null;
    open?: boolean;
    emptyLabel?: string;
    selectable?: boolean;
    selection?: string[] | undefined;
  } = $props();

  const files = $derived(parseUnifiedDiff(diff ?? ""));
  const stat = $derived(diffStat(files));
  const everyHunk = $derived(hunkIds(files));
  // Offered only where it can be honoured: a diff whose sections the server's
  // applier understands, and more than one hunk to choose between.
  const selectable = $derived(allowSelection && diffSelectable(files));
  const accepted = $derived(new Set(selection ?? everyHunk));

  function toggle(id: string) {
    const current = selection ?? everyHunk;
    selection = accepted.has(id)
      ? current.filter((item) => item !== id)
      : everyHunk.filter((item) => current.includes(item) || item === id);
  }
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
      <Icon name={expanded ? "chevron-down" : "chevron-right"} size="sm" />
      <span class="diff-title mono">{path ?? files[0].path ?? "Proposed change"}</span>
      <span class="diff-stat">
        <span class="stat-add">+{stat.added}</span>
        <span class="stat-remove">−{stat.removed}</span>
      </span>
    </button>

    {#if selectable && expanded}
      <p class="pick-note" role="status">
        {accepted.size === everyHunk.length
          ? `All ${everyHunk.length} hunks`
          : `${accepted.size} of ${everyHunk.length} hunks`}
        <button type="button" class="pick-all" onclick={() => (selection = everyHunk)}
          >Select all</button
        >
        <button type="button" class="pick-all" onclick={() => (selection = [])}>Select none</button>
      </p>
    {/if}

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
                  <tr
                    class={`row-${line.kind}`}
                    class:hunk-declined={selectable &&
                      line.hunkIndex !== null &&
                      !accepted.has(hunkId(index, line.hunkIndex))}
                  >
                    {#if selectable}
                      <td class="pick">
                        {#if line.kind === "hunk" && line.hunkIndex !== null}
                          {@const id = hunkId(index, line.hunkIndex)}
                          <input
                            type="checkbox"
                            checked={accepted.has(id)}
                            onchange={() => toggle(id)}
                            aria-label={`Accept hunk ${line.hunkIndex + 1} of ${
                              file.path === "" ? "the proposed change" : file.path
                            }`}
                          />
                        {/if}
                      </td>
                    {/if}
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
  /* B14 — the reviewer's own narrowing. The checkbox sits on the hunk header,
     where the hunk begins, and the lines it governs dim when it is declined —
     so what will and will not be applied is legible without reading the count.
     Dimming is a *second* signal beside the checkbox's own state, never the
     only one. */
  .pick {
    width: 1px;
    padding: 0 0.35rem;
    vertical-align: middle;
  }
  .pick input {
    margin: 0;
    cursor: pointer;
  }
  .hunk-declined td:not(.pick) {
    opacity: 0.4;
  }
  .pick-note {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0;
    padding: 0.3rem 0.55rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-2);
    font-size: var(--text-xs);
  }
  .pick-all {
    border: 0;
    padding: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
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
