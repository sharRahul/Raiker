<script lang="ts">
  import Composer from "./Composer.svelte";
  let value = $state("");
</script>
<Composer ariaLabel="Test composer" inputId="test-prompt" bind:value onsubmit={() => {}}>
  {#snippet left()}{/snippet}
  {#snippet right()}{/snippet}
</Composer>
