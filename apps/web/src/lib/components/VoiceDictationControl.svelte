<script module lang="ts">
  export interface VoiceDictationHandle {
    done(): boolean;
    cancel(): boolean;
    active(): boolean;
  }

  /**
   * Keep the privacy note inside the window when it opens.
   *
   * The note is anchored to the info control, which sits a couple of buttons
   * into the composer. At 390px a 19rem panel starting there ends past the
   * right edge, so the sentence an owner opened the control to read was partly
   * off-screen. The width was already clamped to the viewport; what was missing
   * is that its *left* edge is not the viewport's. Measured on open rather than
   * guessed at, so it holds for both composers and at any width.
   */
  function keepDisclosureOnScreen(event: Event) {
    const details = event.currentTarget as HTMLDetailsElement;
    for (const note of details.querySelectorAll("p")) {
      note.style.transform = "";
      if (!details.open) continue;
      const box = note.getBoundingClientRect();
      const margin = 8;
      const past = box.right - (window.innerWidth - margin);
      const before = margin - box.left;
      const shift = past > 0 ? -past : before > 0 ? before : 0;
      if (shift !== 0) note.style.transform = `translateX(${Math.round(shift)}px)`;
    }
  }
</script>

<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import {
    audioSessionCoordinator,
    browserRecognitionAdapter,
    browserTranscriptionPorts,
    createLocalTranscriptionAdapter,
    type AudioSessionCoordinator,
    type RecognitionPhase,
    type SpeechLanguage,
    type VoiceRecognitionAdapter,
  } from "../voice";
  import Icon from "./Icon.svelte";

  let {
    draft,
    selectionStart = draft.length,
    selectionEnd = selectionStart,
    language = "auto",
    disabled = false,
    runtime = "browser",
    adapter = undefined,
    coordinator = audioSessionCoordinator,
    onchange,
    onfinalized = () => {},
    onrestored = () => {},
    onactivechange = () => {},
  }: {
    draft: string;
    selectionStart?: number;
    selectionEnd?: number;
    language?: SpeechLanguage;
    disabled?: boolean;
    /**
     * Which speech runtime dictation will use (BUG-256).
     *
     * A fact about this install, not a preference: `local` when the owner has
     * set a transcription runtime up on this machine, `browser` when they have
     * not. There is no third state and no switch — the button behaves the same
     * either way, and only the disclosure below it changes.
     */
    runtime?: "browser" | "local";
    /** Overridden in tests; otherwise chosen from `runtime`. */
    adapter?: VoiceRecognitionAdapter;
    coordinator?: AudioSessionCoordinator;
    onchange: (next: string, cursor: number) => void;
    onfinalized?: () => void;
    onrestored?: () => void;
    onactivechange?: (active: boolean) => void;
  } = $props();

  let listening = $state(false);
  let phase = $state<RecognitionPhase>("listening");
  let errorMessage = $state("");
  let snapshotDraft = "";
  let snapshotStart = 0;
  let snapshotEnd = 0;
  let finalized = "";
  let interim = "";
  const ownerId = `voice-dictation-${Math.random().toString(36).slice(2)}`;
  const disclosureId = `${ownerId}-disclosure`;
  const unavailableId = `${ownerId}-unavailable`;

  /**
   * The on-device runtime, built once and only when it is the one in use.
   *
   * It closes over `api.transcribeSpeech`, which is the only thing here that
   * leaves the page — and it goes to Raiker's own host, which forwards it to the
   * address the owner configured and nowhere else.
   */
  const localAdapter = createLocalTranscriptionAdapter(
    browserTranscriptionPorts((wav, chosen) =>
      api.transcribeSpeech(wav, chosen).then((result) => result.text),
    ),
  );

  const activeAdapter = $derived(
    adapter ?? (runtime === "local" ? localAdapter : browserRecognitionAdapter),
  );

  const supported = $derived(activeAdapter.supported());

  const disclosure = $derived(
    runtime === "local"
      ? "Audio is transcribed by the speech runtime on this machine. Raiker does not retain it."
      : "Raiker does not retain audio. Your browser's speech service may process audio externally.",
  );

  const unavailableReason = $derived(
    runtime === "local"
      ? "Dictation is unavailable because this browser cannot record audio. You can keep typing."
      : "Dictation is unavailable because this browser does not provide speech recognition. You can keep typing.",
  );

  function transcriptText(includeInterim: boolean) {
    return [finalized, includeInterim ? interim : ""].filter(Boolean).join(" ");
  }

  function composed(includeInterim: boolean) {
    const before = snapshotDraft.slice(0, snapshotStart);
    const after = snapshotDraft.slice(snapshotEnd);
    const transcript = transcriptText(includeInterim).trim();
    if (!transcript) return { value: before + after, cursor: before.length };
    const leftSpace = before.length > 0 && !/\s$/.test(before) ? " " : "";
    const rightSpace = after.length > 0 && !/^\s/.test(after) ? " " : "";
    const inserted = leftSpace + transcript;
    return {
      value: before + inserted + rightSpace + after,
      cursor: before.length + inserted.length,
    };
  }

  function updateDraft(includeInterim: boolean) {
    const next = composed(includeInterim);
    onchange(next.value, next.cursor);
  }

  function setListening(next: boolean) {
    if (listening === next) return;
    listening = next;
    onactivechange(next);
  }

  function preserveFinalized() {
    interim = "";
    updateDraft(false);
    setListening(false);
  }

  function start() {
    if (disabled || !supported || listening) return;
    errorMessage = "";
    snapshotDraft = draft;
    snapshotStart = Math.max(0, Math.min(selectionStart, draft.length));
    snapshotEnd = Math.max(snapshotStart, Math.min(selectionEnd, draft.length));
    finalized = "";
    interim = "";
    phase = "listening";
    // This callback deliberately precedes adapter.start: a synchronous fake or
    // browser callback must not make dictated text look like pre-existing text.
    setListening(true);
    try {
      coordinator.startRecognition(
        ownerId,
        () => activeAdapter.start(language, {
          interim(text) {
            interim = text.trim();
            updateDraft(true);
          },
          final(text) {
            const segment = text.trim();
            if (!segment) return;
            finalized = [finalized, segment].filter(Boolean).join(" ");
            interim = "";
            updateDraft(false);
            onfinalized();
          },
          end() {
            if (listening) preserveFinalized();
            // The on-device turn finishes here rather than in `done`, because
            // the transcript arrives after the recording stops. Releasing is
            // idempotent, so the browser path — which already released — is
            // unaffected.
            coordinator.release(ownerId);
          },
          phase(next) {
            phase = next;
          },
          error(code) {
            const restore = code === "not-allowed" || code === "audio-capture" || code === "no-speech";
            errorMessage = errorFor(code);
            coordinator.release(ownerId);
            if (restore) {
              onchange(snapshotDraft, snapshotStart);
              onrestored();
            }
            else preserveFinalized();
            setListening(false);
          },
        }),
        () => activeAdapter.abort(),
      );
    } catch {
      setListening(false);
      errorMessage = "Dictation could not start. You can keep typing and try again.";
    }
  }

  function errorFor(code: string) {
    if (code === "not-allowed") return "Allow microphone and speech-recognition access in your browser, then try again.";
    if (code === "audio-capture") return "No usable microphone was found. Check your device and try again.";
    if (code === "no-speech") return "No speech was recognized. Your original draft was restored.";
    // The reason codes the host returns for the on-device runtime. Each names
    // the thing the owner would have to change, rather than "transcription
    // failed" — which is true of all four and useful for none.
    if (code === "speech_runtime_not_configured") return "The speech runtime is no longer set up. Add one under Models → Local.";
    if (code === "speech_runtime_unreachable") return "The speech runtime on this machine did not answer. Check that it is running.";
    if (code === "speech_runtime_refused") return "The speech runtime refused the recording. Check that it serves transcription.";
    if (code === "speech_audio_too_large") return "That recording is too long to transcribe. Dictate in shorter passes.";
    if (code === "network") {
      return runtime === "local"
        ? "The speech runtime on this machine could not be reached. Finalized words were kept; you can keep typing."
        : "The browser speech service is unavailable. Finalized words were kept; you can keep typing.";
    }
    return "Dictation stopped unexpectedly. Finalized words were kept; you can keep typing.";
  }

  export function done() {
    if (!listening) return false;
    if (runtime === "local") {
      // The clip is only complete once recording stops, and the transcript
      // arrives afterwards through `final`. Releasing the coordinator here would
      // abort the recording that is about to be transcribed, so the turn is left
      // running until `end` or `error` reports how it went.
      phase = "transcribing";
      activeAdapter.stop();
      return true;
    }
    preserveFinalized();
    coordinator.release(ownerId);
    return true;
  }

  export function cancel() {
    if (!listening) return false;
    setListening(false);
    coordinator.release(ownerId);
    finalized = "";
    interim = "";
    onchange(snapshotDraft, snapshotStart);
    onrestored();
    return true;
  }

  export function active() {
    return listening;
  }

  onMount(() => {
    const unsubscribe = coordinator.subscribe(ownerId, () => preserveFinalized());
    return () => {
      unsubscribe();
      if (listening) {
        preserveFinalized();
        coordinator.release(ownerId);
      }
    };
  });
