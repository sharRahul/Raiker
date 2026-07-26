<script lang="ts">
  import { onMount, tick } from "svelte";
  import Icon from "../components/Icon.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError, streamPrompt } from "../api";
  import type { AgentResponse, ModelProfile, SessionDetail, StreamEvent } from "../apiTypes";
  import { collectText, groupPhases, PHASE_LABELS, PHASE_ORDER, summarizeEvent, type PhaseId } from "../turnPhases";
  import { humanize, providerName } from "../format";
  import { reactionForResponse, thinkingSteps } from "../chatPresentation";

  // One composer attachment chip: a workspace path, an image, or a text
  // document already uploaded into the governed attachment store (referenced by
  // id — the bytes stay server-side). An image is only ever delivered as an
  // image block when the turn's model profile supports vision; a document's
  // extracted text is folded into context as bounded, untrusted data.
  interface ComposerAttachment {
    kind: "path" | "image" | "document";
    label: string;
    detail: string;
    path?: string;
    attachmentId?: string;
  }

  interface ChatTurn {
    id: number;
    prompt: string;
    attachments: ComposerAttachment[];
    events: StreamEvent[];
    response: AgentResponse | null;
    streaming: boolean;
    error: string | null;
  }

  let { sessionId: continuedSessionId = null }: { sessionId?: string | null } = $props();
  let promptText = $state("");
  let userName = $state("there");
  let turns = $state<ChatTurn[]>([]);
  let streaming = $state(false);
  // Reuse one session across turns so the governed conversation stays continuous.
  let sessionId = $state<string | null>(null);
  $effect(() => {
    if (continuedSessionId === null) return;
    sessionId = continuedSessionId;
    void loadHistory(continuedSessionId);
  });
  let nextId = 1;

  // Optional per-prompt options. Left unset they change nothing — the backend
  // applies its own defaults, exactly as if the option was never sent. They
  // live as compact controls at the bottom of the composer card.
  let modelProfile = $state("");
  let planningMode = $state("");
  let profiles = $state<ModelProfile[]>([]);

  // The persisted selection (Models view / /model use). The default provider
  // option names it so the user can see what will actually serve the turn.
  const selectedProfile = $derived(profiles.find((p) => p.selected) ?? null);

  // Attachments for the next prompt: workspace paths (resolved server-side
  // inside the workspace — anything outside fails closed — and included as
  // bounded, untrusted-labelled context) and uploaded images (validated
  // fail-closed server-side: media-type allowlist, 5 MB cap, magic-byte sniff).
  const MAX_ATTACHMENTS = 8;
  const IMAGE_MEDIA_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];
  const MAX_IMAGE_BYTES = 5_000_000;
  // Documents: extracted text is folded into context as bounded, untrusted data
  // (validated fail-closed server-side: allowlist, 32 MB cap, per-type sniff —
  // UTF-8 for text, %PDF- for PDF, OOXML zip for .docx; PDF/.docx are extracted
  // locally, no bytes leave the box).
  const DOCX_MEDIA_TYPE =
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  const DOCUMENT_MEDIA_TYPES = [
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
    DOCX_MEDIA_TYPE,
  ];
  const DOCUMENT_EXTENSIONS = [".txt", ".md", ".markdown", ".csv", ".pdf", ".docx"];
  const MAX_DOCUMENT_BYTES = 32_000_000;
  let attachments = $state<ComposerAttachment[]>([]);
  let attachInput = $state("");
  // The "+" button reveals the attach controls (path input + image upload).
  let showAttach = $state(false);
  let uploading = $state(false);
  let attachError = $state<string | null>(null);

  function addAttachment() {
    const path = attachInput.trim();
    if (
      path === "" ||
      attachments.some((a) => a.path === path) ||
      attachments.length >= MAX_ATTACHMENTS
    )
      return;
    attachments = [
      ...attachments,
      { kind: "path", label: fileName(path), detail: path, path },
    ];
    attachInput = "";
  }

  function removeAttachment(index: number) {
    attachments = attachments.filter((_, i) => i !== index);
  }

  async function onImagePicked(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file || attachments.length >= MAX_ATTACHMENTS) return;
    attachError = null;
    if (!IMAGE_MEDIA_TYPES.includes(file.type)) {
      attachError = "Only PNG, JPEG, WebP, or GIF images can be attached.";
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      attachError = "Image is too large (5 MB max).";
      return;
    }
    uploading = true;
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      const base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
      const stored = await api.uploadAttachment({
        filename: file.name,
        media_type: file.type,
        data_base64: base64,
      });
      attachments = [
        ...attachments,
        {
          kind: "image",
          label: file.name,
          detail: `${file.name} (${stored.media_type}, ${stored.byte_size} bytes)`,
          attachmentId: stored.attachment_id,
        },
      ];
    } catch (e) {
      attachError =
        e instanceof ApiError
          ? `Upload rejected (${e.reasonCode ?? e.status}).`
          : "Upload failed — could not reach the local runtime.";
    } finally {
      uploading = false;
    }
  }

  // Browsers report text media types inconsistently (a .md file often arrives
  // with an empty or non-standard type), so fall back to the extension. The
  // server re-validates fail-closed regardless of what we send.
  function documentMediaType(file: File): string | null {
    if (DOCUMENT_MEDIA_TYPES.includes(file.type)) return file.type;
    const lower = file.name.toLowerCase();
    if (lower.endsWith(".csv")) return "text/csv";
    if (lower.endsWith(".md") || lower.endsWith(".markdown")) return "text/markdown";
    if (lower.endsWith(".txt")) return "text/plain";
    if (lower.endsWith(".pdf")) return "application/pdf";
    if (lower.endsWith(".docx")) return DOCX_MEDIA_TYPE;
    return null;
  }

  async function onDocumentPicked(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file || attachments.length >= MAX_ATTACHMENTS) return;
    attachError = null;
    const mediaType = documentMediaType(file);
    if (mediaType === null) {
      attachError = "Only plain-text, Markdown, CSV, PDF, or Word (.docx) documents can be attached.";
      return;
    }
    if (file.size > MAX_DOCUMENT_BYTES) {
      attachError = "Document is too large (32 MB max).";
      return;
    }
    uploading = true;
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      const base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
      const stored = await api.uploadAttachment({
        filename: file.name,
        media_type: mediaType,
        data_base64: base64,
      });
      attachments = [
        ...attachments,
        {
          kind: "document",
          label: file.name,
          detail: `${file.name} (${stored.media_type}, ${stored.byte_size} bytes)`,
          attachmentId: stored.attachment_id,
        },
      ];
    } catch (e) {
      attachError =
        e instanceof ApiError
          ? `Upload rejected (${e.reasonCode ?? e.status}).`
          : "Upload failed — could not reach the local runtime.";
    } finally {
      uploading = false;
    }
  }

  // Chips show only the file/folder name; the full workspace path stays in the
  // tooltip and is what actually rides the prompt.
  function fileName(path: string): string {
    const parts = path.split("/").filter(Boolean);
    return parts.length > 0 ? parts[parts.length - 1] : path;
  }

  let scrollEl: HTMLDivElement | undefined = $state();

  onMount(() => {
    void loadProfiles();
    void api.settings().then((view) => { userName = view.status.username || "there"; }).catch(() => {});
    // The Workbench composer hands its text to this mounted chat rather than
    // sending a prompt of its own. There is one governed send path, and it is
    // `submit()` below — the Workbench never talks to the API directly, so a
    // prompt started there is identical to one typed here.
    const onCompose = (event: Event) => {
      const detail = (event as CustomEvent<{ text: string; sessionId: string | null }>).detail;
      if (detail === undefined || detail.text.trim() === "") return;
      if (detail.sessionId !== null && detail.sessionId !== sessionId) {
        sessionId = detail.sessionId;
        void loadHistory(detail.sessionId);
      }
      promptText = detail.text;
      void submit();
    };
    window.addEventListener("raiker:compose", onCompose);
    return () => window.removeEventListener("raiker:compose", onCompose);
  });

  // Hydrate the persisted transcript for a continued session so a search result
  // (or any link into an existing chat) opens its prior turns in the chat surface
  // instead of a blank composer. The backend `/api/sessions/{id}` read is
  // Bearer-authenticated and enforces the same user/session visibility boundary
  // as every other governed read, so no new session is created merely to view
  // history — the restored turns reuse the continued session id and the user
  // can keep typing into it. Restored turns carry only what is persisted: the
  // prompt, the agent's response message (turn.summary), and the turn status.
  // The live per-event timeline is not replayed; new turns stream as usual.
  let historyError = $state<string | null>(null);
  let historyLoading = $state(false);

  async function loadHistory(id: string) {
    historyLoading = true;
    try {
      const detail = await api.session(id);
      turns = detail.turns.map((t) => restoredTurn(t, id));
      nextId = turns.length + 1;
      void scrollToEnd();
    } catch (e) {
      historyError =
        e instanceof ApiError ? `Could not load history (${e.status}).` : "Could not load history.";
    } finally {
      historyLoading = false;
    }
  }

  function restoredTurn(t: SessionDetail["turns"][number], sessionId: string): ChatTurn {
    return {
      id: nextId++,
      prompt: t.prompt_text ?? "",
      attachments: [],
      events: [],
      response: {
        request_id: "",
        session_id: sessionId,
        turn_id: t.turn_id,
        status: t.status,
        message: t.summary ?? "",
        events_path: null,
        checkpoint_path: null,
        approval: null,
        last_event_id: null,
      },
      streaming: false,
      error: null,
    };
  }

  async function loadProfiles() {
    try {
      const models = await api.models();
      // Chat is intentionally limited to concrete configured profiles. Older
      // servers fall back to their profile list, filtering the same fact.
      profiles = models.chat_profiles ?? models.profiles.filter((profile) => profile.configured);
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
          attachments:
            sentAttachments.length > 0
              ? sentAttachments.map((a) =>
                  a.kind === "image"
                    ? { type: "image" as const, attachment_id: a.attachmentId ?? "" }
                    : a.kind === "document"
                      ? { type: "document" as const, attachment_id: a.attachmentId ?? "" }
                      : { type: "path" as const, path: a.path ?? "" },
                )
              : undefined,
          planning_mode: planningMode || undefined,
        },
        (event) => {
          if (event.kind === "final" && event.response !== null) {
            turn.response = event.response;
            sessionId = event.response.session_id;
            window.dispatchEvent(new Event("raiker:chats-changed"));
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
    {#if historyError !== null}
      <p class="error-line" role="alert">{historyError}</p>
    {/if}
    {#if historyLoading}
      <PageState state="loading" title="Loading conversation…" />
    {:else if turns.length === 0}
      <EmptyState
        icon="chat"
        title={`What would you like to work on, ${userName}?`}
        body="Start with a question, a task, or a file."
        serif={true}
      />
    {/if}

    {#each turns as turn (turn.id)}
      {@const answer = answerText(turn)}
      {@const thinking = thinkingSteps(turn.events)}
      {@const reaction = reactionForResponse(answer)}
      <div class="turn">
        <div class="message-group message-group-user">
          <div class="message-bubble message-bubble-user">
          <p class="bubble-text">{turn.prompt}</p>
          {#if turn.attachments.length > 0}
            <p class="turn-attachments">
              {#each turn.attachments as a, i (a.attachmentId ?? a.path ?? i)}
                <span class="attach-chip" title={a.detail}>
                  <Icon name="file" size={13} />
                  {a.label}
                </span>
              {/each}
            </p>
          {/if}
        </div>
        </div>

        <div class="message-group message-group-raiker">
          {#if turn.response !== null}
          {#if false}
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
            <!-- Legacy runtime metadata intentionally omitted from Chat. -->
            <!--
            <div class="response-meta">
              <Badge variant={responseBadge(turn.response!.status)} label={turn.response!.status} />
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
            -->

            {#if turn.response!.status === "needs_approval" && turn.response!.approval}
              <div class="approval-card">
                <p class="approval-title">
                  <Icon name="approvals" size={15} />
                  This action is waiting for your approval
                </p>
                <!--
                <p class="approval-body">
                  <strong>{humanize(turn.response.approval.tool_name)}</strong> — risk
                  <strong>{turn.response.approval.risk_level}</strong>.
                  {turn.response.approval.message}
                </p>
                -->
                <p class="approval-note">
                  Review it in the Approvals inbox. Recording a decision never executes the action.
                </p>
                <a class="btn btn-soft btn-sm" href="#/approvals">Open Approvals</a>
              </div>
            {/if}
          {/if}

          {#if turn.events.some((e) => e.kind === "lifecycle" || e.kind === "tool")}
            <details class="under-hood" open={turn.streaming}>
              <summary>
                <Icon name="shield" size={13} />
                {turn.streaming ? "Governing this turn…" : "How this turn was governed"}
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
          {/if}
          {/if}

          {#if turn.streaming}
            <p class="streaming-label" role="status">
              <span class="pulse" aria-hidden="true"></span>
              {answer === "" ? "Raiker is thinking…" : "Raiker is typing…"}
            </p>
            {#if thinking.length > 0}
              <details class="thinking-details" aria-label="Raiker's thinking">
                <summary>See what Raiker is thinking</summary>
                {#each thinking as step (step)}
                  <p>{step}</p>
                {/each}
              </details>
            {/if}
          {/if}

          {#if answer !== ""}
            <div class="message-bubble message-bubble-raiker"><p class="bubble-text answer">{answer}</p></div>
          {:else if !turn.streaming && turn.error === null && turn.response !== null}
            <div class="message-bubble message-bubble-raiker"><p class="bubble-text answer muted">(No answer text was returned.)</p></div>
          {/if}

          {#if turn.error !== null}
            <p class="error-line" role="alert">{turn.error}</p>
          {/if}

          {#if turn.response?.status === "needs_approval" && turn.response.approval}
            <div class="approval-card">
              <p class="approval-title"><Icon name="approvals" size={15} /> Your approval is needed to continue</p>
              <p class="approval-body">{turn.response.approval.message}</p>
              <a class="btn btn-soft btn-sm" href="#/approvals">Review approval</a>
            </div>
          {/if}

          {#if !turn.streaming && reaction}
            <span class="reaction" aria-label={`Raiker reacted with ${reaction.label}`}>{reaction.emoji}</span>
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
          {#each attachments as a, i (a.attachmentId ?? a.path ?? i)}
            <span class="attach-chip" title={a.detail}>
              <Icon name="file" size={13} />
              {a.label}
              <button
                type="button"
                class="attach-remove"
                onclick={() => removeAttachment(i)}
                aria-label={`Remove attachment ${a.detail}`}
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
          <input
            class="sr-only"
            id="image-upload-input"
            type="file"
            accept={IMAGE_MEDIA_TYPES.join(",")}
            onchange={onImagePicked}
            disabled={streaming || uploading || attachments.length >= MAX_ATTACHMENTS}
            aria-label="Upload image"
          />
          <label
            class="btn btn-sm"
            for="image-upload-input"
            title="Upload an image (PNG/JPEG/WebP/GIF, 5 MB max). Sent to the model only if the selected model supports vision."
          >
            {uploading ? "Uploading…" : "Image…"}
          </label>
          <input
            class="sr-only"
            id="document-upload-input"
            type="file"
            accept={[...DOCUMENT_MEDIA_TYPES, ...DOCUMENT_EXTENSIONS].join(",")}
            onchange={onDocumentPicked}
            disabled={streaming || uploading || attachments.length >= MAX_ATTACHMENTS}
            aria-label="Upload document"
          />
          <label
            class="btn btn-sm"
            for="document-upload-input"
            title="Upload a document (plain text/Markdown/CSV/PDF/Word .docx, 32 MB max). Its extracted text is added to context as untrusted data."
          >
            {uploading ? "Uploading…" : "Document…"}
          </label>
        </div>
        {#if attachError !== null}
          <p class="error-line" role="alert">{attachError}</p>
        {/if}
      {/if}

      <div class="composer-bar">
        <button
          type="button"
          class="round-btn"
          onclick={() => (showAttach = !showAttach)}
          aria-label="Add attachment"
          aria-expanded={showAttach}
          title="Attach a workspace file or folder"
          disabled={streaming}
        >
          +
        </button>
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={newConversation}
          disabled={streaming || turns.length === 0}
        >
          New chat
        </button>

        <div class="bar-right">
          <select
            class="bar-select"
            bind:value={planningMode}
            disabled={streaming}
            aria-label="Planning"
            title="Planning mode for this turn"
          >
            <option value="">Planning: auto</option>
            <option value="always">Always plan</option>
            <option value="never_safe_only">Never plan</option>
          </select>

          <select
            class="bar-select"
            bind:value={modelProfile}
            disabled={streaming}
            aria-label="Model"
            title="Configured model for this turn"
          >
            <option value="">
              {selectedProfile !== null
                ? `${providerName(selectedProfile.provider)} · ${selectedProfile.model}`
                : "Selected model"}
            </option>
            {#each profiles as p (p.profile_id)}
              <option value={p.profile_id}>{providerName(p.provider)} · {p.model}</option>
            {/each}
          </select>

          <button
            type="button"
            class="round-btn"
            disabled
            aria-label="Voice input (coming soon)"
            title="Voice input — planned: local transcription via whisper.cpp; not wired up yet"
          >
            <Icon name="mic" size={15} />
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
  .message-group {
    display: flex;
    flex-direction: column;
    max-width: min(76%, 48rem);
    position: relative;
  }
  .message-group-user {
    align-self: flex-end;
    align-items: flex-end;
  }
  .message-group-raiker {
    align-self: flex-start;
    align-items: flex-start;
  }
  .message-bubble {
    position: relative;
    border-radius: 1.25rem;
    padding: 0.72rem 0.95rem;
    box-shadow: var(--shadow-1);
  }
  .message-bubble-user {
    background: var(--accent);
    color: var(--text-inverse);
    border-bottom-right-radius: 0.35rem;
  }
  .message-bubble-raiker {
    background: var(--sunken);
    color: var(--text-1);
    border: 1px solid var(--border);
    border-bottom-left-radius: 0.35rem;
  }
  .streaming-label {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0 0 0.3rem;
    color: var(--text-3);
    font-size: 0.78rem;
    font-weight: 650;
  }
  .thinking-details {
    margin: 0 0 0.4rem;
    color: var(--text-2);
    font-size: 0.78rem;
  }
  .thinking-details summary {
    cursor: pointer;
    color: var(--text-3);
  }
  .thinking-details p {
    margin: 0.35rem 0 0;
  }
  .reaction {
    margin: -0.25rem 0.75rem 0;
    padding: 0.12rem 0.38rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    box-shadow: var(--shadow-1);
    font-size: 1rem;
    line-height: 1.2;
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
  .round-btn {
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
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .round-btn:hover:not(:disabled) {
    border-color: var(--accent-border);
    color: var(--accent);
  }
  .round-btn:disabled {
    opacity: 0.55;
    cursor: default;
  }
  /* Model/planning controls sit on the right of the bar, like the reference. */
  .bar-right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    min-width: 0;
    justify-content: flex-end;
  }
  .bar-select {
    border: none;
    background: transparent;
    color: var(--text-2);
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.25rem 0.35rem;
    border-radius: var(--r-md);
    max-width: 15rem;
  }
  .bar-select:hover:not(:disabled) {
    background: var(--neutral-soft);
  }
  .bar-select:focus-visible,
  .round-btn:focus-visible {
    outline: 2px solid var(--focus-ring);
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
  @media (max-width: 720px) {
    .message-group {
      max-width: 88%;
    }
  }
</style>
