<script lang="ts">
  // Test-only harness: SidePanel takes snippets, which a component test cannot
  // supply directly. This wraps it with fixed content so the behaviour under
  // test is the panel's, not the caller's.
  import SidePanel from "./SidePanel.svelte";

  let { open = true, onclose = () => {} }: { open?: boolean; onclose?: () => void } = $props();
</script>

<SidePanel {open} title="Model detail" subtitle="local-default" {onclose}>
  <p>Panel body</p>
  {#snippet footer()}
    <button type="button">Panel action</button>
  {/snippet}
</SidePanel>
