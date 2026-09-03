<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import PageState from "../../components/PageState.svelte";
  import type { SpeechMode, SpeechRuntimeSettings } from "../../apiTypes";

  let { settings, save }: {
    settings: Record<string, unknown>;
    save: (p: Record<string, unknown>) => void;
  } = $props();

  const speechLanguage = $derived((settings["general.speech_language"] as string) ?? "auto");

  let runtime = $state<SpeechRuntimeSettings | null>(null);
  let loadError = $state<string | null>(null);
  let endpointDraft = $state("");
  let busy = $state(false);
  let notice = $state<string | null>(null);
  let problem = $state<string | null>(null);

  // Named for what the owner would have to change, not for what failed.
  const REFUSAL: Record<string, string> = {
    speech_endpoint_not_local:
      "That address is not on this machine. On-device dictation only accepts a loopback address such as http://127.0.0.1:8910.",
    speech_runtime_not_configured: "Enter the address of a transcription server first.",
    speech_runtime_unreachable: "Nothing answered at that address. Check the server is running.",
    speech_runtime_refused:
      "Something answered, but it does not serve transcription. Check the port.",
  };

  function refusal(error: unknown): string {
    if (error instanceof ApiError && error.reasonCode) {
      return REFUSAL[error.reasonCode] ?? "That could not be saved.";
    }
    return "That could not be saved.";
  }

  async function load() {
    try {
      loadError = null;
      const view = await api.speechRuntime();
      runtime = view.runtime;
      endpointDraft = view.runtime.endpoint;
    } catch (error) {
      loadError = error instanceof ApiError ? error.message : String(error);
    }
  }

  async function choose(mode: SpeechMode) {
    if (busy) return;
    busy = true;
    notice = null;
    problem = null;
    try {
      runtime = (await api.saveSpeechRuntime({ mode })).runtime;
    } catch (error) {
      problem = refusal(error);
    } finally {
      busy = false;
    }
  }

  async function saveRuntime(event: SubmitEvent) {
    event.preventDefault();
    if (busy) return;
    busy = true;
    notice = null;
    problem = null;
    try {
      runtime = (await api.saveSpeechRuntime({ endpoint: endpointDraft.trim() })).runtime;
      if (!runtime.endpoint) {
        notice = "Removed. Dictation uses your browser's speech service.";
        return;
      }
      const probe = await api.probeSpeechRuntime();
      notice = probe.ok
        ? "Saved. The runtime answered."
        : `Saved, but ${(REFUSAL[probe.reason_code ?? ""] ?? "it did not answer.").toLowerCase()}`;
    } catch (error) {
      problem = refusal(error);
    } finally {
      busy = false;
    }
  }
  onMount(load);
</script>

<header class="section-heading">
  <h2>Voice</h2>
  <p>Where your dictated audio is transcribed, and which language it is spoken in.</p>
</header>

