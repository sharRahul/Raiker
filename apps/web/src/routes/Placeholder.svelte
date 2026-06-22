<script lang="ts">
  let { title }: { title: string } = $props();
</script>

<h1 id="page-title">{title}</h1>
<p class="empty-state">
  Nothing here yet — this screen is a skeleton. It will be wired to the governed backend in a later
  milestone and will only ever show real runtime state (never fabricated data).
</p>

<style>
  .empty-state {
    max-width: 60ch;
    color: #9a9aa2;
    border: 1px dashed #33333a;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    background: #0e0e11;
  }
</style>
