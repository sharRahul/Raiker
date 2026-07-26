<script lang="ts">
  import { renderMarkdown } from "../markdown";

  // The one supported caller of `renderMarkdown`. `{@html}` is safe here and
  // only here: the renderer escapes every run of source text *before* it emits
  // any tag, emits a closed tag set, and never copies an attribute out of the
  // source. See the module header in ../markdown.ts for the full argument.
  let { text, muted = false }: { text: string; muted?: boolean } = $props();
  const html = $derived(renderMarkdown(text));
</script>

<div class="markdown" class:muted>
  <!-- eslint-disable-next-line svelte/no-at-html-tags -->
  {@html html}
</div>

<style>
  .markdown {
    overflow-wrap: anywhere;
  }
  .muted {
    color: var(--text-3);
  }

  /* `{@html}` output is not compiled by Svelte, so every rule below has to be
     :global(). Scoping stays intact because each selector is nested under
     .markdown, which is a scoped class on the wrapper. */
  .markdown :global(> :first-child) {
    margin-top: 0;
  }
  .markdown :global(> :last-child) {
    margin-bottom: 0;
  }
  .markdown :global(p) {
    margin: 0 0 0.6rem;
    white-space: pre-wrap;
  }
  .markdown :global(h1),
  .markdown :global(h2),
  .markdown :global(h3),
  .markdown :global(h4),
  .markdown :global(h5),
  .markdown :global(h6) {
    margin: 1rem 0 0.45rem;
    font-weight: 700;
    line-height: 1.25;
  }
  .markdown :global(h1) {
    font-size: 1.28rem;
  }
  .markdown :global(h2) {
    font-size: 1.14rem;
  }
  .markdown :global(h3) {
    font-size: 1.02rem;
  }
  .markdown :global(h4),
  .markdown :global(h5),
  .markdown :global(h6) {
    font-size: 0.94rem;
  }
  .markdown :global(ul),
  .markdown :global(ol) {
    margin: 0 0 0.6rem;
    padding-left: 1.35rem;
  }
  .markdown :global(li) {
    margin: 0.2rem 0;
  }
  .markdown :global(li > ul),
  .markdown :global(li > ol) {
    margin: 0.2rem 0 0;
  }
  .markdown :global(blockquote) {
    margin: 0 0 0.6rem;
    padding: 0.1rem 0 0.1rem 0.75rem;
    border-left: 3px solid var(--border-strong);
    color: var(--text-2);
  }
  .markdown :global(hr) {
    margin: 0.9rem 0;
    border: 0;
    border-top: 1px solid var(--border);
  }
  .markdown :global(a) {
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .markdown :global(code) {
    font-family: var(--font-mono);
    font-size: 0.86em;
    background: var(--neutral-soft);
    border: 1px solid var(--neutral-border);
    border-radius: 4px;
    padding: 0.06em 0.3em;
  }

  /* Fenced code: its own surface, horizontally scrollable so a long line
     never widens the transcript. */
  .markdown :global(.md-code) {
    position: relative;
    margin: 0 0 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg);
    overflow: hidden;
  }
  .markdown :global(.md-code-lang) {
    display: block;
    padding: 0.25rem 0.6rem;
    border-bottom: 1px solid var(--border);
    background: var(--neutral-soft);
    color: var(--text-3);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .markdown :global(pre) {
    margin: 0;
    padding: 0.65rem 0.75rem;
    overflow-x: auto;
  }
  .markdown :global(pre code) {
    display: block;
    padding: 0;
    border: 0;
    background: none;
    font-size: 0.82rem;
    line-height: 1.5;
    white-space: pre;
  }

  /* Tables scroll inside their own container for the same reason. */
  .markdown :global(.md-table) {
    margin: 0 0 0.6rem;
    overflow-x: auto;
  }
  .markdown :global(table) {
    border-collapse: collapse;
    font-size: 0.86rem;
  }
  .markdown :global(th),
  .markdown :global(td) {
    border: 1px solid var(--border);
    padding: 0.32rem 0.6rem;
    text-align: left;
    vertical-align: top;
  }
  .markdown :global(th) {
    background: var(--neutral-soft);
    font-weight: 650;
  }
  .markdown :global(.md-align-center) {
    text-align: center;
  }
  .markdown :global(.md-align-right) {
    text-align: right;
  }
  .markdown :global(.md-align-left) {
    text-align: left;
  }
</style>
