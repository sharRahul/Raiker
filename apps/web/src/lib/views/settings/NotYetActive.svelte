<script lang="ts">
  // Honest placeholder: a control the runtime does not back yet. It is shown so
  // the taxonomy is complete, but it never claims to do something it cannot.
  let { what }: { what: string } = $props();
</script>

<p class="not-yet" role="note">
  <strong>Not yet active.</strong>
  {what} is not implemented in this local runtime yet, so it fails closed rather than pretending to work.
</p>

<style>
  .not-yet {
    padding: var(--space-2) var(--space-3);
    border: 1px dashed var(--border);
    border-radius: var(--radius-2);
    color: var(--text-2);
    background: var(--bg-2);
  }
</style>
