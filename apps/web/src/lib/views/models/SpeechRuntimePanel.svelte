<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import Icon from "../../components/Icon.svelte";
  import type { SpeechRuntimeSettings } from "../../apiTypes";

  let runtime = $state<SpeechRuntimeSettings | null>(null);
  let draft = $state("");
  /**
   * FIXED-85's rule, applied here: an address typed while the read was in
   * flight must survive it. The row renders before `load()` resolves — that is
   * what keeps the Local tab from flickering — so adopting the stored value
   * unconditionally would silently clear what the owner had already typed.
   */
  let typed = $state(false);
  let busy = $state(false);
  let notice = $state<string | null>(null);
  let problem = $state<string | null>(null);

  const REFUSAL: Record<string, string> = {
    speech_endpoint_not_local: "Only an address on this machine is accepted.",
    speech_runtime_unreachable: "Nothing answered there. Check the server is running.",
    speech_runtime_refused: "Something answered, but it does not serve transcription.",
    speech_runtime_not_configured: "Enter an address first.",
  };

  async function load() {
    try {
      const view = await api.speechRuntime();
      runtime = view.runtime;
      if (!typed) draft = view.runtime.endpoint;
    } catch {
      runtime = null;
    }
  }

  async function saveAndTest() {
    if (busy) return;
    busy = true;
    notice = null;
    problem = null;
    try {
      runtime = (await api.saveSpeechRuntime({ endpoint: draft.trim() })).runtime;
      typed = false;
      draft = runtime.endpoint;
      if (!runtime.endpoint) {
        notice = "Removed.";
        return;
      }
      const probe = await api.probeSpeechRuntime();
      if (probe.ok) notice = "Answered. Dictation can run on this device.";
      else problem = REFUSAL[probe.reason_code ?? ""] ?? "It did not answer.";
    } catch (error) {
      problem =
        error instanceof ApiError
          ? REFUSAL[error.reasonCode ?? ""] ?? "That could not be saved."
          : "That could not be saved.";
    } finally {
      busy = false;
    }
  }

  onMount(load);
</script>

<article class="runtime-row" aria-label="Speech runtime">
  <span class="row-logo"><Icon name="mic" size="lg" /></span>
  <div class="row-main">
    <div class="row-heading">
      <div>
        <h3>Speech</h3>
        <p>Transcribes dictation on this machine — <code>whisper-server</code> or any
          service serving <code>/v1/audio/transcriptions</code>.</p>
      </div>
      <span class="state" data-state={runtime?.configured ? "set" : "unset"}>
        {runtime?.configured ? "Configured" : "Not set up"}
      </span>
    </div>
    <div class="row-controls">
      <label>
        <input
          type="url"
          inputmode="url"
          placeholder="http://127.0.0.1:8910"
          bind:value={draft}
          oninput={() => (typed = true)}
          disabled={busy}
          aria-label="Speech runtime address"
        />
      </label>
      <button class="btn btn-sm" type="button" onclick={saveAndTest} disabled={busy}>
        {busy ? "Testing…" : "Save and test"}
      </button>
    </div>
    {#if problem}<p class="error" role="alert">{problem}</p>{/if}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
  </div>
</article>

<style>
  .runtime-row {
    display: flex; gap: 0.85rem; align-items: flex-start; padding: 0.9rem;
    border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface);
  }
  .row-logo { display: inline-flex; flex: 0 0 auto; color: var(--text-3); }
  .row-main { flex: 1; min-width: 0; }
  .row-heading { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
  h3 { margin: 0; font-size: 0.98rem; }
  .row-heading p { color: var(--text-3); font-size: 0.78rem; margin: 0.2rem 0 0; }
  .state { color: var(--text-3); font-size: 0.75rem; white-space: nowrap; }
  .state[data-state="set"] { color: var(--accent); }
  .row-controls { display: flex; gap: 0.5rem; align-items: center; margin-top: 0.7rem; }
  label { flex: 1; min-width: 0; }
  input {
    width: 100%; min-width: 0; padding: 0.45rem 0.5rem; border: 1px solid var(--border);
    border-radius: var(--r-sm); background: var(--surface-raised); color: var(--text-1);
  }
  .error, .notice { margin: 0.55rem 0 0; font-size: 0.78rem; }
  .error { color: var(--danger); }
  .notice { color: var(--text-2); }
  @media (max-width: 560px) {
    .row-heading { display: block; }
    .row-controls { flex-direction: column; align-items: stretch; }
  }
</style>
