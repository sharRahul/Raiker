<script lang="ts">
  import NotYetActive from "./NotYetActive.svelte";
</script>

<h2>Voice</h2>

<section class="card">
  <h3>Audio devices</h3>
  <NotYetActive what="Input/output device selection" />
</section>
<section class="card">
  <h3>Speech-to-text</h3>
  <NotYetActive what="Speech-to-text sensitivity" />
</section>
<section class="card">
  <h3>Voice profile</h3>
  <NotYetActive what="Voice profile options (no voice runtime exists yet)" />
</section>
