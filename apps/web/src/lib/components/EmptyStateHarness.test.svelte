<script lang="ts">
  /**
   * A snippet cannot be passed through `render(Component, props)`, so the
   * action case needs a component to declare one. This is that component and
   * nothing else.
   */
  import EmptyState from "./EmptyState.svelte";

  let { title, body = null, actionLabel }: {
    title: string;
    body?: string | null;
    actionLabel: string;
  } = $props();
</script>

<EmptyState {title} {body}>
  {#snippet action()}
    <button type="button" class="btn btn-primary">{actionLabel}</button>
  {/snippet}
</EmptyState>
