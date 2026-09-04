<script lang="ts">
  /**
   * The completion menu above a composer (B19 / C14).
   *
   * One component for both kinds of completion — the slash-command list and the
   * `@`-mention path list — because they are the same interaction: a filtered
   * list, an active row, arrows and Enter, Escape to leave. Two components would
   * mean two keyboard behaviours to keep in step, and the second one would drift.
   *
   * It renders nothing when there is nothing to offer, with one deliberate
   * exception: a `notice` is shown *instead* of rows. An `@` that can find
   * nothing because the code map was never built is a different fact from an `@`
   * that matched no file, and a menu that showed the same emptiness for both
   * would send the owner looking for a file that is simply not indexed.
   */
  import Icon from "./Icon.svelte";

  /**
   * Governed refusals are written with Markdown emphasis, because most surfaces
   * that show them render Markdown. This one does not — it is a plain-text row
   * above a textarea — so the markers have to come off rather than reach the
   * owner as literal asterisks around the control they are being pointed at.
   */
  function plain(text: string): string {
    return text.replace(/\*\*(.+?)\*\*/g, "$1").replace(/(^|\s)\*(\S.*?)\*/g, "$1$2");
  }

  export interface MenuItem {
    /** Inserted or run when chosen. */
    id: string;
    /** What the row reads as. */
    label: string;
    /** The quieter second line. Optional — a path needs none. */
    detail?: string;
  }

  let {
    items = [],
    active = 0,
    heading = "",
    notice = null,
    onchoose,
  }: {
    items?: MenuItem[];
    active?: number;
    heading?: string;
    /** Shown instead of rows when the list cannot be filled, with its reason. */
    notice?: { text: string; href?: string; linkLabel?: string } | null;
    onchoose: (item: MenuItem) => void;
  } = $props();
</script>

{#if notice !== null}
  <div class="composer-menu menu-surface" role="status">
    <p class="menu-notice">
      <Icon name="info" size={13} />
      <span>
        {plain(notice.text)}
        {#if notice.href}<a href={notice.href}>{notice.linkLabel ?? "Open"}</a>{/if}
      </span>
    </p>
  </div>
{:else if items.length > 0}
  <div class="composer-menu menu-surface">
    {#if heading}<p class="menu-heading">{heading}</p>{/if}
    <ul role="listbox" aria-label={heading || "Suggestions"}>
      {#each items as item, index (item.id)}
        <li>
          <button
            type="button"
            class="menu-row menu-item"
            class:active={index === active}
            role="option"
            aria-selected={index === active}
            onmousedown={(event) => {
              // `mousedown`, not `click`: the textarea must not lose focus
              // before the choice lands, or the caret position it is inserted
              // at is gone by the time we use it.
              event.preventDefault();
              onchoose(item);
            }}
          >
            <span class="row-label">{item.label}</span>
            {#if item.detail}<span class="row-detail">{item.detail}</span>{/if}
          </button>
        </li>
      {/each}
    </ul>
  </div>
{/if}

<style>
  .composer-menu {
    margin: 0 0 0.45rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-2);
    overflow: hidden;
  }
  .menu-heading {
    margin: 0;
    padding: 0.35rem 0.6rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-3);
    font-size: 0.66rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0.2rem;
    max-height: 14rem;
    overflow-y: auto;
  }
  .menu-row {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    width: 100%;
    padding: 0.3rem 0.45rem;
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: 0.82rem;
    text-align: left;
    cursor: pointer;
  }
  .menu-row:hover { background: var(--sunken); }
  .menu-row.active { background: color-mix(in srgb, var(--accent) 14%, transparent); }
  .row-label { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .row-detail {
    color: var(--text-3);
    font-size: 0.74rem;
    font-weight: 400;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .menu-notice {
    display: flex;
    align-items: flex-start;
    gap: 0.4rem;
    margin: 0;
    padding: 0.45rem 0.6rem;
    color: var(--text-2);
    font-size: 0.78rem;
    line-height: 1.5;
  }
  .menu-notice a { color: var(--accent); margin-left: 0.25rem; }
</style>
