<script lang="ts">
  import { onMount } from "svelte";
  import {
    audioSessionCoordinator,
    speechText,
    voicePlayback,
    type AudioSessionCoordinator,
    type SpeechLanguage,
    type VoicePlayback,
  } from "../voice";
  import Icon from "./Icon.svelte";

  let {
    responseId,
    text,
    language = "auto",
    playback = voicePlayback,
    coordinator = audioSessionCoordinator,
  }: {
    responseId: string;
    text: string;
    language?: SpeechLanguage;
    playback?: VoicePlayback;
    coordinator?: AudioSessionCoordinator;
  } = $props();

  const ownerId = $derived(`read-aloud-${responseId}`);
  let speaking = $state(false);
  let status = $state("");

  function reset() {
    speaking = false;
  }

  function stop() {
    if (!speaking) return;
    speaking = false;
    coordinator.release(ownerId);
  }

  function speak() {
    if (!playback.supported()) {
      status = "This device could not play the response.";
      return;
    }
    const readable = speechText(text);
    if (!readable) {
      status = "This response has no readable text.";
      return;
    }
    status = "";
    coordinator.startPlayback(
      ownerId,
      () => {
        speaking = true;
        playback.speak(responseId, readable, language, {
          end() {
            speaking = false;
            coordinator.release(ownerId);
          },
          error() {
            speaking = false;
            status = "This device could not play the response.";
            coordinator.release(ownerId);
          },
        });
      },
      () => playback.stop(),
    );
  }

  function toggle() {
    if (speaking) stop();
    else speak();
  }

  onMount(() => {
    const unsubscribe = coordinator.subscribe(ownerId, reset);
    return () => {
      unsubscribe();
      if (speaking) coordinator.release(ownerId);
    };
  });
</script>

<span class="read-aloud">
  <button
    type="button"
    class:active={speaking}
    aria-label={speaking ? "Stop speaking" : "Read aloud"}
    aria-pressed={speaking}
    title={speaking ? "Stop speaking" : "Read this response aloud"}
    onclick={toggle}
  >
    <Icon name={speaking ? "stop" : "volume"} size={14} />
  </button>
  {#if status}<span class="playback-status" role="status">{status}</span>{/if}
</span>

<style>
  .read-aloud { display: inline-flex; align-items: center; gap: 0.35rem; }
  button {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; padding: 0; border: 0; border-radius: var(--r-sm);
    background: transparent; color: var(--text-3); cursor: pointer;
  }
  button:hover, button.active { background: var(--accent-soft); color: var(--accent); }
  button:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
  .playback-status { color: var(--text-3); font-size: 0.68rem; line-height: 1.3; }
  @media print { .read-aloud { display: none; } }
</style>
