<script lang="ts">
  import Composer from "./Composer.svelte";
  let { dropActive = false, contextWarning = null }: { dropActive?: boolean; contextWarning?: string | null } = $props();
  let value = $state("");
</script>
<Composer ariaLabel="Test composer" inputId="test-prompt" bind:value {dropActive} {contextWarning} onsubmit={() => {}}>
  {#snippet left()}{/snippet}
  {#snippet right()}{/snippet}
</Composer>
