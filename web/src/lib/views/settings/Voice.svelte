<script lang="ts">
  /**
   * Settings › Voice — voice spec §6.2.
   *
   * Four sections: Engines (listening and speaking, each with its state, where
   * it runs, Test and Remove), Models (profile and Whisper tier, voice and
   * speed), Conversation (push to talk now; hands-free is Labs in beta), and
   * Resources (what voice holds, and the planner's sentence).
   *
   * Nothing here contacts a server or starts an engine until the owner presses
   * a button. A component the catalogue cannot offer yet is shown with the
   * reason, never hidden: "Speech recognition is not available yet — its files
   * are waiting for a verified digest" is a fact an owner can act on, and a
   * missing card is not.
   */
  import { onDestroy, onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { ModelOperationView, VoiceComponentView, VoiceStatus, VoiceTestResult } from "../../generated/apiContract";
  import { formatBytes } from "../../projectLifecycle";

  let status = $state<VoiceStatus | null>(null);
  let loadError = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  let operation = $state<ModelOperationView | null>(null);
  let test = $state<VoiceTestResult | null>(null);
  let confirmRemove = $state(false);
  let poll: ReturnType<typeof setInterval> | null = null;

  const STATE_LABELS: Record<string, string> = {
    off: "Off",
    not_installed: "Not installed",
    installed: "Installed — starts when used",
    ready: "Ready",
    paused: "Paused to save memory",
    unavailable: "Not available yet",
  };

  /** Reason codes, in the owner's words. */
  const REASONS: Record<string, string> = {
    voice_item_pending: "its files are waiting for a verified digest in Raiker's catalogue",
    voice_item_licence_unreviewed: "its licence has not been reviewed yet",
    voice_item_unverified: "it has no verified digest",
    voice_speaking_not_installed: "Install the speaking engine first.",
    voice_listening_not_installed: "Speech recognition is not installed, so the round trip could not be checked.",
    voice_kokoro_runtime_missing:
      "Kokoro's runtime (the kokoro-onnx package) is not part of this Raiker build yet. Choose Lite or the system voice.",
    voice_profile_does_not_fit: "This profile does not fit next to what is already running.",
    voice_profile_nothing_installable: "Nothing in this profile can be installed on this computer yet.",
    voice_off: "Choose a profile first.",
  };
  const reason = (code: string | null | undefined): string =>
    code ? (REASONS[code] ?? code.replaceAll("_", " ")) : "";

  async function load() {
    try {
      status = await api.voiceStatus();
      loadError = null;
    } catch (e) {
      loadError = e instanceof ApiError ? `Voice settings could not be read (${e.status}).` : "Voice settings could not be read.";
    }
  }

  async function act(label: string, run: () => Promise<void>) {
    busy = label;
    notice = null;
    try {
      await run();
    } catch (e) {
      notice = { kind: "error", text: e instanceof ApiError && e.reasonCode ? reason(e.reasonCode) : "Not done." };
    } finally {
      busy = null;
    }
  }

  const save = (change: Parameters<typeof api.saveVoiceSettings>[0]) =>
    act("save", async () => {
      status = await api.saveVoiceSettings(change);
    });

  function watch(operationId: string) {
    stopWatching();
    poll = setInterval(async () => {
      try {
        const listed = await api.modelOperations();
        const found = listed.items.find((item) => item.operation_id === operationId) ?? null;
        operation = found;
        if (!found || ["complete", "failed", "cancelled"].includes(found.state)) {
          stopWatching();
          if (found?.state === "failed") notice = { kind: "error", text: `Install failed: ${reason(found.error_code)}` };
          if (found?.state === "complete") notice = { kind: "ok", text: "Installed and verified." };
          await load();
        }
      } catch {
        // A failed read keeps the last progress; the next tick tries again.
      }
    }, 1500);
  }
  function stopWatching() {
    if (poll !== null) clearInterval(poll);
    poll = null;
  }

  const install = () =>
    act("install", async () => {
      operation = await api.installVoice();
      watch(operation.operation_id);
    });

  const runTest = () =>
    act("test", async () => {
      test = await api.testVoice();
    });

  const remove = () =>
    act("remove", async () => {
      const freed = await api.removeVoice();
      confirmRemove = false;
      notice = { kind: "ok", text: `Voice removed — ${formatBytes(freed.freed_bytes)} freed.` };
      await load();
    });

  let previewAudio: HTMLAudioElement | null = null;
  const preview = () =>
    act("preview", async () => {
      const clip = await api.speakVoice("Hello. This is how I sound on this computer.");
      previewAudio?.pause();
      previewAudio = new Audio(URL.createObjectURL(clip));
      await previewAudio.play();
    });

  const settings = $derived(status?.settings ?? null);
  const chosen = $derived(status?.profiles.find((p) => p.profile_id === settings?.profile) ?? null);
  const installedAnything = $derived((status?.disk_bytes ?? 0) > 0);
  const canInstall = $derived(
    !!status &&
      settings?.profile !== "off" &&
      [...status.listening.components, ...status.speaking.components].some((c) => c.installable && !c.installed),
  );
  const whisperTiers = $derived(
    (status?.listening.components ?? []).filter((c) => c.role === "whisper_model"),
  );

  function componentLine(component: VoiceComponentView): string {
    if (component.installed) return "Installed";
    if (component.refusal) return `Not available yet — ${reason(component.refusal)}`;
    return component.size_bytes ? `${formatBytes(component.size_bytes)} to download` : "To download";
  }

  onMount(load);
  onDestroy(() => {
    stopWatching();
    previewAudio?.pause();
  });
</script>

<header class="section-heading"><h2>Voice</h2></header>

{#if loadError}
  <p class="notice error" role="alert">{loadError}</p>
{:else if status === null || settings === null}
  <p class="description">Loading voice settings…</p>
{:else}
  <section class="settings-card" aria-labelledby="voice-profile-heading">
    <div class="card-heading"><h3 id="voice-profile-heading">Talk to Raiker</h3></div>
    <p class="description">
      Raiker can listen and answer aloud, entirely on this computer. Audio never leaves it. The model that
      thinks is still the one you choose for each conversation.
    </p>
    <fieldset class="profiles">
      <legend class="sr-only">Voice profile</legend>
      <label class="profile">
        <input type="radio" name="voice-profile" value="off" checked={settings.profile === "off"}
          disabled={busy !== null} onchange={() => save({ profile: "off" })} />
        <span><strong>Off</strong><span class="meta">Dictation uses a server you set up yourself, if any.</span></span>
      </label>
      {#each status.profiles as profile (profile.profile_id)}
        <label class="profile">
          <input type="radio" name="voice-profile" value={profile.profile_id}
            checked={settings.profile === profile.profile_id} disabled={busy !== null}
            onchange={() => save({ profile: profile.profile_id as "lite" | "balanced" | "high" })} />
          <span>
            <strong>{profile.name}</strong>
            {#if profile.recommended}<span class="tag">Recommended for this computer</span>{/if}
            <span class="meta">
              {formatBytes(profile.download_bytes)} · {profile.audience}
              {#if !profile.listening_available || !profile.speaking_available}
                · {!profile.listening_available && !profile.speaking_available
                  ? "not available yet"
                  : !profile.listening_available ? "speaking only for now" : "listening only for now"}
              {/if}
            </span>
          </span>
        </label>
      {/each}
    </fieldset>
    <p class="meta">{status.recommendation}</p>
  </section>

  {#if settings.profile !== "off"}
    <section class="settings-card" aria-labelledby="voice-engines-heading">
      <div class="card-heading"><h3 id="voice-engines-heading">Engines</h3></div>
      <div class="engines">
        <article class="engine" aria-label="Listening">
          <h4>Listening <span class="state" data-state={status.listening.state}>{STATE_LABELS[status.listening.state]}</span></h4>
          <ul>
            {#each status.listening.components as component (component.item_id)}
              <li><span>{component.name}</span><span class="meta">{componentLine(component)}</span></li>
            {/each}
          </ul>
          {#if status.listening.device}<p class="meta">Runs on {status.listening.device === "cpu" ? "the processor" : status.listening.device.toUpperCase()}</p>{/if}
        </article>
        <article class="engine" aria-label="Speaking">
          <h4>Speaking <span class="state" data-state={status.speaking.state}>{STATE_LABELS[status.speaking.state]}</span></h4>
          <ul>
            {#each status.speaking.components as component (component.item_id)}
              <li><span>{component.name}</span><span class="meta">{componentLine(component)}</span></li>
            {/each}
          </ul>
        </article>
      </div>
      {#if operation && !["complete", "failed", "cancelled"].includes(operation.state)}
        <p class="notice" role="status">
          Downloading and verifying{operation.progress_percent !== null ? ` — ${operation.progress_percent}%` : "…"}
        </p>
      {/if}
      <div class="actions">
        {#if canInstall}
          <button class="btn btn-primary" type="button" disabled={busy !== null} onclick={() => void install()}>
            {busy === "install" ? "Starting…" : "Install"}
          </button>
        {/if}
        <button class="btn btn-ghost" type="button" disabled={busy !== null || !installedAnything} onclick={() => void runTest()}>
          {busy === "test" ? "Testing…" : "Test"}
        </button>
        {#if installedAnything}
          {#if confirmRemove}
            <span class="confirm">Remove every voice file ({formatBytes(status.disk_bytes)})?</span>
            <button class="btn btn-danger btn-sm" type="button" disabled={busy !== null} onclick={() => void remove()}>Remove</button>
            <button class="btn btn-ghost btn-sm" type="button" onclick={() => (confirmRemove = false)}>Keep</button>
          {:else}
            <button class="btn btn-ghost" type="button" disabled={busy !== null} onclick={() => (confirmRemove = true)}>Remove</button>
          {/if}
        {/if}
      </div>
      {#if test}
        <p class="notice" role="status" data-testid="voice-test-result">
          {#if test.spoke && test.heard}
            Spoke and heard it back in {test.seconds}s — {Math.round((1 - (test.word_error_rate ?? 1)) * 100)}% of the words matched.
          {:else if test.spoke}
            Spoke a test phrase in {test.seconds}s. {reason(test.reason_code)}
          {:else}
            Could not speak: {reason(test.reason_code)}
          {/if}
        </p>
      {/if}
    </section>

    <section class="settings-card" aria-labelledby="voice-models-heading">
      <div class="card-heading"><h3 id="voice-models-heading">Models</h3></div>
      <label class="row">
        <span>Speech recognition</span>
        <select disabled={busy !== null || whisperTiers.length === 0}
          value={settings.whisper_model ?? ""}
          onchange={(e) => save({ whisper_model: (e.currentTarget as HTMLSelectElement).value || null })}>
          <option value="">Profile default</option>
          {#each whisperTiers as tier (tier.item_id)}<option value={tier.item_id}>{tier.name}</option>{/each}
        </select>
      </label>
      <label class="row check">
        <input type="checkbox" checked={settings.english_only} disabled={busy !== null}
          onchange={(e) => save({ english_only: (e.currentTarget as HTMLInputElement).checked })} />
        <span>English only (faster and more accurate for English)</span>
      </label>
      {#if status.speaking.voices.length > 0}
        <label class="row">
          <span>Voice</span>
          <select disabled={busy !== null} value={settings.voice ?? ""}
            onchange={(e) => save({ voice: (e.currentTarget as HTMLSelectElement).value || null })}>
            <option value="">Default</option>
            {#each status.speaking.voices as voice (voice)}<option value={voice}>{voice}</option>{/each}
          </select>
          <button class="btn btn-ghost btn-sm" type="button" aria-label="Preview this voice"
            disabled={busy !== null || status.speaking.state === "not_installed" || status.speaking.state === "unavailable"}
            onclick={() => void preview()}>▶ Preview</button>
        </label>
      {/if}
      <label class="row">
        <span>Speaking speed</span>
        <input type="range" min="0.5" max="2" step="0.1" value={settings.speed} disabled={busy !== null}
          aria-valuetext={`${settings.speed}×`}
          onchange={(e) => save({ speed: Number((e.currentTarget as HTMLInputElement).value) })} />
        <span class="meta">{settings.speed}×</span>
      </label>
    </section>

    <section class="settings-card" aria-labelledby="voice-conversation-heading">
      <div class="card-heading"><h3 id="voice-conversation-heading">Conversation</h3></div>
      <label class="row check">
        <input type="checkbox" checked={settings.conversation.labs_hands_free} disabled={busy !== null}
          onchange={(e) => save({ conversation: { labs_hands_free: (e.currentTarget as HTMLInputElement).checked } })} />
        <span>Hands-free conversation <span class="tag">Preview</span><span class="meta">Raiker listens for the end of your sentence instead of waiting for you to release the button.</span></span>
      </label>
      <label class="row">
        <span>End of speech after</span>
        <input type="range" min="250" max="1500" step="50" value={settings.conversation.end_silence_ms} disabled={busy !== null}
          aria-valuetext={`${settings.conversation.end_silence_ms} milliseconds`}
          onchange={(e) => save({ conversation: { end_silence_ms: Number((e.currentTarget as HTMLInputElement).value) } })} />
        <span class="meta">{settings.conversation.end_silence_ms} ms of silence</span>
      </label>
      <label class="row check">
        <input type="checkbox" checked={settings.conversation.barge_in} disabled={busy !== null}
          onchange={(e) => save({ conversation: { barge_in: (e.currentTarget as HTMLInputElement).checked } })} />
        <span>Interrupt Raiker when I speak</span>
      </label>
      <label class="row check">
        <input type="checkbox" checked={settings.conversation.speak_tool_progress} disabled={busy !== null}
          onchange={(e) => save({ conversation: { speak_tool_progress: (e.currentTarget as HTMLInputElement).checked } })} />
        <span>Say what Raiker is doing when a step takes a while</span>
      </label>
      <label class="row">
        <span>Stop engines after</span>
        <select value={String(settings.idle_unload_minutes)} disabled={busy !== null}
          onchange={(e) => save({ idle_unload_minutes: Number((e.currentTarget as HTMLSelectElement).value) })}>
          {#each [5, 10, 20, 30, 60] as minutes (minutes)}<option value={String(minutes)}>{minutes} minutes unused</option>{/each}
        </select>
      </label>
      <label class="row">
        <span>Run on</span>
        <select value={settings.run_on} disabled={busy !== null}
          onchange={(e) => save({ run_on: (e.currentTarget as HTMLSelectElement).value as "auto" | "cpu" | "gpu" })}>
          <option value="auto">Automatic</option>
          <option value="cpu">Processor only</option>
          <option value="gpu">Prefer the graphics card</option>
        </select>
      </label>
      <p class="meta">Recordings are never kept: each one is held in memory until it is transcribed.</p>
    </section>

    <section class="settings-card" aria-labelledby="voice-resources-heading">
      <div class="card-heading"><h3 id="voice-resources-heading">Resources</h3></div>
      <p class="description" data-testid="voice-plan">{status.plan.sentence}</p>
      {#if !status.plan.fits && status.plan.smaller_profile}
        <button class="btn btn-ghost btn-sm" type="button" disabled={busy !== null}
          onclick={() => save({ profile: status!.plan.smaller_profile as "lite" | "balanced" | "high" })}>
          Use {status.plan.smaller_profile} instead
        </button>
      {/if}
      <p class="meta">
        On disk: {formatBytes(status.disk_bytes)}{chosen ? ` · about ${formatBytes(chosen.memory_bytes)} of memory while talking` : ""}
      </p>
    </section>
  {/if}

  {#if notice}<p class="notice" class:error={notice.kind === "error"} role="status">{notice.text}</p>{/if}
{/if}

<style>
  .profiles { border: 0; padding: 0; margin: var(--space-3) 0 0; display: grid; gap: var(--space-2); }
  .profile { display: flex; gap: var(--space-3); align-items: flex-start; padding: var(--space-2) var(--space-3); border: 1px solid var(--border); border-radius: var(--r-md); cursor: pointer; }
  .profile > span { display: grid; gap: .15rem; }
  .meta { color: var(--text-3); font-size: var(--text-sm); }
  .tag { display: inline-block; margin-left: var(--space-2); font-size: var(--text-2xs); font-weight: 600; padding: .05rem .45rem; border-radius: var(--r-pill); border: 1px solid var(--border); color: var(--text-2); }
  .engines { display: grid; gap: var(--space-3); grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); }
  .engine { border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--space-3); }
  .engine h4 { margin: 0 0 var(--space-2); display: flex; justify-content: space-between; gap: var(--space-2); font-size: var(--text-base); }
  .engine ul { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-1); }
  .engine li { display: grid; gap: .1rem; font-size: var(--text-sm); }
  .state { font-weight: 500; font-size: var(--text-sm); color: var(--text-2); }
  .actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin-top: var(--space-3); }
  .confirm { font-size: var(--text-sm); }
  .row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2) var(--space-3); margin: var(--space-2) 0; }
  .row > span:first-child { min-width: 11rem; }
  .row.check > span { display: grid; gap: .1rem; }
  .notice.error { color: var(--danger); }
</style>
