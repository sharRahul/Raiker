<script module lang="ts">
  export interface VoiceDictationHandle {
    done(): boolean;
    cancel(): boolean;
    active(): boolean;
  }
</script>

<script lang="ts">
  import { onMount } from "svelte";
  import {
    audioSessionCoordinator,
    browserRecognitionAdapter,
    type AudioSessionCoordinator,
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
    adapter = browserRecognitionAdapter,
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
    adapter?: VoiceRecognitionAdapter;
    coordinator?: AudioSessionCoordinator;
    onchange: (next: string, cursor: number) => void;
    onfinalized?: () => void;
    onrestored?: () => void;
    onactivechange?: (active: boolean) => void;
  } = $props();

  let listening = $state(false);
  let errorMessage = $state("");
  let snapshotDraft = "";
  let snapshotStart = 0;
  let snapshotEnd = 0;
  let finalized = "";
  let interim = "";
  const ownerId = `voice-dictation-${Math.random().toString(36).slice(2)}`;
  const disclosureId = `${ownerId}-disclosure`;
  const unavailableId = `${ownerId}-unavailable`;

  const supported = $derived(adapter.supported());

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
    // This callback deliberately precedes adapter.start: a synchronous fake or
    // browser callback must not make dictated text look like pre-existing text.
    setListening(true);
    try {
      coordinator.startRecognition(
        ownerId,
        () => adapter.start(language, {
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
        () => adapter.abort(),
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
    if (code === "network") return "The browser speech service is unavailable. Finalized words were kept; you can keep typing.";
    return "Dictation stopped unexpectedly. Finalized words were kept; you can keep typing.";
  }

  export function done() {
    if (!listening) return false;
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
    <span class="listening" role="status"><span class="live-dot"></span>Listening…</span>
    <button type="button" class="voice-button active" aria-label="Done dictating" onclick={done}>
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

  <details class="voice-info">
    <summary aria-label="About dictation privacy"><Icon name="info" size={14} /></summary>
    <p id={disclosureId}>Raiker does not retain audio. Your browser's speech service may process audio externally.</p>
    {#if !supported}
      <p id={unavailableId}>Dictation is unavailable because this browser does not provide speech recognition. You can keep typing.</p>
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
  .voice-error { margin: 0.25rem 0 0; color: var(--danger, #b42318); font-size: 0.7rem; line-height: 1.35; }
  @keyframes voice-pulse { 50% { opacity: 0.35; transform: scale(0.82); } }
  @media (prefers-reduced-motion: reduce) { .live-dot { animation: none; } }
  @media print { .voice-control, .voice-error { display: none; } }
</style>
