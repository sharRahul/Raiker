<script lang="ts">
  /**
   * QUI-A07 — one verdict, warning or recommended action.
   *
   * The tone is said in a word ("Verdict", "Warning", "Next step") and an
   * icon as well as a tint, so it never rests on colour alone.
   */
  import Icon from "./Icon.svelte";
  import { calloutLead } from "../answerBlocks";

  let { tone = "verdict", text }: { tone?: string; text: string } = $props();

  const icon = $derived(tone === "warning" ? "warning" : tone === "action" ? "chevron-right" : "check");
</script>

<aside class="callout" data-tone={tone}>
  <Icon name={icon} size="md" />
  <p><strong>{calloutLead(tone)}.</strong> {text}</p>
</aside>

<style>
  .callout {
    display: flex;
    gap: var(--space-2);
    align-items: flex-start;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--accent-border);
    border-inline-start-width: 3px;
    border-radius: var(--r-md);
    background: var(--accent-soft);
    color: var(--accent-strong);
  }
  .callout[data-tone="warning"] { border-color: var(--warn-border); background: var(--warn-soft); color: var(--warn); }
  .callout[data-tone="action"] { border-color: var(--info-border); background: var(--info-soft); color: var(--info); }
  p { margin: 0; color: var(--text-1); }
  strong { color: inherit; }
  .callout[data-tone] strong { color: var(--text-1); }
</style>
