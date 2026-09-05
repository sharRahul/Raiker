<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { CredentialDeltaView } from "../apiTypes";

  let { runId, profileId }: { runId: string; profileId: string } = $props();
  let delta = $state<CredentialDeltaView | null>(null);
  let busy = $state(false);
  let message = $state<string | null>(null);

  async function load() {
    try {
      const view = await api.credentialDeltas(profileId);
      delta = view.deltas.find((item) => item.run_id === runId) ?? null;
    } catch { delta = null; }
  }

  async function discard() {
    if (!window.confirm("Discard every file change from this credentialed worker?")) return;
    busy = true; message = null;
    try {
      await api.discardCredentialDelta(runId, crypto.randomUUID());
      delta = null;
      message = "Credentialed worker changes discarded.";
    } catch { message = "The quarantined changes could not be discarded."; }
    finally { busy = false; }
  }

  onMount(load);
</script>

{#if delta}
  <section class="delta-review" aria-labelledby={`delta-${runId}`}>
    <strong id={`delta-${runId}`}>Credential delta · {delta.state}</strong>
    <p>The disposable container is a credential recipient. Its changes are isolated from the standing environment until review.</p>
    <dl>
      <div><dt>Paths</dt><dd>{delta.manifest.files.length}</dd></div>
      <div><dt>First scan</dt><dd><code>{delta.scan_digest.slice(0, 12)}</code></dd></div>
      <div><dt>Cleanup</dt><dd>{delta.cleanup_status.replaceAll("_", " ")}</dd></div>
    </dl>
    {#if delta.manifest.files.length}
      <ul>{#each delta.manifest.files as file}<li><code>{file.path}</code> · {file.kind}</li>{/each}</ul>
    {/if}
    <p class="warning">Matched bytes, credential values, and internal overlay paths are never shown. Quarantined changes are discard-only.</p>
    <button class="btn btn-danger btn-sm" type="button" disabled={busy} onclick={() => void discard()}>Discard quarantined changes</button>
  </section>
{/if}
{#if message}<p class="delta-message" role="status">{message}</p>{/if}

<style>
  .delta-review { display:grid; gap:.45rem; margin-top:.55rem; padding:.65rem; border:1px solid color-mix(in srgb,var(--warn) 45%,var(--border)); border-radius:var(--r-md); background:color-mix(in srgb,var(--warn) 5%,transparent); font-size:var(--text-2xs); }
  .delta-review p { margin:0; color:var(--text-2); }
  .delta-review dl { display:flex; flex-wrap:wrap; gap:.8rem; margin:0; }
  .delta-review dt { color:var(--text-3); font-size:var(--text-2xs); text-transform:uppercase; }
  .delta-review dd { margin:0; }
  .delta-review ul { max-height:7rem; overflow:auto; margin:0; padding-left:1.1rem; }
  .delta-review .warning { color:var(--warn); }
  .delta-review button { justify-self:start; }
  .delta-message { margin:.55rem 0 0; color:var(--text-2); font-size:var(--text-2xs); }
</style>
