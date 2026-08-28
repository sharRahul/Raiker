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
  import ModelReadinessStrip from "../components/ModelReadinessStrip.svelte";
  import BuildSidePanel from "../components/BuildSidePanel.svelte";
  import ExportConversationDialog from "../components/ExportConversationDialog.svelte";
  import { api, ApiError, streamPrompt, streamResumeAfterApproval } from "../api";
  import { rememberSurfaceModel, surfaceModel } from "../surfaceModel.svelte";
  import {
    classifyResumeFailure,
    watchForResumableTurns,
    type ResumableTurn,
    type ResumeWatcher,
  } from "../approvalResume";
  import type {
    AgentPlan,
    AgentResponse,
    AttachmentPreview,
    ContextUsage,
    ConversationBranchOrigin,
    ProjectsList,
    SessionDetail,
    SourceExcerptView,
    StreamEvent,
    TurnSourceView,
  } from "../apiTypes";
  import AttachmentCard from "../components/AttachmentCard.svelte";
  import ComposerAttach from "../components/ComposerAttach.svelte";
  import ComposerAttachPanel from "../components/ComposerAttachPanel.svelte";
  import ComposerChips from "../components/ComposerChips.svelte";
  import PlanChecklist from "../components/PlanChecklist.svelte";
  import ReasoningBlock from "../components/ReasoningBlock.svelte";
  import ToolActivity from "../components/ToolActivity.svelte";
  import SkillLinkNotice from "../components/SkillLinkNotice.svelte";
  import SourceChips from "../components/SourceChips.svelte";
  import TurnControl from "../components/TurnControl.svelte";
  import { createAttachmentStore, type ComposerAttachment } from "../composerAttachments.svelte";
  import ComposerMenu, { type MenuItem } from "../components/ComposerMenu.svelte";
  import MessageActions from "../components/MessageActions.svelte";
  import VoiceDictationControl, { type VoiceDictationHandle } from "../components/VoiceDictationControl.svelte";
  import ReadAloudButton from "../components/ReadAloudButton.svelte";
  import { requestSchedule } from "../scheduleHandoff";
  import ShortcutSheet from "../components/ShortcutSheet.svelte";
  import {
    applyMention,
    autoGrow,
    matchCommands,
    mentionAt,
    slashFragment,
    stripSlashToken,
    type SlashCommand,
  } from "../composerCommands";
  import { collectText } from "../turnPhases";
  import { humanize, relativeTime } from "../format";
  import { hasSteps, planFromEvent } from "../agentPlan";
  import { collectReasoning, hasRunningTool, toolActivity } from "../chatPresentation";
  import {
    citedSourceIds,
    renderableCitations,
    sentenceAround,
    sourcesForTurn,
  } from "../citations";
  import { chatProfiles, refreshModels } from "../models.svelte";
  import { blocksSending, openModelSetup, readinessForSelection } from "../modelReadiness.svelte";
  import {
    audioSessionCoordinator,
    inputModeForDraft,
    speechLanguagePreference,
    type SpeechLanguage,
  } from "../voice";

  interface ChatTurn {
    id: number;
    prompt: string;
    attachments: ComposerAttachment[];
    events: StreamEvent[];
    response: AgentResponse | null;
    streaming: boolean;
    error: string | null;
    // BUG-24 — how a parked turn is presented while its approval is outstanding
    // and once a decision lands, wherever that decision was made.
    //   "waiting"   — Waiting for approval
    //   "continuing"— Approved (or rejected) elsewhere; the turn is resuming here
    //   "elsewhere" — another tab won the race and is streaming the continuation
    resumeState?: "waiting" | "continuing" | "elsewhere" | null;
    resumeNote?: string | null;
    // BUG-215 — a re-opened turn rebuilds from stored rows, not from the stream
    // it was watched on, so its working has to come from the record or be
    // accounted for. `retainedReasoning` is the kept text; `reasoningChars` is
    // how much there was, which stays true whether it was kept or not.
    retainedReasoning?: string | null;
    reasoningChars?: number;
  }

  let {
    sessionId: continuedSessionId = null,
    projects = null,
    onProjectsChanged,
    // Chat keeps its transcript and its unsent draft when the owner navigates
    // away — the view is hidden, not unmounted — so it has to be told when it
    // stops being the surface on screen. Dictation and read-aloud are the
    // reason: an unmount hook never fires here, so without this the microphone
    // would keep listening from a hidden page.
    visible = true,
  }: {
    sessionId?: string | null;
    projects?: ProjectsList | null;
    onProjectsChanged?: () => void;
    visible?: boolean;
  } = $props();

  // C16 — leaving the surface ends the turn's audio.
  //
  // Chat and Build are kept mounted across route visits, so the unmount cleanup
  // that was supposed to carry the `route` reason never ran on an ordinary
  // navigation. A microphone that stays live behind a hidden composer, with its
  // only Stop control hidden along with it, is exactly the invisible capture the
  // dictation design exists to prevent — so the audio owner is released the
  // moment this surface stops being the one on screen. Nothing is discarded:
  // finalized words stay in the draft, exactly as pressing Done would leave them.
  $effect(() => {
    if (!visible) audioSessionCoordinator.stopAll("route");
  });
  let promptText = $state("");
  let speechLanguage = $state<SpeechLanguage>("auto");
  let voiceControl = $state<VoiceDictationHandle | undefined>();
  let voiceDictated = $state(false);
  let voiceTypedBefore = $state(false);
  let voiceEditedAfter = $state(false);
  let voiceProvenanceSnapshot = { dictated: false, typedBefore: false, editedAfter: false };
  let promptSelectionStart = $state(0);
  let promptSelectionEnd = $state(0);
  let userName = $state("there");
  let turns = $state<ChatTurn[]>([]);
  // What the last copy action did. Shown, not only announced: a copy that
  // reports nothing leaves the owner guessing whether it worked.
  let exportNotice = $state<string | null>(null);
  let streaming = $state(false);
  // B17/C13 — whether the owner has already asked this turn to stop. Held here
  // rather than inside the control so a new turn always starts un-stopped.
  let stopping = $state(false);
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
      void loadBranchOrigin(id);
    });
  });
  let nextId = 1;

  // Optional per-prompt options. Left unset they change nothing — the backend
  // applies its own defaults, exactly as if the option was never sent. They
  // live as compact controls at the bottom of the composer card.
  let modelProfile = $state("");
  let model = $state("");
  let reasoningEffort = $state("");
  // One reactive view of the shared model store; refreshes live when the
  // Models page connects a provider or selects a model, without a remount.
  const profiles = $derived(chatProfiles());

  // The persisted selection (Models view / /model use). The default provider
  // option names it so the user can see what will actually serve the turn.
  const selectedProfile = $derived(profiles.find((p) => p.selected) ?? null);
  const activeProfile = $derived(
    profiles.find((p) => p.profile_id === modelProfile && (!model || p.model === model)) ?? selectedProfile,
  );
  const modelReadiness = $derived(readinessForSelection(activeProfile));
  // BUG-238 — a stale observation never blocks: the server re-checks it
  // before admitting the turn, so the only thing that stops a send is a
  // model problem the owner can actually fix.
  const modelBlocked = $derived(blocksSending(modelReadiness));
  // BUG-207 slice B — a provider declares reasoning as an *effort* (OpenAI:
  // low/medium/high) or as a *mode* (Anthropic: adaptive). Offering only the
  // first meant the provider that ships in the box had no reasoning control at
  // all, which is why the extended thinking the runtime asks for was never
  // asked for. Both are offered, and neither is invented: an empty list means
  // this profile declares no reasoning setting and the control is absent.
  const reasoningEfforts = $derived(
    activeProfile?.supports_reasoning === true
      ? [
          ...(activeProfile.supports_reasoning_effort === true
            ? (activeProfile.reasoning_effort_values ?? [])
            : []),
          ...(activeProfile.reasoning_modes ?? []),
        ]
      : [],
  );
  let contextOpen = $state(false);
  let contextControlEl: HTMLDivElement | undefined = $state();
  // The backend will replace this conservative presentation estimate with
  // provider-reported usage when available. It is intentionally labeled.
  const estimatedContextTokens = $derived(
    Math.ceil(turns.reduce((count, turn) => count + turn.prompt.length + answerText(turn).length, 0) / 4),
  );

  // Attachments for the next prompt. The rules, the limits and the upload path
  // are shared with Build (`composerAttachments.svelte.ts`) so a file behaves
  // identically in both conversations rather than only working in this one.
  const attachStore = createAttachmentStore();
  let attachControl = $state<ComposerAttach | undefined>();
  let attachOpen = $state(false);

  // Thumbnails for images already in the transcript, keyed by attachment id.
  //
  // An image the owner just picked shows the local file back and costs nothing.
  // One restored from a reload has no local copy, so its bytes are fetched once
  // — through the same session-authorised preview route the inspector uses,
  // with the bearer token an <img> cannot send — and reused for every render.
  // Failure is silent by design: the card falls back to its type glyph, which
  // is a worse thumbnail and a perfectly good attachment.
  let thumbnails = $state<Record<string, string>>({});
  const resolvingThumbnails = new Set<string>();

  async function resolveThumbnails(attachments: ComposerAttachment[]) {
    for (const attachment of attachments) {
      const id = attachment.attachmentId;
      if (
        attachment.kind !== "image" ||
        id === undefined ||
        sessionId === null ||
        attachment.previewUrl !== undefined ||
        thumbnails[id] !== undefined ||
        resolvingThumbnails.has(id)
      ) {
        continue;
      }
      resolvingThumbnails.add(id);
      try {
        const preview = await api.attachmentPreview(sessionId, id);
        if (preview.image_url === null) continue;
        thumbnails = {
          ...thumbnails,
          [id]: await api.attachmentPreviewObjectUrl(preview.image_url),
        };
      } catch {
        // The card shows its type glyph instead. Nothing is claimed that failed.
      }
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
    inspectorSource = null;
    sourceLoading = false;
    openSourceId = null;
    openSourceTurnId = null;
    downloadState = "idle";
    downloadError = null;
  }

  // BUG-27 — where a generated file came from. Resolved on demand, because the
  // answer depends on what is still readable *now*, not on what was true when
  // the file was written.
  let inspectorSource = $state<SourceExcerptView | null>(null);
  let sourceLoading = $state(false);

  // ── C6/C4: the turn source ledger ─────────────────────────────────────────
  //
  // What each turn in this conversation actually read. Fetched as labels only —
  // opening a chip is what fetches the passage behind it — and refreshed
  // whenever a turn lands, so a citation the model just wrote has something to
  // resolve against by the time the answer finishes rendering.
  let turnSources = $state<TurnSourceView[]>([]);
  // Which source is open, as (turn, id): ids restart at `s1` in every turn, so
  // the id alone would mark a chip open under every turn that happens to have one.
  let openSourceId = $state<string | null>(null);
  let openSourceTurnId = $state<string | null>(null);

  async function refreshTurnSources(id: string) {
    try {
      turnSources = (await api.sessionSources(id)).sources;
    } catch {
      // The ledger is provenance for an answer that already arrived. Losing it
      // must not cost the transcript, so the chips simply do not appear.
      turnSources = [];
    }
  }

  /**
   * Open one cited source at the passage the turn used (C4).
   *
   * An attachment is opened in the file pane *and* marked at its passage, so
   * "which document" and "which part of it" are the same action. Everything
   * else — a web page, an email, a connector response — has no second copy on
   * this machine, so what is shown is the exact text that reached the model.
   */
  async function openSource(source: TurnSourceView, quote = "") {
    if (sessionId === null || !source.openable) return;
    const opened = sessionId;
    openSourceId = source.source_id;
    openSourceTurnId = source.turn_id;
    if (source.attachment_id !== "") {
      await openInspector(source.attachment_id, source.title);
    } else {
      releaseObjectUrl();
      inspecting = { attachmentId: "", filename: source.title };
      preview = null;
      previewError = null;
      previewLoading = false;
    }
    inspectorSource = null;
    sourceLoading = true;
    try {
      const resolved = await api.turnSourceExcerpt(opened, source.turn_id, source.source_id, quote);
      if (openSourceId === source.source_id) inspectorSource = resolved;
    } catch {
      if (openSourceId === source.source_id) {
        inspectorSource = {
          status: "source_deleted",
          kind: source.kind,
          title: source.title,
          excerpt: "",
          highlight_start: -1,
          highlight_length: 0,
          session_id: opened,
          turn_id: source.turn_id,
          attachment_id: source.attachment_id,
          truncated: false,
          resolution_method: "",
        };
      }
    } finally {
      if (openSourceId === source.source_id) sourceLoading = false;
    }
  }

  /**
   * A `[s1]` chip inside the answer opens the same source the strip does — and,
   * unlike the strip, it knows which sentence rests on it, so the pane can open
   * at that part of the source rather than at the whole of it.
   */
  function openSourceById(turnId: string, sourceId: string, answer: string) {
    const match = turnSources.find(
      (source) => source.turn_id === turnId && source.source_id === sourceId,
    );
    if (match !== undefined) void openSource(match, sentenceAround(answer, sourceId));
  }

  async function openGeneratedFile(attachmentId: string, label: string) {
    await openInspector(attachmentId, label);
    if (sessionId === null || inspecting?.attachmentId !== attachmentId) return;
    sourceLoading = true;
    try {
      const resolved = await api.attachmentProvenance(sessionId, attachmentId);
      if (inspecting?.attachmentId === attachmentId) inspectorSource = resolved;
    } catch {
      // Provenance is supplementary to the file itself. A failure leaves the
      // preview intact and simply shows no source panel rather than replacing a
      // readable document with an error.
      if (inspecting?.attachmentId === attachmentId) inspectorSource = null;
    } finally {
      if (inspecting?.attachmentId === attachmentId) sourceLoading = false;
    }
  }

  // BUG-28 — the file itself, saved where the owner wants it. Distinct from
  // Preview (which reads it here) and from conversation export (which writes a
  // transcript). Every outcome is stated: a refusal, an expired retention, and
  // an unreachable runtime all say which one happened.
  let downloadState = $state<"idle" | "working" | "done">("idle");
  let downloadError = $state<string | null>(null);

  /** Download straight from an artifact card, without opening the pane first. */
  async function downloadArtifact(attachmentId: string, label: string) {
    if (sessionId === null) return;
    try {
      const blob = await api.attachmentDownload(sessionId, attachmentId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = label || "download";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      artifactNotice = null;
    } catch (e) {
      artifactNotice = {
        attachmentId,
        text:
          e instanceof ApiError && e.status === 404
            ? `“${label}” is no longer kept in this conversation, so it cannot be downloaded.`
            : `Could not download “${label}”.`,
      };
    }
  }
  // Scoped to the card that failed: a refusal on one artifact must not appear
  // under every other turn that happens to have produced a file.
  let artifactNotice = $state<{ attachmentId: string; text: string } | null>(null);

  async function downloadInspected() {
    if (inspecting === null || sessionId === null) return;
    const { attachmentId, filename } = inspecting;
    downloadState = "working";
    downloadError = null;
    try {
      const blob = await api.attachmentDownload(sessionId, attachmentId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = preview?.filename || filename || "download";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      downloadState = "done";
    } catch (e) {
      downloadState = "idle";
      downloadError =
        e instanceof ApiError && e.status === 404
          ? "This file is no longer kept in this conversation, so it cannot be downloaded."
          : e instanceof ApiError && e.status === 403
            ? "This account is not permitted to download this file."
            : "Could not download this file.";
    }
  }

  // Chips show only the file/folder name; the full workspace path stays in the
  // tooltip and is what actually rides the prompt.
  let scrollEl: HTMLDivElement | undefined = $state();

  onMount(() => {
    void refreshModels();
    // Chat starts on the model Chat was last set to, not on whatever the global
    // default happens to be. An explicit per-turn choice still overrides it.
    void surfaceModel("chat").then((remembered) => {
      if (remembered === null || modelProfile) return;
      modelProfile = remembered.profileId;
      model = remembered.model;
    });
    void api.settings().then((view) => {
      userName = view.status.username || "there";
      speechLanguage = speechLanguagePreference(view.settings["general.speech_language"]);
    }).catch(() => {});
    // The Workbench composer hands its text to this mounted chat rather than
    // sending a prompt of its own. There is one governed send path, and it is
    // `submit()` below — the Workbench never talks to the API directly, so a
    // prompt started there is identical to one typed here.
    const onCompose = (event: Event) => {
      const detail = (event as CustomEvent<{
        text: string;
        sessionId: string | null;
        profileId?: string;
        model?: string;
        attachments?: ComposerAttachment[];
      }>).detail;
      if (detail === undefined || detail.text.trim() === "") return;
      if (detail.sessionId !== null && detail.sessionId !== sessionId) {
        sessionId = detail.sessionId;
        void loadHistory(detail.sessionId);
      }
      modelProfile = detail.profileId ?? "";
      model = detail.model ?? "";
      // Files picked in the Workbench composer ride the handoff, so starting
      // work there is genuinely the same act as starting it here rather than a
      // reduced version of it. They are already uploaded and governed; only
      // their references cross.
      if (detail.attachments?.length) attachStore.set([...detail.attachments]);
      promptText = detail.text;
      void submit();
    };
    window.addEventListener("raiker:compose", onCompose);
    return () => {
      window.removeEventListener("raiker:compose", onCompose);
      audioSessionCoordinator.stopAll("route");
    };
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
      const parked = new Map((detail.parked_approvals ?? []).map((approval) => [approval.turn_id, approval]));
      turns = detail.turns.map((t) => restoredTurn(t, id, parked.get(t.turn_id)));
      nextId = turns.length + 1;
      await restoreAttachmentChips(id);
      await refreshTurnSources(id);
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
        source: file.source,
        createdAt: file.created_at,
        mediaType: file.media_type,
        byteSize: file.byte_size,
      });
      byTurn.set(file.turn_id, chips);
    }
    turns = turns.map((turn) => {
      const chips = byTurn.get(turn.response?.turn_id ?? "");
      if (chips === undefined) return turn;
      const existing = turn.attachments.filter(
        (a) => a.source !== "generated" || a.attachmentId === undefined,
      );
      const merged = [...existing, ...chips.filter((c) => !existing.some((e) => e.attachmentId === c.attachmentId))];
      return { ...turn, attachments: merged };
    });
    void resolveThumbnails(turns.flatMap((turn) => turn.attachments));
  }

  function restoredTurn(
    t: SessionDetail["turns"][number],
    sessionId: string,
    parked?: NonNullable<SessionDetail["parked_approvals"]>[number],
  ): ChatTurn {
    return {
      id: nextId++,
      prompt: t.prompt_text ?? "",
      attachments: [],
      // Backlog #25 — a reopened turn used to show the answer and nothing about
      // how it was reached, because the tool rows only ever existed on the
      // stream it was watched on. The server rebuilds them from the durable
      // record in the same payload shape a live event carries, so they enter
      // here as events and `toolActivity` assembles them exactly as it does
      // live — including merging with a later live event for the same call,
      // which is what a parked turn resumed in this tab produces.
      events: (t.tool_rows ?? []).map((payload) => ({
        kind: "tool" as const,
        text: "",
        event_type: "tool_restored",
        payload,
        response: null,
      })),
      response: {
        request_id: "",
        session_id: sessionId,
        turn_id: t.turn_id,
        status: t.status,
        message: t.summary ?? "",
        events_path: null,
        checkpoint_path: null,
        approval: parked ? {
          action_id: "",
          approval_id: parked.approval_id,
          tool_name: parked.tool_name,
          arguments: {},
          risk_level: "governed",
          reasons: [],
          message: `${humanize(parked.tool_name)} is waiting for your approval.`,
          expected_effect: "The same parked turn continues after your decision.",
          resumable: true,
        } : null,
        last_event_id: null,
      },
      streaming: false,
      error: null,
      resumeState: parked ? "waiting" : null,
      resumeNote: null,
      retainedReasoning: t.reasoning ?? null,
      reasoningChars: t.reasoning_chars ?? 0,
    };
  }

  function answerText(turn: ChatTurn): string {
    const streamed = collectText(turn.events);
    if (streamed.trim() !== "") return streamed;
    return turn.response?.message ?? "";
  }

  async function submit() {
    if (voiceControl?.active()) {
      voiceControl.done();
      promptEl?.focus();
      return;
    }
    const text = promptText.trim();
    if (text === "" || modelBlocked || streaming || attachStore.uploading) return;
    const voiceState = {
      dictated: voiceDictated,
      typedBefore: voiceTypedBefore,
      editedAfter: voiceEditedAfter,
    };
    const inputMode = inputModeForDraft(voiceState);
    audioSessionCoordinator.stopAll("submit");
    const sentAttachments = attachStore.take();
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
    resetVoiceProvenance();
    // B19 — a box that grew to hold a long prompt has to shrink back when the
    // prompt leaves it, or the composer keeps the height of the longest thing
    // ever typed into it.
    menuKind = "none";
    queueMicrotask(() => autoGrow(promptEl ?? null));
    attachStore.clear();
    streaming = true;
    stopping = false;
    void scrollToEnd();
    try {
      await streamPrompt(
        {
          text,
          input_mode: inputMode,
          surface: "chat",
          session_id: sessionId ?? undefined,
          model_profile: modelProfile || undefined,
          model: model || undefined,
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
            // C6 — the citation markers this answer just wrote need the ledger
            // they resolve against, so it is refreshed with the turn.
            void refreshTurnSources(event.response.session_id);
            if (contextOpen) void refreshContextUsage();
            if (plan === null) void loadPlan();
            window.dispatchEvent(new Event("raiker:chats-changed"));
          } else if (event.kind === "error") {
            turn.error = event.text || "An error occurred.";
            turn.events = [...turn.events, event];
          } else {
            turn.events = [...turn.events, event];
            const streamed = planFromEvent(event);
            if (streamed !== null) plan = streamed;
          }
          // B17/C13 — a brand-new chat learns its own session id from the first
          // streamed chunk, which is what lets Stop and steer reach this very
          // turn instead of only the ones after it.
          if (sessionId === null && typeof event.session_id === "string" && event.session_id !== "") {
            sessionId = event.session_id;
          }
          void scrollToEnd();
        },
      );
    } catch (e) {
      if (e instanceof ApiError && e.reasonCode === "model_not_ready") {
        turns = turns.filter((candidate) => candidate !== turn);
        promptText = text;
        voiceDictated = voiceState.dictated;
        voiceTypedBefore = voiceState.typedBefore;
        voiceEditedAfter = voiceState.editedAfter;
        attachStore.set(sentAttachments);
        await refreshModels();
        openModelSetup(activeProfile);
        return;
      }
      turn.error =
        e instanceof ApiError ? `Stream failed (${e.status}).` : "Could not reach the local runtime.";
    } finally {
      turn.streaming = false;
      streaming = false;
      // BUG-24 — a turn that just parked asks immediately whether the decision
      // has already been made elsewhere, rather than waiting out a poll
      // interval before it can say so. Checked here rather than in the event
      // handler because the turn is only genuinely parked once its stream ends.
      if (turn.response?.status === "needs_approval") resumeWatcher?.checkNow();
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

  // ── C14/B19 — composer ergonomics: slash commands, `@` mentions, auto-grow ──
  //
  // Shared with Build through `composerCommands.ts`, so the two composers cannot
  // drift into two different keyboards. Every command listed runs a control this
  // surface already has; none of them grants anything.
  let promptEl = $state<HTMLTextAreaElement | undefined>();
  let modelPickerOpen = $state(false);
  let menuKind = $state<"none" | "slash" | "mention">("none");
  let menuActive = $state(0);
  let mentionItems = $state<MenuItem[]>([]);
  let mentionNotice = $state<{ text: string; href?: string; linkLabel?: string } | null>(null);
  let shortcutsOpen = $state(false);
  let ownerSlashCommands = $state<SlashCommand[]>([]);
  let mentionRequest = 0;

  const slashItems = $derived.by<MenuItem[]>(() => {
    const fragment = menuKind === "slash" ? slashFragment(promptText, caret()) : null;
    if (fragment === null) return [];
    return matchCommands("chat", fragment, ownerSlashCommands).map((command) => ({
      id: command.name,
      label: `/${command.name}`,
      detail: command.summary,
    }));
  });
  const menuItems = $derived(menuKind === "slash" ? slashItems : mentionItems);

  function caret(): number {
    return promptEl?.selectionStart ?? promptText.length;
  }

  async function loadOwnerSlashCommands() {
    try {
      ownerSlashCommands = (await api.skills())
        .filter((skill) => skill.active && skill.command_trigger)
        .map((skill) => ({
          name: skill.command_trigger as string,
          summary: `Use ${skill.name} · permissions unchanged`,
          action: "skill" as const,
        }));
    } catch {
      ownerSlashCommands = [];
    }
  }

  onMount(loadOwnerSlashCommands);

  function trackPromptSelection() {
    promptSelectionStart = promptEl?.selectionStart ?? promptText.length;
    promptSelectionEnd = promptEl?.selectionEnd ?? promptSelectionStart;
  }

  function onVoiceDraft(next: string, cursor: number) {
    promptText = next;
    promptSelectionStart = cursor;
    promptSelectionEnd = cursor;
    queueMicrotask(() => {
      promptEl?.focus();
      promptEl?.setSelectionRange(cursor, cursor);
      autoGrow(promptEl ?? null);
    });
  }

  function onVoiceActive(active: boolean) {
    if (!active) return;
    voiceProvenanceSnapshot = {
      dictated: voiceDictated,
      typedBefore: voiceTypedBefore,
      editedAfter: voiceEditedAfter,
    };
    if (!voiceDictated) voiceTypedBefore = promptText.trim() !== "";
  }

  function restoreVoiceProvenance() {
    voiceDictated = voiceProvenanceSnapshot.dictated;
    voiceTypedBefore = voiceProvenanceSnapshot.typedBefore;
    voiceEditedAfter = voiceProvenanceSnapshot.editedAfter;
  }

  function resetVoiceProvenance() {
    voiceDictated = false;
    voiceTypedBefore = false;
    voiceEditedAfter = false;
  }

  /** Re-read what the caret is sitting in after every edit. */
  function onPromptInput() {
    if (voiceDictated) voiceEditedAfter = true;
    trackPromptSelection();
    autoGrow(promptEl ?? null);
    menuActive = 0;
    const position = caret();
    if (slashFragment(promptText, position) !== null) {
      menuKind = "slash";
      return;
    }
    const mention = mentionAt(promptText, position);
    if (mention !== null) {
      menuKind = "mention";
      void loadMentions(mention.fragment);
      return;
    }
    menuKind = "none";
    mentionNotice = null;
  }

  async function loadMentions(fragment: string) {
    const request = ++mentionRequest;
    try {
      const view = await api.codeMapPaths(fragment);
      if (request !== mentionRequest) return;
      if (view.status !== "success") {
        // A refusal is not an empty menu. Say which one it is, and offer the
        // control that changes it — an owner who has never built the index and
        // an owner whose search matched nothing need different next steps.
        mentionItems = [];
        mentionNotice = {
          text: view.error?.message ?? "Workspace file mentions are unavailable.",
          href: view.error?.type === "code_map_gate_disabled" ? "#/capabilities" : "#/build",
          linkLabel: view.error?.type === "code_map_gate_disabled" ? "Permissions" : "Build",
        };
        return;
      }
      mentionNotice = null;
      mentionItems = (view.paths ?? []).map((entry) => ({
        id: entry.path,
        label: entry.path,
        detail: entry.language,
      }));
    } catch {
      if (request !== mentionRequest) return;
      mentionItems = [];
      mentionNotice = { text: "Could not reach the local runtime to look up files." };
    }
  }

  function chooseMenuItem(item: MenuItem) {
    if (menuKind === "slash") {
      promptText = stripSlashToken(promptText);
      menuKind = "none";
      runSlashCommand(item.id);
      return;
    }
    const mention = mentionAt(promptText, caret());
    if (mention === null) return;
    const applied = applyMention(promptText, mention, item.id);
    promptText = applied.text;
    menuKind = "none";
    queueMicrotask(() => {
      promptEl?.focus();
      promptEl?.setSelectionRange(applied.caret, applied.caret);
      autoGrow(promptEl ?? null);
    });
  }

  /** Run one command. Each of these is a control the owner already has. */
  function runSlashCommand(name: string) {
    if (ownerSlashCommands.some((command) => command.name === name)) {
      const args = promptText.trim();
      promptText = `/${name}${args ? ` ${args}` : ""}`;
      void submit();
      return;
    }
    switch (name) {
      case "new": newConversation(); break;
      case "model": modelPickerOpen = true; break;
      case "attach": attachOpen = true; break;
      case "context": contextOpen = true; void refreshContextUsage(); break;
      case "approvals": window.location.hash = "#/approvals"; break;
      // Cowork's own two: schedule work, and see what is already running. The
      // Tasks surface owns both, including the cadence chips (once / daily /
      // background agent) that make a routine a routine. `/schedule` also asks
      // that surface to open on **Schedule once**, so the command arranges the
      // control it names — it still creates nothing and starts nothing.
      case "schedule":
        requestSchedule();
        window.location.hash = "#/tasks";
        break;
      case "tasks": window.location.hash = "#/tasks"; break;
      case "export": if (sessionId !== null) exportOpen = true; break;
      case "plan": planCollapsed = false; void loadPlan(); break;
      // The same governed `POST /api/interrupts` the composer's Stop button and
      // the top-bar STOP switch use. It does nothing when nothing is running,
      // which is the honest outcome rather than a message about it.
      case "stop": if (streaming) void stopRunningTurn(); break;
      case "shortcuts": shortcutsOpen = true; break;
    }
  }

  /**
   * C14 — put a past prompt back in the composer to change and send again.
   *
   * The transcript is left exactly as it was. An assistant that edits what the
   * owner asked, in place, is no longer a record of the conversation — so the
   * original turn stays and the edited one arrives as a new turn beneath it.
   */
  function editPrompt(text: string) {
    if (streaming) return;
    promptText = text;
    menuKind = "none";
    queueMicrotask(() => {
      promptEl?.focus();
      promptEl?.setSelectionRange(text.length, text.length);
      autoGrow(promptEl ?? null);
    });
  }

  /** Send the same prompt again, unchanged, as a new turn. */
  function retryPrompt(text: string) {
    if (streaming || text.trim() === "") return;
    promptText = text;
    void submit();
  }

  // ── C14 — branch from here ───────────────────────────────────────────
  // The last open part of C14. Edit and Retry both continue *this* conversation;
  // branching opens a second one from a chosen point, so two lines of thought can
  // exist side by side without either overwriting the other. It is deliberately
  // not "edit the message and throw away what followed": this conversation keeps
  // every turn it had, and the branch says where it grew from.
  let branchingTurn = $state<string | null>(null);
  /** Where this conversation came from, when it is itself a branch. */
  let branchOrigin = $state<ConversationBranchOrigin | null>(null);

  async function loadBranchOrigin(id: string | null) {
    if (id === null) {
      branchOrigin = null;
      return;
    }
    try {
      const origin = await api.conversationBranchOrigin(id);
      branchOrigin = origin.source_session_id ? origin : null;
    } catch {
      // Lineage is context, not content: a failed read leaves the banner off
      // rather than claiming the conversation is a root when that is unknown.
      branchOrigin = null;
    }
  }

  async function branchFromTurn(turnId: string) {
    if (sessionId === null || streaming) return;
    branchingTurn = turnId;
    projectNotice = null;
    try {
      const checkpoints = await api.checkpoints(sessionId);
      const point = checkpoints.find((checkpoint) => checkpoint.turn_id === turnId);
      if (point === undefined) {
        // No checkpoint means no state to seed a branch from. Saying so is the
        // honest answer; inventing a seed from the transcript is not.
        projectNotice =
          "No checkpoint was written for that turn, so there is no point to branch from.";
        return;
      }
      const branch = await api.branchConversation(point.checkpoint_id);
      window.location.hash = `#/new-chat?session=${encodeURIComponent(branch.session_id)}`;
    } catch (error) {
      projectNotice =
        error instanceof ApiError
          ? `That conversation could not be branched (${error.reasonCode ?? error.status}).`
          : "That conversation could not be branched.";
    } finally {
      branchingTurn = null;
    }
  }

  // ── Backlog #9 — summarise up to here ────────────────────────────────
  // Compaction was the threshold's decision: a conversation crossed 90% of the
  // window and Raiker summarised the oldest exchanges it was allowed to. The
  // owner is the one who knows the first forty turns were a digression, so this
  // is the same operation started for a different reason. It shortens what the
  // *model* is sent and removes nothing: every turn stays in the transcript,
  // which is why the notice says so rather than asking for a confirmation.
  let compactingTurn = $state<string | null>(null);

  async function compactThroughTurn(turnId: string) {
    if (sessionId === null || streaming) return;
    compactingTurn = turnId;
    projectNotice = null;
    try {
      const result = await api.compactConversation(sessionId, turnId);
      projectNotice = result.compacted
        ? `Summarised ${result.source_turn_count} earlier ${
            result.source_turn_count === 1 ? "exchange" : "exchanges"
          } for the model. Nothing was removed from this transcript.`
        : result.reason_code === "nothing_to_summarise"
          ? "Everything up to that point is already summarised."
          : `That range could not be summarised (${result.reason_code}).`;
    } catch (error) {
      projectNotice =
        error instanceof ApiError
          ? `That range could not be summarised (${error.reasonCode ?? error.status}).`
          : "That range could not be summarised.";
    } finally {
      compactingTurn = null;
    }
  }

  async function stopRunningTurn() {
    if (sessionId === null) return;
    try {
      await api.interrupt({
        session_id: sessionId,
        all: true,
        action_type: "cancel",
        reason: "user stopped this turn (/stop)",
      });
      stopping = true;
    } catch {
      exportNotice = "Could not reach the local runtime to stop the turn.";
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey && voiceControl?.active()) {
      e.preventDefault();
      voiceControl.done();
      promptEl?.focus();
      return;
    }
    // An open menu owns the arrows, Enter, Tab and Escape — otherwise Enter
    // would send the half-typed `/mo` the owner is picking from.
    if (menuKind !== "none" && (menuItems.length > 0 || mentionNotice !== null)) {
      if (e.key === "Escape") {
        e.preventDefault();
        menuKind = "none";
        return;
      }
      if (menuItems.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          menuActive = (menuActive + 1) % menuItems.length;
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          menuActive = (menuActive - 1 + menuItems.length) % menuItems.length;
          return;
        }
        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          chooseMenuItem(menuItems[menuActive]);
          return;
        }
      }
    }
    // Enter submits; Shift+Enter inserts a newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }

  function newConversation() {
    if (streaming) return;
    audioSessionCoordinator.stopAll("route");
    resetVoiceProvenance();
    // Release the transcript's thumbnails with the transcript. They are held
    // for as long as the images are on screen and no longer — a blob URL kept
    // past its last render pins the whole file in memory.
    releaseThumbnails();
    turns = [];
    sessionId = null;
    plan = null;
  }

  // B6 — the same plan checklist Build shows. The `update_plan` tool is
  // model-visible in every conversation, so a plan written here needs the same
  // surface: a Chat that silently stored one would be exactly the invisible
  // product surface the backlog exists to prevent.
  let plan = $state<AgentPlan | null>(null);
  let planCollapsed = $state(false);

  async function loadPlan() {
    if (sessionId === null) {
      plan = null;
      return;
    }
    try {
      const stored = await api.sessionPlan(sessionId);
      plan = hasSteps(stored) ? stored : null;
    } catch {
      plan = null;
    }
  }

  function releaseThumbnails() {
    for (const url of Object.values(thumbnails)) URL.revokeObjectURL?.(url);
    thumbnails = {};
    resolvingThumbnails.clear();
  }

  function onWindowClick(event: MouseEvent) {
    if (contextOpen && contextControlEl && !contextControlEl.contains(event.target as Node)) {
      contextOpen = false;
    }
    attachControl?.handleOutsideClick(event);
    if (
      conversationMenuOpen &&
      !(event.target as HTMLElement | null)?.closest?.(".conversation-menu")
    ) {
      conversationMenuOpen = false;
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

  // ── BUG-24: continue a turn whose approval was resolved anywhere ──────────
  //
  // A parked turn used to be a dead end in Chat: Build could stream a parked
  // continuation and Approvals could offer a manual one, but a Chat tab that
  // did not itself record the decision never learned it had been made. The
  // watcher below closes that, and the server keeps the guarantee — its atomic
  // claim means a turn resumes exactly once even when two tabs both react.
  let liveChannelDown = $state(false);
  let resumeWatcher: ResumeWatcher | null = null;

  onMount(() => {
    resumeWatcher = watchForResumableTurns({
      sessionId: () => sessionId,
      hasParkedTurn: () =>
        turns.some((turn) => turn.response?.status === "needs_approval" && !turn.streaming),
      onResume: (turn) => resumeParkedTurn(turn.approval_id, turn.outcome_status),
      onChannelUnavailable: (unavailable) => (liveChannelDown = unavailable),
    });
    return () => resumeWatcher?.stop();
  });

  /**
   * Decide what a refused continuation means for the turn that asked (BUG-196).
   *
   * The turn's own state is the authority, not the refusal: a turn that already
   * carries a finished response *continued*, so whatever refused this attempt
   * refused a duplicate. Only a turn still parked can honestly report a failure,
   * and only for reasons that really are failures.
   */
  function applyResumeFailure(turn: ChatTurn, error: unknown, code: string | null) {
    const finished = turn.response !== null && turn.response.status !== "needs_approval";
    const outcome = classifyResumeFailure(code);
    if (finished) {
      // The answer is on screen. Saying "could not continue" beneath it is the
      // single most misleading thing this surface can do.
      turn.resumeState = null;
      turn.resumeNote = null;
      return;
    }
    if (outcome === "continued-elsewhere") {
      turn.resumeState = "elsewhere";
      turn.resumeNote = "Continued in another tab. Reload to see the result here.";
      return;
    }
    if (outcome === "not-yet-resolved") {
      // Still genuinely parked: no decision has reached the runtime yet. The
      // waiting state it was already in is the truthful surface.
      turn.resumeState = "waiting";
      turn.resumeNote = null;
      return;
    }
    turn.resumeState = "waiting";
    turn.resumeNote = null;
    turn.error =
      error instanceof ApiError
        ? `The turn could not continue (${code ?? error.status}).`
        : "Could not reach the local runtime to continue the turn.";
  }

  /**
   * Stream the continuation of a parked turn into its own transcript row.
   *
   * The row is the one that parked, so the resumed work lands in the same
   * conversation rather than opening a second turn — the original session,
   * tool-call boundary and cancellation controls are all preserved because the
   * server replays the same suspended state.
   */
  async function resumeParkedTurn(approvalId: string, outcomeStatus = "") {
    // BUG-196 — tell the poller this id is ours before the request goes out, so
    // it cannot start a second continuation of the same decision and turn its
    // own loss into an error line under a perfectly good answer.
    resumeWatcher?.claim(approvalId);
    const turn = turns.findLast((candidate) => candidate.response?.status === "needs_approval");
    if (turn === undefined || turn.streaming) return;
    turn.resumeState = "continuing";
    turn.resumeNote =
      outcomeStatus === "rejected" ? "Rejected — telling Raiker…" : "Approved — continuing…";
    turn.streaming = true;
    turn.error = null;
    streaming = true;
    void scrollToEnd();
    try {
      await streamResumeAfterApproval(approvalId, (event) => {
        if (event.kind === "final" && event.response !== null) {
          turn.response = event.response;
          turn.resumeState = null;
          turn.resumeNote = null;
          void restoreAttachmentChips(event.response.session_id);
          void refreshTurnSources(event.response.session_id);
          if (contextOpen) void refreshContextUsage();
        } else if (event.kind === "error") {
          turn.error = event.text || "The continuation reported an error.";
        } else {
          turn.events = [...turn.events, event];
          const streamed = planFromEvent(event);
          if (streamed !== null) plan = streamed;
        }
        void scrollToEnd();
      });
    } catch (error) {
      const code = error instanceof ApiError ? error.reasonCode : null;
      applyResumeFailure(turn, error, code);
    } finally {
      turn.streaming = false;
      streaming = false;
      void scrollToEnd();
    }
  }

  /** The manual path, offered whenever the live channel cannot be relied on. */
  async function continueNow() {
    if (sessionId === null || streaming) return;
    try {
      const { turns: resumable } = await api.resumableTurns(sessionId);
      if (resumable.length === 0) {
        exportNotice = "No decision has been recorded for this turn yet.";
        return;
      }
      const next: ResumableTurn = resumable[0];
      await resumeParkedTurn(next.approval_id, next.outcome_status);
    } catch {
      exportNotice = "Could not check for a decision — the local runtime is unreachable.";
    }
  }

  // ── BUG-22: export and print this conversation ───────────────────────────
  let conversationMenuOpen = $state(false);
  let exportOpen = $state(false);
  let conversationActionsButton = $state<HTMLButtonElement>();

  function openExport() {
    conversationMenuOpen = false;
    exportOpen = true;
  }

  function openExportFromKeyboard(event: KeyboardEvent) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.stopPropagation();
    openExport();
  }

  async function closeExport() {
    exportOpen = false;
    await tick();
    conversationActionsButton?.focus();
  }

  function printConversation() {
    conversationMenuOpen = false;
    exportOpen = false;
    // The dedicated print stylesheet at the bottom of this file drops the app
    // chrome, so this produces a document rather than a screenshot of the UI.
    setTimeout(() => window.print?.(), 0);
  }

  // Which response was last copied, so the icon-only control can confirm it
  // did something. An icon that reports nothing is worse than a word that does.
  let copiedTurnId = $state<string | null>(null);

  async function copyAnswer(turn: ChatTurn) {
    // The clipboard is not always available (an insecure origin, or a denied
    // permission). Say so rather than failing silently — a copy button that
    // does nothing and reports nothing is worse than no copy button.
    try {
      await navigator.clipboard.writeText(answerText(turn));
      exportNotice = "Response copied.";
      copiedTurnId = String(turn.id);
      window.setTimeout(() => {
        if (copiedTurnId === String(turn.id)) copiedTurnId = null;
      }, 2000);
    } catch {
      exportNotice = "Could not copy — your browser blocked clipboard access.";
      copiedTurnId = null;
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
      <!-- BUG-22 — the conversation menu. Export lives here, beside the other
           whole-conversation actions, rather than inside a per-message row. -->
      <div class="conversation-menu">
        <button
          bind:this={conversationActionsButton}
          type="button"
          class="btn btn-ghost btn-sm"
          aria-label="Conversation actions"
          aria-expanded={conversationMenuOpen}
          aria-haspopup="menu"
          title="Conversation actions"
          onclick={() => (conversationMenuOpen = !conversationMenuOpen)}
        >•••</button>
        {#if conversationMenuOpen}
          <div class="menu" role="menu" aria-label="Conversation actions">
            <button
              type="button"
              role="menuitem"
              disabled={sessionId === null}
              onclick={openExport}
              onkeydown={openExportFromKeyboard}
            >Export conversation…</button>
            <button type="button" role="menuitem" onclick={printConversation}>
              Print / Save as PDF
            </button>
          </div>
        {/if}
      </div>
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
  <!-- C14 — a branch says where it grew from, which is what makes two branches of
       one conversation legible rather than two unrelated chats that happen to
       start the same way. The original is reachable and unchanged. -->
  {#if branchOrigin !== null}
    <p class="branch-origin">
      <Icon name="branch" size={14} />
      <span>
        Branched from
        <a href={`#/new-chat?session=${encodeURIComponent(branchOrigin.source_session_id ?? "")}`}
          >{branchOrigin.source_title ?? "an earlier conversation"}</a
        >{#if branchOrigin.summary}, at “{branchOrigin.summary}”{/if}. That conversation kept every
        turn it had.
      </span>
    </p>
  {/if}
  {#if plan !== null}
    <div class="plan-slot">
      <PlanChecklist {plan} bind:collapsed={planCollapsed} />
    </div>
  {/if}

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
        compactTitle="What can I help with?"
        body="Start with a question, a task, or a file."
        serif={true}
      />
    {/if}

    {#each turns as turn (turn.id)}
      {@const answer = answerText(turn)}
      {@const toolRows = toolActivity(turn.events)}
      <!-- BUG-215 — the stream first, because a turn that is running has the
           freshest working; the stored text when there is no stream to read,
           which is every re-opened turn. -->
      {@const reasoning = collectReasoning(turn.events) || (turn.retainedReasoning ?? "")}
      {@const uploadedAttachments = turn.attachments.filter((a) => a.source !== "generated")}
      {@const generatedFiles = turn.attachments.filter((a) => a.source === "generated")}
      {@const turnSourceList = sourcesForTurn(turnSources, turn.response?.turn_id)}
      <div class="turn">
        <div class="message-group message-group-user">
          <div class="message-bubble message-bubble-user">
          <p class="bubble-text">{turn.prompt}</p>
          </div>
          <!-- C14 — the owner's own message, with the three actions that make
               correcting a prompt cheap. Neither rewrites the transcript: an
               edited or retried prompt is a new turn. -->
          {#if turn.prompt !== ""}
            <MessageActions
              text={turn.prompt}
              disabled={streaming}
              onedit={editPrompt}
              onretry={retryPrompt}
              onbranch={turn.response?.turn_id
                ? () => void branchFromTurn(turn.response?.turn_id ?? "")
                : undefined}
              branching={branchingTurn === turn.response?.turn_id}
              oncompact={turn.response?.turn_id
                ? () => void compactThroughTurn(turn.response?.turn_id ?? "")
                : undefined}
              compacting={compactingTurn === turn.response?.turn_id}
            />
          {/if}
          <!-- BUG-208 slice F. An emoji used to be appended here, to the
               *owner's own message*, labelled "Raiker reacted with …". It was
               computed from `turn.prompt` by regex — before the model had
               answered — so it could not be a reaction to anything: saying
               "thanks" produced a heart whatever Raiker went on to do, or fail
               to do. A label that names an actor and an act, for an act that did
               not happen, is the same claim FIXED-204 removed from the provider
               cards and BUG-207 removed from the streaming turn. -->
          {#if uploadedAttachments.length > 0}
            <div class="turn-attachments">
              {#each uploadedAttachments as a, i (a.attachmentId ?? a.path ?? i)}
                <!-- The same card the composer used, so what you sent looks
                     like what you attached. An uploaded file opens in the
                     inspector; a workspace path has no stored bytes to show,
                     so it stays inert rather than pretending to be clickable. -->
                <AttachmentCard
                  attachment={a}
                  thumbnail={a.attachmentId ? (thumbnails[a.attachmentId] ?? null) : null}
                  expanded={inspecting?.attachmentId === a.attachmentId}
                  onopen={a.attachmentId !== undefined && sessionId !== null
                    ? () => void openInspector(a.attachmentId as string, a.label)
                    : null}
                />
              {/each}
            </div>
          {/if}
        </div>

        <div class="message-group message-group-raiker">
          <!-- BUG-207 slices C and D. What used to be here was a disclosure
               labelled "See what Raiker is thinking" holding three fixed
               sentences chosen by lifecycle event type — the same words for a
               one-word question and a twenty-tool build, and not the model's
               reasoning at all. Slice A removed it. This is the real thing:
               shown only when the turn produced reasoning, collapsed the moment
               the answer starts, and absent entirely when there is none.

               The one indicator below still ends at the first token, and now
               ends at the first *tool row* too — once the transcript is saying
               what Raiker is doing, "Working…" is the less specific of the two
               and has nothing left to add. -->
          <ReasoningBlock
            text={reasoning}
            streaming={turn.streaming}
            notKeptChars={turn.reasoningChars ?? 0}
          />

          <!-- BUG-206 slice D. Every call this turn made, in call order, one
               line each: what ran, what it acted on, and — when it did not run —
               why. Above the answer because it happened before it. -->
          <ToolActivity rows={toolRows} />

          {#if turn.streaming && answer === "" && reasoning === "" && toolRows.length === 0}
            <p class="streaming-label" role="status">
              <span class="pulse" aria-hidden="true"></span>
              Working…
            </p>
          {:else if turn.streaming && answer === "" && hasRunningTool(toolRows)}
            <span class="sr-only" role="status">Running a tool.</span>
          {/if}

          <!-- B17/C13 — a turn the owner stopped says so. Without this the
               transcript just ends early and the owner is left wondering whether
               Raiker stopped or broke. -->
          {#if !turn.streaming && turn.response?.status === "stopped"}
            <p class="stopped-line" role="status">
              Stopped at your request — this turn ended at a safe boundary and kept what it had
              already done.
            </p>
          {/if}

          {#if answer !== ""}
            <div class="message-bubble message-bubble-raiker">
              <!-- C6 — `[s1]` becomes a chip only when this turn's ledger has an
                   s1. A marker the model invented stays the characters it is. -->
              <Markdown
                text={answer}
                citations={renderableCitations(turnSourceList)}
                oncite={(sourceId) => openSourceById(turn.response?.turn_id ?? "", sourceId, answer)}
              />
            </div>
            {#if !turn.streaming}
              <!-- A glyph, like the code-block copy action, so the transcript
                   reads as the answer rather than as chrome around it. -->
              <div class="response-actions">
              <ReadAloudButton
                responseId={turn.response?.turn_id ?? String(turn.id)}
                text={answer}
                language={speechLanguage}
              />
              <button
                type="button"
                class="copy-message"
                class:copied={copiedTurnId === String(turn.id)}
                onclick={() => void copyAnswer(turn)}
                aria-label={copiedTurnId === String(turn.id) ? "Response copied" : "Copy response"}
                title={copiedTurnId === String(turn.id) ? "Response copied" : "Copy response"}
              ><Icon name={copiedTurnId === String(turn.id) ? "check" : "copy"} size={15} /></button>
              </div>
            {/if}
          {:else if !turn.streaming && turn.error === null && turn.response !== null && turn.response.status !== "needs_approval"}
            <!-- BUG-73 — a turn with no answer has a state, not an answer. It
                 used to store "No command was executed." as though that were
                 the answer, which is how one conversation ended up denying,
                 durably, a write that had happened.

                 BUG-206 — the parked case no longer renders here. It used to
                 read "Waiting for your decision — nothing has run yet.", which
                 the approval card immediately below already says, and which the
                 call's own row now says of the call it is actually about. Three
                 statements of one fact, and only one of them named the call. -->
            <div class="message-bubble message-bubble-raiker"><p class="bubble-text answer muted">(No answer text was returned.)</p></div>
          {/if}

          <!-- C6 — everything this turn actually read, under the answer that
               used it. Shown whether or not the model cited: the ledger is what
               the runtime recorded, the citation is only what the model claims. -->
          <!-- `sentenceAround` on open: when the model cited this source inline,
               the strip opens it at the same place the marker does. The sentence
               is the claim, and which control the owner clicked should not
               change what they are shown. It is empty for an uncited source, and
               the pane then says the whole of it was read. -->
          {#if !turn.streaming && turnSourceList.length > 0}
            <SourceChips
              sources={turnSourceList}
              citedIds={citedSourceIds(answer, turnSourceList)}
              openSourceId={openSourceTurnId === turn.response?.turn_id ? openSourceId : null}
              onopen={(source) => void openSource(source, sentenceAround(answer, source.source_id))}
            />
          {/if}

          {#if generatedFiles.length > 0}
            <section class="artifact-stack" aria-label="Generated documents">
              {#each generatedFiles as file (file.attachmentId)}
                <article class="artifact-card" data-status={file.attachmentId ? "ready" : "unavailable"}>
                  <div class="artifact-icon" aria-hidden="true"><Icon name="file" size={20} /></div>
                  <div class="artifact-copy">
                    <div class="artifact-heading">
                      <strong>{file.label}</strong>
                      <span class="artifact-status">{file.attachmentId ? "Ready" : "Unavailable"}</span>
                    </div>
                    <p>Generated document from this response, preserved in this conversation.</p>
                    <p class="artifact-meta">
                      {file.label.split(".").pop()?.toUpperCase() ?? "Document"}
                      {#if file.createdAt} · Created {relativeTime(file.createdAt)}{/if}
                    </p>
                  </div>
                  {#if file.attachmentId !== undefined && sessionId !== null}
                    <div class="artifact-actions">
                      <button
                        type="button"
                        class="btn btn-primary btn-sm artifact-preview"
                        aria-expanded={inspecting?.attachmentId === file.attachmentId}
                        onclick={() => void openGeneratedFile(file.attachmentId as string, file.label)}
                      >Preview</button>
                      <!-- BUG-28 — Download is its own action, not a second
                           name for Preview: it produces the file on disk. -->
                      <button
                        type="button"
                        class="btn btn-ghost btn-sm artifact-download"
                        aria-label={`Download ${file.label}`}
                        onclick={() => void downloadArtifact(file.attachmentId as string, file.label)}
                      ><Icon name="download" size={14} /> Download</button>
                    </div>
                  {:else}
                    <span class="artifact-unavailable">Preview unavailable</span>
                  {/if}
                  {#if artifactNotice !== null && artifactNotice.attachmentId === file.attachmentId}
                    <p class="artifact-error error-line" role="alert">{artifactNotice.text}</p>
                  {/if}
                </article>
              {/each}
            </section>

          {/if}

          {#if turn.error !== null}
            <p class="error-line" role="alert">{turn.error}</p>
          {/if}

          <!-- BUG-206 slice E. A refusal card used to sit here, listing the
               calls policy would not run (BUG-52). It existed because a refused
               call was the *only* call the transcript could speak about, which
               made refusal the single visible tool outcome while every success
               was silent. Now that each call has a row, a refused one is that
               same row in a refused state, in the place it was refused — with
               its reasons and its remediation link on the row rather than in a
               block after the answer. This removes a surface instead of adding
               one; nothing it said has been lost. -->

          {#if turn.response?.status === "needs_approval" && turn.response.approval}
            <!-- BUG-24 — this card is the parked turn's live state. Once a
                 decision is recorded anywhere it flips to "continuing" without
                 a reload, and the manual action stays available whenever the
                 live channel cannot be relied on. -->
            <div class="approval-card" class:continuing={turn.resumeState === "continuing"}>
              {#if turn.resumeState === "continuing"}
                <p class="approval-title" role="status" aria-live="polite">
                  <span class="pulse" aria-hidden="true"></span>
                  {turn.resumeNote ?? "Approved — continuing…"}
                </p>
                <p class="approval-note">
                  Raiker is picking this turn up where it stopped, in this same conversation.
                </p>
              {:else if turn.resumeState === "elsewhere"}
                <p class="approval-title" role="status" aria-live="polite">
                  <Icon name="approvals" size={15} /> Continued in another tab
                </p>
                <p class="approval-note">{turn.resumeNote}</p>
              {:else}
                <p class="approval-title">
                  <Icon name="approvals" size={15} /> Waiting for approval
                </p>
                <p class="approval-body">{turn.response.approval.message}</p>
                <p class="approval-note">
                  Decide here or in the Approvals inbox — this conversation continues on its own
                  as soon as you do, in whichever tab you use.
                </p>
                <div class="approval-actions">
                  <a class="btn btn-soft btn-sm" href="#/approvals">Review approval</a>
                  {#if liveChannelDown}
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm"
                      disabled={streaming}
                      onclick={() => void continueNow()}
                    >Continue now</button>
                  {/if}
                </div>
                {#if liveChannelDown}
                  <p class="approval-note">
                    Raiker cannot currently watch for a decision made elsewhere, so use
                    <strong>Continue now</strong> once you have recorded one.
                  </p>
                {/if}
              {/if}
            </div>
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
      <ComposerChips store={attachStore} disabled={streaming} />
      <ModelReadinessStrip readiness={modelReadiness} draftPreserved={promptText.trim() !== ""} />
      <SkillLinkNotice text={promptText} />

      {#if shortcutsOpen}
        <ShortcutSheet surface="chat" onclose={() => (shortcutsOpen = false)} />
      {/if}
      {#if menuKind !== "none"}
        <ComposerMenu
          items={menuItems}
          active={menuActive}
          heading={menuKind === "slash" ? "Commands" : "Files in the code map"}
          notice={menuKind === "mention" ? mentionNotice : null}
          onchoose={chooseMenuItem}
        />
      {/if}

      <label for="prompt-input" class="sr-only">Prompt</label>
      <div class="composer-upper">
        <textarea
          id="prompt-input"
          class="prompt-input"
          bind:this={promptEl}
          bind:value={promptText}
          oninput={onPromptInput}
          onselect={trackPromptSelection}
          onclick={trackPromptSelection}
          onkeyup={trackPromptSelection}
          onkeydown={onKeydown}
          onblur={() => (menuKind = "none")}
          rows="2"
          placeholder="How can I help you today?"
          title="Enter to send, Shift+Enter for a new line, / for commands, @ to mention a file"
          spellcheck="true"
          lang="en-US"
          disabled={streaming}
        ></textarea>
      </div>

      {#if attachOpen}
        <ComposerAttachPanel store={attachStore} disabled={streaming} idPrefix="chat" />
      {/if}

      {#if streaming}
        <!-- B17/C13 — while a turn is running the composer's job changes: it is
             no longer where the next question is written, it is where this turn
             is stopped or corrected. -->
        <div class="composer-bar">
          <TurnControl sessionId={sessionId} bind:stopping />
        </div>
      {/if}

      <div class="composer-bar">
        <div class="bar-left">
          <ComposerAttach bind:this={attachControl} bind:open={attachOpen} disabled={streaming} />
          <VoiceDictationControl
            bind:this={voiceControl}
            draft={promptText}
            selectionStart={promptSelectionStart}
            selectionEnd={promptSelectionEnd}
            language={speechLanguage}
            disabled={streaming}
            onchange={onVoiceDraft}
            onfinalized={() => (voiceDictated = true)}
            onrestored={restoreVoiceProvenance}
            onactivechange={onVoiceActive}
          />
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
          <ModelPicker
            bind:profileId={modelProfile}
            bind:model
            bind:open={modelPickerOpen}
            bind:effort={reasoningEffort}
            efforts={reasoningEfforts}
            {profiles}
            {selectedProfile}
            onchosen={(profileId, chosen) => void rememberSurfaceModel("chat", profileId, chosen)}
            disabled={streaming}
          />
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
            disabled={streaming || attachStore.uploading || promptText.trim() === "" || modelBlocked}
            aria-label={streaming ? "Running" : "Send"}
          >
            <Icon name="send" size={15} />
            <span class="send-label">{streaming ? "Running…" : "Send"}</span>
          </button>
        </div>
      </div>
      <p class="shortcut-hint">
        Enter sends · Shift+Enter adds a line · <code>/</code> for commands ·
        <code>@</code> to mention a file ·
        <button type="button" class="hint-link" onclick={() => (shortcutsOpen = !shortcutsOpen)}>
          all shortcuts
        </button>
      </p>
    </div>
  </form>
  {#if projectNotice}<p class="project-notice" role="status">{projectNotice}</p>{/if}
</div>
  {#if backgroundWorkOpen}
    <div id="chat-background-work" class="rail-slot">
      <BuildSidePanel
        projectId={projectId || null}
        {projects}
        onclose={() => (backgroundWorkOpen = false)}
      />
    </div>
  {/if}

{#if exportOpen && sessionId !== null}
  <ExportConversationDialog
    sessionId={sessionId}
    onclose={() => void closeExport()}
    onprint={printConversation}
  />
{/if}

{#if inspecting !== null}
  <FileInspector
    preview={preview}
    filename={inspecting.filename}
    loading={previewLoading}
    error={previewError}
    objectUrl={objectUrl}
    source={inspectorSource}
    {sourceLoading}
    ondownload={inspecting.attachmentId === "" ? null : downloadInspected}
    {downloadState}
    {downloadError}
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
      /* Stacked, the column still starts as tall as the room the shell gives it.
         `height: auto` is what lets the transcript and the rail below it take
         the space they need; without a floor to go with it, an empty or short
         conversation collapsed to its content and left the composer floating in
         the middle of a tall tablet screen with half the page blank under it.
         A minimum, rather than a fixed height, keeps both: the composer sits at
         the bottom when there is little to show, and the page still scrolls
         normally once there is more. */
      min-height: var(--content-h);
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
    .thread :global(.empty-body) { display: none; }
    .thread :global(.empty) { padding-block: var(--space-5); }
  }
  /* On narrow screens the model picker wraps under the textarea even when the
     page layout hasn't hit the split-view breakpoint yet. */
  @media (max-width: 30rem) {
    .composer-upper {
      flex-direction: column;
    }
  }
  /* Below the split breakpoint the inspector is a sheet over the conversation
     (see FileInspector.svelte), so the grid stays single-column. */
  .plan-slot {
    flex: 0 0 auto;
    margin-bottom: var(--space-3);
  }
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
  /* Lineage, not a warning: the quietest possible band that still says this
     conversation has a parent and links to it. */
  .branch-origin {
    display: flex;
    align-items: flex-start;
    gap: 0.4rem;
    margin: 0 0 var(--space-2);
    padding: 0.45rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
    color: var(--text-2);
    font-size: var(--text-xs);
    line-height: 1.45;
  }
  .branch-origin > :global(svg) { flex: none; margin-top: 0.15rem; color: var(--accent); }
  .response-actions { display: inline-flex; align-items: center; gap: 0.15rem; }
  .copy-message {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--r-sm);
    color: var(--text-3);
    cursor: pointer;
    padding: 0;
  }
  .copy-message:hover { color: var(--text-1); border-color: var(--border); }
  .copy-message.copied { color: var(--ok); }
  .artifact-stack { display: grid; gap: var(--space-2); margin-top: var(--space-3); }
  .artifact-card {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--accent-border);
    border-radius: var(--r-lg);
    background: linear-gradient(135deg, var(--surface), var(--accent-soft));
    box-shadow: var(--shadow-1);
  }
  .artifact-icon {
    display: grid; place-items: center; width: 2.5rem; height: 2.5rem;
    border-radius: var(--r-md); color: var(--accent); background: var(--surface);
  }
  .artifact-copy { min-width: 0; }
  .artifact-copy p { margin: 0.15rem 0 0; color: var(--text-2); font-size: 0.8rem; }
  .artifact-heading { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  .artifact-heading strong { overflow-wrap: anywhere; }
  .stopped-line {
    margin: 0 0 0.4rem;
    font-size: 0.82rem;
    color: var(--text-2);
  }
  .artifact-status {
    border-radius: 999px; padding: 0.1rem 0.45rem; color: var(--ok);
    background: var(--ok-soft); font-size: 0.7rem; font-weight: 700;
  }
  .artifact-meta { color: var(--text-3) !important; font-size: 0.72rem !important; }
  .artifact-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  .artifact-error { grid-column: 1 / -1; margin: var(--space-2) 0 0; font-size: 0.78rem; }
  .artifact-unavailable { color: var(--text-3); font-size: 0.78rem; }
  @media (max-width: 40rem) {
    .artifact-card { grid-template-columns: auto minmax(0, 1fr); }
    .artifact-actions, .artifact-unavailable { grid-column: 1 / -1; justify-self: stretch; }
    .artifact-actions { justify-content: stretch; }
    .artifact-actions > * { flex: 1; justify-content: center; }
    .artifact-unavailable { text-align: center; }
  }

  /* BUG-22 — the print layout. Save as PDF has to produce a document, not a
     photograph of the application: every piece of chrome and every control is
     dropped, the transcript stops being a scroller, and a turn never splits
     across a page boundary. Code blocks keep their frame but lose the copy
     button, which means nothing on paper. */
  @media print {
    :global(.sidebar), :global(.topbar), :global(.skip-link), .composer,
    .copy-message, .chat-header, .rail-slot, .approval-actions,
    :global(.md-copy), :global(.file-inspector) { display: none !important; }
    :global(.app-shell), :global(.app-main), :global(.content), :global(.responsive-page),
    .chat-layout, .chat { display: block !important; height: auto !important; max-width: none !important; }
    .thread { display: block; overflow: visible; }
    .turn { break-inside: avoid; margin-bottom: 1.5rem; }
    .message-group { max-width: none; }
    .message-bubble { box-shadow: none; border: 1px solid #bbb; }
    :global(.md-code) { break-inside: avoid; }
    @page { margin: 18mm 15mm; }
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
  .approval-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  /* BUG-206 slice E — the refusal card's styles went with it. A refused call is
     now one `ToolActivity` row, which is where its colour lives. */
  /* A turn that is picking itself up again reads as progress, not as a warning
     still waiting on the owner. */
  .approval-card.continuing {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  .approval-card.continuing .approval-title {
    color: var(--accent);
  }
  /* BUG-22 — the conversation menu, anchored to its trigger. */
  .conversation-menu {
    position: relative;
    display: inline-block;
  }
  .conversation-menu .menu {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    z-index: 40;
    min-width: 13rem;
    display: grid;
    gap: var(--space-1);
    padding: var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  .conversation-menu .menu button {
    border: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: 0.86rem;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--r-sm);
    text-align: left;
    cursor: pointer;
  }
  .conversation-menu .menu button:hover:not(:disabled) { background: var(--accent-soft); }
  .conversation-menu .menu button:disabled { color: var(--text-3); cursor: default; }
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
  .shortcut-hint code {
    padding: 0 0.22rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    font-family: var(--font-mono);
    font-size: 0.68rem;
  }
  .hint-link {
    border: 0;
    padding: 0;
    background: transparent;
    color: var(--accent);
    font: inherit;
    cursor: pointer;
    text-decoration: underline;
  }
  /* One clean card: prompt on top, "+" and the per-turn controls at the bottom. */
  /* One composer surface, defined identically in Chat and Build so the two
     conversations are the same instrument in two rooms rather than two
     instruments that resemble each other. */
  .composer-card {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-1);
    transition: border-color 120ms ease, box-shadow 120ms ease;
    /* Even padding all round: the old tighter bottom made the control bar look
       cropped against the card edge. */
    padding: 0.75rem 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  /* Typing is the primary act on both pages, so the card lifts while it has
     focus instead of only changing a border colour by one shade. */
  .composer-card:focus-within {
    border-color: var(--accent-border);
    box-shadow: var(--shadow-2);
  }
  @media (prefers-reduced-motion: reduce) {
    .composer-card { transition: none; }
  }
  /* Upper area: the prompt, and nothing else. The per-turn controls used to sit
     in a column to the right of it, which cost the prompt a third of the card's
     width and put the model chip somewhere no other composer keeps it. They are
     all on the control bar below now, so the prompt gets the whole card. */
  .composer-upper {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }
  .composer-upper .prompt-input {
    flex: 1;
    min-width: 0;
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
  /* The focus ring was previously stranded on the front of the
     `.turn-attachments` selector, so focusing a bar select silently applied a
     flex layout and a top margin to it and never drew a ring at all. */
  .bar-select:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .turn-attachments {
    margin: 0.5rem 0 0;
    display: flex;
    gap: 0.4rem;
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
  /* Kept after the base composer rules so compact declarations win without
     changing a single desktop selector. */
  @media (max-width: 63.9rem) {
    .composer { flex-shrink: 0; padding-top: var(--space-2); }
    .composer-card {
      gap: .3rem;
      padding: .55rem .6rem;
      border-radius: 1rem;
      box-shadow: none;
    }
    .prompt-input { min-height: 2.25rem; resize: none; }
    .composer-bar { flex-wrap: nowrap; gap: .25rem; padding-top: .4rem; }
    .bar-left, .bar-right { flex-wrap: nowrap; gap: .2rem; }
    .bar-right { margin-left: auto; width: auto; justify-content: flex-end; }
    .composer-scope, .context-control, .shortcut-hint { display: none; }
    .send {
      width: 2.75rem;
      height: 2.75rem;
      min-width: 2.75rem;
      margin-left: 0;
      padding: 0;
      border-radius: 50%;
    }
    .send-label { display: none; }
    :global(.composer-card .model-trigger) {
      min-width: 2.75rem;
      width: 2.75rem;
      height: 2.75rem;
      padding: 0;
      justify-content: center;
    }
    :global(.composer-card .model-trigger > span),
    :global(.composer-card .model-trigger > svg:last-child),
    :global(.composer-card .approval-trigger > span),
    :global(.composer-card .approval-trigger > svg:last-child) { display: none; }
    :global(.composer-card .approval-trigger) {
      width: 2.75rem;
      height: 2.75rem;
      padding: 0;
      justify-content: center;
    }
  }
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
      margin-left: auto;
      width: auto;
      justify-content: flex-end;
    }
  }
</style>
