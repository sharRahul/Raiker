<script lang="ts">
  import { onMount, tick } from "svelte";
  import Icon from "../components/Icon.svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import { api, ApiError, streamPrompt } from "../api";
  import type { AgentResponse, ModelProfile, StreamEvent } from "../apiTypes";
  import { groupPhases, PHASE_LABELS, PHASE_ORDER, summarizeEvent, type PhaseId } from "../turnPhases";
  import { responseBadge } from "../statusMaps";
  import { collectText } from "../turnPhases";
  import { humanize, providerName } from "../format";

  interface ChatTurn {
    id: number;
    prompt: string;
    events: StreamEvent[];
    response: AgentResponse | null;
    streaming: boolean;
    error: string | null;
  }

  let promptText = $state("");
  let turns = $state<ChatTurn[]>([]);
  let streaming = $state(false);
  // Reuse one session across turns so the governed conversation stays continuous.
  let sessionId = $state<string | null>(null);
  let nextId = 1;

  // Optional per-prompt options. Left unset they change nothing — the backend
  // applies its own defaults, exactly as if the option was never sent.
  let showOptions = $state(false);
  let modelProfile = $state("");
  let planningMode = $state("");
  let maxToolCalls = $state("");
  let profiles = $state<ModelProfile[]>([]);

  let scrollEl: HTMLDivElement | undefined = $state();

  onMount(() => {
    void loadProfiles();
  });

  async function loadProfiles() {
    try {
      const models = await api.models();
      profiles = models.profiles;
    } catch {
      // The options panel simply omits the model list; prompting still works.
    }
  }

  function currentPhase(turn: ChatTurn): PhaseId | null {
    const rows = groupPhases(turn.events);
    return rows.length > 0 ? rows[rows.length - 1].phase : null;
  }

  function answerText(turn: ChatTurn): string {
    const streamed = collectText(turn.events);
    if (streamed.trim() !== "") return streamed;
    return turn.response?.message ?? "";
  }

  async function submit() {
    const text = promptText.trim();
    if (text === "" || streaming) return;
    turns = [
      ...turns,
      {
        id: nextId++,
        prompt: text,
        events: [],
        response: null,
        streaming: true,
        error: null,
      },
    ];
    // Mutate the $state-proxied instance, not the raw literal: raw-object writes
    // bypass Svelte 5's signals and the transcript would never re-render.
    const turn = turns[turns.length - 1];
    promptText = "";
    streaming = true;
    void scrollToEnd();
    try {
      await streamPrompt(
        {
          text,
          session_id: sessionId ?? undefined,
          model_profile: modelProfile || undefined,
          planning_mode: planningMode || undefined,
          max_tool_calls: maxToolCalls !== "" ? Number(maxToolCalls) : undefined,
        },
        (event) => {
          if (event.kind === "final" && event.response !== null) {
            turn.response = event.response;
            sessionId = event.response.session_id;
          } else {
            turn.events = [...turn.events, event];
          }
          void scrollToEnd();
        },
      );
    } catch (e) {
      turn.error =
        e instanceof ApiError ? `Stream failed (${e.status}).` : "Could not reach the local runtime.";
    } finally {
      turn.streaming = false;
      streaming = false;
      void scrollToEnd();
    }
  }

  async function scrollToEnd() {
    await tick();
    // Guarded: jsdom (vitest) has no scrollTo implementation.
    if (typeof scrollEl?.scrollTo === "function") {
      scrollEl.scrollTo({ top: scrollEl.scrollHeight });
    }
  }

  function onKeydown(e: KeyboardEvent) {
    // Enter submits; Shift+Enter inserts a newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }

  function newConversation() {
    if (streaming) return;
    turns = [];
    sessionId = null;
  }
</script>

<div class="chat">
  <div class="thread" bind:this={scrollEl}>
    {#if turns.length === 0}
      <EmptyState
        icon="chat"
        title="Talk to your governed agent"
        body="Every turn runs gather → plan → act → verify through policy, approvals, and the audit log. Nothing executes outside that path."
      />
    {/if}

    {#each turns as turn (turn.id)}
      <div class="turn">
        <div class="bubble user">
          <p class="bubble-text">{turn.prompt}</p>
        </div>

        <div class="bubble agent">
          {#if turn.streaming}
            <p class="phase-line" role="status">
              <span class="pulse" aria-hidden="true"></span>
              {#if currentPhase(turn)}
                Working — {PHASE_LABELS[currentPhase(turn) as PhaseId]}
              {:else}
                Working…
              {/if}
            </p>
          {/if}

          {#if answerText(turn) !== ""}
            <p class="bubble-text answer">{answerText(turn)}</p>
          {:else if !turn.streaming && turn.error === null && turn.response !== null}
            <p class="bubble-text answer muted">(No answer text was returned.)</p>
          {/if}

          {#if turn.error !== null}
            <p class="error-line" role="alert">{turn.error}</p>
          {/if}

          {#if turn.response !== null}
            <div class="response-meta">
              <Badge variant={responseBadge(turn.response.status)} label={turn.response.status} />
            </div>

            {#if turn.response.status === "needs_approval" && turn.response.approval}
              <div class="approval-card">
                <p class="approval-title">
                  <Icon name="approvals" size={15} />
                  This action is waiting for your approval
                </p>
                <p class="approval-body">
                  <strong>{humanize(turn.response.approval.tool_name)}</strong> — risk
                  <strong>{turn.response.approval.risk_level}</strong>.
                  {turn.response.approval.message}
                </p>
                <p class="approval-note">
                  Review it in the Approvals inbox. Recording a decision never executes the action.
                </p>
                <a class="btn btn-soft btn-sm" href="#/approvals">Open Approvals</a>
              </div>
            {/if}
          {/if}

          {#if turn.events.some((e) => e.kind === "lifecycle" || e.kind === "tool")}
            <details class="under-hood">
              <summary>
                <Icon name="shield" size={13} />
                How this turn was governed
              </summary>
              <ol class="phases">
                {#each groupPhases(turn.events) as row (row.phase)}
                  <li>
                    <span class="phase-name">
                      {PHASE_ORDER.indexOf(row.phase) + 1}. {row.label}
                    </span>
                    <ul class="phase-events">
                      {#each row.events as ev, i (i)}
                        <li>{summarizeEvent(ev)}</li>
                      {/each}
                    </ul>
                  </li>
                {/each}
              </ol>
              {#each turn.events.filter((e) => e.kind === "tool") as ev, i (i)}
                <p class="tool-line">{humanize(ev.event_type)} {ev.text}</p>
              {/each}
            </details>
          {/if}
        </div>
      </div>
    {/each}
  </div>

  <form
    class="composer"
    onsubmit={(e) => {
      e.preventDefault();
      void submit();
    }}
  >
    {#if showOptions}
      <div class="options">
        <div class="option">
          <label class="field-label" for="opt-model">Model profile</label>
          <select id="opt-model" class="select" bind:value={modelProfile} disabled={streaming}>
            <option value="">Selected model (see Models)</option>
            {#each profiles as p (p.profile_id)}
              <option
                value={p.profile_id}
                disabled={p.model === "<model>" && !p.selected}
                title={p.model === "<model>" && !p.selected
                  ? "Pick a concrete model for this profile first (/model use)"
                  : undefined}
              >
                {providerName(p.provider)} · {p.profile_id}
              </option>
            {/each}
          </select>
        </div>
        <div class="option">
          <label class="field-label" for="opt-planning">Planning</label>
          <select id="opt-planning" class="select" bind:value={planningMode} disabled={streaming}>
            <option value="">Auto</option>
            <option value="always">Always plan</option>
            <option value="never">Never plan</option>
          </select>
        </div>
        <div class="option">
          <label class="field-label" for="opt-tools">Max tool calls</label>
          <input
            id="opt-tools"
            class="input"
            type="number"
            min="0"
            max="50"
            placeholder="10"
            bind:value={maxToolCalls}
            disabled={streaming}
          />
        </div>
      </div>
    {/if}

    <div class="composer-row">
      <label for="prompt-input" class="sr-only">Prompt</label>
      <textarea
        id="prompt-input"
        class="textarea prompt-input"
        bind:value={promptText}
        onkeydown={onKeydown}
        rows="2"
        placeholder="Ask Raiker… (Enter to send, Shift+Enter for a new line)"
        disabled={streaming}
      ></textarea>
      <div class="composer-actions">
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={() => (showOptions = !showOptions)}
          aria-expanded={showOptions}
        >
          Options
        </button>
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={newConversation}
          disabled={streaming || turns.length === 0}
        >
          New chat
        </button>
        <button
          type="submit"
          class="btn btn-primary send"
          disabled={streaming || promptText.trim() === ""}
        >
          <Icon name="send" size={15} />
          {streaming ? "Running…" : "Send"}
        </button>
      </div>
    </div>
  </form>
</div>

<style>
  .chat {
    display: flex;
    flex-direction: column;
    height: 100%;
    max-width: 52rem;
    margin: 0 auto;
  }
  .thread {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding-bottom: var(--space-4);
  }
  .turn {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .bubble {
    border-radius: var(--r-lg);
    padding: 0.75rem 1rem;
    max-width: 85%;
  }
  .bubble.user {
    align-self: flex-end;
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
  }
  .bubble.agent {
    align-self: flex-start;
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-1);
    min-width: 14rem;
  }
  .bubble-text {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .answer {
    color: var(--text-1);
  }
  .muted {
    color: var(--text-3);
  }
  .phase-line {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--text-2);
    font-size: 0.85rem;
    margin: 0 0 0.35rem;
  }
  .pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,
    100% {
      opacity: 0.35;
    }
    50% {
      opacity: 1;
    }
  }
  .error-line {
    color: var(--danger);
    font-size: 0.86rem;
    margin: 0.35rem 0 0;
  }
  .response-meta {
    margin-top: 0.5rem;
  }
  .approval-card {
    margin-top: 0.65rem;
    border: 1px solid var(--warn-border);
    background: var(--warn-soft);
    border-radius: var(--r-sm);
    padding: 0.65rem 0.85rem;
  }
  .approval-title {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 650;
    font-size: 0.86rem;
    margin: 0 0 0.3rem;
    color: var(--warn);
  }
  .approval-body {
    font-size: 0.85rem;
    margin: 0 0 0.3rem;
  }
  .approval-note {
    font-size: 0.76rem;
    color: var(--text-2);
    margin: 0 0 0.5rem;
  }
  .under-hood {
    margin-top: 0.7rem;
    border-top: 1px dashed var(--border);
    padding-top: 0.5rem;
  }
  .under-hood summary {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    cursor: pointer;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-3);
    list-style: none;
  }
  .under-hood summary::-webkit-details-marker {
    display: none;
  }
  .under-hood summary:hover {
    color: var(--text-1);
  }
  .phases {
    margin: 0.5rem 0 0;
    padding-left: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .phase-name {
    font-size: 0.78rem;
    font-weight: 650;
    color: var(--accent);
  }
  .phase-events {
    margin: 0.15rem 0 0;
    padding-left: 1rem;
    font-size: 0.8rem;
    color: var(--text-2);
  }
  .tool-line {
    font-size: 0.8rem;
    color: var(--text-2);
    margin: 0.3rem 0 0;
  }
  .composer {
    border-top: 1px solid var(--border);
    padding-top: var(--space-3);
    background: var(--bg);
  }
  .options {
    display: flex;
    gap: var(--space-4);
    flex-wrap: wrap;
    padding: 0.35rem 0 0.7rem;
  }
  .option .input,
  .option .select {
    min-width: 11rem;
  }
  .composer-row {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .prompt-input {
    width: 100%;
  }
  .composer-actions {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    justify-content: flex-end;
  }
  .send {
    min-width: 6.5rem;
  }
</style>
