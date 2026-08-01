<script lang="ts">
  import { renderMarkdown } from "../markdown";

  // The one supported caller of `renderMarkdown`. `{@html}` is safe here and
  // only here: the renderer escapes every run of source text *before* it emits
  // any tag, emits a closed tag set, and never copies an attribute out of the
  // source. See the module header in ../markdown.ts for the full argument.
  let { text, muted = false }: { text: string; muted?: boolean } = $props();
  const html = $derived(renderMarkdown(text));

  // BUG-23 — the copy action for rendered code blocks.
  //
  // `{@html}` output is inert markup, so the button the renderer emits has no
  // handler of its own. One delegated listener on the wrapper supplies it,
  // which keeps the renderer free of anything executable and means a block that
  // arrives mid-stream is operable the moment it renders.
  //
  // What is copied is the *code*, not the rendered spans: `textContent` on the
  // `<code>` element yields exactly the source the model wrote, highlighting
  // and all removed.
  let announcement = $state("");
  let announcementTimer: ReturnType<typeof setTimeout> | undefined;

  function announce(message: string) {
    announcement = message;
    clearTimeout(announcementTimer);
    // Cleared so a second copy of the same block re-announces rather than
    // leaving a stale "Copied" that no longer refers to anything.
    announcementTimer = setTimeout(() => (announcement = ""), 4000);
  }

  // The button ships all three glyphs and CSS picks one, so feedback is an
  // attribute flip rather than DOM the handler writes. The accessible name is
  // kept in step with the glyph — an icon-only control that silently changes
  // meaning is worse than a word.
  function setCopyState(button: HTMLElement, state: "idle" | "copied" | "failed") {
    button.setAttribute("data-copy-state", state);
    const label =
      state === "copied" ? "Copied" : state === "failed" ? "Copy failed" : "Copy code";
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);
  }

  async function onWrapperClick(event: MouseEvent) {
    const target = event.target as HTMLElement | null;
    const button = target?.closest?.("[data-md-copy]") as HTMLElement | null;
    if (button === null || button === undefined) return;
    const block = button.closest(".md-code")?.querySelector("code");
    const code = block?.textContent ?? "";
    try {
      await navigator.clipboard.writeText(code);
      setCopyState(button, "copied");
      announce("Code copied to the clipboard.");
      setTimeout(() => {
        if (button.isConnected) setCopyState(button, "idle");
      }, 2000);
    } catch {
      // A denied clipboard permission or an insecure origin. Say so — a copy
      // button that silently does nothing is worse than no copy button.
      setCopyState(button, "failed");
      announce("Could not copy — your browser blocked clipboard access.");
      setTimeout(() => {
        if (button.isConnected) setCopyState(button, "idle");
      }, 2500);
    }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="markdown" class:muted onclick={onWrapperClick}>
  <!-- eslint-disable-next-line svelte/no-at-html-tags -->
  {@html html}
</div>
<span class="sr-only" role="status" aria-live="polite">{announcement}</span>

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
  /* BUG-23 — the block header: what language this is, and how to take it. */
  .markdown :global(.md-code-head) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.2rem 0.35rem 0.2rem 0.6rem;
    border-bottom: 1px solid var(--border);
    background: var(--neutral-soft);
  }
  .markdown :global(.md-code-lang) {
    color: var(--text-3);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .markdown :global(.md-copy) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border: 1px solid transparent;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
    padding: 0;
  }
  /* Exactly one glyph is visible, chosen by the state the handler set. */
  .markdown :global(.md-copy .md-copy-glyph) { display: none; }
  .markdown :global(.md-copy[data-copy-state="idle"] .md-copy-glyph[data-state="idle"]),
  .markdown :global(.md-copy[data-copy-state="copied"] .md-copy-glyph[data-state="copied"]),
  .markdown :global(.md-copy[data-copy-state="failed"] .md-copy-glyph[data-state="failed"]) {
    display: block;
  }
  .markdown :global(.md-copy[data-copy-state="copied"]) { color: var(--ok); }
  .markdown :global(.md-copy[data-copy-state="failed"]) { color: var(--danger); }
  .markdown :global(.md-copy:hover) {
    border-color: var(--border-strong);
    color: var(--text-1);
  }
  /* Always focusable and always visible on focus: the action must be reachable
     by keyboard, not only by a mouse that happens to be over the block. */
  .markdown :global(.md-copy:focus-visible) {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
    color: var(--text-1);
  }

  /* Token colours. Both themes are served by the same variables the rest of
     the product uses, so highlighting follows a theme switch rather than
     pinning one palette. Under forced colours the spans drop back to system
     text — a high-contrast reader gets contrast, not our accent ramp. */
  .markdown :global(.tok-comment) { color: var(--text-3); font-style: italic; }
  .markdown :global(.tok-string) { color: var(--ok); }
  .markdown :global(.tok-keyword) { color: var(--accent); font-weight: 650; }
  .markdown :global(.tok-number) { color: var(--warn); }
  .markdown :global(.tok-type) { color: var(--text-1); font-weight: 600; }
  .markdown :global(.tok-punct) { color: var(--text-2); }
  @media (forced-colors: active) {
    .markdown :global(.tok-comment),
    .markdown :global(.tok-string),
    .markdown :global(.tok-keyword),
    .markdown :global(.tok-number),
    .markdown :global(.tok-type),
    .markdown :global(.tok-punct) {
      color: CanvasText;
      font-weight: inherit;
      font-style: normal;
    }
    .markdown :global(.md-copy) { border-color: ButtonBorder; color: ButtonText; }
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
