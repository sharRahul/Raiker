<script lang="ts">
  import ChatTurnTimeline from "../lib/ChatTurnTimeline.svelte";
  import { ApiError, streamPrompt } from "../lib/api";
  import type { AgentResponse, StreamEvent } from "../lib/apiTypes";

  let promptText = $state("");
  let events = $state<StreamEvent[]>([]);
  let finalResponse = $state<AgentResponse | null>(null);
  let streaming = $state(false);
  let error = $state<string | null>(null);
  // Reuse one session across turns so the governed conversation stays continuous.
  let sessionId = $state<string | null>(null);
  let hasSubmitted = $state(false);

  async function submit() {
    const text = promptText.trim();
    if (text === "" || streaming) return;
    hasSubmitted = true;
    error = null;
    events = [];
    finalResponse = null;
    streaming = true;
    try {
      await streamPrompt(
        { text, session_id: sessionId ?? undefined },
        (event) => {
          if (event.kind === "final" && event.response !== null) {
            finalResponse = event.response;
            sessionId = event.response.session_id;
          } else {
            // Reassign for Svelte 5 reactivity.
            events = [...events, event];
          }
        },
      );
    } catch (e) {
      error = e instanceof ApiError ? `Stream failed (${e.status}).` : "Could not reach the local runtime.";
    } finally {
      streaming = false;
      promptText = "";
    }
  }

  function onKeydown(e: KeyboardEvent) {
    // Cmd/Ctrl+Enter submits; plain Enter inserts a newline.
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void submit();
    }
  }
</script>

<h1 id="page-title">Home</h1>
<p class="lead">
  Submit a prompt and watch the governed <strong>gather → plan → act → verify</strong> turn stream
  live. Every tool call still flows through the broker, policy, and approval path — nothing executes
  outside it.
</p>

<form
  class="prompt"
  onsubmit={(e) => {
    e.preventDefault();
    void submit();
  }}
>
  <label for="prompt-input" class="sr-only">Prompt</label>
  <textarea
    id="prompt-input"
    bind:value={promptText}
    onkeydown={onKeydown}
    rows="3"
    placeholder="Ask Raiker to do something local… (Cmd/Ctrl+Enter to send)"
    disabled={streaming}
  ></textarea>
  <div class="prompt-actions">
    <span class="hint">{streaming ? "Streaming the governed turn…" : "Cmd/Ctrl+Enter to send"}</span>
    <button type="submit" disabled={streaming || promptText.trim() === ""}>
      {streaming ? "Running…" : "Send"}
    </button>
  </div>
</form>

{#if error}
  <p class="state-error" role="alert">{error}</p>
{/if}

{#if !hasSubmitted}
  <p class="empty">No turns yet. Submit a prompt to start a governed turn.</p>
{:else}
  <ChatTurnTimeline {events} {finalResponse} {streaming} />
{/if}

<style>
  .lead {
    max-width: 64ch;
    color: #c2c2c9;
  }
  .prompt {
    margin-top: 1rem;
  }
  .prompt textarea {
    width: 100%;
    box-sizing: border-box;
    background: #0e0e11;
    border: 1px solid #33333a;
    color: #d6d6dc;
    border-radius: 8px;
    padding: 0.6rem 0.7rem;
    font: inherit;
    resize: vertical;
  }
  .prompt textarea:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  .prompt-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 0.5rem;
    gap: 0.75rem;
  }
  .hint {
    font-size: 0.78rem;
    color: #8b8b93;
  }
  .prompt-actions button {
    background: #1c2a3a;
    color: #cfe5ff;
    border: 1px solid #2d5a82;
    border-radius: 6px;
    padding: 0.4rem 1rem;
    cursor: pointer;
    font-weight: 600;
  }
  .prompt-actions button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .prompt-actions button:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  .empty {
    margin-top: 1.25rem;
    color: #9a9aa2;
  }
  .state-error {
    margin-top: 0.75rem;
    color: #ef9a9a;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
</style>
