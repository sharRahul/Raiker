<script lang="ts">
  import Badge from "../lib/Badge.svelte";
  import { BADGE_VARIANTS } from "../lib/badges";
</script>

<h1 id="page-title">Home</h1>
<p class="lead">
  Mission control for a governed AI agent. This is the Milestone&nbsp;1 skeleton: navigation, the
  runtime status banner, the STOP switch, and the status-badge system. No backend is connected and
  no data here reflects a real runtime.
</p>

<section aria-labelledby="badges-h" class="card">
  <h2 id="badges-h">Status badges</h2>
  <p>Every risk/status state is shown by text and shape — never colour alone.</p>
  <div class="badge-gallery">
    {#each BADGE_VARIANTS as variant (variant)}
      <Badge {variant} />
    {/each}
  </div>
</section>

<style>
  .lead {
    max-width: 60ch;
    color: #c2c2c9;
  }
  .card {
    border: 1px solid #2a2a2e;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    background: #101013;
    margin-top: 1rem;
  }
  .badge-gallery {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
</style>
