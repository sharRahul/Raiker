<script lang="ts">
  /**
   * QUI-F01 — Quick Entry: one input and a "send to" picker.
   *
   * Opened by Ctrl/Cmd+Shift+Space from anywhere on the computer, in a small
   * window of its own (`desktop/src/main.ts`). It is a page of the same origin,
   * so it sends through the same governed routes as the rest of Raiker:
   *
   * * **New task** files the message as a task that starts now — the same
   *   `POST /api/tasks` Chat's *Run in background* uses (QUI-C11). It shows in
   *   the top bar's live work line, Background work and Home.
   * * **A recent conversation** sends it there as the owner's next message.
   *
   * Sending hides the window at once and never brings the main window
   * forward. Esc hides it. If sending fails, the window comes back with the
   * message kept and the reason said.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type { SessionSummary } from "../apiTypes";
  import { desktopBridge } from "../desktopShell";
  import { newIdempotencyKey } from "../idempotency";

  let text = $state("");
  let target = $state("new");
  let recent = $state<SessionSummary[]>([]);
  let problem = $state<string | null>(null);
  let sending = $state(false);
  let input = $state<HTMLInputElement>();
  let key = newIdempotencyKey();

  onMount(() => {
    input?.focus();
    void api
      .sessions(undefined, false, "chat")
      .then((sessions) => {
        recent = [...sessions].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5);
      })
      .catch(() => (recent = []));
    // The shell shows this window again on the next shortcut: put the caret back.
    const refocus = () => input?.focus();
    window.addEventListener("focus", refocus);
    return () => window.removeEventListener("focus", refocus);
  });

  function hide() {
    const bridge = desktopBridge();
    if (bridge?.closeWindow) bridge.closeWindow();
    else window.location.hash = "#/home";
  }

  async function send() {
    const message = text.trim();
    if (message === "" || sending) return;
    sending = true;
    problem = null;
    hide();
    try {
      if (target === "new") {
        const firstLine = message.split("\n")[0];
        await api.createTask(
          { title: firstLine.length > 80 ? `${firstLine.slice(0, 79)}…` : firstLine, description: message, surface: "chat" },
          key,
        );
        key = newIdempotencyKey();
      } else {
        await api.submitPrompt({ text: message, session_id: target, surface: "chat" });
      }
      text = "";
    } catch (error) {
      problem =
        error instanceof ApiError && error.reasonCode === "model_not_ready"
          ? "No model is ready, so nothing was sent. Your message is kept."
          : "It was not sent. Your message is kept; try again.";
      desktopBridge()?.focusWindow();
    } finally {
      sending = false;
    }
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      hide();
    } else if (event.key === "Enter" && !event.isComposing) {
      event.preventDefault();
      void send();
    }
  }
</script>

<svelte:window onkeydown={(event) => event.key === "Escape" && hide()} />

<form class="quick-entry" aria-label="Quick Entry" onsubmit={(event) => { event.preventDefault(); void send(); }}>
  <input
    bind:this={input}
    bind:value={text}
    class="message"
    type="text"
    aria-label="Ask Raiker"
    placeholder="Ask Raiker…"
    autocomplete="off"
    onkeydown={onKeydown}
  />
  <div class="row">
    <label class="send-to">
      <span>Send to</span>
      <select bind:value={target} aria-label="Send to">
        <option value="new">New task</option>
        {#each recent as session (session.session_id)}
          <option value={session.session_id}>{session.title || "Untitled conversation"}</option>
        {/each}
      </select>
    </label>
    {#if problem}<span class="problem" role="alert">{problem}</span>{:else}<span class="hint">Enter sends · Esc closes</span>{/if}
    <button type="submit" class="btn btn-primary btn-sm" disabled={text.trim() === "" || sending}>Send</button>
  </div>
</form>

<style>
  .quick-entry{height:100vh;box-sizing:border-box;display:grid;grid-template-rows:1fr auto;gap:var(--space-2);padding:var(--space-3) var(--space-4);background:var(--surface);border:1px solid var(--border);-webkit-app-region:drag}
  .message,.row select,.row button{-webkit-app-region:no-drag}
  .message{width:100%;border:0;background:transparent;color:var(--text-1);font:inherit;font-size:var(--text-md);outline:none}
  .row{display:flex;align-items:center;gap:var(--space-3)}
  .send-to{display:flex;align-items:center;gap:var(--space-2);font-size:var(--text-xs);color:var(--text-3)}
  .send-to select{max-width:16rem;font:inherit;font-size:var(--text-sm);color:var(--text-1);background:var(--sunken);border:1px solid var(--border);border-radius:var(--r-sm);padding:.15rem .4rem}
  .hint{margin-left:auto;font-size:var(--text-xs);color:var(--text-3)}
  .problem{margin-left:auto;font-size:var(--text-xs);color:var(--danger)}
</style>
