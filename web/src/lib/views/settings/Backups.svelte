<script lang="ts">
  /*
   * Settings › Backups — the copies Raiker makes of this workspace, and
   * restoring one somewhere new. It was a card at the foot of General, under
   * the account; a backup is a decision about your data, so it sits with
   * Privacy and Security now, and the backup reminder links straight here.
   */
  import BackupsCard from "../../components/BackupsCard.svelte";
</script>

<header class="section-heading">
  <h2>Backups</h2>
</header>

<BackupsCard />

<style>
  .section-heading { margin-bottom: var(--space-3); }
  .section-heading h2 { margin: 0; }
</style>
