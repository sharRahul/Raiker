<script lang="ts">
  import { askConfirm } from "../confirm.svelte";
  import { LARGE_PASTE_CHARS } from "../composerAttachments.svelte";
  import { NOT_ANSWERING } from "../errorCopy";
  import { pickableProjects } from "../projectLifecycle";
  import { workDraft } from "../workDraft.svelte";
  import { onMount, tick, untrack } from "svelte";
  import Icon from "../components/Icon.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import ContextMeterPopover from "../components/ContextMeterPopover.svelte";
  import AnswerParts from "../components/AnswerParts.svelte";
  import FileInspector from "../components/FileInspector.svelte";
  import RewindPanel from "../components/RewindPanel.svelte";
  import ProfileChip from "../components/ProfileChip.svelte";
  import {
    profileCapabilityModes,
    rememberProfile,
    rememberedProfile,
    type ConversationProfile,
  } from "../conversationProfile";
  import ModelPicker from "../components/ModelPicker.svelte";
  import ModelReadinessStrip from "../components/ModelReadinessStrip.svelte";
  import BuildSidePanel from "../components/BuildSidePanel.svelte";
  import ExportConversationDialog from "../components/ExportConversationDialog.svelte";
  import { densityGap, workSurface } from "../workSurface";
  import { api, ApiError, streamPrompt, streamResumeAfterApproval } from "../api";
  import { ComposerLookups } from "../composerLookups.svelte";
  import { SourceInspector } from "./chat/sourceInspector.svelte";
  import { RecallLedger } from "./chat/recallLedger.svelte";
  import { TurnContinuity } from "./chat/turnContinuity.svelte";
  import { modelDecision, forgetSurfaceModel, rememberSurfaceModel, surfaceModel } from "../surfaceModel.svelte";
  import {
    classifyResumeFailure,
    watchForResumableTurns,
    type ResumableTurn,
    type ResumeWatcher,
  } from "../approvalResume";
  import type {
    AgentPlan,
    AgentResponse,
    ContextUsage,
    CapabilityGate,
    ModelDecision,
    ProjectsList,
    SessionDetail,
    StreamEvent,
  } from "../apiTypes";
  import AttachmentCard from "../components/AttachmentCard.svelte";
  import Composer from "../components/Composer.svelte";
  import ComposerAttach from "../components/ComposerAttach.svelte";
  import ComposerActionMenu from "../components/ComposerActionMenu.svelte";
  import ComposerContext from "../components/ComposerContext.svelte";
  import ComposerAttachPanel from "../components/ComposerAttachPanel.svelte";
  import ComposerChips from "../components/ComposerChips.svelte";
  import PlanChecklist from "../components/PlanChecklist.svelte";
  import ReasoningBlock from "../components/ReasoningBlock.svelte";
  import ToolActivity from "../components/ToolActivity.svelte";
  import TurnEvidence from "../components/TurnEvidence.svelte";
  import SafetyCard from "../components/SafetyCard.svelte";
  import ClarifyCard from "../components/ClarifyCard.svelte";
  import TurnReceipt from "../components/TurnReceipt.svelte";
  import CorrectionMemory from "../components/CorrectionMemory.svelte";
  import { correctionToRemember } from "../corrections";
  import { ownerQuestions } from "../clarify";
  import SkillLinkNotice from "../components/SkillLinkNotice.svelte";
  import SourceChips from "../components/SourceChips.svelte";
  import RecallStrip from "../components/RecallStrip.svelte";
  import TurnControl from "../components/TurnControl.svelte";
  import { createAttachmentStore, wireAttachments, type ComposerAttachment } from "../composerAttachments.svelte";
  import { newIdempotencyKey } from "../idempotency";
  import { taskDetailHref } from "../taskHistory";
  import { createFileDrop } from "../fileDrop.svelte";
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
  } from "../composerCommands";
  import { composerMenu } from "../composerCapabilities";
  import { setWorkProject, workProject } from "../workProject.svelte";
  import { readReadiness, refreshReadCapabilities } from "../readCapabilities.svelte";
  import { collectText } from "../turnPhases";
  import { relativeTime } from "../format";
  import { backgroundLabel, backgroundSummary, hasBackgroundWork, type BackgroundSummary } from "../backgroundWork";
  import {
    attachmentChipsByTurn,
    mergeRestoredChips,
    parkedByTurn,
    restoredTurnCore,
    type ParkedApproval,
  } from "../conversationRestore";
  import { rememberSessionInRoute } from "../sessionRoute";
  import { evidenceLink, forgetTurnInRoute, revealTurn } from "../turnAnchor";
  import { hasSteps, planFromEvent } from "../agentPlan";
  import { collectReasoning, hasRunningTool, toolActivity, turnOutcome, workingLine, type ToolCallRow } from "../chatPresentation";
  import { turnFailureMessage } from "../turnFailure";
  import { retryConfirmation, retryConsequence } from "../conversationCommands";
  import {
    citedSourceIds,
    renderableCitations,
    sentenceAround,
    sourcesForTurn,
  } from "../citations";
  import { allProfiles, chatProfiles, refreshModels, modelCatalogues, modelsKnown } from "../models.svelte";
  import { catalogueChoices } from "../modelCatalogue";
  import { COMPOSE_EVENT, takeChatHandoff, type ChatHandoff } from "../chatHandoff";
  import { conversationMatches, matchLabel } from "../conversationSearch";
  import { filesInUse } from "../contextPanel";
  import ChatContextPanel from "../components/ChatContextPanel.svelte";
  import { STARTERS } from "../starters";
  import { composerDataLabel, inferenceLocation, inferenceSentence } from "../inferenceLocation";
  import { reportForegroundWork } from "../liveWork.svelte";
  import { requestTaskDraft, routineFromTurn, routineSteps } from "../taskDrafts";
  import { announceResponseReady } from "../desktopNotice";
  import { delivery } from "../deliveryPolicy.svelte";
  import {
    activeComposerProfile,
    blocksSending,
    closeModelSetup,
    openModelSetup,
    setupDialog,
    readinessForSelection,
  } from "../modelReadiness.svelte";
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
    // DEC-22 step 3 — the earlier turn this one asked again, when it was a Retry.
    retryOf?: string | null;
  }


  /** What this mode is about, and how tightly it packs it. */
  const surface = workSurface("chat");

  let {
    sessionId: continuedSessionId = null,
    // MEM-08 — the exchange this link is pointing at inside that conversation.
    anchoredTurnId = null,
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
    anchoredTurnId?: string | null;
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
  let projectId = $state(workProject());
  const draft = $derived(workDraft(projectId));
  let speechLanguage = $state<SpeechLanguage>("auto");
  // BUG-256 — which speech runtime dictation will use. Read once on mount and
  // defaulted to the browser, so a composer that cannot reach the host still
  // offers dictation rather than nothing.
  let speechRuntime = $state<"browser" | "local">("browser");
  let voiceControl = $state<VoiceDictationHandle | undefined>();
  let voiceDictated = $state(false);
  let voiceTypedBefore = $state(false);
  let voiceEditedAfter = $state(false);
  let voiceProvenanceSnapshot = { dictated: false, typedBefore: false, editedAfter: false };
  let promptSelectionStart = $state(0);
  let promptSelectionEnd = $state(0);
  // Empty until the account is read, so the greeting never names a placeholder
  // in the first second of a load; with no name it asks without one.
  let userName = $state("");
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
  /**
   * The project this conversation is filed under.
   *
   * A conversation that already exists owns its own answer, and changing it
   * moves the session. A conversation that does not exist yet has no answer of
   * its own, so it starts in the shared Work project — which is what makes
   * "choose a project in Build, switch to Chat, keep working in it" true rather
   * than something the owner does twice.
   *
   * The shared value is never allowed to re-file an existing chat: it is read
   * only while `sessionId` is null.
   */
  let pendingProjectId: string | null = workProject() === "" ? null : workProject();
  let projectNotice = $state<string | null>(null);

  /*
   * RR-PROJECT-01 — the shared value, while this conversation does not exist yet.
   *
   * Chat is mounted once and hidden between route visits, so the two reads above
   * happen when the application starts and never again. Choosing a project
   * somewhere else — pressing "New chat" on a project card, or picking one in
   * Build — therefore reached a composer that had already made up its mind, and
   * the conversation was filed nowhere while the page named the project.
   *
   * The three rules of the shared value are unchanged and are what makes this
   * safe: it is read only while `sessionId` is null, so nothing that already
   * exists is re-filed; the surface names the project before Send; and it
   * decides filing, never retrieval. `sessionId` is read untracked because it is
   * a condition on this rule, not a reason to re-apply it — a conversation that
   * has just been created must not have the shared value reapplied to it.
   */
  $effect(() => {
    const shared = workProject();
    untrack(() => {
      if (sessionId !== null || projectId === shared) return;
      projectId = shared;
      pendingProjectId = shared === "" ? null : shared;
    });
  });
  let backgroundWorkOpen = $state(false);
  /*
   * UX-CHAT-04 — the rail's toggle says what is in it before it is opened: a
   * label, how much is running, and whether anything failed today. Read from
   * the same `/api/tasks` filter the rail itself draws, every thirty seconds,
   * and silently absent when the read fails (the rail says why when opened).
   */
  let background = $state<BackgroundSummary | null>(null);
  $effect(() => {
    const filter = projectId ? { project_id: projectId } : {};
    let cancelled = false;
    const read = async () => {
      try {
        const tasks = await api.tasks(filter);
        if (!cancelled) background = backgroundSummary(tasks);
      } catch {
        if (!cancelled) background = null;
      }
    };
    void read();
    const timer = window.setInterval(read, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  });

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
      void continuity.loadBranchOrigin(id);
    });
  });

  // BUG-242 — the address bar follows the open conversation, so a reload comes
  // back to it rather than to an empty one. Only the surface on screen writes:
  // Chat and Build stay mounted behind each other.
  $effect(() => {
    if (!visible) return;
    rememberSessionInRoute("new-chat", sessionId);
  });
  let nextId = 1;

  // Optional per-prompt options. Left unset they change nothing — the backend
  // applies its own defaults, exactly as if the option was never sent. They
  // live as compact controls at the bottom of the composer card.
  let modelProfile = $state("");
  let model = $state("");
  /**
   * The authoritative answer for this surface.
   *
   * `null` until the first read, and `null` again if that read fails: the
   * composer renders identically without it, minus the line explaining a
   * fallback. A model control that will not draw because a status endpoint is
   * down is worse for the owner than one that simply says less.
   */
  let decision = $state<ModelDecision | null>(null);
  let reasoningEffort = $state("");
  // One reactive view of the shared model store; refreshes live when the
  // Models page connects a provider or selects a model, without a remount.
  const profiles = $derived(chatProfiles());

  // The persisted selection (Models view / /model use). The default provider
  // option names it so the user can see what will actually serve the turn.
  const selectedProfile = $derived(profiles.find((p) => p.selected) ?? null);
  // BUG-314 — the bound pair as the picker reads it, so a searched model is
  // described as itself and not as the default.
  const activeProfile = $derived(activeComposerProfile(profiles, modelProfile, model, allProfiles()));
  const modelReadiness = $derived(readinessForSelection(activeProfile, catalogueChoices(profiles, modelCatalogues()).length));
  // QUI-C04 — where the next message is processed, for the model that will run it.
  const dataLocation = $derived(
    activeProfile === null ? null : inferenceLocation(activeProfile, model !== "" ? model : activeProfile.model),
  );
  // BUG-238 — a stale observation never blocks: the server re-checks it
  // before admitting the turn, so the only thing that stops a send is a
  // model problem the owner can actually fix.
  const modelBlocked = $derived(blocksSending(modelReadiness));
  // QUI-P02 — the conversation's profile, remembered per conversation in this
  // browser. Careful is sent as a per-turn override the runtime enforces.
  let conversationProfile = $state<ConversationProfile>("standard");
  // An opened conversation brings its own; a new one starts at Standard
  // (`newConversation`), or with what Home's composer chose.
  //
  // A new chat learns its id from its first streamed chunk: that id keeps the
  // profile it was sent with (found live, RT-QUI-29). Any other change of id
  // is a conversation being opened, which brings its own.
  let profileFor: string | null = null;
  $effect(() => {
    const id = sessionId;
    if (id === null) {
      profileFor = null;
      return;
    }
    if (id === profileFor) return;
    const justStarted = profileFor === null && untrack(() => turns.some((turn) => turn.streaming));
    if (justStarted) rememberProfile(id, untrack(() => conversationProfile));
    else conversationProfile = rememberedProfile(id);
    profileFor = id;
  });
  /**
   * The override to send with the next prompt, or null when Careful is chosen
   * and the capabilities it covers cannot be read. Careful then refuses to
   * send rather than quietly sending a Standard turn.
   */
  let profileGates = $state<CapabilityGate[] | null>(null);
  async function loadProfileGates(): Promise<void> {
    try {
      profileGates = await api.capabilityGates();
    } catch {
      profileGates = null;
    }
  }
  $effect(() => {
    // Re-read each time Careful is chosen, so it covers what Permissions lists now.
    if (conversationProfile === "careful") void loadProfileGates();
  });
  async function profileModes(): Promise<Record<string, string> | null> {
    if (conversationProfile !== "careful") return {};
    if (profileGates === null) await loadProfileGates();
    return profileGates === null ? null : profileCapabilityModes("careful", profileGates);
  }

  // QUI-C03 — the running turn's one status line, read from its own events.
  const runningActivity = $derived.by(() => {
    const running = [...turns].reverse().find((turn) => turn.streaming);
    if (!running) return "";
    return workingLine(toolActivity(running.events));
  });
  // QUI-F04 — the turn being written here shows in the top bar's live work
  // line from every page, with the same step the status line says.
  $effect(() => {
    if (!streaming) {
      reportForegroundWork("chat", null);
      return;
    }
    reportForegroundWork("chat", {
      label: conversationTitle || "New chat",
      step: runningActivity || "Writing the answer",
      href: sessionId === null ? "#/new-chat" : `#/new-chat?session=${encodeURIComponent(sessionId)}`,
      waiting: runningActivity.startsWith("Waiting for your"),
    });
  });
  $effect(() => () => reportForegroundWork("chat", null));
  // QUI-F05 — *Response ready*: the turn this page ran has its answer while
  // Raiker is in the background. A parked turn is announced by its own notice.
  let wasStreaming = false;
  $effect(() => {
    const now = streaming;
    if (wasStreaming && !now) {
      const last = turns[turns.length - 1];
      if (last?.response && last.response.status !== "needs_approval") {
        announceResponseReady(conversationTitle, `#/new-chat?session=${encodeURIComponent(last.response.session_id)}`, `response-${last.response.turn_id}`, delivery.current?.quiet_hours.active ?? false);
      }
    }
    wasStreaming = now;
  });
  // QUI-C05 — the message Send kept while no model was usable. It goes the
  // moment one is, through the same `submit()`, and is dropped if the owner
  // edits the draft or cancels.
  let sendWhenReady = $state<string | null>(null);
  // Resolves once Chat has read the model it was last set to (or failed to).
  let surfaceModelRead: Promise<void> = Promise.resolve();
  $effect(() => {
    if (sendWhenReady === null) return;
    if (draft.text.trim() !== sendWhenReady) {
      sendWhenReady = null;
      return;
    }
    if (!modelBlocked && modelsKnown() && !streaming) {
      // The dialog asked for a model; one is ready now, so it has nothing left
      // to ask.
      if (setupDialog.open) closeModelSetup();
      void submit();
    }
  });
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
  // A file dropped on the composer is attached to the next turn, exactly as if
  // it had been picked from the attach panel (BUG-252).
  const composerDrop = createFileDrop({
    onFiles: (files) => void attachStore.acceptFiles(files),
    enabled: () => !(streaming) && !attachStore.full,
  });
  async function onComposerPaste(event: ClipboardEvent) {
    if (streaming || attachStore.uploading || attachStore.full) return;
    const files = event.clipboardData?.files;
    if (files?.length) {
      event.preventDefault();
      await attachStore.acceptFiles(files);
      return;
    }
    const text = event.clipboardData?.getData("text/plain") ?? "";
    if (text.length < LARGE_PASTE_CHARS) return;
    event.preventDefault();
    const targetDraft = draft;
    const original = targetDraft.text;
    const start = promptEl?.selectionStart ?? original.length;
    const end = promptEl?.selectionEnd ?? start;
    if (!(await attachStore.attachPastedText(text))) {
      targetDraft.text = targetDraft.text === original
        ? original.slice(0, start) + text + original.slice(end)
        : targetDraft.text + text;
    }
  }
  let attachControl = $state<ComposerAttach | undefined>();
  let attachOpen = $state(false);

  /**
   * COMPOSER-02/03/04 — two entry points instead of a row of permanent buttons.
   *
   * Chat's bar carried an attach control, a dictation control, a project select
   * and a posture chip, permanently, under every message anyone ever typed.
   * Every one of them is still reachable; they are behind `+` and Tools now,
   * which is where a control belongs when it is used occasionally and
   * understood immediately. What stays on the bar is what changes per turn and
   * has to be legible without opening anything: which model will answer, what
   * this turn can see, and Send.
   *
   * The lists come from the typed registry (COMPOSER-19), so what Chat offers
   * is a fact about the surface rather than a decision re-made in this file,
   * and `HANDLED` is the contract in the other direction — an id this view has
   * no handler for is not drawn, so the menu cannot promise something Chat
   * cannot do.
   */
  let composerGates = $state<CapabilityGate[]>([]);
  const HANDLED = new Set([
    "attach-file",
    "set-project",
    "dictate",
    "web-search",
    "web-read",
    "web-extract",
    "weather",
    "use-mcp",
    "use-connector",
    "generate-image",
    "create-task",
    "run-background",
    "schedule",
    "use-memory",
  ]);
  // The readiness half comes from the shared snapshot, so a
  // search provider configured on another page reaches this still-mounted view
  // without a reload, and the menu never prints `Ready` for a call the runtime
  // is about to refuse.
  const readiness = $derived(readReadiness());
  const addItems = $derived(composerMenu("add", "chat", composerGates, HANDLED, readiness));
  const toolItems = $derived(
    composerMenu("tools", "chat", composerGates, HANDLED, readiness),
  );

  /**
   * Where a Tools entry goes.
   *
   * Chat cannot itself invoke an MCP tool or a connector on demand — the model
   * asks for one mid-turn and the gate judges it then. So the honest thing this
   * menu can do is name the capability and take the owner to where it is
   * configured or where the work happens. A menu item that silently did nothing
   * would be the permanent-toolbar problem again, only harder to notice.
   */
  const TOOL_ROUTES: Record<string, string> = {
    // The three reads and the weather lookup are model-invoked mid-turn: the
    // owner asks for something and the model reaches for the tool the gate then
    // judges. So the honest destination for the menu entry is where that
    // capability is governed and where its readiness is explained.
    "web-search": "#/capabilities",
    "web-read": "#/capabilities",
    "web-extract": "#/capabilities",
    weather: "#/settings?tab=general",
    "use-mcp": "#/connections?tab=advanced&kind=mcp",
    "use-connector": "#/connections?tab=services",
    "generate-image": "#/design",
    "create-task": "#/tasks",
    schedule: "#/tasks",
    "use-memory": "#/memory",
  };

  /** Open state for the project chooser the `+` menu reveals. */
  let projectPickerOpen = $state(false);

  function runComposerAction(id: string) {
    if (id === "attach-file") {
      attachOpen = true;
      return;
    }
    if (id === "dictate") {
      voiceControl?.begin();
      return;
    }
    if (id === "set-project") {
      projectPickerOpen = true;
      return;
    }
    if (id === "run-background") {
      void runInBackground();
      return;
    }
    const route = TOOL_ROUTES[id];
    if (route !== undefined) window.location.hash = route;
  }

  /**
   * QUI-C11 — Run in background. The draft is filed as a task that starts now,
   * through the same governed `POST /api/tasks` the Tasks page uses; the task
   * then shows in Background work and on Home under In progress. Nothing runs
   * here, and a refused or failed save keeps the draft.
   */
  let backgroundNotice = $state<{ text: string; href: string | null } | null>(null);
  let backgroundKey = newIdempotencyKey();

  async function runInBackground() {
    const text = draft.text.trim();
    if (text === "") {
      backgroundNotice = { text: "Type what Raiker should work on, then choose Run in background.", href: null };
      return;
    }
    const firstLine = text.split("\n")[0];
    const title = firstLine.length > 80 ? `${firstLine.slice(0, 79)}…` : firstLine;
    const attachments = wireAttachments(attachStore.items);
    try {
      const created = await api.createTask(
        {
          title,
          description: text,
          surface: "chat",
          ...(projectId ? { project_id: projectId } : {}),
          ...(modelProfile && model ? { model_profile: modelProfile, model } : {}),
          ...(attachments ? { attachments } : {}),
        },
        backgroundKey,
      );
      backgroundKey = newIdempotencyKey();
      draft.text = "";
      attachStore.clear();
      backgroundNotice = { text: "Running in the background.", href: taskDetailHref(created.task_id) };
    } catch (error) {
      backgroundNotice = {
        text:
          error instanceof ApiError && error.reasonCode === "model_not_ready"
            ? "The chosen model is not ready, so nothing was started. Your message is kept."
            : "Could not start it in the background. Your message is kept; try again or use Tasks.",
        href: error instanceof ApiError && error.reasonCode === "model_not_ready" ? "#/models" : "#/tasks",
      };
    }
  }

  /**
   * COMPOSER-06 — what this turn will see, as one line.
   *
   * Only facts that are true. A chat with no project and no attachments has
   * nothing to say here and the control is absent, rather than reporting its
   * own emptiness in a row that is on screen either way.
   */
  const selectedProject = $derived(
    (projects?.projects ?? []).find((project) => project.project_id === projectId) ?? null,
  );

  /**
   * The token count this turn carries, provider-reported once a turn has run
   * and locally estimated before that. The same precedence the context meter
   * uses, so the line and the panel it opens cannot disagree.
   */
  const usedTokens = $derived(
    contextUsage?.usage_source === "provider" && contextUsage.used_tokens !== null
      ? contextUsage.used_tokens
      : estimatedContextTokens,
  );

  /** "12.4k" rather than "12,431" — a summary line has one line of room. */
  function compactTokens(count: number): string {
    if (count < 1000) return String(count);
    if (count < 1_000_000) return `${(count / 1000).toFixed(count < 10_000 ? 1 : 0)}k`;
    return `${(count / 1_000_000).toFixed(1)}M`;
  }

  const contextPercent = $derived.by(() => {
    // The provider's own count once a turn has produced one, the local estimate
    // until then. The ring this replaces drew the same distinction; losing it
    // would turn a measured number into a guess without saying so.
    const window =
      contextUsage?.context_window_tokens ?? activeProfile?.context_window_tokens ?? null;
    if (!window) return null;
    const used = contextUsage?.used_tokens ?? estimatedContextTokens;
    return Math.min(100, (used / window) * 100);
  });

  const contextFacts = $derived([
    ...(selectedProject !== null
      ? [
          /*
           * UX-BUILD-05 — the link goes to this project, not to the list of
           * them. Naming the project and then opening a page where the owner
           * has to find it again is the weak return path the review names; the
           * id is already here, so the link can carry it.
           */
          /*
           * UX-CHAT-03 — filing is organisation, not a narrower memory. A
           * project's instructions and shared files ride each Chat turn, but
           * Chat's recall stays owner-wide (`RetrievalScope("chat", None)` in
           * the gatherer; only Build narrows to the project). A line that only
           * named the project read as "this chat can see only this project".
           */
          {
            label: "Project",
            value:
              `Filed in ${selectedProject.name}. Its instructions and shared files apply; ` +
              "recall still draws on all your memory, not only this project's, unless " +
              "Incognito is on in Memory.",
            short: `Filed in ${selectedProject.name}`,
            href: `#/projects?project=${encodeURIComponent(selectedProject.project_id)}`,
            action: "Open project work",
          },
        ]
      : []),
    ...(attachStore.items.length > 0
      ? [
          {
            label: "Attached",
            value: attachStore.items.map((item) => item.label).join(", "),
            short: `${attachStore.items.length} file${attachStore.items.length === 1 ? "" : "s"}`,
          },
        ]
      : []),
    // The conversation's own size, once there is one. Without this the line
    // disappears entirely on a model that reports no context window — which is
    // a real state, and one the ring this replaces at least said out loud
    // ("capacity unknown"). How much is in play is true and useful whether or
    // not the window it is measured against is known.
    ...(usedTokens > 0
      ? [
          {
            label: "Conversation",
            value: `${usedTokens.toLocaleString()} tokens so far`,
            short: contextPercent === null ? `${compactTokens(usedTokens)} tokens` : undefined,
          },
        ]
      : []),
  ]);

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

  // UX-CHAT-01 — the file/source pane and the recall ledger are their own
  // state machines, each with one owner (see `./chat/`). Opening either side
  // panel closes the rewind panel: they share the right-hand column (B18).
  const inspector = new SourceInspector(
    () => sessionId,
    () => {
      continuity.rewindCheckpointId = null;
    },
  );
  const recall = new RecallLedger(() => sessionId);

  // Chips show only the file/folder name; the full workspace path stays in the
  // tooltip and is what actually rides the prompt.
  let scrollEl: HTMLDivElement | undefined = $state();

  onMount(() => {
    void refreshModels();
    // Chat starts on the model Chat was last set to, not on whatever the global
    // default happens to be. An explicit per-turn choice still overrides it.
    surfaceModelRead = surfaceModel("chat").then((remembered) => {
      if (remembered === null || modelProfile) return;
      modelProfile = remembered.profileId;
      model = remembered.model;
    }).catch(() => {});
    // The authoritative decision for this surface: what is selected,
    // what will actually run, and why they differ when they do. The picker
    // needs it to keep an unavailable selection visible instead of quietly
    // re-rendering as the fallback.
    void modelDecision("chat").then((answer) => (decision = answer));
    // COMPOSER-04 — which capabilities are on. A failed read leaves the list
    // empty, and an entry with no gate reported is offered rather than hidden:
    // the runtime still judges the action when it is invoked, and refusing to
    // show a capability because a status read failed would be Raiker deciding
    // on worse evidence than it will have at the point of use.
    void api
      .capabilityGates()
      .then((view) => (composerGates = view))
      .catch(() => (composerGates = []));
    void refreshReadCapabilities();
    void api.speechRuntime().then((view) => {
      speechRuntime = view.runtime.effective;
    }).catch(() => {});
    void api.settings().then((view) => {
      // RR-IDENTITY-01 — the name the owner chose, not their sign-in handle.
      // Chat greeted them by the handle however many times they set a display
      // name, because `username` is the fixed handle and the two were conflated.
      // The server resolves which one applies, so the greeting and the model's
      // own identity block cannot disagree about what to call the same person.
      userName = view.status.display_name || view.status.username || "";
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
        fromHandoff?: boolean;
      }>).detail;
      if (detail === undefined || detail.text.trim() === "") return;
      if (detail.fromHandoff) {
        // QUI-H01 — Home's composer. Taken from the one-shot store so a Chat
        // that mounts later cannot send the same message a second time.
        const handed = takeChatHandoff();
        if (handed !== null) void startHandedOffChat(handed);
        return;
      }
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
      draft.text = detail.text;
      void submit();
    };
    window.addEventListener(COMPOSE_EVENT, onCompose);
    // QUI-H01 — a message Home handed over before this Chat existed.
    const waiting = takeChatHandoff();
    if (waiting !== null) void startHandedOffChat(waiting);
    return () => {
      window.removeEventListener(COMPOSE_EVENT, onCompose);
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
    inspector.close();
    // B18 — a preflight belongs to one conversation. Left open across a load
    // it would describe a checkpoint from a conversation no longer on screen.
    continuity.rewindCheckpointId = null;
    landedAnchor = null;
    try {
      const detail = await api.session(id);
      conversationTitle = detail.session?.title ?? "";
      const parked = parkedByTurn(detail);
      earlierShown = 0;
      turns = detail.turns.map((t) => restoredTurn(t, id, parked.get(t.turn_id)));
      nextId = turns.length + 1;
      await restoreAttachmentChips(id);
      await inspector.refreshTurnSources(id);
      await recall.refresh(id);
      // MEM-08 — a link that named an exchange lands on it; everything else
      // opens where the conversation left off. The landing itself belongs to
      // the effect below, so a *second* link into the same conversation is
      // honoured too — that reload never happens, because the session id has
      // not changed.
      if (anchoredTurnId === null || anchoredTurnId === "") void scrollToEnd(true);
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
    turns = mergeRestoredChips(turns, attachmentChipsByTurn(files));
    void resolveThumbnails(turns.flatMap((turn) => turn.attachments));
  }

  function restoredTurn(
    t: SessionDetail["turns"][number],
    sessionId: string,
    parked?: ParkedApproval,
  ): ChatTurn {
    return { id: nextId++, ...restoredTurnCore(t, sessionId, parked) };
  }

  function answerText(turn: ChatTurn): string {
    const streamed = collectText(turn.events);
    if (streamed.trim() !== "") return streamed;
    return turn.response?.message ?? "";
  }

  // QUI-C07 — the context panel: closed by default, opened from the header.
  let contextPanelOpen = $state(false);
  const contextFiles = $derived(filesInUse(turns.map((turn) => turn.attachments)));
  const contextActivity = $derived(turns.flatMap((turn) => toolActivity(turn.events)));

  // QUI-C01 — search in conversation: the turns on screen that mention the
  // words typed, stepped through in order. Search finds across conversations.
  let searchOpen = $state(false);
  let searchQuery = $state("");
  let searchAt = $state(0);
  let searchInput = $state<HTMLInputElement>();
  const searchHits = $derived(
    conversationMatches(turns.map((turn) => ({ prompt: turn.prompt, answer: answerText(turn) })), searchQuery),
  );
  const currentHit = $derived(searchHits.length > 0 ? searchHits[Math.min(searchAt, searchHits.length - 1)] : null);

  async function openSearch() {
    searchOpen = true;
    await tick();
    searchInput?.focus();
  }

  function closeSearch() {
    searchOpen = false;
    searchQuery = "";
    searchAt = 0;
  }

  function showHit(step: number) {
    if (searchHits.length === 0) return;
    searchAt = (Math.min(searchAt, searchHits.length - 1) + step + searchHits.length) % searchHits.length;
    following = false;
    const index = searchHits[searchAt];
    ensureShown(index);
    void tick().then(() =>
      document.querySelector(`[data-turn-index="${index}"]`)?.scrollIntoView?.({ block: "center" }),
    );
  }

  /*
   * QUI-G04 — a long conversation draws its latest turns, not all of them.
   * A thousand turns rendered at once made typing and scrolling lag; the
   * transcript shows the newest TURN_WINDOW and offers the earlier ones a
   * window at a time. Search, a Retry's source and a linked turn widen the
   * window to the turn they need before scrolling to it. Settled turns off
   * screen also skip layout and paint (`content-visibility`, in the styles).
   */
  const TURN_WINDOW = 100;
  let earlierShown = $state(0);
  const firstShown = $derived(Math.max(0, turns.length - TURN_WINDOW - earlierShown));
  const shownTurns = $derived(turns.slice(firstShown));

  function ensureShown(index: number) {
    if (index >= 0 && index < firstShown) earlierShown = turns.length - TURN_WINDOW - index;
  }

  async function showEarlier() {
    const before = scrollEl?.scrollHeight ?? 0;
    earlierShown += TURN_WINDOW;
    await tick();
    // Keep the turn the owner was reading where it was, rather than letting
    // the new turns above push it down the screen.
    if (scrollEl) scrollEl.scrollTop += scrollEl.scrollHeight - before;
  }

  function onSearchKeydown(event: KeyboardEvent) {
    if (event.key === "Enter") {
      event.preventDefault();
      showHit(event.shiftKey ? -1 : 1);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeSearch();
    }
  }

  $effect(() => {
    // A new query starts from its first match and shows it, as find does. Only
    // the query re-runs this: a streaming answer must not move the view.
    void searchQuery;
    untrack(() => {
      searchAt = 0;
      if (searchHits.length > 0) {
        searchAt = searchHits.length - 1;
        showHit(1);
      }
    });
  });

  async function submit(retryOf: string | null = null) {
    if (voiceControl?.active()) {
      voiceControl.done();
      promptEl?.focus();
      return;
    }
    const sentDraft = draft;
    const text = sentDraft.text.trim();
    if (text === "" || streaming || attachStore.uploading) return;
    // QUI-Q04 — Send is never a dead button. With no usable model the press
    // opens the dialog that fixes it, and the draft stays where it is.
    if (modelBlocked) {
      // QUI-C05 — and the message is sent once a model is ready, unless the
      // owner changes it or cancels. The line under the composer says so.
      sendWhenReady = text;
      openModelSetup(null, modelReadiness);
      return;
    }
    sendWhenReady = null;
    const voiceState = {
      dictated: voiceDictated,
      typedBefore: voiceTypedBefore,
      editedAfter: voiceEditedAfter,
    };
    const inputMode = inputModeForDraft(voiceState);
    audioSessionCoordinator.stopAll("submit");
    // Careful's capabilities are normally read already; only a send that
    // races the read waits for it.
    const sentModes = await profileModes();
    if (sentModes === null) {
      exportNotice =
        "Raiker could not read your permissions, so Careful could not be applied. Nothing was sent; your message is still here.";
      return;
    }
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
        retryOf,
      },
    ];
    // Mutate the $state-proxied instance, not the raw literal: raw-object writes
    // bypass Svelte 5's signals and the transcript would never re-render.
    const turn = turns[turns.length - 1];
    draft.text = "";
    resetVoiceProvenance();
    // B19 — a box that grew to hold a long prompt has to shrink back when the
    // prompt leaves it, or the composer keeps the height of the longest thing
    // ever typed into it.
    menuKind = "none";
    queueMicrotask(() => autoGrow(promptEl ?? null));
    attachStore.clear();
    streaming = true;
    stopping = false;
    void scrollToEnd(true);
    try {
      await streamPrompt(
        {
          text,
          input_mode: inputMode,
          surface: "chat",
          session_id: sessionId ?? undefined,
          ...(retryOf !== null && sessionId !== null ? { retry_of_turn_id: retryOf } : {}),
          model_profile: modelProfile || undefined,
          model: model || undefined,
          ...(reasoningEfforts.includes(reasoningEffort) ? { reasoning_effort: reasoningEffort } : {}),
          attachments: wireAttachments(sentAttachments),
          ...(Object.keys(sentModes).length > 0 ? { capability_modes: sentModes } : {}),
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
            void inspector.refreshTurnSources(event.response.session_id);
            void recall.refresh(event.response.session_id);
            void refreshContextUsage();
            if (plan === null) void loadPlan();
            window.dispatchEvent(new Event("raiker:chats-changed"));
            // QUI-C01 — a new conversation learns the title the runtime gave it.
            if (handoffTitle !== null) void nameHandedOffChat(event.response.session_id, handoffTitle);
            else if (conversationTitle === "") void refreshTitle(event.response.session_id);
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
        if (sentDraft.text === "") sentDraft.text = text;
        voiceDictated = voiceState.dictated;
        voiceTypedBefore = voiceState.typedBefore;
        voiceEditedAfter = voiceState.editedAfter;
        attachStore.set(sentAttachments);
        await refreshModels();
        openModelSetup(activeProfile);
        return;
      }
      // BUG-285 — the refusal the runtime named, not the status number it came
      // with, and no blanket reachability claim about a turn that had already
      // streamed something.
      turn.error = turnFailureMessage(e, {
        produced: answerText(turn) !== "" || toolActivity(turn.events).length > 0,
      });
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

  /**
   * QUI-C08 — the transcript follows a streaming answer only while the owner is
   * at the bottom. Scrolling up to read stops the following, and **Jump to
   * latest** brings it back. Sending, opening a conversation and continuing
   * after a decision are the owner's own acts, so they always scroll.
   */
  let following = $state(true);
  const FOLLOW_SLACK_PX = 48;

  function onThreadScroll() {
    if (!scrollEl) return;
    const fromBottom = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight;
    following = fromBottom <= FOLLOW_SLACK_PX;
  }

  async function scrollToEnd(force = false) {
    if (!force && !following) return;
    following = true;
    await tick();
    // Guarded: jsdom (vitest) has no scrollTo implementation.
    if (typeof scrollEl?.scrollTo === "function") {
      scrollEl.scrollTo({ top: scrollEl.scrollHeight });
    }
  }

  // MEM-08 — land on the exchange the link named.
  //
  // The anchor is spent on arrival: it is dropped from the address bar so a
  // later reload opens the conversation as it is rather than replaying a
  // highlight, and the notice says plainly when the coordinate is not in this
  // conversation instead of leaving the reader at the top wondering.
  let anchorNotice = $state<string | null>(null);

  async function landOnAnchor(turnId: string) {
    ensureShown(turns.findIndex((turn) => turn.response?.turn_id === turnId));
    await tick();
    anchorNotice = revealTurn(scrollEl, turnId)
      ? null
      : "That exchange is not in this conversation.";
    forgetTurnInRoute();
    if (anchorNotice === null) return;
    void scrollToEnd(true);
  }

  // The anchor is honoured whenever it changes and the transcript is ready to
  // receive it — not only on the load that first opened the conversation.
  // Opening one search result and then a second one *in the same conversation*
  // never reloads anything, so landing from `loadHistory` alone would silently
  // ignore the second link. `landedAnchor` is what keeps a still-set anchor
  // from re-marking the exchange every time a new turn arrives.
  let landedAnchor: string | null = null;

  $effect(() => {
    const anchor = anchoredTurnId;
    const ready = !historyLoading && turns.length > 0;
    if (anchor === null || anchor === "" || anchor === landedAnchor || !ready) return;
    landedAnchor = anchor;
    untrack(() => void landOnAnchor(anchor));
  });

  // ── C14/B19 — composer ergonomics: slash commands, `@` mentions, auto-grow ──
  //
  // Shared with Build through `composerCommands.ts`, so the two composers cannot
  // drift into two different keyboards. Every command listed runs a control this
  // surface already has; none of them grants anything.
  let promptEl = $state<HTMLTextAreaElement | undefined>();
  let modelPickerOpen = $state(false);
  let menuKind = $state<"none" | "slash" | "mention">("none");
  let menuActive = $state(0);
  // UX-CHAT-01 / UX-BUILD-01 — the mention lookup and the owner's skill
  // commands, one controller shared with the other composer.
  const lookups = new ComposerLookups({ href: "#/build", label: "Build" });
  let shortcutsOpen = $state(false);

  const slashItems = $derived.by<MenuItem[]>(() => {
    const fragment = menuKind === "slash" ? slashFragment(draft.text, caret()) : null;
    if (fragment === null) return [];
    return matchCommands("chat", fragment, lookups.slashCommands).map((command) => ({
      id: command.name,
      label: `/${command.name}`,
      detail: command.summary,
    }));
  });
  const menuItems = $derived(menuKind === "slash" ? slashItems : lookups.mentionItems);

  function caret(): number {
    return promptEl?.selectionStart ?? draft.text.length;
  }


  onMount(lookups.loadSlashCommands);

  function trackPromptSelection() {
    promptSelectionStart = promptEl?.selectionStart ?? draft.text.length;
    promptSelectionEnd = promptEl?.selectionEnd ?? promptSelectionStart;
  }

  function onVoiceDraft(next: string, cursor: number) {
    draft.text = next;
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
    if (!voiceDictated) voiceTypedBefore = draft.text.trim() !== "";
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
    if (slashFragment(draft.text, position) !== null) {
      menuKind = "slash";
      return;
    }
    const mention = mentionAt(draft.text, position);
    if (mention !== null) {
      menuKind = "mention";
      void lookups.loadMentions(mention.fragment);
      return;
    }
    menuKind = "none";
    lookups.mentionNotice = null;
  }


  function chooseMenuItem(item: MenuItem) {
    if (menuKind === "slash") {
      draft.text = stripSlashToken(draft.text);
      menuKind = "none";
      runSlashCommand(item.id);
      return;
    }
    const mention = mentionAt(draft.text, caret());
    if (mention === null) return;
    const applied = applyMention(draft.text, mention, item.id);
    draft.text = applied.text;
    menuKind = "none";
    queueMicrotask(() => {
      promptEl?.focus();
      promptEl?.setSelectionRange(applied.caret, applied.caret);
      autoGrow(promptEl ?? null);
    });
  }

  /** Run one command. Each of these is a control the owner already has. */
  function runSlashCommand(name: string) {
    if (lookups.slashCommands.some((command) => command.name === name)) {
      const args = draft.text.trim();
      draft.text = `/${name}${args ? ` ${args}` : ""}`;
      void submit();
      return;
    }
    switch (name) {
      case "new": newConversation(); break;
      case "model": modelPickerOpen = true; break;
      case "attach": attachOpen = true; break;
      case "context": contextOpen = true; void refreshContextUsage(); break;
      case "approvals": window.location.hash = "#/approvals"; break;
      // The workspace assistant's two: schedule work, and see what is already running. The
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
    draft.text = text;
    menuKind = "none";
    queueMicrotask(() => {
      promptEl?.focus();
      promptEl?.setSelectionRange(text.length, text.length);
      autoGrow(promptEl ?? null);
    });
  }

  /**
   * Quiet UI 04 — an answer of more than three blocks offers *Create
   * document*. It puts the request in the composer rather than sending it: the
   * document is written by the governed `create_document` tool on a turn the
   * owner chose to send, never by the offer itself.
   */
  /** QUI-F18 — the request that worked, with its recorded steps, as a draft routine. */
  function saveAsRoutine(prompt: string, rows: ToolCallRow[]) {
    requestTaskDraft(routineFromTurn(prompt, conversationTitle, routineSteps(rows)));
    window.location.hash = "#/tasks";
  }

  function documentFromAnswer() {
    editPrompt("Put your last answer, with its figures, comparisons and charts, into a document I can keep.");
  }

  /**
   * Send the same prompt again, unchanged, as a new turn.
   *
   * BUG-306 — **Retry** looked identical whether the first attempt had done
   * nothing or had written a file, run a command or sent a message. Re-sending
   * runs those again, and Raiker cannot tell whether doing them twice is safe:
   * that is the owner's decision, so it is put to them, with what would be
   * repeated named rather than implied.
   */
  async function retryPrompt(text: string, rows: ToolCallRow[] = [], sourceTurnId: string | null = null) {
    if (streaming || text.trim() === "") return;
    const consequence = retryConsequence(rows);
    if (consequence.repeats && !(await askConfirm({ title: retryConfirmation(consequence), confirmLabel: "Ask again" }))) return;
    draft.text = text;
    // DEC-22 step 3 — the new turn names the one it asks again, so the record
    // says these are one request tried twice rather than two requests.
    void submit(sourceTurnId);
  }

  /** Bring the turn a Retry asked again into view. */
  async function showRetrySource(turnId: string) {
    ensureShown(turns.findIndex((turn) => turn.response?.turn_id === turnId));
    await tick();
    const target = document.querySelector(`[data-turn-id="${CSS.escape(turnId)}"]`);
    if (target instanceof HTMLElement) target.scrollIntoView({ block: "center" });
  }

  // UX-CHAT-01 — branch, rewind and summarise: the Continuity actions, owned
  // by one controller (see `./chat/turnContinuity.svelte.ts`).
  const continuity = new TurnContinuity(
    () => sessionId,
    () => streaming,
    (text) => {
      projectNotice = text;
    },
    () => inspector.close(),
  );

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
      exportNotice = `Stop was not sent. The turn is still running. ${NOT_ANSWERING}`;
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
    if (menuKind !== "none" && (menuItems.length > 0 || lookups.mentionNotice !== null)) {
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

  /**
   * QUI-H01 — a message from Home's composer starts a conversation of its own.
   * It is never appended to whatever conversation Chat last showed. While a
   * turn is still running the message waits in the composer instead of being
   * dropped, because `submit()` refuses to start a second turn.
   */
  /**
   * QUI-C01 — the conversation's title, shown and renamed in the header.
   *
   * It is the same title Work › Threads and the sidebar show, renamed through
   * the same `PUT /api/sessions/{id}/rename`. A failed rename keeps the old
   * title and says so; it never shows a name the runtime did not store.
   */
  let conversationTitle = $state("");
  let editingTitle = $state(false);
  let titleDraft = $state("");
  let titleNotice = $state<string | null>(null);

  async function refreshTitle(id: string) {
    try {
      const detail = await api.session(id);
      if (id === sessionId) conversationTitle = detail.session?.title ?? "";
    } catch {
      // The header simply keeps no title until the next read.
    }
  }

  /** QUI-W05 — the first task from setup is kept in Threads as "Getting started". */
  async function nameHandedOffChat(id: string, title: string) {
    handoffTitle = null;
    try {
      const renamed = await api.renameSession(id, title);
      if (id === sessionId) conversationTitle = renamed.title;
      window.dispatchEvent(new Event("raiker:chats-changed"));
    } catch {
      void refreshTitle(id);
    }
  }

  function startTitleEdit() {
    titleDraft = conversationTitle;
    titleNotice = null;
    editingTitle = true;
  }

  async function commitTitle() {
    if (!editingTitle) return;
    editingTitle = false;
    const next = titleDraft.trim();
    if (sessionId === null || next === "" || next === conversationTitle) return;
    try {
      const renamed = await api.renameSession(sessionId, next);
      conversationTitle = renamed.title;
      window.dispatchEvent(new Event("raiker:chats-changed"));
    } catch {
      titleNotice = "Could not rename this conversation. Its title is unchanged.";
    }
  }

  function onTitleKeydown(event: KeyboardEvent) {
    if (event.key === "Enter") {
      event.preventDefault();
      void commitTitle();
    } else if (event.key === "Escape") {
      event.preventDefault();
      editingTitle = false;
    }
  }

  function useStarter(prompt: string) {
    draft.text = prompt;
    promptEl?.focus();
  }

  /** QUI-W05 — a title the hand-off asked the new conversation to carry. */
  let handoffTitle: string | null = null;

  async function startHandedOffChat({ text, attachments, title, profile }: ChatHandoff) {
    if (streaming) {
      draft.text = text;
      if (attachments.length > 0) attachStore.set([...attachments]);
      return;
    }
    if (turns.length > 0 || sessionId !== null) newConversation();
    handoffTitle = title ?? null;
    // QUI-P02 — the profile chosen on Home's composer.
    conversationProfile = profile ?? "standard";
    draft.text = text;
    // QUI-H01 — files attached on Home's composer travel with the message.
    if (attachments.length > 0) attachStore.set([...attachments]);
    // A Chat that has only just mounted has not read its models, or the model
    // Chat was last set to, and an unread choice looks like no model at all.
    // Both are read before the message is judged (found live, RT-QUI-03).
    if (!modelsKnown()) await refreshModels();
    await surfaceModelRead;
    await tick();
    void submit();
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
    earlierShown = 0;
    sessionId = null;
    conversationProfile = "standard";
    conversationTitle = "";
    editingTitle = false;
    titleNotice = null;
    /*
     * Found while closing RR-PROJECT-01: the *second* chat in a project was
     * filed nowhere. `pendingProjectId` is consumed when the first conversation
     * is created, and starting another one left it null while the composer went
     * on naming the project — the picker said one thing and the filing did
     * another, which is the consistency gate this review is built around. A new
     * conversation re-reads the project the composer is showing.
     */
    pendingProjectId = projectId === "" ? null : projectId;
    plan = null;
    continuity.rewindCheckpointId = null;
    anchorNotice = null;
    landedAnchor = null;
    recall.reset();
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
    // The owner chose a project for the work they are doing, so the next Build
    // turn and the next Design generation start there too.
    setWorkProject(value);
    projectNotice = null;
    const target = value === "" ? null : value;
    if (sessionId === null) {
      pendingProjectId = target;
      projectNotice =
        target === null
          ? "This chat will stay outside every project."
          : "This chat will be filed there as soon as it starts. Filing organises it; recall still draws on all your memory.";
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
          : `Filed under ${projects?.projects.find((project) => project.project_id === target)?.name ?? "the project"}. Recall still draws on all your memory.`;
      onProjectsChanged?.();
    } catch (error) {
      projectNotice = error instanceof ApiError ? `Could not move this chat (${error.status}).` : "Could not move this chat.";
    }
  }

  // ── BUG-24: continue a turn whose approval was resolved anywhere ──────────
  //
  // A Chat tab learns of a decision made anywhere — another tab, Approvals —
  // and continues the parked turn. The server's atomic claim keeps the
  // guarantee: a turn resumes exactly once even when two tabs both react.
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
        : `The turn did not continue. It is still waiting here. ${NOT_ANSWERING}`;
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
      outcomeStatus === "rejected"
        ? "Rejected — telling Raiker…"
        : outcomeStatus === "answered"
          ? "Answered — continuing…"
          : "Approved — continuing…";
    turn.streaming = true;
    turn.error = null;
    streaming = true;
    void scrollToEnd(true);
    try {
      await streamResumeAfterApproval(approvalId, (event) => {
        if (event.kind === "final" && event.response !== null) {
          turn.response = event.response;
          turn.resumeState = null;
          turn.resumeNote = null;
          void restoreAttachmentChips(event.response.session_id);
          void inspector.refreshTurnSources(event.response.session_id);
          void refreshContextUsage();
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
      exportNotice = `Raiker could not check whether a decision is waiting. Nothing was approved or refused. ${NOT_ANSWERING}`;
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
<!-- One detail panel at a time: the inspector and the rewind preflight share
     the right-hand column, so opening either never stacks a second panel under
     the composer where nobody looks for it. -->
<!-- The Work contract, declared where it can be seen. The mode and
     its density are on the shell itself, so what this surface is *about* and how
     tightly it packs are readable from the page rather than asserted in a
     comment; `workSurface.ts` is the one place either can change. -->
<div
  class="chat-layout"
  data-work-surface={surface.mode}
  data-primary-object={surface.primaryObject}
  data-density={surface.density}
  style={`--surface-gap:${densityGap(surface.density)}`}
  class:with-inspector={inspector.inspecting !== null || continuity.rewindCheckpointId !== null}
  class:with-rail={backgroundWorkOpen}
  class:with-context={contextPanelOpen}
>
<div class="chat">
  <header class="chat-header">
    {#if sessionId !== null && (conversationTitle !== "" || editingTitle)}
      <div class="conversation-title">
        {#if editingTitle}
          <!-- svelte-ignore a11y_autofocus -->
          <input
            class="title-input"
            aria-label="Conversation title"
            bind:value={titleDraft}
            onkeydown={onTitleKeydown}
            onblur={() => void commitTitle()}
            maxlength="200"
            autofocus
          />
        {:else}
          <h2 class="title-text" title={conversationTitle}>{conversationTitle}</h2>
          <button type="button" class="btn btn-ghost btn-sm" aria-label="Rename conversation" title="Rename conversation" onclick={startTitleEdit}>
            <Icon name="pencil" size="sm" />
          </button>
        {/if}
        {#if titleNotice}<span class="title-notice" role="alert">{titleNotice}</span>{/if}
      </div>
    {/if}
    <!-- QUI-C01 — the project this chat is filed in, as a chip that opens it.
         No chip when the chat is not filed anywhere. -->
    {#if selectedProject !== null}
      <a
        class="project-chip"
        href={`#/projects?project=${encodeURIComponent(selectedProject.project_id)}`}
        title={`Filed in ${selectedProject.name}`}
      ><Icon name="folder" size="sm" /><span>{selectedProject.name}</span></a>
    {/if}
    <div class="header-actions">
      {#if searchOpen}
        <div class="conversation-search" role="search">
          <input
            bind:this={searchInput}
            bind:value={searchQuery}
            type="search"
            aria-label="Search in conversation"
            placeholder="Find in this chat"
            onkeydown={onSearchKeydown}
          />
          {#if searchQuery.trim() !== ""}
            <span class="search-count" aria-live="polite">{matchLabel(Math.min(searchAt, Math.max(searchHits.length - 1, 0)), searchHits.length)}</span>
          {/if}
          <button type="button" class="btn btn-ghost btn-sm" aria-label="Previous match" title="Previous match" disabled={searchHits.length === 0} onclick={() => showHit(-1)}>↑</button>
          <button type="button" class="btn btn-ghost btn-sm" aria-label="Next match" title="Next match" disabled={searchHits.length === 0} onclick={() => showHit(1)}>↓</button>
          <button type="button" class="btn btn-ghost btn-sm" aria-label="Close search" title="Close search" onclick={closeSearch}><Icon name="x" size="sm" /></button>
        </div>
      {:else if turns.length > 0}
        <button type="button" class="btn btn-ghost btn-sm" aria-label="Search in conversation" title="Search in conversation" onclick={() => void openSearch()}>
          <Icon name="search" size="sm" />
        </button>
      {/if}
      {#if turns.length > 0 || contextPanelOpen}
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          aria-expanded={contextPanelOpen}
          aria-controls="chat-context"
          title="What this conversation is using"
          onclick={() => (contextPanelOpen = !contextPanelOpen)}
        >Context</button>
      {/if}
      <!-- QUI-Q05 — offered once there is a conversation to leave. A disabled
           "New chat" on an empty one read as a faded title, not an action. -->
      {#if turns.length > 0}
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={newConversation}
          disabled={streaming}
        >
          New chat
        </button>
      {/if}
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
          <!-- UX-CHAT-05 — one model for every conversation-level action:
               **Conversation** (the record itself), **Evidence** (how it was
               produced) and **Continuity** (where it goes next). The same
               three words head the per-message More menu's Continuity group
               and the turn's own Evidence disclosure, so an action is found
               under the same name wherever it is reached. -->
          <div class="menu grouped-menu" role="menu" aria-label="Conversation actions">
            <div role="group" aria-label="Conversation">
              <p class="menu-group" aria-hidden="true">Conversation</p>
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
            <div role="group" aria-label="Evidence">
              <p class="menu-group" aria-hidden="true">Evidence</p>
              {#if sessionId !== null}
                <a
                  role="menuitem"
                  href={evidenceLink(sessionId)}
                  onclick={() => (conversationMenuOpen = false)}
                >Every governed step in this conversation</a>
              {:else}
                <button type="button" role="menuitem" disabled>Every governed step in this conversation</button>
              {/if}
            </div>
            <div role="group" aria-label="Continuity">
              <p class="menu-group" aria-hidden="true">Continuity</p>
              <button
                type="button"
                role="menuitem"
                onclick={() => {
                  conversationMenuOpen = false;
                  backgroundWorkOpen = true;
                }}
              >Background work</button>
            </div>
          </div>
        {/if}
      </div>
      <!-- QUI-Q05 — the toggle appears when there is background work to look
           at; the conversation menu's "Background work" opens it any time. -->
      {#if backgroundWorkOpen || hasBackgroundWork(background)}
      <button
        type="button"
        class="btn btn-ghost btn-sm rail-toggle"
        onclick={() => (backgroundWorkOpen = !backgroundWorkOpen)}
        aria-expanded={backgroundWorkOpen}
        aria-controls="chat-background-work"
        aria-label={backgroundLabel(background)}
        title={backgroundLabel(background)}
        class:rail-failed={(background?.failed ?? 0) > 0}
      >
        <Icon name="panel" size="sm" />
        <span class="rail-label">Background</span>
        {#if background && background.active > 0}
          <span class="rail-count" aria-hidden="true">{background.active}</span>
        {/if}
        {#if background && background.failed > 0}
          <span class="rail-alert" aria-hidden="true">!</span>
        {/if}
      </button>
      {/if}
    </div>
  </header>
  {#if exportNotice}<span class="export-notice" role="status" aria-live="polite">{exportNotice}</span>{/if}
  <!-- MEM-08 — said only when a link named an exchange this conversation does
       not hold. Landing successfully is shown by the highlight, not by text. -->
  {#if anchorNotice}<span class="export-notice" role="status">{anchorNotice}</span>{/if}
  <!-- C17 — the result of a correction or a forget made from the transcript,
       said once, where the other turn-level outcomes are said. -->
  {#if recall.notice}<span class="export-notice" role="status" aria-live="polite">{recall.notice}</span>{/if}
  <!-- C14 — a branch says where it grew from, which is what makes two branches of
       one conversation legible rather than two unrelated chats that happen to
       start the same way. The original is reachable and unchanged. -->
  {#if continuity.branchOrigin !== null}
    <p class="branch-origin">
      <Icon name="branch" size="sm" />
      <span>
        Branched from
        <a href={`#/new-chat?session=${encodeURIComponent(continuity.branchOrigin.source_session_id ?? "")}`}
          >{continuity.branchOrigin.source_title ?? "an earlier conversation"}</a
        >{#if continuity.branchOrigin.summary}, at “{continuity.branchOrigin.summary}”{/if}. That conversation kept every
        turn it had.
      </span>
    </p>
  {/if}
  {#if plan !== null}
    <div class="plan-slot">
      <PlanChecklist {plan} bind:collapsed={planCollapsed} />
    </div>
  {/if}

  <div class="thread" bind:this={scrollEl} onscroll={onThreadScroll}>
    {#if historyError !== null}
      <p class="error-line" role="alert">{historyError}</p>
    {/if}
    {#if historyLoading}
      <PageState state="loading" title="Loading conversation…" />
    {:else if turns.length === 0}
      <EmptyState
        icon="chat"
        title={userName ? `What would you like to work on, ${userName}?` : "What would you like to work on?"}
        compactTitle="What can I help with?"
        body="Start with a question, a task, or a file."
        serif={true}
      />
      <!-- QUI-C10 — at most four starters, the same four Home offers on a
           first day. A question fills the composer for the owner to edit; it
           never sends on its own. Build and Design open their own surface. -->
      <ul class="chat-starters" aria-label="Ways to start">
        {#each STARTERS as starter (starter.id)}
          <li>
            {#if starter.kind === "prompt"}
              <button type="button" class="chat-starter" onclick={() => useStarter(starter.prompt)}>
                <Icon name={starter.icon} size="sm" /><span>{starter.label}</span>
              </button>
            {:else}
              <a class="chat-starter" href={starter.href}>
                <Icon name={starter.icon} size="sm" /><span>{starter.label}</span>
              </a>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if firstShown > 0}
      <button type="button" class="btn btn-ghost btn-sm show-earlier" onclick={() => void showEarlier()}>
        Show {Math.min(TURN_WINDOW, firstShown)} earlier messages
      </button>
    {/if}
    {#each shownTurns as turn, shownIndex (turn.id)}
      {@const turnIndex = firstShown + shownIndex}
      {@const answer = answerText(turn)}
      {@const toolRows = toolActivity(turn.events)}
      <!-- BUG-215 — the stream first, because a turn that is running has the
           freshest working; the stored text when there is no stream to read,
           which is every re-opened turn. -->
      {@const reasoning = collectReasoning(turn.events) || (turn.retainedReasoning ?? "")}
      {@const uploadedAttachments = turn.attachments.filter((a) => a.source !== "generated")}
      {@const generatedFiles = turn.attachments.filter((a) => a.source === "generated")}
      {@const turnSourceList = sourcesForTurn(inspector.turnSources, turn.response?.turn_id)}
      <!-- MEM-08 — the coordinate a link can name. Present on every settled
           turn, so a search result, a citation or a checkpoint can land here. -->
      <div
        class="turn"
        class:search-hit={currentHit === turnIndex}
        class:settled={!turn.streaming && turnIndex < turns.length - 2}
        data-turn-id={turn.response?.turn_id ?? undefined}
        data-turn-index={turnIndex}
      >
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
              onretry={(text: string) => retryPrompt(text, toolRows, turn.response?.turn_id ?? null)}
              onbranch={turn.response?.turn_id
                ? () => void continuity.branchFromTurn(turn.response?.turn_id ?? "")
                : undefined}
              branching={continuity.branchingTurn === turn.response?.turn_id}
              oncompact={turn.response?.turn_id
                ? () => void continuity.compactThroughTurn(turn.response?.turn_id ?? "")
                : undefined}
              compacting={continuity.compactingTurn === turn.response?.turn_id}
              onrewind={turn.response?.turn_id
                ? () => void continuity.rewindFromTurn(turn.response?.turn_id ?? "")
                : undefined}
              rewinding={continuity.rewindingTurn === turn.response?.turn_id}
            />
          {/if}
          {#if turn.retryOf}
            <!-- DEC-22 step 3 — a Retry is a new attempt linked to its source;
                 the earlier turn is kept exactly as it was. -->
            <p class="retry-of">
              Retry of
              <button type="button" class="retry-link" onclick={() => void showRetrySource(turn.retryOf ?? "")}
                >an earlier turn</button>
              — that turn is kept as it was.
            </p>
          {/if}
          <!-- BUG-208 slice F — nothing is appended to the owner's message. A
               label that names an actor and an act may only describe an act
               that happened. -->
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
                  expanded={inspector.inspecting?.attachmentId === a.attachmentId}
                  onopen={a.attachmentId !== undefined && sessionId !== null
                    ? () => void inspector.openFile(a.attachmentId as string, a.label)
                    : null}
                />
              {/each}
            </div>
          {/if}
        </div>

        <div class="message-group message-group-raiker">
          <!-- BUG-207 slices C and D — the model's own reasoning, and nothing
               standing in for it: shown only when the turn produced some,
               collapsed when the answer starts, absent when there is none.
               The indicator below ends at the first token or the first tool
               row, whichever says more about what Raiker is doing. -->
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
          {#if !turn.streaming}
            {@const outcome = turnOutcome(turn.response?.status, toolRows)}
            {#if outcome !== null}
              <!-- QUI-C03 — how a turn that did something ended, in one line. -->
              <p class="outcome-line outcome-{outcome.tone}">
                <strong>{outcome.label}</strong><span> · {outcome.detail}</span>
              </p>
            {/if}
          {/if}

          {#if !turn.streaming && turn.response?.status === "stopped"}
            <p class="stopped-line" role="status">
              Stopped at your request — this turn ended at a safe boundary and kept what it had
              already done.
            </p>
          {/if}

          {#if answer !== "" && !(turn.response?.status === "needs_approval" && ownerQuestions(turn.response.approval) !== null)}
            <!-- QUI-F02 — a turn parked on a question shows its card below;
                 the parked notice ("Waiting for your decision") is not said
                 a second time, and not in the wrong words. -->
            <div class="message-bubble message-bubble-raiker">
              <!-- C6 — `[s1]` becomes a chip only when this turn's ledger has an
                   s1. A marker the model invented stays the characters it is. -->
              <!-- BUG-288 — the answer's declared parts, when it declared
                   any. A turn that declared none renders exactly as before,
                   through the same Markdown component. -->
              <AnswerParts
                text={answer}
                parts={turn.response?.content_parts ?? []}
                citations={renderableCitations(turnSourceList)}
                oncite={(sourceId) => inspector.openSourceById(turn.response?.turn_id ?? "", sourceId, answer)}
                ondocument={turn.streaming ? undefined : documentFromAnswer}
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
              ><Icon name={copiedTurnId === String(turn.id) ? "check" : "copy"} size="sm" /></button>
              {#if turn.response?.status === "completed" && !toolRows.some((row) => row.state === "failed" || row.state === "denied" || row.state === "refused")}
                <!-- QUI-F18 — after a task goes well: make it repeatable. It
                     opens a filled task form in Work › Tasks; nothing is saved
                     or scheduled until the owner presses Create there. -->
                <button
                  type="button"
                  class="copy-message"
                  onclick={() => saveAsRoutine(turn.prompt, toolRows)}
                  aria-label="Save as routine"
                  title="Save as routine"
                ><Icon name="refresh" size="sm" /></button>
              {/if}
              </div>
            {/if}
          {:else if !turn.streaming && turn.error === null && turn.response !== null && turn.response.status !== "needs_approval"}
            <!-- BUG-73 — a turn with no answer has a state, not an answer; a
                 placeholder stored as the answer becomes a durable false claim.
                 BUG-206 — a parked turn says so on the waiting call's own row and
                 in the approval card, not a third time here. -->
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
              openSourceId={inspector.openSourceTurnId === turn.response?.turn_id ? inspector.openSourceId : null}
              onopen={(source) => void inspector.openSource(source, sentenceAround(answer, source.source_id))}
            />
          {/if}
          {#if !turn.streaming && sessionId !== null && turn.response?.turn_id && turn.response.status !== "needs_approval"}
            <!-- QUI-F16 — the receipt at the end of the task: model, cost, what
                 was read, changed or sent, and what left this computer. -->
            <TurnReceipt {sessionId} turnId={turn.response.turn_id} />
            {@const correction = turn.response.status === "completed" ? correctionToRemember(turn.prompt) : null}
            {#if correction !== null}
              <!-- QUI-F20 — the owner corrected Raiker: offer to remember it. -->
              <CorrectionMemory {sessionId} turnId={turn.response.turn_id} text={correction} />
            {/if}
          {/if}

          <!-- C17 — the memories this turn was given, correctable here. Recall
               is ambient, so it leaves no citation to click: without this strip
               the only place an owner could see what Raiker remembers about
               them is the Memory route, never the answer it shaped. -->
          {#if !turn.streaming}
            <RecallStrip
              memories={recall.forTurn(turn.response?.turn_id)}
              disclosure={recall.disclosureFor(turn.response?.turn_id)}
              onforget={recall.forget}
              oncorrect={recall.correct}
            />
          {/if}

          {#if generatedFiles.length > 0}
            <section class="artifact-stack" aria-label="Generated documents">
              {#each generatedFiles as file (file.attachmentId)}
                <article class="artifact-card" data-status={file.attachmentId ? "ready" : "unavailable"}>
                  <div class="artifact-icon" aria-hidden="true"><Icon name="file" size="lg" /></div>
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
                        aria-expanded={inspector.inspecting?.attachmentId === file.attachmentId}
                        onclick={() => void inspector.openGeneratedFile(file.attachmentId as string, file.label)}
                      >Preview</button>
                      <!-- BUG-28 — Download is its own action, not a second
                           name for Preview: it produces the file on disk. -->
                      <button
                        type="button"
                        class="btn btn-ghost btn-sm artifact-download"
                        aria-label={`Download ${file.label}`}
                        onclick={() => void inspector.downloadArtifact(file.attachmentId as string, file.label)}
                      ><Icon name="download" size="sm" /> Download</button>
                    </div>
                  {:else}
                    <span class="artifact-unavailable">Preview unavailable</span>
                  {/if}
                  {#if inspector.artifactNotice !== null && inspector.artifactNotice.attachmentId === file.attachmentId}
                    <p class="artifact-error error-line" role="alert">{inspector.artifactNotice.text}</p>
                  {/if}
                </article>
              {/each}
            </section>

          {/if}

          {#if turn.error !== null}
            <p class="error-line" role="alert">{turn.error}</p>
          {/if}

          <!-- BUG-206 slice E — a refused call is its own row in a refused
               state, with its reasons and remediation link, where it was refused;
               there is no separate refusal block after the answer. -->

          <!-- REM-CHAT-01 — the turn's own evidence, under the turn rather than
               on another route. Collapsed, so the answer and the decisions it
               asked for keep the primary reading order; it reads nothing until
               it is opened. -->
          {#if !turn.streaming && turn.response?.turn_id}
            <TurnEvidence
              sessionId={sessionId}
              turnId={turn.response.turn_id}
              rows={toolRows}
              sources={turnSourceList.length}
              approvals={turn.response?.approval ? 1 : 0}
            />
          {/if}

          {#if turn.response?.status === "needs_approval" && turn.response.approval}
            <!-- BUG-24 — this card is the parked turn's live state. Once a
                 decision is recorded anywhere it flips to "continuing" without
                 a reload, and the manual action stays available whenever the
                 live channel cannot be relied on. -->
            <div
              class="approval-card"
              class:continuing={turn.resumeState === "continuing"}
              class:inline-decision={turn.resumeState !== "continuing" && turn.resumeState !== "elsewhere"}
            >
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
                  <Icon name="approvals" size="sm" /> Continued in another tab
                </p>
                <p class="approval-note">{turn.resumeNote}</p>
              {:else}
                <!-- QUI-P05 — the decision itself, in place: Decline, Change,
                     Allow once. Decided here, it clears the top bar's count,
                     the floating card and the Approvals queue too. -->
                {@const asked = ownerQuestions(turn.response.approval)}
                {#if asked !== null && asked.length > 0}
                <!-- QUI-F02 — a question is answered, not allowed: its own
                     card and its own route, never Decline / Allow once. -->
                <ClarifyCard
                  approvalId={turn.response.approval.approval_id}
                  questions={asked}
                  {sessionId}
                  disabled={streaming}
                  onAnswered={(resumable) => {
                    if (resumable) void resumeParkedTurn(turn.response?.approval?.approval_id ?? "", "answered");
                  }}
                />
                {:else}
                <SafetyCard
                  approval={turn.response.approval}
                  {sessionId}
                  disabled={streaming}
                  onDecided={(approved, resumable) => {
                    if (resumable) void resumeParkedTurn(turn.response?.approval?.approval_id ?? "", approved ? "approved" : "rejected");
                  }}
                  onAskAgain={() => retryPrompt(turn.prompt, toolRows, turn.response?.turn_id ?? null)}
                />
                {/if}
                {#if liveChannelDown}
                  <div class="approval-actions">
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm"
                      disabled={streaming}
                      onclick={() => void continueNow()}
                    >Continue now</button>
                  </div>
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

  {#if !following && turns.length > 0}
    <!-- QUI-C08 — reading further up stops the transcript following the
         answer; this brings it back. -->
    <div class="jump-slot">
      <button type="button" class="btn btn-soft btn-sm jump-latest" onclick={() => void scrollToEnd(true)}>
        <Icon name="chevron-down" size="sm" />Jump to latest
      </button>
    </div>
  {/if}

  <Composer
    ariaLabel="Message composer"
    inputId="prompt-input"
    bind:value={draft.text}
    bind:inputEl={promptEl}
    inputProps={{
      placeholder: "What would you like Raiker to do?",
      title: "Enter to send, Shift+Enter for a new line, / for commands, @ to mention a file",
      disabled: streaming,
      onpaste: onComposerPaste,
      oninput: onPromptInput,
      onselect: trackPromptSelection,
      onclick: trackPromptSelection,
      onkeyup: trackPromptSelection,
      onkeydown: onKeydown,
      onblur: () => (menuKind = "none"),
    }}
    dropActive={composerDrop.over}
    dropHandlers={{
      ondragenter: composerDrop.ondragenter,
      ondragover: composerDrop.ondragover,
      ondragleave: composerDrop.ondragleave,
      ondrop: composerDrop.ondrop,
    }}
    onsubmit={() => void submit()}
    turnActive={streaming}
  >
    {#snippet above()}
      <ComposerChips store={attachStore} disabled={streaming} oninline={(text) => { draft.text += text; }} />
      <ModelReadinessStrip readiness={modelsKnown() ? modelReadiness : null} draftPreserved={draft.text.trim() !== ""} />
      {#if sendWhenReady !== null}
        <p class="send-when-ready" role="status">
          Your message will send as soon as a model is ready.
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => (sendWhenReady = null)}>Don't send</button>
        </p>
      {/if}
      <SkillLinkNotice text={draft.text} />

      {#if shortcutsOpen}
        <ShortcutSheet surface="chat" onclose={() => (shortcutsOpen = false)} />
      {/if}
      {#if menuKind !== "none"}
        <ComposerMenu
          items={menuItems}
          active={menuActive}
          heading={menuKind === "slash" ? "Commands" : "Files in the code map"}
          notice={menuKind === "mention" ? lookups.mentionNotice : null}
          onchoose={chooseMenuItem}
        />
      {/if}
    {/snippet}

    {#snippet below()}
      {#if attachOpen}
        <ComposerAttachPanel store={attachStore} disabled={streaming} idPrefix="chat" />
      {/if}
      <!-- COMPOSER-03 — the project select was a permanent control for a choice
           that changes every few days. It opens from `+`, in flow between the
           prompt and the bar rather than as a popover over the text being
           typed, which is the same reasoning `ComposerAttachPanel` was built
           on. -->
      {#if projectPickerOpen}
        <div class="project-choice" role="group" aria-label="Choose a project">
          <label for="chat-project-choice">Project for this chat</label>
          <select
            id="chat-project-choice"
            class="bar-select"
            value={projectId}
            onchange={(event) => {
              projectPickerOpen = false;
              void onProjectPicked((event.currentTarget as HTMLSelectElement).value);
            }}
          >
            <option value="">No project — this chat stands alone</option>
            {#each pickableProjects(projects, projectId) as project (project.project_id)}
              <option value={project.project_id}>{project.name}</option>
            {/each}
          </select>
          <button
            type="button"
            class="btn btn-ghost btn-sm"
            onclick={() => (projectPickerOpen = false)}>Done</button
          >
        </div>
      {/if}
    {/snippet}

    {#snippet turn()}
      <TurnControl sessionId={sessionId} bind:stopping activity={runningActivity} />
    {/snippet}

    {#snippet left()}
          <!-- COMPOSER-02 — two controls at rest, holding every composer
               action, so the prompt is the thing on the screen. -->
          <ComposerActionMenu
            kind="add"
            items={addItems}
            disabled={streaming}
            onchoose={runComposerAction}
          />
          <ComposerActionMenu
            kind="tools"
            items={toolItems}
            disabled={streaming}
            onchoose={runComposerAction}
          />
          <!-- The session, not the trigger: "Listening…", Done and Cancel are
               the state of dictation in progress and belong beside the prompt
               being filled, not behind a menu that has already closed. The
               trigger is an entry in `+`. -->
          <VoiceDictationControl
            bind:this={voiceControl}
            showTrigger={false}
            draft={draft.text}
            selectionStart={promptSelectionStart}
            selectionEnd={promptSelectionEnd}
            language={speechLanguage}
            runtime={speechRuntime}
            disabled={streaming}
            onchange={onVoiceDraft}
            onfinalized={() => (voiceDictated = true)}
            onrestored={restoreVoiceProvenance}
            onactivechange={onVoiceActive}
          />
          <!-- COMPOSER-06 — project, attachments and context in one
               inspectable line. -->
          <ComposerContext
            facts={contextFacts}
            usedPercent={contextPercent}
            disabled={streaming}
            bind:open={contextOpen}
            onopen={() => void refreshContextUsage()}
          >
          {#snippet detail()}
            <!-- COMPOSER-06 — the token counts, the window and the
                 compaction notice, unchanged. They did not become less true
                 when the ring came off the bar; reading them is a deliberate
                 act now rather than a permanent control. -->
            <ContextMeterPopover
              usedTokens={estimatedContextTokens}
              contextWindowTokens={activeProfile?.context_window_tokens ?? null}
              estimated={true}
              usage={contextUsage}
              inline={true}
            />
          {/snippet}
          </ComposerContext>
    {/snippet}

    {#snippet right()}
          <ModelPicker
            bind:profileId={modelProfile}
            bind:model
            bind:open={modelPickerOpen}
            bind:effort={reasoningEffort}
            efforts={reasoningEfforts}
            {profiles}
            catalogues={modelCatalogues()}
            {selectedProfile}
            {decision}
            onchosen={(profileId, chosen) => void rememberSurfaceModel("chat", profileId, chosen)}
            onreset={() => void forgetSurfaceModel("chat")}
            disabled={streaming}
          />
          <button
            type="submit"
            class="btn btn-primary send"
            disabled={streaming || attachStore.uploading || draft.text.trim() === ""}
            aria-label={streaming ? "Running" : "Send"}
          >
            <Icon name="send" size="sm" />
            <span class="send-label">{streaming ? "Running…" : "Send"}</span>
          </button>
    {/snippet}

    {#snippet footer()}
      <!-- COMPOSER-12 — governance appears when it changes what the next press
           will do, not permanently. At the careful default this renders
           nothing; the posture stays inspectable through Permissions, which
           Tools links to. -->
      <!-- QUI-P02 — how much Raiker does without asking, in this
           conversation. It only narrows; the account's approval mode lives
           in Permissions › Advanced. One line with where the message goes. -->
      <div class="footer-facts">
        <ProfileChip
          bind:profile={conversationProfile}
          disabled={streaming}
          onchange={(next) => rememberProfile(sessionId, next)}
        />
        {#if dataLocation !== null}
          <!-- QUI-C04 — where the next message goes, said before it is sent. It
               follows the model chosen for this turn. -->
          <p class="data-label" title={inferenceSentence(dataLocation)}>
            <Icon name={dataLocation.kind === "device" ? "lock" : "globe"} size="sm" />
            <span>{composerDataLabel(dataLocation, attachStore.items.length)}</span>
          </p>
        {/if}
      </div>
    {/snippet}

    {#snippet hint()}
      <!-- Quiet UI — one link; the shortcuts are listed behind it. -->
      <button type="button" class="hint-link" onclick={() => (shortcutsOpen = !shortcutsOpen)}>
        all shortcuts
      </button>
    {/snippet}
  </Composer>
  {#if projectNotice}<p class="project-notice" role="status">{projectNotice}</p>{/if}
  {#if backgroundNotice}
    <p class="project-notice" role="status">
      {backgroundNotice.text}
      {#if backgroundNotice.href}<a href={backgroundNotice.href}>{backgroundNotice.href.includes("task=") ? "Open the task" : backgroundNotice.href === "#/models" ? "Open Models" : "Open Tasks"}</a>{/if}
    </p>
  {/if}
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

  {#if contextPanelOpen}
    <div id="chat-context" class="context-slot">
      <ChatContextPanel
        files={contextFiles}
        {plan}
        sources={inspector.turnSources}
        activity={contextActivity}
        onclose={() => (contextPanelOpen = false)}
        onopensource={(source) => void inspector.openSource(source, "")}
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

<!-- B18 — the same rewind funnel Checkpoints opens, asked for at the turn. -->
<RewindPanel checkpointId={continuity.rewindCheckpointId} onclose={() => (continuity.rewindCheckpointId = null)} />

{#if inspector.inspecting !== null}
  <FileInspector
    preview={inspector.preview}
    filename={inspector.inspecting.filename}
    loading={inspector.previewLoading}
    error={inspector.previewError}
    objectUrl={inspector.objectUrl}
    source={inspector.source}
    sourceLoading={inspector.sourceLoading}
    ondownload={inspector.inspecting.attachmentId === "" ? null : inspector.downloadInspected}
    downloadState={inspector.downloadState}
    downloadError={inspector.downloadError}
    onclose={inspector.close}
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
  .project-chip {
    display: inline-flex; align-items: center; gap: var(--space-1); min-width: 0; max-width: 14rem;
    padding: 0.15rem var(--space-2); border: 1px solid var(--border); border-radius: 999px;
    color: var(--text-2); font-size: var(--text-xs); text-decoration: none; white-space: nowrap;
  }
  .project-chip span { overflow: hidden; text-overflow: ellipsis; }
  .project-chip:hover { border-color: var(--accent-border); color: var(--text-1); }
  .conversation-search { display: inline-flex; align-items: center; gap: var(--space-1); }
  .conversation-search input {
    width: 12rem; padding: 0.25rem var(--space-2); border: 1px solid var(--border);
    border-radius: var(--r-sm); background: var(--surface); color: var(--text-1); font: inherit; font-size: var(--text-sm);
  }
  .search-count { font-size: var(--text-xs); color: var(--text-3); white-space: nowrap; }
  .turn.search-hit { outline: 2px solid var(--accent-border); outline-offset: 6px; border-radius: var(--r-md); }
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
  /* QUI-C01 — the title sits left and takes the room; actions stay right. */
  .conversation-title { display: flex; align-items: center; gap: var(--space-1); min-width: 0; margin-right: auto; }
  .title-text { margin: 0; font-size: var(--text-md); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 32rem; }
  .title-input { font: inherit; font-size: var(--text-md); font-weight: 600; min-width: 16rem; padding: .2rem .45rem; border: 1px solid var(--accent-border); border-radius: var(--r-sm); background: var(--surface); color: var(--text-1); }
  .title-notice { font-size: var(--text-xs); color: var(--danger, var(--text-2)); }
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
  /* QUI-C12 — the context panel opens over the transcript on a laptop and
     sits beside it from 1,920 px up, where the transcript keeps its 720 px. */
  .context-slot {
    position: fixed;
    top: calc(var(--topbar-h) + var(--space-3));
    right: var(--space-4);
    /* Over the transcript means above the composer: Send stays reachable. */
    max-height: calc(100vh - var(--topbar-h) - 16rem);
    z-index: var(--z-panel);
    display: flex;
  }
  .context-slot > :global(.context-panel) { box-shadow: var(--shadow-3); }
  @media (min-width: 120rem) {
    .chat-layout.with-context { grid-template-columns: minmax(0, 1fr) 20rem; }
    .chat-layout.with-rail.with-context { grid-template-columns: minmax(0, 1fr) 21rem 20rem; }
    .context-slot { position: static; max-height: none; }
    .context-slot > :global(.context-panel) { box-shadow: none; }
  }
  /* UX-CHAT-05 — three named groups in the conversation menu. */
  .grouped-menu { min-width: 16rem; }
  .grouped-menu [role="group"] + [role="group"] { border-top: 1px solid var(--border); margin-top: 0.25rem; padding-top: 0.25rem; }
  .menu-group { margin: 0.2rem 0.6rem 0.15rem; color: var(--text-3); font-size: var(--text-2xs); font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
  .grouped-menu [role="group"] { display: grid; gap: var(--space-1); }
  .conversation-menu .menu a[role="menuitem"] {
    display: block; text-decoration: none; color: var(--text-1); font-size: var(--text-sm);
    padding: var(--space-1) var(--space-2); border-radius: var(--r-sm);
  }
  .conversation-menu .menu a[role="menuitem"]:hover { background: var(--accent-soft); }
  /* UX-CHAT-04 — a labelled toggle with a count, and a failure that shows. */
  .rail-toggle { display: inline-flex; align-items: center; gap: 0.35rem; }
  .rail-label { font-size: var(--text-xs); font-weight: 600; }
  .rail-count {
    min-width: 1.2rem; padding: 0 0.3rem; border-radius: var(--r-pill);
    background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent-border);
    font-size: var(--text-2xs); font-weight: 700; text-align: center;
  }
  .rail-alert {
    display: inline-grid; place-items: center; width: 1.1rem; height: 1.1rem; border-radius: 50%;
    background: var(--danger-soft); color: var(--danger); border: 1px solid var(--danger-border);
    font-size: var(--text-2xs); font-weight: 800;
  }
  .rail-failed { color: var(--danger); }
  @media (max-width: 560px) {
    .rail-label { display: none; }
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
    .thread :global(.empty-body) { display: none; }
    .thread :global(.empty) { padding-block: var(--space-5); }
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
    /* Density, from the Work contract rather than from this file. A
       transcript is read in order and wants air between its turns. */
    gap: var(--surface-gap, var(--space-4));
    padding-bottom: var(--space-4);
  }
  .export-notice {
    color: var(--text-2);
    font-size: var(--text-sm);
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
  .artifact-copy p { margin: 0.15rem 0 0; color: var(--text-2); font-size: var(--text-sm); }
  .artifact-heading { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  .artifact-heading strong { overflow-wrap: anywhere; }
  .stopped-line {
    margin: 0 0 0.4rem;
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .artifact-status {
    border-radius: 999px; padding: 0.1rem 0.45rem; color: var(--ok);
    background: var(--ok-soft); font-size: var(--text-2xs); font-weight: 700;
  }
  .artifact-meta { color: var(--text-3) !important; font-size: var(--text-xs) !important; }
  .artifact-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  .artifact-error { grid-column: 1 / -1; margin: var(--space-2) 0 0; font-size: var(--text-sm); }
  .artifact-unavailable { color: var(--text-3); font-size: var(--text-sm); }
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
    :global(.sidebar), :global(.topbar), :global(.skip-link), :global(.composer),
    .copy-message, .chat-header, .rail-slot, .approval-actions,
    :global(.md-copy), :global(.file-inspector) { display: none !important; }
    :global(.app-shell), :global(.app-main), :global(.content), :global(.responsive-page),
    .chat-layout, .chat { display: block !important; height: auto !important; max-width: none !important; }
    .thread { display: block; overflow: visible; }
    .turn { break-inside: avoid; margin-bottom: 1.5rem; }
    .message-group { max-width: none; }
    .message-bubble { box-shadow: none; border: 1px solid var(--border); }
    :global(.md-code) { break-inside: avoid; }
    @page { margin: 18mm 15mm; }
  }
  .turn {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  /* QUI-G04 — a settled turn off screen skips layout and paint. The last two
     and any streaming turn are always drawn, so following the answer and
     Jump to latest measure real heights. */
  .turn.settled {
    content-visibility: auto;
    contain-intrinsic-size: auto 16rem;
  }
  .show-earlier { align-self: center; }
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
    /* QUI-F12 — conversation text follows its own size (Settings ›
       Personalisation), 110% of the interface's unless the owner chose. */
    font-size: calc(var(--text-base) * var(--chat-text-scale, 1.1));
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
  /* Quiet UI 04 — a chart is drawn to a 640-unit box and scaled to fit. In a
     bubble that shrinks to its content it was scaled down until its labels
     could not be read, so a bubble holding a chart, comparison or key figures
     and its group take the group's full width (still capped at 48rem). */
  .message-group-raiker:has(:global(.answer-block:is([data-block="chart"], [data-block="compare"], [data-block="figures"]))),
  .message-bubble-raiker:has(:global(.answer-block:is([data-block="chart"], [data-block="compare"], [data-block="figures"]))) {
    align-self: stretch;
  }
  .streaming-label {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0 0 0.3rem;
    color: var(--text-3);
    font-size: var(--text-sm);
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
  .outcome-line { margin: var(--space-1) 0 0; font-size: var(--text-xs); color: var(--text-3); }
  .outcome-line strong { font-weight: 650; color: var(--text-2); }
  .outcome-partial strong, .outcome-unknown strong { color: var(--warn-text); }
  .outcome-not-done strong { color: var(--danger); }
  .footer-facts { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2) var(--space-3); }
  .data-label { margin: 0; display: inline-flex; align-items: center; gap: var(--space-1); font-size: var(--text-xs); color: var(--text-3); }
  .send-when-ready { margin: 0; display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); color: var(--text-2); }
  /* QUI-C08 — floats just above the composer without moving the layout. */
  .jump-slot { position: relative; height: 0; display: flex; justify-content: center; z-index: 2; }
  .jump-latest {
    position: absolute;
    bottom: var(--space-2);
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    box-shadow: var(--shadow-1);
  }
  /* QUI-C10 — the four starters under an empty conversation. */
  .chat-starters {
    list-style: none;
    margin: 0 auto;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
    width: min(100%, 34rem);
  }
  .chat-starter {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-sm);
    text-align: left;
    text-decoration: none;
    cursor: pointer;
  }
  .chat-starter:hover { border-color: var(--accent-border); }
  .error-line {
    color: var(--danger);
    font-size: var(--text-sm);
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
    font-size: var(--text-sm);
    margin: 0 0 0.3rem;
    color: var(--warn);
  }
  .approval-body {
    font-size: var(--text-sm);
    margin: 0 0 0.3rem;
  }
  .approval-note {
    font-size: var(--text-xs);
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
  /* The Safety card draws its own frame; this one only holds it. */
  .approval-card.inline-decision {
    border: 0;
    background: transparent;
    padding: 0;
  }
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
    z-index: var(--z-popover);
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
    font-size: var(--text-sm);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--r-sm);
    text-align: left;
    cursor: pointer;
  }
  .conversation-menu .menu button:hover:not(:disabled) { background: var(--accent-soft); }
  .conversation-menu .menu button:disabled { color: var(--text-3); cursor: default; }
  .project-notice {
    margin: var(--space-2) 0 0;
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .project-choice {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    padding: 0.5rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--sunken);
    font-size: var(--text-sm);
  }
  .project-choice label {
    color: var(--text-2);
    font-size: var(--text-xs);
  }
  .project-choice select {
    flex: 1;
    min-width: 0;
  }
  .turn-attachments {
    margin: 0.5rem 0 0;
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  @media (max-width: 720px) {
    .message-group {
      max-width: 88%;
    }
  }
  /* MEM-08 — the exchange a link landed on. A brief mark, not a state: a
     shared coordinate says "look here", and the conversation is otherwise
     exactly as it always was. */
  :global(.turn.turn-anchored) {
    border-radius: var(--r-md);
    box-shadow: 0 0 0 2px var(--accent-border);
    background: var(--accent-soft);
    transition: box-shadow 0.4s ease, background 0.4s ease;
  }
  @media (prefers-reduced-motion: reduce) {
    :global(.turn.turn-anchored) { transition: none; }
  }
  .retry-of { margin: 0.2rem 0 0; font-size: var(--text-xs); color: var(--text-3); text-align: right; }
  .retry-link {
    border: 0; background: none; padding: 0; font: inherit; color: var(--accent);
    text-decoration: underline; cursor: pointer;
  }
</style>