</script>

<div class="voice-control">
  {#if listening}
    <span class="listening" role="status"
      ><span class="live-dot"></span>{phase === "transcribing" ? "Transcribing…" : "Listening…"}</span
    >
    <button
      type="button"
      class="voice-button active"
      aria-label="Done dictating"
      disabled={phase === "transcribing"}
      onclick={done}
    >
      <Icon name="check" size={15} />
    </button>
    <button type="button" class="voice-button" aria-label="Cancel dictation" onclick={cancel}>
      <Icon name="x" size={15} />
    </button>
  {:else}
    <button
      type="button"
      class="voice-button"
      aria-label="Dictate"
      aria-describedby={supported ? disclosureId : `${unavailableId} ${disclosureId}`}
      title="Dictate into the editable prompt"
      disabled={disabled || !supported}
      onclick={start}
    >
      <Icon name="mic" size={15} />
    </button>
  {/if}

  <details class="voice-info" ontoggle={keepDisclosureOnScreen}>
    <summary aria-label="About dictation privacy"><Icon name="info" size={14} /></summary>
    <p id={disclosureId}>{disclosure}</p>
    {#if !supported}
      <p id={unavailableId}>{unavailableReason}</p>
    {/if}
  </details>
</div>

{#if errorMessage}
  <p class="voice-error" role="alert">{errorMessage}</p>
{/if}

<style>
  .voice-control { display: inline-flex; align-items: center; gap: 0.3rem; position: relative; }
  .voice-button {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; padding: 0; border: 1px solid var(--border);
    border-radius: 50%; background: var(--surface); color: var(--text-2); cursor: pointer;
  }
  .voice-button:hover:not(:disabled) { border-color: var(--accent-border); color: var(--accent); }
  .voice-button.active { border-color: var(--accent-border); background: var(--accent-soft); color: var(--accent); }
  .voice-button:disabled { opacity: 0.5; cursor: not-allowed; }
  .voice-button:focus-visible, summary:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
  .listening { display: inline-flex; align-items: center; gap: 0.3rem; color: var(--accent); font-size: 0.72rem; font-weight: 700; }
  .live-dot { width: 0.42rem; height: 0.42rem; border-radius: 50%; background: currentColor; animation: voice-pulse 1.2s ease-in-out infinite; }
  .voice-info { position: relative; }
  summary { display: inline-flex; color: var(--text-3); cursor: pointer; list-style: none; }
  summary::-webkit-details-marker { display: none; }
  .voice-info p {
    position: absolute; z-index: 6; left: 0; bottom: calc(100% + 0.45rem); width: min(19rem, calc(100vw - 2rem));
    margin: 0; padding: 0.55rem 0.65rem; border: 1px solid var(--neutral-border); border-radius: var(--r-sm);
    background: var(--surface); box-shadow: var(--shadow-2); color: var(--text-2); font-size: 0.68rem; line-height: 1.4;
  }
  .voice-info p + p { bottom: calc(100% + 4.8rem); }
  .voice-error { margin: 0.25rem 0 0; color: var(--danger); font-size: 0.7rem; line-height: 1.35; }
  @keyframes voice-pulse { 50% { opacity: 0.35; transform: scale(0.82); } }
  @media (prefers-reduced-motion: reduce) { .live-dot { animation: none; } }
  @media print { .voice-control, .voice-error { display: none; } }
</style>