{#if loadError}
  <PageState state="error" title="Couldn't load voice settings" detail={loadError} />
{:else if runtime === null}
  <PageState state="loading" title="Loading voice settings…" />
{:else}
  <section class="settings-card" aria-labelledby="speech-runtime">
    <div class="card-heading">
      <h3 id="speech-runtime">Where audio is transcribed</h3>
      <p>Nothing is contacted until you dictate.</p>
    </div>

    <div class="choices" role="radiogroup" aria-label="Where audio is transcribed">
      {#each [
        { id: "auto", label: "Automatic", detail: "Uses a local runtime when one is set up, otherwise your browser." },
        { id: "local", label: "On this device", detail: "Audio never leaves this machine." },
        { id: "browser", label: "Browser speech", detail: "Your browser's service may process audio externally." },
      ] as const as option (option.id)}
        <label class="choice" class:selected={runtime.mode === option.id}>
          <input
            type="radio"
            name="speech-mode"
            value={option.id}
            checked={runtime.mode === option.id}
            disabled={busy}
            onchange={() => choose(option.id)}
          />
          <span>
            <strong>{option.label}</strong>
            <small>{option.detail}</small>
          </span>
        </label>
      {/each}
    </div>

    <p class="verdict" role="status" data-effective={runtime.effective}>
      {#if runtime.effective === "local" && runtime.configured}
        Dictation runs on this device.
      {:else if runtime.effective === "local"}
        Dictation is off until you add a runtime below.
      {:else}
        Dictation uses your browser's speech service.
      {/if}
    </p>
  </section>

  <section class="settings-card" aria-labelledby="speech-server">
    <div class="card-heading">
      <h3 id="speech-server">Speech runtime</h3>
      <p>
        A transcription server on this machine — <code>whisper-server</code> or any
        service serving <code>/v1/audio/transcriptions</code>. Loopback addresses only.
      </p>
    </div>
    <form onsubmit={saveRuntime}>
      <label>
        <span>Address</span>
        <input
          type="url"
          inputmode="url"
          placeholder="http://127.0.0.1:8910"
          bind:value={endpointDraft}
          disabled={busy}
          aria-label="Speech runtime address"
        />
      </label>
      <div class="actions">
        <button class="btn btn-primary btn-sm" type="submit" disabled={busy}>
          {busy ? "Checking…" : "Save and test"}
        </button>
      </div>
    </form>
    {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
  </section>

  <section class="settings-card" aria-labelledby="speech-language">
    <div class="card-heading">
      <h3 id="speech-language">Language</h3>
      <p>Used for dictation and read-aloud in both Chat and Build.</p>
    </div>
    <label>
      <select
        aria-label="Speech language"
        value={speechLanguage}
        onchange={(e) => save({ "general.speech_language": e.currentTarget.value })}
      >
        <option value="auto">Auto (device language)</option>
        <option value="en">English</option>
        <option value="fr">Français</option>
        <option value="de">Deutsch</option>
        <option value="hi">हिन्दी</option>
        <option value="it">Italiano</option>
        <option value="ja">日本語</option>
        <option value="ko">한국어</option>
        <option value="pt">Português</option>
        <option value="ru">Русский</option>
        <option value="es">Español</option>
        <option value="tr">Türkçe</option>
        <option value="uk">Українська</option>
      </select>
    </label>
  </section>
{/if}

<style>
  .section-heading { margin-bottom: var(--space-4); }
  .section-heading h2, .card-heading h3 { margin: 0; }
  .section-heading p, .card-heading p { color: var(--text-2); margin: .3rem 0 0; }
  .settings-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-lg); padding: var(--card-pad-y) var(--card-pad-x);
    margin-bottom: var(--space-4);
  }
  .choices { display: grid; gap: .5rem; margin-top: var(--space-4); max-width: 34rem; }
  .choice {
    display: flex; gap: .6rem; align-items: flex-start; padding: .6rem .7rem;
    border: 1px solid var(--border); border-radius: var(--r-md); cursor: pointer;
  }
  .choice.selected { border-color: var(--accent-border); background: var(--accent-soft); }
  .choice span { display: grid; gap: .1rem; }
  .choice small { color: var(--text-2); }
  /* No width here on purpose. The full-width rule below is for the address
     field; when it applied to the radios too, each one stretched across a third
     of its row and pushed the option's text to the right of it. Setting `auto`
     instead was the other half of the same mistake — it overrode the shell's own
     control sizing and left a 13x24 target, under WCAG 2.2's 24px minimum on a
     phone. Leaving the property alone lets `app.css` size it. */
  .choice input { flex: 0 0 auto; margin-top: .2rem; }
  .verdict { margin: var(--space-4) 0 0; color: var(--text-2); font-size: .82rem; }
  form { display: grid; gap: .6rem; margin-top: var(--space-4); max-width: 34rem; }
  label { display: grid; gap: .3rem; font-weight: 650; }
  input[type="url"], select { width: 100%; }
  .actions { display: flex; justify-content: flex-end; }
  .problem { margin: .6rem 0 0; color: var(--danger); font-size: .82rem; }
  .notice { margin: .6rem 0 0; color: var(--text-2); font-size: .82rem; }
  @media (max-width: 560px) { .actions { justify-content: stretch; } .actions .btn { width: 100%; } }
</style>
