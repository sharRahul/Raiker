<script lang="ts">
  /**
   * C4 — one cited source, opened at the passage the turn used, inline.
   *
   * Chat opens a source in the file inspector because Chat has one. Build has
   * a file explorer of its own now (B13), but it is a view of the repository
   * rather than of a cited passage, and a chip that opens nothing would be a
   * dead control — so Build still gets the passage where the citation is, under
   * the answer that cited it.
   *
   * The same two rules the inspector follows apply here and are the reason this
   * is safe: the excerpt is bounded plain text, and the highlight is applied by
   * *slicing that text* (`splitExcerpt`), never by rendering markup the source
   * supplied. Every unresolvable case is a named state in words rather than an
   * empty box.
   */
  import Icon from "./Icon.svelte";
  import SourceAnchorLinks from "./SourceAnchorLinks.svelte";
  import { splitExcerpt } from "../citations";
  import type { TurnSourceExcerptView } from "../apiTypes";

  let {
    source,
    loading = false,
    onclose,
  }: {
    source: TurnSourceExcerptView | null;
    loading?: boolean;
    onclose: () => void;
  } = $props();

  const STATUS_TEXT: Record<string, string> = {
    resolved: "",
    no_provenance: "This source did not keep the text it contributed, so there is nothing to open.",
    source_deleted: "What this came from is no longer there, so its passage cannot be shown.",
    source_changed: "The source no longer contains this passage, so it is shown without a highlight.",
    unsupported_source: "This source has no text passage to open at.",
    not_authorized: "This account cannot read the source this came from.",
  };

  const RESOLUTION_TEXT: Record<string, string> = {
    stored_coordinates: "Verified from stored coordinates",
    matching_text: "Located by matching text",
    answer_quote: "Located by matching this answer's own words",
    recorded_passage: "Exactly what this turn received",
    whole_source: "The whole of this source was read",
  };

  const note = $derived(
    source === null ? "" : (STATUS_TEXT[source.status] ?? "This source could not be resolved."),
  );
  const parts = $derived(
    source === null
      ? null
      : splitExcerpt(source.excerpt, source.highlight_start, source.highlight_length),
  );

</script>

{#if loading || source !== null}
  <section class="source-panel" aria-label="Cited source">
    <header>
      <span class="eyebrow"><Icon name="quote" size={13} /> Source</span>
      {#if source !== null}
        <strong>{source.title}</strong>
        <!-- The locator repeats the title for a file source; saying the same
             thing twice is noise, so it is shown only when it adds something. -->
        {#if source.locator && source.locator !== source.title}
          <span class="locator">{source.locator}</span>
        {/if}
      {/if}
      <button type="button" class="btn btn-ghost btn-sm" onclick={onclose} aria-label="Close source">
        <Icon name="x" size={14} />
      </button>
    </header>
    {#if loading}
      <p class="muted" role="status">Opening the source…</p>
    {:else if source !== null}
      {#if source.status === "resolved" && source.resolution_method}
        <span class="resolution">{RESOLUTION_TEXT[source.resolution_method] ?? "Located by matching text"}</span>
      {/if}
      {#if note}<p class="muted">{note}</p>{/if}
      {#if parts !== null && source.excerpt !== ""}
        <blockquote>{parts.before}<mark>{parts.passage}</mark>{parts.after}</blockquote>
        {#if source.truncated}
          <p class="muted truncation">Showing the passage and the text around it only.</p>
        {/if}
      {/if}
      <!-- BUG-245 — the passage above names each exchange it returned, which
           is what made the citation checkable; these are the same names as
           links, so checking one stops meaning retyping its title into chat
           search. -->
      <SourceAnchorLinks anchors={source.anchors ?? []} />
    {/if}
  </section>
{/if}

<style>
  .source-panel {
    margin: 0.5rem 0 0;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }
  .eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: var(--text-2xs);
    font-weight: 600;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    color: var(--text-3);
  }
  header strong {
    font-size: var(--text-sm);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .locator {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  header button {
    margin-left: auto;
  }
  .resolution {
    display: inline-block;
    margin-bottom: var(--space-2);
    padding: 0.1rem 0.45rem;
    border-radius: var(--r-pill);
    background: var(--surface);
    font-size: var(--text-2xs);
    color: var(--text-3);
  }
  blockquote {
    margin: 0;
    padding: 0.55rem 0.75rem;
    border-left: 3px solid var(--border-strong);
    background: var(--surface);
    border-radius: 0 var(--r-sm) var(--r-sm) 0;
    max-height: 22rem;
    overflow: auto;
    white-space: pre-wrap;
    font-size: var(--text-sm);
    line-height: 1.55;
    color: var(--text-2);
  }
  /* The same marking the file inspector uses, so a passage looks the same
     whichever surface opened it. */
  blockquote mark {
    background: var(--warn-soft, color-mix(in srgb, var(--accent) 22%, transparent));
    color: inherit;
    border-radius: 2px;
    padding: 0 0.1em;
  }
  .muted {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-3);
  }
  .truncation {
    margin-top: var(--space-2);
    font-size: var(--text-xs);
  }
</style>
