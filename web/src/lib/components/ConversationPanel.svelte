<script lang="ts">
  /**
   * Voice spec §8.2 — the conversation panel (Preview).
   *
   * Docks over the chat so the transcript stays readable. One status orb with
   * five states, each a distinct shape *and* words (never colour alone), live
   * captions, and the controls: Talk (hold, or hold Space), Mute, Stop talking
   * (or press any key while Raiker speaks), End. The privacy line says where
   * the words go. Orb states are announced politely for screen readers.
   */
  import { onDestroy, onMount, untrack } from "svelte";
  import { Conversation, ORB_LABELS, type ConversationPorts } from "../speech/conversation.svelte";

  let {
    ports,
    handsFree = false,
    bargeIn = true,
    endSilenceMs = 500,
    privacyLine,
    onClose = () => {},
    conversation = $bindable(null),
  }: {
    ports: ConversationPorts;
    handsFree?: boolean;
    bargeIn?: boolean;
    endSilenceMs?: number;
    privacyLine: string;
    onClose?: () => void;
    conversation?: Conversation | null;
  } = $props();

  // One conversation per panel, configured as it opens: a setting changed in
  // Settings applies to the next conversation, not halfway through this one.
  const session = untrack(() => new Conversation(ports, { handsFree, bargeIn, endSilenceMs }));
  conversation = session;
  let talkHeld = false;

  function press() {
    if (talkHeld) return;
    talkHeld = true;
    session.pressTalk();
  }
  function release() {
    if (!talkHeld) return;
    talkHeld = false;
    session.releaseTalk();
  }
  function end() {
    session.end();
    onClose();
  }

  function onKeyDown(event: KeyboardEvent) {
    const target = event.target as HTMLElement | null;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
    if (event.key === "Escape") {
      event.preventDefault();
      end();
      return;
    }
    if (session.state === "speaking" && event.key !== " ") {
      session.stopTalking();
      return;
    }
    if (event.key === " " && !handsFree) {
      event.preventDefault();
      press();
    }
  }
  function onKeyUp(event: KeyboardEvent) {
    if (event.key === " " && !handsFree) {
      event.preventDefault();
      release();
    }
  }

  onMount(() => {
    void session.start();
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    // §9 — the microphone is released when the page is hidden.
    const hidden = () => {
      if (document.visibilityState === "hidden") end();
    };
    document.addEventListener("visibilitychange", hidden);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      document.removeEventListener("visibilitychange", hidden);
    };
  });
  onDestroy(() => session.end());

  const lastCaptions = $derived(session.captions.slice(-4));
</script>

<section class="conversation" aria-label="Voice conversation">
  <header>
    <strong>Conversation</strong>
    <span class="preview">Preview</span>
  </header>
  <div class="orb-row">
    <span class="orb" data-state={session.state} style:--level={Math.min(1, session.level * 8)} aria-hidden="true"></span>
    <p class="orb-label" role="status" aria-live="polite">{ORB_LABELS[session.state]}{session.muted ? " · muted" : ""}</p>
  </div>
  {#if session.error}<p class="error" role="alert">{session.error}</p>{/if}
  <ol class="captions" aria-label="Captions">
    {#each lastCaptions as caption (caption.id)}
      <li class={caption.who}><span class="who">{caption.who === "owner" ? "You" : "Raiker"}</span> {caption.text || "…"}</li>
    {/each}
  </ol>
  <div class="controls">
    {#if !handsFree}
      <button type="button" class="btn btn-primary talk" disabled={!session.active || session.muted}
        aria-label="Hold to talk (or hold Space)"
        onpointerdown={press} onpointerup={release} onpointerleave={release} onpointercancel={release}
        onkeydown={(e) => { if (e.key === "Enter") press(); }} onkeyup={(e) => { if (e.key === "Enter") release(); }}
      >{session.state === "hearing" ? "Release to send" : "Hold to talk"}</button>
    {/if}
    <button type="button" class="btn btn-ghost" aria-pressed={session.muted} onclick={() => session.setMuted(!session.muted)}>
      {session.muted ? "Unmute" : "Mute"}
    </button>
    <button type="button" class="btn btn-ghost" disabled={session.state !== "speaking" && session.state !== "thinking"}
      onclick={() => session.stopTalking()}>Stop talking</button>
    {#if session.state === "paused"}
      <button type="button" class="btn btn-ghost" onclick={() => session.resume()}>Continue</button>
    {/if}
    <button type="button" class="btn btn-ghost" onclick={end}>End</button>
  </div>
  <p class="privacy">{privacyLine}</p>
</section>

<style>
  .conversation { position: sticky; bottom: var(--space-3); z-index: var(--z-popover); margin: 0 auto var(--space-3); width: min(36rem, 100%); display: grid; gap: var(--space-2); padding: var(--space-3) var(--space-4); border: 1px solid var(--border); border-radius: var(--r-lg); background: var(--raised); box-shadow: var(--shadow-2); }
  header { display: flex; align-items: center; gap: var(--space-2); }
  .preview { font-size: var(--text-2xs); font-weight: 600; padding: .05rem .45rem; border-radius: var(--r-pill); border: 1px solid var(--border); color: var(--text-2); }
  .orb-row { display: flex; align-items: center; gap: var(--space-3); }
  .orb-label { margin: 0; font-weight: 600; }
  /* Five states, five shapes: a ring, a ring that follows your voice, three
     dots, a filled disc that follows Raiker's voice, and two bars. */
  .orb { --level: 0; width: 2.25rem; height: 2.25rem; border-radius: 50%; border: 3px solid var(--accent); flex: none; }
  .orb[data-state="idle"] { border-color: var(--border); }
  .orb[data-state="listening"] { animation: pulse 2.4s ease-in-out infinite; }
  .orb[data-state="hearing"] { transform: scale(calc(1 + var(--level) * .35)); }
  .orb[data-state="thinking"] { border-style: dotted; animation: spin 2s linear infinite; }
  .orb[data-state="speaking"] { background: var(--accent); }
  .orb[data-state="paused"] { border-radius: var(--r-sm); border-style: double; }
  @keyframes pulse { 50% { transform: scale(1.12); } }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .orb { animation: none !important; transform: none !important; } }
  .captions { list-style: none; margin: 0; padding: 0; display: grid; gap: .3rem; max-height: 9rem; overflow: auto; font-size: var(--text-sm); }
  .captions .who { font-weight: 600; color: var(--text-2); margin-right: .3rem; }
  .controls { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .talk { touch-action: none; user-select: none; }
  .privacy { margin: 0; color: var(--text-3); font-size: var(--text-xs); }
  .error { margin: 0; color: var(--danger); font-size: var(--text-sm); }
</style>
