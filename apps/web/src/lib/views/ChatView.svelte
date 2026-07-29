<script lang="ts">
  import { onMount, tick, untrack } from "svelte";
  import Icon from "../components/Icon.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import ContextMeterPopover from "../components/ContextMeterPopover.svelte";
  import ContextRing from "../components/ContextRing.svelte";
  import Markdown from "../components/Markdown.svelte";
  import FileInspector from "../components/FileInspector.svelte";
  import ApprovalModeControl from "../components/ApprovalModeControl.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import BuildSidePanel from "../components/BuildSidePanel.svelte";
  import { api, ApiError, streamPrompt } from "../api";
  import type {
    AgentResponse,
    AttachmentPreview,
    ContextUsage,
    ProjectsList,
    SessionDetail,
    StreamEvent,
  } from "../apiTypes";
  import { collectText, groupPhases, PHASE_LABELS, PHASE_ORDER, summarizeEvent, type PhaseId } from "../turnPhases";
  import { humanize } from "../format";
  import { reactionForResponse, thinkingSteps } from "../chatPresentation";
  import { chatProfiles, refreshModels } from "../models.svelte";

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

  let {
    sessionId: continuedSessionId = null,
    projects = null,
    onProjectsChanged,
  }: {
    sessionId?: string | null;
    projects?: ProjectsList | null;
    onProjectsChanged?: () => void;
  } = $props();
  let promptText = $state("");
  let userName = $state("there");
  let turns = $state<ChatTurn[]>([]);
  // What the last copy action did. Shown, not only announced: a copy that
  // reports nothing leaves the owner guessing whether it worked.
  let exportNotice = $state<string | null>(null);
  let streaming = $state(false);
  // Reuse one session across turns so the governed conversation stays continuous.
  let sessionId = $state<string | null>(null);
  // Provider-reported usage and API cost for this conversation. Null until the
  // popover is opened at least once; the meter falls back to the labelled local
  // estimate until the server has something real to report.
  let contextUsage = $state<ContextUsage | null>(null);
  let projectId = $state("");
  let pendingProjectId: string | null = null;
  let projectNotice = $state<string | null>(null);
  let backgroundWorkOpen = $state(false);

  async function refreshContextUsage() {
    if (sessionId === null) {
      contextUsage = null;
      return;
    }
    try {
      contextUsage = await api.sessionContextUsage(sessionId);
    } catch {
      // Cost is supplementary — a failed read leaves the meter on its estimate
      // rather than replacing the popover with an error.
      contextUsage = null;
    }
  }
  $effect(() => {
    if (continuedSessionId === null) return;
    const id = continuedSessionId;
    // Only the prop may retrigger this. `loadHistory` reads component state
    // before its first await (it closes an open file preview), and a tracked
    // read there would make every later change to that state reload the whole
    // conversation — which reads as the transcript flickering back to the top.
    untrack(() => {
      sessionId = id;
      void loadHistory(id);
    });
  });
  let nextId = 1;

  // Optional per-prompt options. Left unset they change nothing — the backend
  // applies its own defaults, exactly as if the option was never sent. They
  // live as compact controls at the bottom of the composer card.
  let modelProfile = $state("");
  let reasoningEffort = $state("");
  // One reactive view of the shared model store; refreshes live when the
  // Models page connects a provider or selects a model, without a remount.
  const profiles = $derived(chatProfiles());

  // The persisted selection (Models view / /model use). The default provider
  // option names it so the user can see what will actually serve the turn.
  const selectedProfile = $derived(profiles.find((p) => p.selected) ?? null);
  const activeProfile = $derived(profiles.find((p) => p.profile_id === modelProfile) ?? selectedProfile);
  const reasoningEfforts = $derived(
    activeProfile?.supports_reasoning === true && activeProfile.supports_reasoning_effort === true
      ? (activeProfile.reasoning_effort_values ?? [])
      : [],
  );
  let contextOpen = $state(false);
  let contextControlEl: HTMLDivElement | undefined = $state();
  // The backend will replace this conservative presentation estimate with
  // provider-reported usage when available. It is intentionally labeled.
  const estimatedContextTokens = $derived(
    Math.ceil(turns.reduce((count, turn) => count + turn.prompt.length + answerText(turn).length, 0) / 4),
  );

  // Attachments for the next prompt: workspace paths (resolved server-side
  // inside the workspace — anything outside fails closed — and included as
  // bounded, untrusted-labelled context) and uploaded images (validated
  // fail-closed server-side: media-type allowlist, 5 MB cap, magic-byte sniff).
  const MAX_ATTACHMENTS = 8;
  const IMAGE_MEDIA_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];
  const MAX_IMAGE_BYTES = 5_000_000;
  // Documents: extracted text is folded into context as bounded, untrusted data
  // (validated fail-closed server-side: allowlist, 32 MB cap, per-type sniff —
  // UTF-8 for text, %PDF- for PDF, OOXML zip for .docx/.xlsx; PDF and the
  // Office formats are extracted locally, no bytes leave the box).
  const DOCX_MEDIA_TYPE =
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  const XLSX_MEDIA_TYPE =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  const DOCUMENT_MEDIA_TYPES = [
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
    DOCX_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
  ];
  const DOCUMENT_EXTENSIONS = [".txt", ".md", ".markdown", ".csv", ".pdf", ".docx", ".xlsx"];
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
    if (lower.endsWith(".xlsx")) return XLSX_MEDIA_TYPE;
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
      attachError =
        "Only plain-text, Markdown, CSV, PDF, Word (.docx), or Excel (.xlsx) documents can be attached.";
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

  // ── File inspector (BUG-07) ───────────────────────────────────────────────
  // An attachment chip opens a view-only preview of the file it names. Nothing
  // is fetched until the chip is clicked, the preview is authorized by the
  // conversation that carried the file (a chip from another chat previews
  // nothing), and the pane offers no upload, edit, or download control.
  let inspecting = $state<{ attachmentId: string; filename: string } | null>(null);
  let preview = $state<AttachmentPreview | null>(null);
  let previewLoading = $state(false);
  let previewError = $state<string | null>(null);
  // Object URL for a preview served as bytes (a PDF or an image): neither an
  // <object> nor an <img> can send the bearer token, so the bytes are fetched
  // here and handed over as a blob. Revoked on close and whenever another file
  // is opened — a stale handle keeps the whole file alive in memory.
  let objectUrl = $state<string | null>(null);

  function releaseObjectUrl() {
    if (objectUrl === null) return;
    URL.revokeObjectURL?.(objectUrl);
    objectUrl = null;
  }

  async function openInspector(attachmentId: string, filename: string) {
    if (sessionId === null) return;
    const openedSession = sessionId;
    releaseObjectUrl();
    inspecting = { attachmentId, filename };
    preview = null;
    previewError = null;
    previewLoading = true;
    try {
      const result = await api.attachmentPreview(openedSession, attachmentId);
      // A second chip clicked while this was in flight wins; drop the late one
      // rather than overwriting the file the user is now looking at.
      if (inspecting?.attachmentId !== attachmentId) return;
      preview = result;
      // PDFs and images are the two kinds whose content is bytes rather than
      // JSON; everything else is already in the preview.
      const bytesPath = result.pdf_url ?? result.image_url;
      if (bytesPath !== null) {
        const url = await api.attachmentPreviewObjectUrl(bytesPath);
        if (inspecting?.attachmentId === attachmentId) {
          objectUrl = url;
        } else {
          URL.revokeObjectURL?.(url);
        }
      }
    } catch (e) {
      if (inspecting?.attachmentId !== attachmentId) return;
      previewError =
        e instanceof ApiError && e.status === 404
          ? "This file is no longer available in this conversation."
          : "Could not open this file.";
    } finally {
      if (inspecting?.attachmentId === attachmentId) previewLoading = false;
    }
  }

  function closeInspector() {
    releaseObjectUrl();
    inspecting = null;
    preview = null;
    previewError = null;
    previewLoading = false;
  }

  // Chips show only the file/folder name; the full workspace path stays in the
  // tooltip and is what actually rides the prompt.
  function fileName(path: string): string {
    const parts = path.split("/").filter(Boolean);
    return parts.length > 0 ? parts[parts.length - 1] : path;
  }

  let scrollEl: HTMLDivElement | undefined = $state();
  let composerCardEl: HTMLDivElement | undefined = $state();

  onMount(() => {
    void refreshModels();
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
    closeInspector();
    try {
      const detail = await api.session(id);
      turns = detail.turns.map((t) => restoredTurn(t, id));
      nextId = turns.length + 1;
      await restoreAttachmentChips(id);
      void scrollToEnd();
    } catch (e) {
      historyError =
        e instanceof ApiError ? `Could not load history (${e.status}).` : "Could not load history.";
    } finally {
      historyLoading = false;
    }
  }

  // A transcript persists prompt text, not the files that rode with it, so a
  // reloaded chat asks the server which attachments belong to which turn and
  // redraws the chips. Metadata only — no file content is fetched until a chip
  // is actually clicked.
  async function restoreAttachmentChips(id: string) {
    let files;
    try {
      files = (await api.sessionAttachments(id)).files;
    } catch {
      // Chips are a convenience; losing them must not cost the transcript.
      return;
    }
    const byTurn = new Map<string, ComposerAttachment[]>();
    for (const file of files) {
      const chips = byTurn.get(file.turn_id) ?? [];
      chips.push({
        kind: file.kind === "image" ? "image" : "document",
        label: file.filename,
        detail: `${file.filename} (${file.media_type}, ${file.byte_size} bytes)`,
        attachmentId: file.attachment_id,
      });
      byTurn.set(file.turn_id, chips);
    }
    if (byTurn.size === 0) return;
    turns = turns.map((turn) => {
      const chips = byTurn.get(turn.response?.turn_id ?? "");
      return chips === undefined ? turn : { ...turn, attachments: chips };
    });
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
          ...(reasoningEfforts.includes(reasoningEffort) ? { reasoning_effort: reasoningEffort } : {}),
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
        },
        (event) => {
          if (event.kind === "final" && event.response !== null) {
            turn.response = event.response;
            sessionId = event.response.session_id;
            void applyPendingProject();
            // A file written by this turn is stored as a session-authorized
            // attachment before the final SSE event reaches us. Refreshing the
            // chips here makes the generated file immediately openable in the
            // existing right-hand inspector, without exposing the workspace.
            void restoreAttachmentChips(event.response.session_id);
            if (contextOpen) void refreshContextUsage();
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

  function onWindowClick(event: MouseEvent) {
    if (contextOpen && contextControlEl && !contextControlEl.contains(event.target as Node)) {
      contextOpen = false;
    }
    if (showAttach && composerCardEl && !composerCardEl.contains(event.target as Node)) {
      showAttach = false;
    }
  }

  async function onProjectPicked(value: string) {
    projectId = value;
    projectNotice = null;
    const target = value === "" ? null : value;
    if (sessionId === null) {
      pendingProjectId = target;
      projectNotice = target === null ? "This chat will stay outside every project." : "This chat will be filed there as soon as it starts.";
      return;
    }
    await moveSession(target);
  }

  async function applyPendingProject() {
    if (sessionId === null || pendingProjectId === null) return;
    const target = pendingProjectId;
    pendingProjectId = null;
    await moveSession(target);
  }

  async function moveSession(target: string | null) {
    if (sessionId === null) return;
    try {
      await api.setSessionProject(sessionId, target);
      projectNotice =
        target === null
          ? "Moved out of every project."
          : `Filed under ${projects?.projects.find((project) => project.project_id === target)?.name ?? "the project"}.`;
      onProjectsChanged?.();
    } catch (error) {
      projectNotice = error instanceof ApiError ? `Could not move this chat (${error.status}).` : "Could not move this chat.";
    }
  }

  async function copyAnswer(turn: ChatTurn) {
    // The clipboard is not always available (an insecure origin, or a denied
    // permission). Say so rather than failing silently — a copy button that
    // does nothing and reports nothing is worse than no copy button.
    try {
      await navigator.clipboard.writeText(answerText(turn));
      exportNotice = "Response copied.";
    } catch {
      exportNotice = "Could not copy — your browser blocked clipboard access.";
    }
  }
</script>

<svelte:window onclick={onWindowClick} />

<!-- Split shell: the conversation, plus the file inspector when one is open.
     The chat column keeps its own indentation so opening a file stays a
     wrapper, not a reflow of the whole transcript's markup. -->
<div class="chat-layout" class:with-inspector={inspecting !== null} class:with-rail={backgroundWorkOpen}>
<div class="chat">
  <header class="chat-header">
    <div class="header-actions">
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        onclick={newConversation}
        disabled={streaming || turns.length === 0}
      >
        New chat
      </button>
      <button
        type="button"
        class="btn btn-ghost btn-sm rail-toggle"
        onclick={() => (backgroundWorkOpen = !backgroundWorkOpen)}
        aria-expanded={backgroundWorkOpen}
        aria-controls="chat-background-work"
        aria-label="Background work"
        title="Background work"
      >
        <Icon name="panel" size={15} />
      </button>
    </div>
  </header>
  {#if exportNotice}<span class="export-notice" role="status" aria-live="polite">{exportNotice}</span>{/if}
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
                {#if a.attachmentId !== undefined && sessionId !== null}
                  <!-- Uploaded files open in the inspector. A workspace-path
                       chip has no stored bytes to show, so it stays inert
                       rather than pretending to be clickable. -->
                  <button
                    type="button"
                    class="attach-chip attach-chip-button"
                    title={a.detail}
                    aria-expanded={inspecting?.attachmentId === a.attachmentId}
                    onclick={() => void openInspector(a.attachmentId as string, a.label)}
                  >
                    <Icon name="file" size={13} />
                    {a.label}
                  </button>
                {:else}
                  <span class="attach-chip" title={a.detail}>
                    <Icon name="file" size={13} />
                    {a.label}
                  </span>
                {/if}
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
                  Review it in the Approvals inbox.
                  {turn.response!.approval!.expected_effect ||
                    "Recording a decision never executes the action."}
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
            <div class="message-bubble message-bubble-raiker">
              <Markdown text={answer} />
            </div>
            {#if !turn.streaming}
              <button type="button" class="copy-message" onclick={() => void copyAnswer(turn)}>Copy response</button>
            {/if}
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
    <div class="composer-card" bind:this={composerCardEl}>
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
      <div class="composer-upper">
        <textarea
          id="prompt-input"
          class="prompt-input"
          bind:value={promptText}
          onkeydown={onKeydown}
          rows="2"
          placeholder="How can I help you today?"
          title="Enter to send, Shift+Enter for a new line"
          spellcheck="true"
          lang="en-US"
          disabled={streaming}
        ></textarea>
        <div class="upper-controls">
          <ModelPicker bind:value={modelProfile} {profiles} {selectedProfile} disabled={streaming} />
          {#if reasoningEfforts.length > 0}
            <select
              class="bar-select"
              bind:value={reasoningEffort}
              disabled={streaming}
              aria-label="Thinking effort"
              title="Thinking effort for this model"
            >
              <option value="">Thinking: default</option>
              {#each reasoningEfforts as effort (effort)}
                <option value={effort}>{effort}</option>
              {/each}
            </select>
          {/if}
        </div>
      </div>

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
            title="Upload a document (plain text/Markdown/CSV/PDF/Word .docx/Excel .xlsx, 32 MB max). Its extracted text is added to context as untrusted data."
          >
            {uploading ? "Uploading…" : "Document…"}
          </label>
        </div>
        {#if attachError !== null}
          <p class="error-line" role="alert">{attachError}</p>
        {/if}
      {/if}

      <div class="composer-bar">
        <div class="bar-left">
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
          {#if projects && projects.projects.length > 0}
            <label class="composer-scope">
              <span class="sr-only">Project for this chat</span>
              <Icon name="folder" size={14} />
              <select
                class="bar-select"
                value={projectId}
                aria-label="Project for this chat"
                onchange={(event) => void onProjectPicked((event.currentTarget as HTMLSelectElement).value)}
              >
                <option value="">Project or folder</option>
                {#each projects.projects as project (project.project_id)}
                  <option value={project.project_id}>{project.name}</option>
                {/each}
              </select>
            </label>
          {/if}
          <ApprovalModeControl />
        </div>

        <div class="bar-right">
          <div class="context-control" bind:this={contextControlEl}>
            <button
              type="button"
              class="context-trigger"
              aria-label="Context window"
              aria-expanded={contextOpen}
              title="Context window"
              onclick={() => { contextOpen = !contextOpen; if (contextOpen) void refreshContextUsage(); }}
            >
              <ContextRing
                usedTokens={estimatedContextTokens}
                contextWindowTokens={activeProfile?.context_window_tokens ?? null}
                usage={contextUsage}
              />
            </button>
            {#if contextOpen}
              <ContextMeterPopover
                usedTokens={estimatedContextTokens}
                contextWindowTokens={activeProfile?.context_window_tokens ?? null}
                estimated={true}
                usage={contextUsage}
              />
            {/if}
          </div>

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
      <p class="shortcut-hint">Enter sends · Shift+Enter adds a line</p>
    </div>
  </form>
  {#if projectNotice}<p class="project-notice" role="status">{projectNotice}</p>{/if}
</div>
  {#if backgroundWorkOpen}
    <div id="chat-background-work" class="rail-slot">
      <BuildSidePanel
        projectId={projectId || projects?.active_project_id || null}
        {projects}
        onclose={() => (backgroundWorkOpen = false)}
      />
    </div>
  {/if}

{#if inspecting !== null}
  <FileInspector
    preview={preview}
    filename={inspecting.filename}
    loading={previewLoading}
    error={previewError}
    objectUrl={objectUrl}
    onclose={closeInspector}
  />
{/if}
</div>

<style>
  /* A chat column is as tall as the room the shell gives it — not as tall as
     its transcript. `height: 100%` cannot express that here (the page wrapper
     is auto-height, so the percentage resolved to `auto` and the column simply
     grew), which pushed the composer off the bottom of the screen and handed
     the scroll to the shell. Sizing from `--content-h` makes the height
     definite, so the transcript scrolls inside itself and the composer stays
     where you left it. */
  .chat {
    display: flex;
    flex-direction: column;
    height: var(--content-h);
    min-height: 24rem;
    /* The conversation column must be allowed to shrink inside the grid, or an
       open inspector pushes the composer off the right edge instead of
       narrowing the transcript. */
    min-width: 0;
  }
  /* Same header pattern as Build: a thin bar above the transcript that holds
     the background-work rail toggle, so the control lives in the same place on
     both conversation surfaces rather than buried in the composer. */
  .chat-header {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
  }
  /* Chat owns the same local two-column work layout as Build: transcript and
     composer on the left, background work on the right. The inspector is a
     third desktop column only while a file is open. */
  .chat-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-4);
    align-items: stretch;
  }
  @media (min-width: 64rem) {
    .chat-layout.with-rail {
      grid-template-columns: minmax(0, 1fr) 21rem;
    }
    .chat-layout.with-inspector {
      grid-template-columns: minmax(0, 1fr) minmax(20rem, 26rem);
    }
    .chat-layout.with-rail.with-inspector {
      grid-template-columns: minmax(0, 1fr) 21rem minmax(20rem, 26rem);
    }
    .chat-layout.with-inspector .chat {
      margin: 0;
      max-width: none;
    }
  }
  .rail-slot {
    min-height: 0;
    display: flex;
  }
  .rail-slot > :global(*) {
    flex: 1;
    min-height: 0;
  }
  @media (max-width: 63.9rem) {
    .chat-layout,
    .chat-layout.with-rail,
    .chat-layout.with-inspector,
    .chat-layout.with-rail.with-inspector {
      grid-template-columns: minmax(0, 1fr);
    }
    .chat {
      height: auto;
      min-height: 0;
    }
    .thread {
      overflow-y: visible;
    }
    .rail-slot {
      max-height: 32rem;
    }
    .composer-upper {
      flex-direction: column;
    }
    .upper-controls {
      flex-direction: row;
      align-items: center;
      flex-wrap: wrap;
    }
  }
  /* On narrow screens the model picker wraps under the textarea even when the
     page layout hasn't hit the split-view breakpoint yet. */
  @media (max-width: 30rem) {
    .composer-upper {
      flex-direction: column;
    }
    .upper-controls {
      flex-direction: row;
      align-items: center;
      flex-wrap: wrap;
    }
  }
  /* Below the split breakpoint the inspector is a sheet over the conversation
     (see FileInspector.svelte), so the grid stays single-column. */
  .thread {
    flex: 1;
    /* Without this the thread refuses to shrink below its content and never
       becomes a scroller. */
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding-bottom: var(--space-4);
  }
  .export-notice {
    color: var(--text-2);
    font-size: .78rem;
    order: -1;
    margin-right: auto;
  }
  .copy-message {
    background: transparent;
    border: 0;
    color: var(--text-3);
    cursor: pointer;
    font: inherit;
    font-size: .75rem;
    padding: .3rem .2rem;
  }
  .copy-message:hover { color: var(--text-1); }

  @media print {
    :global(.sidebar), :global(.topbar), :global(.skip-link), .composer,
    .copy-message, :global(.file-inspector) { display: none !important; }
    :global(.app-shell), :global(.app-main), :global(.content), :global(.responsive-page),
    .chat-layout, .chat { display: block !important; height: auto !important; max-width: none !important; }
    .thread { display: block; overflow: visible; }
    .turn { break-inside: avoid; margin-bottom: 1.5rem; }
    .message-group { max-width: none; }
    .message-bubble { box-shadow: none; border: 1px solid #bbb; }
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
  .project-notice {
    margin: var(--space-2) 0 0;
    color: var(--text-3);
    font-size: .75rem;
  }
  .shortcut-hint {
    color: var(--text-3);
    font-size: 0.72rem;
    line-height: 1.35;
    margin: 0;
    text-align: right;
  }
  /* One clean card: prompt on top, "+" and the per-turn controls at the bottom. */
  .composer-card {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-1);
    /* Even padding all round: the old tighter bottom made the control bar look
       cropped against the card edge. */
    padding: 0.75rem 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .composer-card:focus-within {
    border-color: var(--accent-border);
  }
  /* Upper area: textarea on the left, model + effort on the right. The
     controls column stays top-aligned so it doesn't drift as the textarea
     grows. Below the split-view breakpoint the column wraps under the
     textarea rather than squeezing it. */
  .composer-upper {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }
  .composer-upper .prompt-input {
    flex: 1;
    min-width: 0;
  }
  .upper-controls {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.3rem;
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
    gap: 0.5rem 0.75rem;
    border-top: 1px solid var(--border);
    padding-top: 0.55rem;
    flex-wrap: wrap;
  }
  .bar-left {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    flex-wrap: wrap;
    min-width: 0;
  }
  .composer-scope {
    display: inline-flex;
    align-items: center;
    gap: .25rem;
    min-width: 0;
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
  /* Per-turn settings sit on the right of the bar, ending in the send action. */
  .bar-right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.3rem;
    flex-wrap: wrap;
    min-width: 0;
    justify-content: flex-end;
  }
  /* Each setting is a pill so a control reads as a control. Previously they
     were borderless and shared the body weight, which ran the whole bar
     together as one line of prose; and a fixed max-width stretched the select
     so its chevron floated far from its own label. */
  .bar-select {
    border: 1px solid var(--neutral-border);
    background: var(--surface);
    color: var(--text-2);
    font-size: 0.76rem;
    font-weight: 600;
    padding: 0.2rem 0.45rem;
    border-radius: var(--r-pill);
    width: auto;
    max-width: 11rem;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .bar-select:hover:not(:disabled) {
    border-color: var(--accent-border);
    color: var(--text-1);
  }
  .bar-select:disabled {
    opacity: 0.6;
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
  /* A chip that opens the inspector is a real button: it looks identical to the
     inert one, but it is focusable, keyboard-operable, and says so on hover. */
  .attach-chip-button {
    cursor: pointer;
    font-family: inherit;
  }
  .attach-chip-button:hover,
  .attach-chip-button:focus-visible {
    border-color: var(--border-strong);
    color: var(--text-1);
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
  .context-control { position: relative; }
  .context-trigger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.7rem;
    height: 1.7rem;
    padding: 0;
    border: 1px solid var(--neutral-border);
    border-radius: 50%;
    background: var(--surface);
    color: var(--text-2);
    cursor: pointer;
  }
  .context-trigger:hover { border-color: var(--accent-border); color: var(--accent); }
  .context-trigger:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
  @media (max-width: 720px) {
    .message-group {
      max-width: 88%;
    }
  }
  /* Narrow: the settings stop competing with the left actions for one line and
     take a row of their own, so nothing wraps into a ragged half-row with the
     send button stranded from its group. */
  @media (max-width: 34rem) {
    .bar-right {
      margin-left: 0;
      width: 100%;
      justify-content: flex-start;
    }
    .send {
      margin-left: auto;
    }
  }
</style>
