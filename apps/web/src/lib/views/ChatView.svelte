<script lang="ts">
  import { onMount, tick } from "svelte";
  import Icon from "../components/Icon.svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import { api, ApiError, streamPrompt } from "../api";
  import type { AgentResponse, ModelProfile, ProviderModelList, StreamEvent } from "../apiTypes";
  import { groupPhases, PHASE_LABELS, PHASE_ORDER, summarizeEvent, type PhaseId } from "../turnPhases";
  import { responseBadge } from "../statusMaps";
  import { collectText } from "../turnPhases";
  import { humanize, providerName } from "../format";

  interface ChatTurn {
    id: number;
    prompt: string;
    attachments: string[];
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
  // applies its own defaults, exactly as if the option was never sent. They
  // live as compact controls at the bottom of the composer card.
  let modelProfile = $state("");
  let planningMode = $state("");
  let maxToolCalls = $state("");
  let profiles = $state<ModelProfile[]>([]);

  // Per-turn model for the chosen profile. Populated on demand from the
  // provider's own catalogue; when the catalogue is unavailable the user can
  // still type a model id. Empty means the profile/persisted default.
  let modelChoice = $state("");
  let providerModels = $state<ProviderModelList | null>(null);
  let loadingModels = $state(false);

  const chosenProfile = $derived(profiles.find((p) => p.profile_id === modelProfile) ?? null);

  // Workspace path attachments for the next prompt (this slice supports paths
  // only). Paths are resolved server-side inside the workspace — anything
  // outside fails closed — and included as bounded, untrusted-labelled context.
  const MAX_ATTACHMENTS = 8;
  let attachments = $state<string[]>([]);
  let attachInput = $state("");
  // The "+" button reveals the path input.
  let showAttach = $state(false);

  function addAttachment() {
    const path = attachInput.trim();
    if (path === "" || attachments.includes(path) || attachments.length >= MAX_ATTACHMENTS) return;
    attachments = [...attachments, path];
    attachInput = "";
  }

  function removeAttachment(index: number) {
    attachments = attachments.filter((_, i) => i !== index);
  }

  async function onProfileChange() {
    modelChoice = "";
    providerModels = null;
    if (modelProfile === "") return;
    loadingModels = true;
    try {
      providerModels = await api.providerModels(modelProfile);
    } catch {
      providerModels = null; // manual entry still works below
    } finally {
      loadingModels = false;
    }
  }

  function providerModelsNote(list: ProviderModelList): string {
    switch (list.status) {
      case "policy_denied":
        return "Model list denied by provider policy — enable the provider's gate first.";
      case "unsupported":
        return "This provider does not support model listing.";
      default:
        return "Provider unreachable — type a model id if you know it.";
    }
  }

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

  // Provider-agnostic cache metrics from the last model_request_completed event.
  // The runtime normalises every provider's usage into the same shape, so this
  // reads cache-hit tokens irrespective of which model served the turn.
  function cacheInfo(turn: ChatTurn): { read: number; hit: boolean } | null {
    for (let i = turn.events.length - 1; i >= 0; i--) {
      const ev = turn.events[i];
      if (ev.kind !== "lifecycle" || ev.event_type !== "model_request_completed") continue;
      const usage = ev.payload?.usage as Record<string, number> | undefined;
      if (usage && typeof usage.cache_read_tokens === "number") {
        return { read: usage.cache_read_tokens, hit: usage.cache_read_tokens > 0 };
      }
      return null;
    }
    return null;
  }

  function answerText(turn: ChatTurn): string {
    const streamed = collectText(turn.events);
    if (streamed.trim() !== "") return streamed;
    return turn.response?.message ?? "";
  }

  async function submit() {
    const text = promptText.trim();
    if (text === "" || streaming) return;
    const sentAttachments = [...attachments];
    turns = [
      ...turns,
      {
        id: nextId++,
        prompt: text,
        attachments: sentAttachments,
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
    attachments = [];
    streaming = true;
    void scrollToEnd();
    try {
      await streamPrompt(
        {
          text,
          session_id: sessionId ?? undefined,
          model_profile: modelProfile || undefined,
          model: modelChoice.trim() || undefined,
          attachments:
            sentAttachments.length > 0
              ? sentAttachments.map((path) => ({ type: "path" as const, path }))
              : undefined,
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
          {#if turn.attachments.length > 0}
            <p class="turn-attachments">
              {#each turn.attachments as path (path)}
                <span class="attach-chip" title="Attached workspace path"><code>{path}</code></span>
              {/each}
            </p>
          {/if}
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
              {#if cacheInfo(turn)}
                {@const cache = cacheInfo(turn)}
                <span
                  class="cache-chip"
                  class:hit={cache?.hit}
                  title="Prompt cache — cached input tokens reused this turn (cuts cost and latency)"
                >
                  {cache?.hit ? `Cache hit · ${cache.read} tok` : "Cache miss"}
                </span>
              {/if}
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
    <div class="composer-card">
      {#if attachments.length > 0}
        <div class="attach-chips">
          {#each attachments as path, i (path)}
            <span class="attach-chip">
              <code>{path}</code>
              <button
                type="button"
                class="attach-remove"
                onclick={() => removeAttachment(i)}
                aria-label={`Remove attachment ${path}`}
              >
                ×
              </button>
            </span>
          {/each}
        </div>
      {/if}

      <label for="prompt-input" class="sr-only">Prompt</label>
      <textarea
        id="prompt-input"
        class="prompt-input"
        bind:value={promptText}
        onkeydown={onKeydown}
        rows="2"
        placeholder="How can I help you today?"
        title="Enter to send, Shift+Enter for a new line"
        disabled={streaming}
      ></textarea>

      {#if showAttach}
        <div class="attach-popover">
          <input
            class="attach-input"
            type="text"
            placeholder="Workspace file or folder path…"
            bind:value={attachInput}
            onkeydown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addAttachment();
              }
            }}
            disabled={streaming || attachments.length >= MAX_ATTACHMENTS}
            aria-label="Attachment path"
          />
          <button
            type="button"
            class="btn btn-sm"
            onclick={addAttachment}
            disabled={streaming || attachInput.trim() === "" || attachments.length >= MAX_ATTACHMENTS}
          >
            Attach
          </button>
        </div>
      {/if}

      <div class="composer-bar">
        <button
          type="button"
          class="plus-btn"
          onclick={() => (showAttach = !showAttach)}
          aria-label="Add attachment"
          aria-expanded={showAttach}
          title="Attach a workspace file or folder path"
          disabled={streaming}
        >
          +
        </button>

        <div class="bar-controls">
          <select
            class="bar-select"
            bind:value={modelProfile}
            onchange={() => void onProfileChange()}
            disabled={streaming}
            aria-label="Provider"
            title="Provider for this turn (default: your selected model)"
          >
            <option value="">Selected model</option>
            {#each profiles as p (p.profile_id)}
              <option value={p.profile_id}>{providerName(p.provider)}</option>
            {/each}
          </select>

          {#if modelProfile !== ""}
            {#if loadingModels}
              <span class="bar-note" role="status">Loading models…</span>
            {:else if providerModels !== null && providerModels.status === "available" && providerModels.models.length > 0}
              <select
                class="bar-select"
                bind:value={modelChoice}
                disabled={streaming}
                aria-label="Model"
                title="Model for this turn, from the provider's catalogue"
              >
                <option value="">
                  {chosenProfile !== null && chosenProfile.model !== "<model>"
                    ? `Default (${chosenProfile.model})`
                    : "Pick a model…"}
                </option>
                {#each providerModels.models as m (m)}
                  <option value={m}>{m}</option>
                {/each}
              </select>
            {:else}
              <input
                class="bar-input"
                type="text"
                placeholder="model id"
                bind:value={modelChoice}
                disabled={streaming}
                aria-label="Model"
                title={providerModels !== null && providerModels.status !== "available"
                  ? providerModelsNote(providerModels)
                  : "Model for this turn"}
              />
            {/if}
          {/if}

          <select
            class="bar-select"
            bind:value={planningMode}
            disabled={streaming}
            aria-label="Planning"
            title="Planning mode for this turn"
          >
            <option value="">Planning: auto</option>
            <option value="always">Always plan</option>
            <option value="never">Never plan</option>
          </select>

          <input
            class="bar-input bar-tools"
            type="number"
            min="0"
            max="50"
            placeholder="10"
            bind:value={maxToolCalls}
            disabled={streaming}
            aria-label="Max tool calls"
            title="Tool-call budget for this turn"
          />
        </div>

        <div class="bar-actions">
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
            aria-label={streaming ? "Running" : "Send"}
          >
            <Icon name="send" size={15} />
            {streaming ? "Running…" : "Send"}
          </button>
        </div>
      </div>
    </div>

    {#if modelProfile !== "" && !loadingModels}
      {#if providerModels !== null && providerModels.status !== "available"}
        <p class="model-note">{providerModelsNote(providerModels)}</p>
      {:else if chosenProfile !== null && chosenProfile.model === "<model>" && modelChoice.trim() === ""}
        <p class="model-note">
          This provider needs a concrete model — without one the turn uses your persisted selection.
        </p>
      {/if}
    {/if}
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
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .cache-chip {
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-3);
    padding: 0.08rem 0.55rem;
  }
  .cache-chip.hit {
    border-color: var(--ok-border);
    background: var(--ok-soft);
    color: var(--ok);
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
    padding-top: var(--space-3);
    background: var(--bg);
  }
  /* One clean card: prompt on top, "+" and the per-turn controls at the bottom. */
  .composer-card {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-1);
    padding: 0.75rem 0.85rem 0.6rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .composer-card:focus-within {
    border-color: var(--accent-border);
  }
  .prompt-input {
    width: 100%;
    border: none;
    outline: none;
    resize: vertical;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: 0.95rem;
    min-height: 2.6rem;
  }
  .prompt-input::placeholder {
    color: var(--text-3);
  }
  .composer-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border-top: 1px solid var(--border);
    padding-top: 0.5rem;
    flex-wrap: wrap;
  }
  .plus-btn {
    width: 1.9rem;
    height: 1.9rem;
    border-radius: 50%;
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    font-size: 1.1rem;
    line-height: 1;
    cursor: pointer;
    flex-shrink: 0;
  }
  .plus-btn:hover:not(:disabled) {
    border-color: var(--accent-border);
    color: var(--accent);
  }
  .bar-controls {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    min-width: 0;
  }
  .bar-select,
  .bar-input {
    border: none;
    background: transparent;
    color: var(--text-2);
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.25rem 0.35rem;
    border-radius: var(--r-md);
    max-width: 15rem;
  }
  .bar-select:hover:not(:disabled),
  .bar-input:hover:not(:disabled) {
    background: var(--neutral-soft);
  }
  .bar-select:focus-visible,
  .bar-input:focus-visible,
  .plus-btn:focus-visible {
    outline: 2px solid var(--focus-ring);
  }
  .bar-input {
    border: 1px dashed var(--neutral-border);
  }
  .bar-tools {
    width: 3.4rem;
  }
  .bar-note {
    font-size: 0.76rem;
    color: var(--text-3);
  }
  .bar-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .model-note {
    font-size: 0.74rem;
    color: var(--text-3);
    margin: 0.35rem 0.2rem 0;
  }
  .attach-popover {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .attach-input {
    flex: 1;
    min-width: 12rem;
    font-size: 0.8rem;
    padding: 0.35rem 0.5rem;
    border-radius: var(--r-md);
    border: 1px solid var(--neutral-border);
    background: var(--surface-1);
    color: var(--text-1);
  }
  .attach-chips {
    display: flex;
    gap: 0.3rem;
    flex-wrap: wrap;
  }
  .attach-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.74rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    padding: 0.1rem 0.5rem;
  }
  .attach-remove {
    border: none;
    background: none;
    color: var(--text-3);
    cursor: pointer;
    font-size: 0.85rem;
    padding: 0 0.1rem;
    line-height: 1;
  }
  .attach-remove:hover {
    color: var(--danger);
  }
  .turn-attachments {
    margin: 0.4rem 0 0;
    display: flex;
    gap: 0.3rem;
    flex-wrap: wrap;
  }
  .send {
    min-width: 6.5rem;
  }
</style>
