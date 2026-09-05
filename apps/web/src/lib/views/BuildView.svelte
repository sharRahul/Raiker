<script lang="ts">
  /**
   * Build — Raiker's coding workspace.
   *
   * One conversation, pointed at one repository, with the posture stated on the
   * composer instead of buried in settings. The three modes are the whole idea:
   *
   *   Plan  — research and propose; write capabilities are set to deny.
   *   Edit  — every change becomes a decision you accept or reject.
   *   Auto  — low-risk changes run; medium and up still wait for you.
   *
   * Each one is enforced by the runtime (per-capability decision modes plus the
   * per-turn planning option), not by prompt wording, so the label on the
   * composer is a claim the server will keep. Nothing on this page adds
   * authority: it composes the same governed prompt, approval, task, and project
   * surfaces the rest of the workspace uses.
   */
  import { onMount, tick, untrack } from "svelte";
  import { rememberSurfaceModel, surfaceModel } from "../surfaceModel.svelte";
  import { readBuildProject, rememberBuildProject } from "../buildProject";
  import {
    clampExplorerWidth,
    DEFAULT_EXPLORER_WIDTH,
    MAX_EXPLORER_WIDTH,
    MIN_EXPLORER_WIDTH,
    readExplorerOpen,
    readExplorerWidth,
    rememberExplorerOpen,
    rememberExplorerWidth,
  } from "../buildExplorer";
  import Badge from "../components/Badge.svelte";
  import ApprovalModeControl from "../components/ApprovalModeControl.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import ModelReadinessStrip from "../components/ModelReadinessStrip.svelte";
  import ExecutionEnvironmentBadge from "../components/ExecutionEnvironmentBadge.svelte";
  import BuildSidePanel from "../components/BuildSidePanel.svelte";
  import CodeExplorer from "../components/CodeExplorer.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import Icon from "../components/Icon.svelte";
  import ContextMeterPopover from "../components/ContextMeterPopover.svelte";
  import ContextRing from "../components/ContextRing.svelte";
  import Markdown from "../components/Markdown.svelte";
  import RepoConnector from "../components/RepoConnector.svelte";
  import PlanChecklist from "../components/PlanChecklist.svelte";
  import ReasoningBlock from "../components/ReasoningBlock.svelte";
  import ToolActivity from "../components/ToolActivity.svelte";
  import RewindPanel from "../components/RewindPanel.svelte";
  import ExportConversationDialog from "../components/ExportConversationDialog.svelte";
  import DiffView from "../components/DiffView.svelte";
  import SourceChips from "../components/SourceChips.svelte";
  import SourceExcerptPanel from "../components/SourceExcerptPanel.svelte";
  import { api, ApiError, streamPrompt, streamResumeAfterApproval } from "../api";
  import {
    classifyResumeFailure,
    publishApprovalResolved,
    watchForResumableTurns,
    type ResumeWatcher,
  } from "../approvalResume";
  import type {
    AgentPlan,
    AgentResponse,
    ApprovalView,
    CodeRepo,
    CodeReposView,
    ContextUsage,
    ProjectsList,
    SessionDetail,
    StreamEvent,
    TurnSourceExcerptView,
    TurnSourceView,
  } from "../apiTypes";
  import {
    BUILD_WRITE_CAPABILITIES,
    buildMode,
    DEFAULT_BUILD_MODE,
    nextBuildMode,
    repoPreamble,
    standingPostureNote,
    turnCapabilityModes,
    type BuildMode,
  } from "../buildModes";
  import { humanize, relativeTime } from "../format";
  import {
    attachmentChipsByTurn,
    mergeRestoredChips,
    parkedByTurn,
    restoredTurnCore,
    type ParkedApproval,
  } from "../conversationRestore";
  import { rememberSessionInRoute } from "../sessionRoute";
  import { forgetTurnInRoute, revealTurn } from "../turnAnchor";
  import { hasSteps, planFromEvent } from "../agentPlan";
  import { approvalBadge } from "../statusMaps";
  import AttachmentCard from "../components/AttachmentCard.svelte";
  import Composer from "../components/Composer.svelte";
  import ComposerAttach from "../components/ComposerAttach.svelte";
  import ComposerAttachPanel from "../components/ComposerAttachPanel.svelte";
  import ComposerChips from "../components/ComposerChips.svelte";
  import SkillLinkNotice from "../components/SkillLinkNotice.svelte";
  import BuildModePicker from "../components/BuildModePicker.svelte";
  import TurnControl from "../components/TurnControl.svelte";
  import CommandOutputPane from "../components/CommandOutputPane.svelte";
  import { createAttachmentStore, type ComposerAttachment } from "../composerAttachments.svelte";
  import { createFileDrop } from "../fileDrop.svelte";
  import ComposerMenu, { type MenuItem } from "../components/ComposerMenu.svelte";
  import MessageActions from "../components/MessageActions.svelte";
  import VoiceDictationControl, { type VoiceDictationHandle } from "../components/VoiceDictationControl.svelte";
  import ReadAloudButton from "../components/ReadAloudButton.svelte";
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
  import { collectText, groupPhases, summarizeEvent } from "../turnPhases";
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
  import { activateModalDrawer, type DeactivateModalDrawer } from "../modalDrawer";

  let {
    // BUG-242 — the conversation this surface was opened on, from the URL. Build
    // used to learn its session only from the stream, so a reload — the thing an
    // owner does exactly when a change looked wrong — mounted an empty
    // conversation over a session that was still stored, still findable, and
    // still holding the approvals for that change.
    sessionId: continuedSessionId = null,
    // MEM-08 — the exchange this link is pointing at inside that conversation.
    anchoredTurnId = null,
    projects = null,
    onProjectsChanged,
    // Build keeps its transcript when the owner navigates away — the view is
    // hidden, not unmounted — so anything it read once would otherwise stay as
    // it was. Knowing when it comes back is what lets repository state (and the
    // code map that follows the selected repository) be re-read rather than
    // shown as it stood before a visit to Permissions.
    visible = true,
  }: {
    sessionId?: string | null;
    anchoredTurnId?: string | null;
    projects?: ProjectsList | null;
    onProjectsChanged?: () => void;
    visible?: boolean;
  } = $props();

  // C16 — leaving the surface ends the turn's audio. See the matching comment in
  // ChatView: Build is hidden rather than unmounted, so the release has to be
  // driven by visibility instead of by an unmount hook that never fires.
  $effect(() => {
    if (!visible) audioSessionCoordinator.stopAll("route");
  });

  $effect(() => {
    if (!visible) return;
    void loadRepos();
    // The standing write permissions are what the Auto chip reports on, and a
    // visit to Permissions is exactly when they change — so they are re-read on
    // return rather than held as they stood when Build first mounted.
    void readStandingModes();
    void api.speechRuntime().then((view) => {
      speechRuntime = view.runtime.effective;
    }).catch(() => {});
    void api.settings().then((view) => {
      speechLanguage = speechLanguagePreference(view.settings["general.speech_language"]);
    }).catch(() => {});
  });

  interface BuildTurn {
    id: number;
    prompt: string;
    mode: BuildMode;
    /** What this turn carried, shown back the way the composer showed it. */
    attachments: ComposerAttachment[];
    events: StreamEvent[];
    response: AgentResponse | null;
    streaming: boolean;
    error: string | null;
    // BUG-24 — the same parked-turn presentation Chat uses, so a decision made
    // in either surface reads identically in both.
    resumeState?: "waiting" | "continuing" | "elsewhere" | null;
    resumeNote?: string | null;
    // BUG-215/BUG-242 — a turn rebuilt from the record has no stream to read its
    // working from, so it carries the kept text and how much there was. The pair
    // is what keeps a reopened turn honest: none produced, or produced and not
    // retained, are different statements.
    retainedReasoning?: string | null;
    reasoningChars?: number;
  }

  // BUG-35 — Build carries files too. Same store, same limits, same governed
  // upload path as Chat: a stack trace, a failing screenshot or a spec document
  // is exactly what you want to hand a coding agent, and until now this
  // composer had no way to hand it one.
  const attachStore = createAttachmentStore();
  // A file dropped on the composer is attached to the next turn, exactly as if
  // it had been picked from the attach panel (BUG-252).
  const composerDrop = createFileDrop({
    onFiles: (files) => void attachStore.acceptFiles(files),
    enabled: () => !streaming && !attachStore.full,
  });
  let attachControl = $state<ComposerAttach | undefined>();
  let attachOpen = $state(false);

  let promptText = $state("");
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
  let turns = $state<BuildTurn[]>([]);
  let streaming = $state(false);
  // B17/C13 — whether the owner has already asked this turn to stop.
  let stopping = $state(false);
  let sessionId = $state<string | null>(null);
  // Build runs the same governed turns as Chat against the same providers, so
  // it gets the same read-only context and spend panel rather than a variant.
  let contextOpen = $state(false);
  let contextControlEl: HTMLDivElement | undefined = $state();
  let contextUsage = $state<ContextUsage | null>(null);
  // Roughly four characters per token — a deliberately coarse local fallback,
  // always labelled as an estimate, used only until the server reports real
  // provider usage for this session.
  const estimatedContextTokens = $derived(
    Math.ceil(
      (promptText.length +
        turns.reduce(
          (total, turn) => total + turn.prompt.length + (turn.response?.message?.length ?? 0),
          0,
        )) /
        4,
    ),
  );

  // ── C6/C4: the turn source ledger ─────────────────────────────────────────
  //
  // Build reads the same material Chat does and receives the same `cite_as`
  // markers, so it owes the same account of where an answer came from. Build has
  // no inspector pane (B13/B14), so a cited source opens inline, under the
  // answer that cited it, rather than in a pane that does not exist.
  let turnSources = $state<TurnSourceView[]>([]);
  // Which source is open, as (turn, id): ids restart at `s1` in every turn, so
  // the id alone would open the panel under every turn that happens to have one.
  let openSourceId = $state<string | null>(null);
  let openSourceTurnId = $state<string | null>(null);
  let openSource = $state<TurnSourceExcerptView | null>(null);
  let openSourceLoading = $state(false);

  async function refreshTurnSources(id: string) {
    try {
      turnSources = (await api.sessionSources(id)).sources;
    } catch {
      // Provenance for an answer that already arrived: losing it must not cost
      // the transcript, so the chips simply do not appear.
      turnSources = [];
    }
  }

  function closeSource() {
    openSourceId = null;
    openSourceTurnId = null;
    openSource = null;
    openSourceLoading = false;
  }

  function isOpen(source: TurnSourceView): boolean {
    return openSourceId === source.source_id && openSourceTurnId === source.turn_id;
  }

  async function showSource(source: TurnSourceView, quote = "") {
    if (sessionId === null || !source.openable) return;
    if (isOpen(source)) {
      closeSource();
      return;
    }
    openSourceId = source.source_id;
    openSourceTurnId = source.turn_id;
    openSource = null;
    openSourceLoading = true;
    try {
      const resolved = await api.turnSourceExcerpt(sessionId, source.turn_id, source.source_id, quote);
      if (isOpen(source)) openSource = resolved;
    } catch {
      if (isOpen(source)) openSource = null;
    } finally {
      if (isOpen(source)) openSourceLoading = false;
    }
  }

  /**
   * A `[s1]` chip inside the answer opens the same source the strip does — and,
   * unlike the strip, it knows which sentence rests on it, so the panel can open
   * at that part of the source rather than at the whole of it.
   */
  function showSourceById(turnId: string, sourceId: string, answer: string) {
    const match = turnSources.find(
      (source) => source.turn_id === turnId && source.source_id === sourceId,
    );
    if (match !== undefined) void showSource(match, sentenceAround(answer, sourceId));
  }

  async function refreshContextUsage() {
    if (sessionId === null) {
      contextUsage = null;
      return;
    }
    try {
      contextUsage = await api.sessionContextUsage(sessionId);
    } catch {
      contextUsage = null;
    }
  }
  let nextId = 1;

  // ── BUG-242: restoring the conversation the URL names ─────────────────
  //
  // Same shape as Chat, over the same governed session read. A restored turn
  // carries what is persisted — the prompt, the answer, the status, the tool
  // rows and the retained working — and nothing that only existed on the
  // stream. `mode` is not part of the record: the chip on a reopened turn shows
  // the mode the composer is set to, which is the honest reading of a posture
  // that is chosen per turn and never stored.
  let historyError = $state<string | null>(null);
  let historyLoading = $state(false);

  async function loadHistory(id: string) {
    historyLoading = true;
    closeSource();
    // B18 — a preflight belongs to one conversation. Left open across a load
    // it would describe a checkpoint from a conversation no longer on screen.
    rewindCheckpointId = null;
    landedAnchor = null;
    try {
      const detail = await api.session(id);
      const parked = parkedByTurn(detail);
      turns = detail.turns.map((t) => restoredTurn(t, id, parked.get(t.turn_id)));
      nextId = turns.length + 1;
      await restoreAttachmentChips(id);
      await refreshTurnSources(id);
      await loadApprovals();
      // MEM-08 — a link that named an exchange lands on it, through the effect
      // below rather than here, so a second link into the same conversation is
      // honoured too.
      if (anchoredTurnId === null || anchoredTurnId === "") void scrollToEnd();
    } catch (e) {
      historyError =
        e instanceof ApiError ? `Could not load history (${e.status}).` : "Could not load history.";
    } finally {
      historyLoading = false;
    }
  }

  function restoredTurn(
    t: SessionDetail["turns"][number],
    id: string,
    parked?: ParkedApproval,
  ): BuildTurn {
    return { id: nextId++, mode, ...restoredTurnCore(t, id, parked) };
  }

  async function restoreAttachmentChips(id: string) {
    let files;
    try {
      files = (await api.sessionAttachments(id)).files;
    } catch {
      // Chips are a convenience; losing them must not cost the transcript.
      return;
    }
    turns = mergeRestoredChips(turns, attachmentChipsByTurn(files));
  }

  $effect(() => {
    if (continuedSessionId === null) return;
    const id = continuedSessionId;
    // Only the prop may retrigger this — see the matching comment in Chat.
    untrack(() => {
      sessionId = id;
      void loadHistory(id);
    });
  });

  // The address bar follows the open conversation, so a reload comes back to
  // it. Only the surface on screen writes: Build and Chat stay mounted behind
  // each other.
  $effect(() => {
    if (!visible) return;
    rememberSessionInRoute("build", sessionId);
  });

  let scrollEl: HTMLDivElement | undefined = $state();
  let promptEl: HTMLTextAreaElement | undefined = $state();

  // ── Posture ──────────────────────────────────────────────────────────
  // BUG-70 — the mode is this conversation's own posture and nothing more. It
  // rides with each prompt as `capability_modes` and is applied to that turn;
  // it never writes the owner's standing decision modes, so pressing a chip has
  // no effect on Chat, Tasks, or any later session. There is therefore nothing
  // to "apply" and nothing that can be refused: the composer shows the mode it
  // will send.
  let mode = $state<BuildMode>(DEFAULT_BUILD_MODE);
  // The owner's standing write permissions, read only so the composer can say
  // what Auto will actually amount to. Never written from this page.
  let standingModes = $state<Record<string, string> | null>(null);
  const standingNote = $derived(standingPostureNote(mode, standingModes));

  // ── Repository ───────────────────────────────────────────────────────
  let repos = $state<CodeReposView | null>(null);
  let reposOpen = $state(false);
  const activeRepo = $derived<CodeRepo | null>(
    repos?.repos.find((repo) => repo.repo_id === repos?.selected_repo_id) ?? null,
  );

  // ── File explorer (B13) ───────────────────────────────────────────────
  // Only a local folder has files on this machine. A GitHub repository is a
  // coordinate, so the control is offered and says why it is empty rather than
  // being hidden — a missing button reads as a missing feature.
  let filesOpen = $state(false);
  let filesWidth = $state(DEFAULT_EXPLORER_WIDTH);
  let filesElement = $state<HTMLElement>();
  let filesTrigger = $state<HTMLElement | null>(null);
  let deactivateFiles: DeactivateModalDrawer | null = null;
  let resizing = $state(false);

  function closeFiles(restoreFocus = true) {
    deactivateFiles?.(restoreFocus);
    deactivateFiles = null;
    filesOpen = false;
    rememberExplorerOpen(false);
  }

  function toggleFiles(event: MouseEvent) {
    filesTrigger = event.currentTarget as HTMLElement;
    if (filesOpen) closeFiles(true);
    else {
      filesOpen = true;
      rememberExplorerOpen(true);
    }
  }

  /** Drag the divider. Pointer capture keeps the drag alive over the transcript. */
  function startResize(event: PointerEvent) {
    if (compactRail) return;
    const handle = event.currentTarget as HTMLElement;
    handle.setPointerCapture(event.pointerId);
    resizing = true;
    const origin = event.clientX;
    const start = filesWidth;
    const move = (moved: PointerEvent) => {
      filesWidth = clampExplorerWidth(start + (moved.clientX - origin));
    };
    const done = () => {
      resizing = false;
      handle.releasePointerCapture(event.pointerId);
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", done);
      handle.removeEventListener("pointercancel", done);
      rememberExplorerWidth(filesWidth);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", done);
    handle.addEventListener("pointercancel", done);
  }

  /** The keyboard's half of the same control, so resizing is not pointer-only. */
  function resizeByKey(event: KeyboardEvent) {
    const step = event.shiftKey ? 48 : 16;
    if (event.key === "ArrowLeft") filesWidth = clampExplorerWidth(filesWidth - step);
    else if (event.key === "ArrowRight") filesWidth = clampExplorerWidth(filesWidth + step);
    else if (event.key === "Home") filesWidth = MIN_EXPLORER_WIDTH;
    else if (event.key === "End") filesWidth = MAX_EXPLORER_WIDTH;
    else return;
    event.preventDefault();
    rememberExplorerWidth(filesWidth);
  }

  $effect(() => {
    if (!visible && filesOpen) closeFiles(false);
  });

  $effect(() => {
    if (!compactRail || !filesOpen || filesElement === undefined) return;
    const shellBackground = Array.from(document.querySelectorAll<HTMLElement>(".topbar, .sidebar"));
    deactivateFiles = activateModalDrawer({
      id: "build-files",
      container: filesElement,
      returnFocusTo: filesTrigger,
      backgroundElements:
        buildMainElement === undefined
          ? shellBackground
          : [buildMainElement, ...shellBackground],
      onDismiss: () => closeFiles(true),
    });
    return () => {
      deactivateFiles?.(false);
      deactivateFiles = null;
    };
  });

  // ── Side rail ────────────────────────────────────────────────────────
  let railOpen = $state(false);
  let compactRail = $state(false);
  let railElement = $state<HTMLElement>();
  let buildMainElement = $state<HTMLElement>();
  let railTrigger = $state<HTMLElement | null>(null);
  let deactivateRail: DeactivateModalDrawer | null = null;

  function closeRail(restoreFocus = true) {
    deactivateRail?.(restoreFocus);
    deactivateRail = null;
    railOpen = false;
  }

  function toggleRail(event: MouseEvent) {
    railTrigger = event.currentTarget as HTMLElement;
    if (railOpen) closeRail(true);
    else railOpen = true;
  }

  $effect(() => {
    if (!visible && railOpen) closeRail(false);
  });

  $effect(() => {
    if (!compactRail || !railOpen || railElement === undefined) return;
    const shellBackground = Array.from(document.querySelectorAll<HTMLElement>(".topbar, .sidebar"));
    deactivateRail = activateModalDrawer({
      id: "build-background",
      container: railElement,
      returnFocusTo: railTrigger,
      backgroundElements: buildMainElement === undefined ? shellBackground : [buildMainElement, ...shellBackground],
      onDismiss: () => closeRail(true),
    });
    return () => {
      deactivateRail?.(false);
      deactivateRail = null;
    };
  });

  // ── The agent's plan (B6) ────────────────────────────────────────────
  // A long change had no visible spine: the transcript looked identical on
  // step two and step nine. The checklist is the model's own `update_plan`
  // output, updated live from the stream and re-read on load so a reload or a
  // second tab does not start blank.
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
      // A plan is context, never a precondition: failing to read one leaves
      // the workspace exactly as usable as it was before B6.
      plan = null;
    }
  }

  // ── Project selection ────────────────────────────────────────────────
  // Build owns its project, and a project is required before work can start.
  // That is not a UI preference: the selection *is* the execution boundary —
  // the files, memories and conversations the turn may retrieve — so a Build
  // session with no project has no boundary to run inside. It used to fall back
  // to an account-level "active project" set from the top bar, which meant the
  // boundary could change from another page without anything here saying so.
  //
  // The choice is remembered locally so returning to Build resumes where the
  // owner left off, and it cannot change mid-turn.
  let projectId = $state(readBuildProject());

  // A remembered id that no longer names an owned project must not silently
  // stand as a boundary. Resolving it against the loaded list is what turns a
  // stale preference back into "no project selected".
  const selectedProject = $derived(
    projects?.projects.find((project) => project.project_id === projectId) ?? null,
  );
  const projectReady = $derived(projectId !== "" && selectedProject !== null);
  let pendingProjectId: string | null = null;
  let projectNotice = $state<string | null>(null);

  // ── Approvals raised by this conversation ────────────────────────────
  let approvals = $state<ApprovalView[]>([]);
  let approvalBusy = $state<string | null>(null);
  let approvalNotice = $state<string | null>(null);

  let modelProfile = $state("");
  let model = $state("");
  let reasoningEffort = $state("");
  // One reactive view of the shared model store; refreshes live when the
  // Models page connects a provider or selects a model, without a remount.
  const profiles = $derived(chatProfiles());
  const selectedProfile = $derived(profiles.find((profile) => profile.selected) ?? null);
  const activeProfile = $derived(
    profiles.find(
      (profile) => profile.profile_id === modelProfile && (!model || profile.model === model),
    ) ?? selectedProfile,
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

  onMount(() => {
    const railQuery = typeof window.matchMedia === "function"
      ? window.matchMedia("(max-width: 1023px)")
      : null;
    const updateRailMode = () => { compactRail = railQuery?.matches ?? false; };
    updateRailMode();
    railQuery?.addEventListener("change", updateRailMode);
    // B13 — the explorer opens where it was left, at the width it was left,
    // but never as a drawer over a narrow window nobody asked to open.
    filesWidth = readExplorerWidth();
    filesOpen = readExplorerOpen() && !compactRail;
    void loadRepos();
    void refreshModels();
    // Build keeps its own model. Coding work and conversation rarely want the
    // same one, and before this both surfaces shared the global default.
    void surfaceModel("build").then((remembered) => {
      if (remembered === null || modelProfile) return;
      modelProfile = remembered.profileId;
      model = remembered.model;
    });
    void readStandingModes();
    const onCompose = (event: Event) => {
      const detail = (event as CustomEvent<{
        text: string;
        profileId?: string;
        model?: string;
        attachments?: ComposerAttachment[];
      }>).detail;
      if (!detail?.text.trim()) return;
      promptText = detail.text;
      modelProfile = detail.profileId ?? "";
      model = detail.model ?? "";
      // Same handoff contract as Chat: files picked in the Workbench composer
      // arrive here as references, already uploaded and governed.
      if (detail.attachments?.length) attachStore.set([...detail.attachments]);
    };
    window.addEventListener("raiker:build-compose", onCompose);
    return () => {
      railQuery?.removeEventListener("change", updateRailMode);
      deactivateRail?.(false);
      window.removeEventListener("raiker:build-compose", onCompose);
      audioSessionCoordinator.stopAll("route");
    };
  });

  async function loadRepos() {
    try {
      repos = await api.codeRepos();
    } catch {
      // The workspace still works without a repository; the panel says so.
      repos = null;
    }
  }

  /**
   * Read the owner's standing write permissions — read-only, so the Auto chip
   * can state what it will actually amount to rather than promising unprompted
   * execution the owner never granted. Nothing on this page writes them.
   */
  async function readStandingModes() {
    try {
      const gates = await api.capabilityGates();
      const observed: Record<string, string> = {};
      for (const gate of gates) {
        if ((BUILD_WRITE_CAPABILITIES as readonly string[]).includes(gate.capability)) {
          observed[gate.capability] = gate.decision_mode;
        }
      }
      standingModes = observed;
    } catch {
      standingModes = null;
    }
  }

  function setMode(next: BuildMode) {
    // Local, instant, and free of consequence beyond this conversation's turns.
    mode = next;
    // Auto is the one mode whose hint depends on the owner's standing
    // permissions, so an earlier read that failed is retried when it is picked
    // rather than leaving "could not read" on screen for the rest of the session.
    if (next === "auto" && standingModes === null) void readStandingModes();
  }

  // ── B19 — composer ergonomics, shared with Chat through composerCommands.ts ──
  //
  // Build's set is the coding agent's: the three modes the runtime really
  // enforces, the governed terminal, the repository list, plus everything Chat
  // has. `@` completes against the code map the owner built for the selected
  // repository, so pointing the agent at a file is a keystroke rather than a
  // path typed exactly.
  let modelPickerOpen = $state(false);
  let commandPaneOpen = $state(false);
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
    return matchCommands("build", fragment, ownerSlashCommands).map((command) => ({
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
        // An unbuilt map and a search that matched nothing look identical as an
        // empty list and are not the same problem, so the reason is shown with
        // the control that fixes it.
        mentionItems = [];
        mentionNotice = {
          text: view.error?.message ?? "Workspace file mentions are unavailable.",
          href: view.error?.type === "code_map_gate_disabled" ? "#/capabilities" : "#/build?tab=repositories",
          linkLabel: view.error?.type === "code_map_gate_disabled" ? "Permissions" : "Repositories",
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

  /**
   * B13 — carry the open file into the composer as a mention.
   *
   * Reading a file and asking about it are the same act a second apart, and
   * retyping the path between them is the friction that stops the second one
   * happening. It writes the same `@path ` token the completion menu writes, so
   * the turn sees no difference between the two ways of naming a file.
   */
  function mentionPath(path: string) {
    if (path === "") return;
    const separator = promptText === "" || promptText.endsWith(" ") ? "" : " ";
    promptText = `${promptText}${separator}@${path} `;
    const caretAt = promptText.length;
    queueMicrotask(() => {
      promptEl?.focus();
      promptEl?.setSelectionRange(caretAt, caretAt);
      autoGrow(promptEl ?? null);
    });
  }

  /** Run one command. Each is a control this surface already has. */
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
      case "plan": planCollapsed = false; void loadPlan(); break;
      case "stop": if (streaming) void stopRunningTurn(); break;
      case "shortcuts": shortcutsOpen = true; break;
      case "mode-plan": setMode("plan"); break;
      case "mode-edit": setMode("edit"); break;
      case "mode-auto": setMode("auto"); break;
      case "terminal": commandPaneOpen = true; break;
      case "repos": window.location.hash = "#/build?tab=repositories"; break;
    }
  }

  /** C14 — a past prompt back in the composer, leaving the transcript intact. */
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

  /** Send the same prompt again, under the mode that is selected now. */
  function retryPrompt(text: string) {
    if (streaming || text.trim() === "") return;
    promptText = text;
    void submit();
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
      /* The composer's own Stop control reports its failures; a slash command
         that could not reach the runtime leaves the turn exactly as it was. */
    }
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey && voiceControl?.active()) {
      event.preventDefault();
      voiceControl.done();
      promptEl?.focus();
      return;
    }
    // An open menu owns the arrows, Enter, Tab and Escape.
    if (menuKind !== "none" && (menuItems.length > 0 || mentionNotice !== null)) {
      if (event.key === "Escape") {
        event.preventDefault();
        menuKind = "none";
        return;
      }
      if (menuItems.length > 0) {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          menuActive = (menuActive + 1) % menuItems.length;
          return;
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          menuActive = (menuActive - 1 + menuItems.length) % menuItems.length;
          return;
        }
        if (event.key === "Enter" || (event.key === "Tab" && !event.shiftKey)) {
          event.preventDefault();
          chooseMenuItem(menuItems[menuActive]);
          return;
        }
      }
    }
    // Shift+Tab cycles Plan → Edit → Auto without leaving the prompt.
    if (event.key === "Tab" && event.shiftKey) {
      event.preventDefault();
      setMode(nextBuildMode(mode));
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  /** The repository path plus the composer's own files, in wire order. */
  function buildAttachments(sent: ReturnType<typeof attachStore.take>) {
    const wire = [
      ...(activeRepo?.kind === "local" && activeRepo.local_subpath
        ? [{ type: "path" as const, path: activeRepo.local_subpath }]
        : []),
      ...sent.map((a) =>
        a.kind === "image"
          ? { type: "image" as const, attachment_id: a.attachmentId ?? "" }
          : a.kind === "document"
            ? { type: "document" as const, attachment_id: a.attachmentId ?? "" }
            : { type: "path" as const, path: a.path ?? "" },
      ),
    ];
    return wire.length > 0 ? wire : undefined;
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
    const preamble = repoPreamble(activeRepo);
    // The preamble is prepended here, not server-side, so the transcript shows
    // the exact text the turn received.
    const sent = preamble === "" ? text : `${preamble}\n\n${text}`;
    const sentMode = mode;
    const sentAttachments = attachStore.take();
    turns = [
      ...turns,
      {
        id: nextId++, prompt: sent, mode: sentMode, attachments: sentAttachments,
        events: [], response: null, streaming: true, error: null,
      },
    ];
    const turn = turns[turns.length - 1];
    promptText = "";
    resetVoiceProvenance();
    // B19 — shrink the box back with the prompt that grew it.
    menuKind = "none";
    queueMicrotask(() => autoGrow(promptEl ?? null));
    attachStore.clear();
    streaming = true;
    stopping = false;
    void scrollToEnd();
    try {
      await streamPrompt(
        {
          text: sent,
          input_mode: inputMode,
          surface: "build",
          // The boundary rides the turn. The server re-checks it and refuses a
          // Build turn without an owned project, so this is what to send, not
          // merely what to display.
          project_id: projectId,
          session_id: sessionId ?? undefined,
          model_profile: modelProfile || undefined,
          model: model || undefined,
          ...(reasoningEfforts.includes(reasoningEffort) ? { reasoning_effort: reasoningEffort } : {}),
          planning_mode: buildMode(sentMode).planningMode ?? undefined,
          // BUG-70 — the mode travels with the turn instead of being written
          // into the owner's standing permissions. Auto sends nothing, which is
          // how "follow your standing permissions" is expressed on the wire.
          capability_modes: turnCapabilityModes(sentMode),
          // A local repository rides the turn as a real workspace-path
          // attachment, resolved and bounded server-side like any other — now
          // alongside whatever the composer is carrying, in the same shape the
          // prompt route already accepts from Chat.
          attachments: buildAttachments(sentAttachments),
        },
        (event) => {
          if (event.kind === "final" && event.response !== null) {
            turn.response = event.response;
            sessionId = event.response.session_id;
            // C6 — the citation markers this answer just wrote need the ledger
            // they resolve against, so it is refreshed with the turn.
            void refreshTurnSources(event.response.session_id);
            if (contextOpen) void refreshContextUsage();
            if (plan === null) void loadPlan();
            window.dispatchEvent(new Event("raiker:chats-changed"));
            void applyPendingProject();
            void loadApprovals();
          } else {
            turn.events = [...turn.events, event];
            const streamed = planFromEvent(event);
            if (streamed !== null) plan = streamed;
          }
          // B17/C13 — as in Chat: the first streamed chunk names the session, so
          // a first Build turn can be stopped or steered like any later one.
          if (sessionId === null && typeof event.session_id === "string" && event.session_id !== "") {
            sessionId = event.session_id;
          }
          void scrollToEnd();
        },
      );
    } catch (error) {
      if (error instanceof ApiError && error.reasonCode === "model_not_ready") {
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
        error instanceof ApiError
          ? `The turn could not be streamed (${error.status}).`
          : "Could not reach the local runtime.";
    } finally {
      turn.streaming = false;
      streaming = false;
      // BUG-24 — see ChatView: a turn is only genuinely parked once its stream
      // ends, so that is where it asks whether a decision already exists.
      if (turn.response?.status === "needs_approval") resumeWatcher?.checkNow();
      void scrollToEnd();
    }
  }

  /**
   * Decide what a refused continuation means for the turn that asked (BUG-196).
   *
   * Mirrors ChatView exactly: the turn's own state decides, then the reason. A
   * turn already carrying a finished response continued, so a later refusal is a
   * duplicate and stays silent.
   */
  function applyResumeFailure(turn: BuildTurn, error: unknown, code: string | null) {
    const finished = turn.response !== null && turn.response.status !== "needs_approval";
    const outcome = classifyResumeFailure(code);
    if (finished) {
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

  /** Continue the turn this approval parked, streaming into its own transcript row. */
  async function resumeTurn(approvalId: string, outcomeStatus = "") {
    // BUG-196 — claim the id before the request, so the poller cannot start the
    // same continuation and report losing that race as a failed turn.
    resumeWatcher?.claim(approvalId);
    const parked = turns.findLast((candidate) => candidate.response?.status === "needs_approval");
    const turn =
      parked ??
      (() => {
        turns = [
          ...turns,
          {
            id: nextId++, prompt: "", mode, attachments: [],
            events: [], response: null, streaming: true, error: null,
          },
        ];
        return turns[turns.length - 1];
      })();
    if (turn.streaming && turn !== parked) return;
    turn.streaming = true;
    turn.error = null;
    turn.resumeState = "continuing";
    turn.resumeNote =
      outcomeStatus === "rejected" ? "Rejected — telling Raiker…" : "Approved — continuing…";
    streaming = true;
    void scrollToEnd();
    try {
      await streamResumeAfterApproval(approvalId, (event) => {
        if (event.kind === "final" && event.response !== null) {
          turn.response = event.response;
          turn.resumeState = null;
          turn.resumeNote = null;
          void refreshTurnSources(event.response.session_id);
          if (contextOpen) void refreshContextUsage();
          void loadApprovals();
        } else {
          turn.events = [...turn.events, event];
          const streamed = planFromEvent(event);
          if (streamed !== null) plan = streamed;
        }
        void scrollToEnd();
      });
    } catch (error) {
      // BUG-24 — losing the race is a success: the turn did continue, in the
      // client that claimed it first. Saying "error" here would be a lie.
      const code = error instanceof ApiError ? error.reasonCode : null;
      applyResumeFailure(turn, error, code);
    } finally {
      turn.streaming = false;
      streaming = false;
      void scrollToEnd();
    }
  }

  // ── BUG-24: a decision recorded in another tab continues this one too ─────
  let liveChannelDown = $state(false);
  let resumeWatcher: ResumeWatcher | null = null;

  onMount(() => {
    resumeWatcher = watchForResumableTurns({
      sessionId: () => sessionId,
      hasParkedTurn: () =>
        turns.some((turn) => turn.response?.status === "needs_approval" && !turn.streaming),
      onResume: (turn) => resumeTurn(turn.approval_id, turn.outcome_status),
      onChannelUnavailable: (unavailable) => (liveChannelDown = unavailable),
    });
    return () => resumeWatcher?.stop();
  });

  /** The manual path, offered whenever the live channel cannot be relied on. */
  async function continueNow() {
    if (sessionId === null || streaming) return;
    try {
      const { turns: resumable } = await api.resumableTurns(sessionId);
      if (resumable.length === 0) {
        approvalNotice = "No decision has been recorded for this turn yet.";
        return;
      }
      await resumeTurn(resumable[0].approval_id, resumable[0].outcome_status);
    } catch {
      approvalNotice = "Could not check for a decision — the local runtime is unreachable.";
    }
  }

  // ── BUG-22: export and print this conversation ───────────────────────────
  let conversationMenuOpen = $state(false);
  let exportOpen = $state(false);

  function printConversation() {
    conversationMenuOpen = false;
    exportOpen = false;
    setTimeout(() => window.print?.(), 0);
  }

  // ── B18 — rewind to before this turn ─────────────────────────────────
  // The governed restore has had an executor, a capability and a route since
  // BUG-230, reachable only from the Checkpoints page. Build is where the files
  // actually change, so this resolves the checkpoint the turn wrote and opens
  // the shared funnel. Nothing here restores anything: the funnel raises an
  // approval and a human decision runs it.
  let rewindCheckpointId = $state<string | null>(null);
  let rewindingTurn = $state<string | null>(null);

  async function rewindFromTurn(turnId: string) {
    if (sessionId === null || streaming) return;
    rewindingTurn = turnId;
    projectNotice = null;
    try {
      const checkpoints = await api.checkpoints(sessionId);
      const point = checkpoints.find((checkpoint) => checkpoint.turn_id === turnId);
      if (point === undefined) {
        projectNotice = "No checkpoint was written for that turn, so there is nothing to rewind to.";
        return;
      }
      rewindCheckpointId = point.checkpoint_id;
    } catch (error) {
      projectNotice =
        error instanceof ApiError
          ? `Could not read this conversation's checkpoints (${error.reasonCode ?? error.status}).`
          : "Could not read this conversation's checkpoints.";
    } finally {
      rewindingTurn = null;
    }
  }

  async function scrollToEnd() {
    await tick();
    // Guarded: jsdom has no scrollTo implementation.
    if (typeof scrollEl?.scrollTo === "function") scrollEl.scrollTo({ top: scrollEl.scrollHeight });
  }

  // MEM-08 — land on the exchange the link named, as Chat does. The anchor is
  // spent on arrival so a reload opens the conversation as it is.
  let anchorNotice = $state<string | null>(null);

  async function landOnAnchor(turnId: string) {
    await tick();
    anchorNotice = revealTurn(scrollEl, turnId) ? null : "That exchange is not in this conversation.";
    forgetTurnInRoute();
    if (anchorNotice !== null) void scrollToEnd();
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

  function newConversation() {
    if (streaming) return;
    audioSessionCoordinator.stopAll("route");
    resetVoiceProvenance();
    turns = [];
    sessionId = null;
    approvals = [];
    approvalDiffs = {};
    plan = null;
    rewindCheckpointId = null;
    anchorNotice = null;
    landedAnchor = null;
    promptEl?.focus();
  }

  // ── Projects ─────────────────────────────────────────────────────────
  async function onProjectPicked(value: string) {
    if (streaming) return;
    projectId = value;
    rememberBuildProject(value);
    projectNotice = null;
    const target = value === "" ? null : value;
    if (sessionId === null) {
      pendingProjectId = target;
      projectNotice =
        target === null
          ? "This chat will stay outside every project."
          : "This chat will be filed there as soon as it starts.";
      return;
    }
    await moveSession(target);
  }

  async function applyPendingProject() {
    if (sessionId === null) return;
    if (pendingProjectId === null && projectId === "") return;
    const target = pendingProjectId ?? (projectId === "" ? null : projectId);
    pendingProjectId = null;
    if (target === null) return;
    await moveSession(target);
  }

  async function moveSession(target: string | null) {
    if (sessionId === null) return;
    try {
      await api.setSessionProject(sessionId, target);
      projectNotice =
        target === null
          ? "Moved out of every project."
          : `Filed under ${projects?.projects.find((p) => p.project_id === target)?.name ?? "the project"}.`;
      onProjectsChanged?.();
    } catch (error) {
      projectNotice =
        error instanceof ApiError
          ? `Could not move this chat (${error.status}).`
          : "Could not move this chat.";
    }
  }

  // ── Approvals ────────────────────────────────────────────────────────
  //
  // B14 — the change itself, where it was proposed. Reviewing a diff used to
  // mean leaving Build for the Approvals inbox, which is a route change at the
  // one moment an owner is reading code. The preview is the same governed
  // read the inbox performs (`GET /api/approvals/{id}`), rendered here; nothing
  // about the decision moves — Accept and Reject still resolve the same record,
  // and per-hunk acceptance is not offered because the runtime has no such
  // decision to record.
  let approvalDiffs = $state<
    Record<string, { diff: string | null; path: string | null; kind: string }>
  >({});
  /**
   * B14 — per decision, the hunks the reviewer has accepted, keyed by approval.
   *
   * Absent means they have not narrowed this one and Accept means all of it,
   * which is what a decision has always meant. Keyed rather than held as one
   * value because Build renders every pending decision at once, and a selection
   * belongs to the diff it was made on.
   */
  let approvalHunks = $state<Record<string, string[] | undefined>>({});
  /**
   * BUG-271 — the reviewer's own version of a proposed patch, per approval,
   * while they are writing it. `undefined` is the resting state: correcting a
   * change is the rarer thing to want, and an open editor under every patch
   * would crowd a panel that has to stay a review surface.
   */
  let approvalEdits = $state<Record<string, string | undefined>>({});

  async function loadApprovals() {
    if (sessionId === null) return;
    try {
      const pending = await api.approvals();
      approvals = pending.filter((approval) => approval.session_id === sessionId);
    } catch {
      approvals = [];
      approvalDiffs = {};
      return;
    }
    await loadApprovalDiffs();
  }

  async function loadApprovalDiffs() {
    const wanted = approvals.filter((approval) => approvalDiffs[approval.approval_id] === undefined);
    const loaded = await Promise.all(
      wanted.map(async (approval) => {
        try {
          const detail = await api.approval(approval.approval_id);
          const shows =
            detail.preview_kind === "file_diff" ||
            detail.preview_kind === "patch" ||
            detail.preview_kind === "git_change";
          // Only a change with a diff gets one. Everything else keeps the
          // inbox's own presentation rather than being forced into this shape.
          return shows
            ? ([
                approval.approval_id,
                // BUG-271 — `kind` decides whether the edit control is offered:
                // only a proposed patch can be corrected as text.
                { diff: detail.diff, path: detail.diff_path, kind: detail.preview_kind },
              ] as const)
            : null;
        } catch {
          // The preview is a convenience on top of the decision. Losing it must
          // not remove the Accept and Reject the turn is parked on.
          return null;
        }
      }),
    );
    approvalDiffs = {
      ...approvalDiffs,
      ...Object.fromEntries(loaded.filter((entry) => entry !== null)),
    };
  }

  /**
   * BUG-271 — propose the reviewer's own version instead of this one.
   *
   * The same route Approvals uses, so a correction means the same thing
   * wherever it is made: the proposal in front of the reviewer is denied and
   * theirs is raised as a new one with its own preview and its own hash.
   * Nothing runs until they accept that.
   */
  async function proposeEdit(approval: ApprovalView) {
    const patch = approvalEdits[approval.approval_id];
    if (patch === undefined || approvalBusy !== null) return;
    approvalBusy = approval.approval_id;
    approvalNotice = null;
    try {
      await api.replaceApproval(approval.approval_id, {
        patch,
        reason: "edited in the Build workspace",
      });
      approvalEdits = { ...approvalEdits, [approval.approval_id]: undefined };
      approvalNotice =
        "The proposed change was denied and yours is waiting for your approval. Nothing has run.";
      approvalDiffs = {};
      await loadApprovals();
    } catch (error) {
      approvalNotice =
        error instanceof ApiError && error.reasonCode
          ? `That version was not accepted (${error.reasonCode}).`
          : "That version was not accepted.";
    } finally {
      approvalBusy = null;
    }
  }

  async function resolve(approval: ApprovalView, approve: boolean) {
    approvalBusy = approval.approval_id;
    approvalNotice = null;
    try {
      const accepted = approvalHunks[approval.approval_id];
      const result = await api.resolveApproval(approval.approval_id, {
        approve,
        reason: approve ? "accepted in the Build workspace" : "rejected in the Build workspace",
        // B14 — sent only when this reviewer actually narrowed this change.
        ...(approve && accepted !== undefined ? { accepted_hunks: accepted } : {}),
      });
      approvalNotice = !approve
        ? "Rejection recorded."
        : result.executes_action
          ? result.execution?.path
            ? `Applied once — wrote ${result.execution.path}. The previous contents were checkpointed.`
            : // BUG-62 — a capability whose result is a row, not a file, names it.
              result.execution?.receipt
              ? `Applied once — “${result.execution.receipt.title}” now exists. ${result.execution.receipt.label}.`
              : "Applied once, under a fresh capability, policy and posture check."
          : "Decision recorded. Raiker re-governs the action before anything runs.";
      await loadApprovals();
      // BUG-24 — tell every other tab of this browser immediately, so a Chat
      // window showing the same parked turn continues without a reload. This is
      // a hint only: the receiving tab re-checks with the server before acting.
      publishApprovalResolved({
        approvalId: approval.approval_id,
        sessionId: approval.session_id ?? null,
        turnId: result.resume?.turn_id ?? null,
        approved: approve,
      });
      // B2 — the decision closed the tool call the model was waiting on, so the
      // turn it parked picks up from here instead of costing a re-prompt.
      if (result.resume?.resumable) {
        await resumeTurn(approval.approval_id, approve ? "success" : "rejected");
      }
    } catch (error) {
      approvalNotice =
        error instanceof ApiError
          ? `The decision was not accepted (${error.reasonCode ?? error.status}).`
          : "The decision could not be recorded.";
    } finally {
      approvalBusy = null;
    }
  }

  // Copying a response, matching Chat exactly (BUG-23 / composer parity). The
  // clipboard is not always available — an insecure origin, a denied
  // permission — so a failure is stated rather than swallowed.
  let copiedTurnId = $state<string | null>(null);
  let copyNotice = $state<string | null>(null);

  async function copyAnswer(turn: BuildTurn) {
    try {
      await navigator.clipboard.writeText(answerText(turn));
      copyNotice = null;
      copiedTurnId = String(turn.id);
      window.setTimeout(() => {
        if (copiedTurnId === String(turn.id)) copiedTurnId = null;
      }, 2000);
    } catch {
      copiedTurnId = null;
      copyNotice = "Could not copy — your browser blocked clipboard access.";
    }
  }

  function answerText(turn: BuildTurn): string {
    const streamed = collectText(turn.events);
    return streamed.trim() !== "" ? streamed : (turn.response?.message ?? "");
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
</script>

<svelte:window onclick={onWindowClick} />

<div
  class="build"
  class:with-files={filesOpen && !compactRail}
  class:with-rail={railOpen && !compactRail}
  class:with-panel={rewindCheckpointId !== null}
  style={`--explorer-w:${filesWidth}px`}
>
  <!-- B13 — the repository, beside the conversation about it. First column on
       a wide window; a dismissible sheet below the split, exactly as the
       background-work rail is, so neither panel invents a second pattern. -->
  {#if filesOpen}
    {#if compactRail}
      <button
        type="button"
        class="rail-scrim"
        aria-label="Close files"
        onclick={() => closeFiles(true)}
      ></button>
    {/if}
    <div
      id="build-files"
      class="files-slot"
      class:drawer={compactRail}
      role={compactRail ? "dialog" : undefined}
      aria-modal={compactRail ? "true" : undefined}
      aria-label={compactRail ? "Repository files" : undefined}
      bind:this={filesElement}
    >
      <CodeExplorer
        repoId={activeRepo?.repo_id ?? ""}
        repoLabel={activeRepo?.label ?? ""}
        onclose={() => closeFiles(true)}
        onmention={mentionPath}
      />
      {#if !compactRail}
        <!-- Separator, not decoration: it carries the value it sets, so the
             keyboard can resize what the pointer can drag. This is the ARIA
             window-splitter pattern — a focusable `separator` with a value —
             which the two rules below do not model. -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <div
          class="files-resize"
          class:active={resizing}
          role="separator"
          aria-label="Resize the file explorer"
          aria-orientation="vertical"
          aria-valuemin={MIN_EXPLORER_WIDTH}
          aria-valuemax={MAX_EXPLORER_WIDTH}
          aria-valuenow={filesWidth}
          tabindex="0"
          onpointerdown={startResize}
          onkeydown={resizeByKey}
        ></div>
      {/if}
    </div>
  {/if}

  <div class="main" bind:this={buildMainElement}>
    <header class="build-header">
      <div class="repo-slot">
        <button
          type="button"
          class="repo-button"
          onclick={() => (reposOpen = !reposOpen)}
          aria-expanded={reposOpen}
        >
          <Icon name={activeRepo?.kind === "github" ? "branch" : "folder"} size="sm" />
          <span class="repo-name">{activeRepo?.label ?? "No repository"}</span>
          <Icon name="chevron-down" size="sm" />
        </button>
        {#if activeRepo?.kind === "local" && !activeRepo.local_exists}
          <span class="repo-warning" role="status">That folder is no longer in the workspace.</span>
        {/if}
      </div>

      <div class="header-actions">
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={newConversation}
          disabled={streaming || turns.length === 0}
        >
          New chat
        </button>
        <!-- BUG-22 — the same conversation menu Chat carries, in the same
             place, so export is one action wherever the work happened. -->
        <div class="conversation-menu">
          <button
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
                onclick={() => { conversationMenuOpen = false; exportOpen = true; }}
              >Export conversation…</button>
              <button type="button" role="menuitem" onclick={printConversation}>
                Print / Save as PDF
              </button>
            </div>
          {/if}
        </div>
        <!-- Both toggles carry an `aria-label`, because their visible words are
             the first thing a narrow window drops. A button that loses its name
             below the split is unreachable by voice and unreadable by a screen
             reader on exactly the device that needs it most. -->
        <button
          type="button"
          class="btn btn-ghost btn-sm files-toggle"
          onclick={toggleFiles}
          aria-expanded={filesOpen}
          aria-controls="build-files"
          aria-label={filesOpen ? "Hide repository files" : "Show repository files"}
          disabled={activeRepo === null}
          title={activeRepo === null
            ? "Connect a repository to browse its files"
            : filesOpen
              ? "Hide files"
              : "Show files"}
        >
          <Icon name="folder" size="sm" />
          <span class="rail-label">{filesOpen ? "Hide files" : "Files"}</span>
        </button>
        <button
          type="button"
          class="btn btn-ghost btn-sm rail-toggle"
          onclick={toggleRail}
          aria-expanded={railOpen}
          aria-controls="build-rail"
          aria-label={railOpen ? "Hide background work" : "Show background work"}
          title={railOpen ? "Hide background work" : "Background work"}
        >
          <Icon name="panel" size="sm" />
          <span class="rail-label">{railOpen ? "Hide background work" : "Background work"}</span>
        </button>
      </div>
    </header>

    {#if projectNotice}<p class="line-notice" role="status">{projectNotice}</p>{/if}
    <!-- MEM-08 — said only when a link named an exchange this conversation
         does not hold; landing is shown by the highlight, not by text. -->
    {#if anchorNotice}<p class="line-notice" role="status">{anchorNotice}</p>{/if}

    {#if reposOpen}
      <RepoConnector
        view={repos}
        onchanged={loadRepos}
        onclose={() => (reposOpen = false)}
      />
    {/if}

    {#if plan !== null}
      <!-- B6 — the plan sits above the transcript rather than inside a turn:
           it is the conversation's spine, not one turn's output, and it has to
           stay visible while the thread scrolls under it. -->
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
          icon="code"
          title="What should we build?"
          compactTitle="What should we build?"
          body={activeRepo === null
            ? "Connect a repository to give Raiker something to work in, or just describe what you want and start from nothing."
            : `Working in ${activeRepo.label}. Describe the change, and pick how much Raiker may do on its own.`}
          serif={true}
        />
      {/if}

      {#each turns as turn (turn.id)}
        {@const answer = answerText(turn)}
        {@const toolRows = toolActivity(turn.events)}
        {@const reasoning = collectReasoning(turn.events) || (turn.retainedReasoning ?? "")}
        {@const turnSourceList = sourcesForTurn(turnSources, turn.response?.turn_id)}
        <!-- MEM-08 — the coordinate a link can name. -->
        <article class="turn" data-turn-id={turn.response?.turn_id ?? undefined}>
          <div class="user-message">
            <div class="from-you">
              <span class="mode-tag">{buildMode(turn.mode).label}</span>
              <p class="bubble-text">{turn.prompt}</p>
            </div>
            <!-- C14/B19 — the same actions Chat carries. A retried prompt is a
                 new turn under the current mode, never a replay of the governed
                 actions the first one took.

                 B18 — and Rewind, which is why this control matters more here
                 than anywhere else: Build is the surface whose turns change
                 files, so "undo that turn" is the control that makes leaving it
                 running reasonable. It opens the preflight for the checkpoint
                 this turn wrote and restores nothing on its own. -->
            {#if turn.prompt !== ""}
              <MessageActions
                text={turn.prompt}
                disabled={streaming}
                onedit={editPrompt}
                onretry={retryPrompt}
                onrewind={turn.response?.turn_id
                  ? () => void rewindFromTurn(turn.response?.turn_id ?? "")
                  : undefined}
                rewinding={rewindingTurn === turn.response?.turn_id}
              />
            {/if}
            {#if turn.attachments.length > 0}
              <!-- The same cards the composer showed, so what you sent looks
                   like what you attached. Build has no file inspector of its
                   own, so these state what rode along without claiming to
                   open it. -->
              <div class="turn-attachments">
                {#each turn.attachments as a, i (a.attachmentId ?? a.path ?? i)}
                  <AttachmentCard attachment={a} />
                {/each}
              </div>
            {/if}
          </div>

          <div class="from-raiker">
            {#if turn.response?.status === "needs_approval" || turn.resumeState}
              <!-- BUG-24 — parity with Chat: the parked turn states its own
                   status and flips the moment a decision lands anywhere. -->
              <div class="parked" class:continuing={turn.resumeState === "continuing"}>
                {#if turn.resumeState === "continuing"}
                  <p role="status" aria-live="polite">
                    <span class="pulse" aria-hidden="true"></span>
                    {turn.resumeNote ?? "Approved — continuing…"}
                  </p>
                {:else if turn.resumeState === "elsewhere"}
                  <p role="status" aria-live="polite">{turn.resumeNote}</p>
                {:else}
                  <p><Icon name="approvals" size="sm" /> Waiting for approval</p>
                  {#if liveChannelDown}
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm"
                      disabled={streaming}
                      onclick={() => void continueNow()}
                    >Continue now</button>
                  {/if}
                {/if}
              </div>
            {/if}
            <!-- BUG-207 slices C and D, as in Chat: the model's own reasoning
                 when the turn produced any, collapsed once the answer starts,
                 and nothing at all when it produced none. -->
            <ReasoningBlock
              text={reasoning}
              streaming={turn.streaming}
              notKeptChars={turn.reasoningChars ?? 0}
            />

            <!-- BUG-206 slice D, as in Chat: every call this turn made, in call
                 order. Build is where a turn makes the most of them, and where
                 a silent one was hardest to account for. -->
            <ToolActivity rows={toolRows} />

            {#if turn.streaming && answer === "" && reasoning === "" && toolRows.length === 0}
              <p class="working" role="status">
                <span class="pulse" aria-hidden="true"></span>
                Reading and planning…
              </p>
            {:else if turn.streaming && answer === "" && hasRunningTool(toolRows)}
              <!-- Parity with Chat. The pulsing row says this to anyone who can
                   see it; without this line a screen reader hears "Reading and
                   planning…" stop and then nothing until the answer arrives. -->
              <span class="sr-only" role="status">Running a tool.</span>
            {/if}

            <!-- B17/C13 — as in Chat: a turn the owner stopped says so, rather
                 than simply ending early. -->
            {#if !turn.streaming && turn.response?.status === "stopped"}
              <p class="stopped-line" role="status">
                Stopped at your request — this turn ended at a safe boundary and kept what it had
                already done.
              </p>
            {/if}

            {#if answer !== ""}
              <div class="answer">
                <!-- C6 — `[s1]` becomes a chip only when this turn's ledger has
                     an s1. A marker the model invented stays literal text. -->
                <Markdown
                  text={answer}
                  citations={renderableCitations(turnSourceList)}
                  oncite={(sourceId) => showSourceById(turn.response?.turn_id ?? "", sourceId, answer)}
                />
              </div>
              {#if !turn.streaming}
                <!-- Parity with Chat: the same glyph, the same behaviour, so a
                     response reads the same way in either conversation. -->
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
                </div>
              {/if}
            {:else if !turn.streaming && turn.error === null && turn.response !== null && turn.response.status !== "needs_approval"}
              <!-- BUG-73 / BUG-206 — see ChatView: a turn with no answer reports
                   its state, never a claim about whether anything ran, and the
                   parked case is left to the row and the card that state it. -->
              <div class="answer"><p class="bubble-text muted">(No answer text was returned.)</p></div>
            {/if}

            <!-- C6 — everything this turn actually read, under the answer that
                 used it, and C4 — the passage it used, opened where the citation
                 is rather than in a pane Build does not have yet. -->
            {#if !turn.streaming && turnSourceList.length > 0}
              <SourceChips
                sources={turnSourceList}
                citedIds={citedSourceIds(answer, turnSourceList)}
                openSourceId={openSourceTurnId === turn.response?.turn_id ? openSourceId : null}
                onopen={(source) => void showSource(source, sentenceAround(answer, source.source_id))}
              />
              {#if openSourceId !== null && openSourceTurnId === turn.response?.turn_id}
                <SourceExcerptPanel
                  source={openSource}
                  loading={openSourceLoading}
                  onclose={closeSource}
                />
              {/if}
            {/if}

            {#if copyNotice !== null}<p class="error" role="alert">{copyNotice}</p>{/if}
            {#if turn.error !== null}<p class="error" role="alert">{turn.error}</p>{/if}

            {#if turn.events.some((event) => event.kind === "lifecycle" || event.kind === "tool")}
              <details class="governance" open={turn.streaming}>
                <summary><Icon name="shield" size="sm" /> How this turn was governed</summary>
                <ol>
                  {#each groupPhases(turn.events) as row (row.phase)}
                    <li>
                      <span class="phase">{row.label}</span>
                      <ul>
                        {#each row.events as event, index (index)}<li>{summarizeEvent(event)}</li>{/each}
                      </ul>
                    </li>
                  {/each}
                </ol>
              </details>
            {/if}
          </div>
        </article>
      {/each}

      {#if approvals.length > 0}
        <section class="decisions" aria-labelledby="build-decisions">
          <h2 id="build-decisions">Waiting on you</h2>
          <p class="decisions-lead">
            Raiker re-governs every accepted action before it runs — a recorded decision is never treated as permission
            it already had. Each decision below reports afterwards whether it was applied or only recorded.
          </p>
          {#each approvals as approval (approval.approval_id)}
            <div class="decision">
              <div class="decision-head">
                <span class="decision-title">{humanize(approval.tool_name)}</span>
                <Badge variant={approvalBadge(approval.status)} label={`${approval.risk_level} risk`} />
              </div>
              <p class="decision-meta">
                {humanize(approval.capability)} · raised {relativeTime(approval.created_at)}
              </p>
              {#if approvalDiffs[approval.approval_id] !== undefined}
                <!-- B14 — the change, read *and decided* where it was
                     proposed. Accepting part of it is the act a coding review
                     is made of, and it used to mean rejecting everything and
                     asking again. -->
                <DiffView
                  diff={approvalDiffs[approval.approval_id].diff}
                  path={approvalDiffs[approval.approval_id].path}
                  selectable={approval.status === "pending"}
                  bind:selection={approvalHunks[approval.approval_id]}
                />
              {/if}
              <!-- BUG-271 — the reviewer can correct the change as well as
                   narrow it. An edit is a different action, so it denies this
                   proposal and raises theirs; the copy says so rather than
                   letting it read as an amendment. -->
              {#if approvalEdits[approval.approval_id] !== undefined}
                <div class="decision-edit">
                  <label class="sr-only" for={`edit-${approval.approval_id}`}>
                    Your version of this change
                  </label>
                  <textarea
                    id={`edit-${approval.approval_id}`}
                    class="textarea"
                    rows="10"
                    spellcheck="false"
                    disabled={approvalBusy === approval.approval_id}
                    bind:value={approvalEdits[approval.approval_id]}
                  ></textarea>
                  <p class="decision-meta">
                    Denies the change above and proposes yours. You will be asked to accept it.
                  </p>
                  <div class="decision-actions">
                    <button
                      type="button"
                      class="btn btn-primary btn-sm"
                      disabled={approvalBusy === approval.approval_id}
                      onclick={() => proposeEdit(approval)}
                    >
                      Propose as a new change
                    </button>
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm"
                      disabled={approvalBusy === approval.approval_id}
                      onclick={() =>
                        (approvalEdits = { ...approvalEdits, [approval.approval_id]: undefined })}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              {:else}
                <div class="decision-actions">
                  <button
                    type="button"
                    class="btn btn-primary btn-sm"
                    disabled={approvalBusy === approval.approval_id}
                    onclick={() => resolve(approval, true)}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    class="btn btn-ghost btn-sm"
                    disabled={approvalBusy === approval.approval_id}
                    onclick={() => resolve(approval, false)}
                  >
                    Reject
                  </button>
                  {#if approval.status === "pending" && approvalDiffs[approval.approval_id]?.kind === "patch" && approvalDiffs[approval.approval_id]?.diff}
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm"
                      disabled={approvalBusy === approval.approval_id}
                      onclick={() =>
                        (approvalEdits = {
                          ...approvalEdits,
                          [approval.approval_id]:
                            approvalDiffs[approval.approval_id]?.diff ?? "",
                        })}
                    >
                      Edit…
                    </button>
                  {/if}
                  <a class="btn btn-ghost btn-sm" href="#/approvals">Open in Approvals</a>
                </div>
              {/if}
            </div>
          {/each}
          {#if approvalNotice}<p class="line-notice" role="status">{approvalNotice}</p>{/if}
        </section>
      {/if}
    </div>

    <CommandOutputPane {sessionId} {visible} bind:open={commandPaneOpen} />

    <Composer
      ariaLabel="Build composer"
      cardClass="composer-build"
      inputId="build-prompt"
      inputLabel="Describe the change"
      bind:value={promptText}
      bind:inputEl={promptEl}
      inputProps={{
        placeholder: activeRepo === null
          ? "Describe what you want built…"
          : `Describe the change in ${activeRepo.label}…`,
        title: "Enter to send, Shift+Enter for a new line, Shift+Tab to change mode, / for commands, @ to mention a file",
        disabled: streaming,
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
        <ComposerChips store={attachStore} disabled={streaming} />
        <ModelReadinessStrip readiness={modelReadiness} draftPreserved={promptText.trim() !== ""} />
        <SkillLinkNotice text={promptText} />

        {#if shortcutsOpen}
          <ShortcutSheet surface="build" onclose={() => (shortcutsOpen = false)} />
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
      {/snippet}

      {#snippet below()}
        <!-- BUG-70 — the mode picker's own menu carries what each mode does, so
             the composer keeps only the line the picker cannot know: for Auto,
             what the owner's standing permissions actually allow. Auto promises
             nothing it has not read. -->
        {#if standingNote !== null}
          <p class="line-notice" role="status">
            <span class="standing-wide">{standingNote} <a href="#/capabilities">Change in Permissions →</a></span>
            <span class="standing-compact">Auto follows your Permissions.</span>
          </p>
        {/if}

        {#if attachOpen}
          <ComposerAttachPanel store={attachStore} disabled={streaming} idPrefix="build" />
        {/if}
      {/snippet}

      {#snippet turn()}
        <TurnControl sessionId={sessionId} bind:stopping />
      {/snippet}

      {#snippet left()}
            <ComposerAttach bind:this={attachControl} bind:open={attachOpen} disabled={streaming} />
            <VoiceDictationControl
              bind:this={voiceControl}
              draft={promptText}
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
            <BuildModePicker {mode} onchange={setMode} disabled={streaming} />
            <label class="project-picker" data-selected={projectReady}>
              <Icon name="folder" size="sm" />
              <span class="sr-only">Project for this build</span>
              <select
                class="bar-select"
                value={projectId}
                aria-label="Project for this build"
                disabled={streaming}
                onchange={(event) => void onProjectPicked((event.currentTarget as HTMLSelectElement).value)}
              >
                <option value="">Select a project</option>
                {#each projects?.projects ?? [] as project (project.project_id)}
                  <option value={project.project_id}>{project.name}</option>
                {/each}
              </select>
            </label>
            <ApprovalModeControl />
            <ExecutionEnvironmentBadge />
      {/snippet}

      {#snippet right()}
            <ModelPicker
              bind:profileId={modelProfile}
              bind:model
              bind:open={modelPickerOpen}
              bind:effort={reasoningEffort}
              efforts={reasoningEfforts}
              {profiles}
              {selectedProfile}
              onchosen={(profileId, chosen) => void rememberSurfaceModel("build", profileId, chosen)}
              disabled={streaming}
            />
            <div class="context-wrap" bind:this={contextControlEl}>
              <button
                type="button"
                class="context-trigger"
                aria-label={activeProfile?.context_window_tokens
                  ? "Context window"
                  : "Context window — capacity unknown"}
                aria-expanded={contextOpen}
                title={activeProfile?.context_window_tokens
                  ? "Context window"
                  : "Context window — capacity unknown"}
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
              disabled={streaming || attachStore.uploading || promptText.trim() === "" || modelBlocked || !projectReady}
            >
              <Icon name={streaming ? "clock" : "send"} size="sm" />
              <span class="send-label">{streaming ? "Working…" : "Send"}</span>
            </button>
      {/snippet}

      {#snippet footer()}
        <!-- The composer states the boundary, not the lesson: which project a
             turn will run in is what changes between turns, and what a project
             lets Build reach is explained once in the guide. -->
        {#if !projectReady}
          <p class="project-required" role="status">Select a project to start.</p>
        {:else}
          <p class="project-boundary" role="status">
            Working in <strong>{selectedProject?.name}</strong>
          </p>
        {/if}
      {/snippet}

      {#snippet hint()}
        Shift+Tab changes mode · Enter sends · <code>/</code> for commands ·
        <code>@</code> to mention a file ·
        <button type="button" class="hint-link" onclick={() => (shortcutsOpen = !shortcutsOpen)}>
          all shortcuts
        </button>
      {/snippet}
    </Composer>
  </div>

  {#if exportOpen && sessionId !== null}
    <ExportConversationDialog
      sessionId={sessionId}
      onclose={() => (exportOpen = false)}
      onprint={printConversation}
    />
  {/if}

  {#if railOpen}
    {#if compactRail}
      <button type="button" class="rail-scrim" aria-label="Close background work" onclick={() => closeRail(true)}></button>
    {/if}
    <div
      id="build-rail"
      class="rail-slot"
      class:drawer={compactRail}
      role={compactRail ? "dialog" : undefined}
      aria-modal={compactRail ? "true" : undefined}
      aria-label={compactRail ? "Background work" : undefined}
      bind:this={railElement}
    >
      <BuildSidePanel
        projectId={projectId || null}
        {projects}
        onclose={() => closeRail(true)}
      />
    </div>
  {/if}

  <!-- B18 — the same rewind funnel Checkpoints opens, asked for at the turn.
       Inside the workspace grid so it takes the right-hand column beside the
       transcript, rather than stacking under the composer. -->
  <RewindPanel checkpointId={rewindCheckpointId} onclose={() => (rewindCheckpointId = null)} />
</div>

<style>
  /* MEM-08 — the exchange a link landed on. A brief mark, not a state. */
  :global(.turn.turn-anchored) {
    border-radius: var(--r-md);
    box-shadow: 0 0 0 2px var(--accent-border);
    background: var(--accent-soft);
    transition:
      box-shadow 0.4s ease,
      background 0.4s ease;
  }
  @media (prefers-reduced-motion: reduce) {
    :global(.turn.turn-anchored) {
      transition: none;
    }
  }

  /* BUG-22 — the print layout, matching Chat's. Save as PDF produces the
     transcript as a document: no chrome, no controls, no split turns. */
  @media print {
    :global(.sidebar), :global(.topbar), :global(.skip-link), :global(.composer),
    .build-header, .rail-slot, .decisions, .parked,
    :global(.md-copy) { display: none !important; }
    :global(.app-shell), :global(.app-main), :global(.content), :global(.responsive-page),
    .build, .main { display: block !important; height: auto !important; max-width: none !important; }
    .thread { display: block; overflow: visible; }
    .turn { break-inside: avoid; margin-bottom: 1.5rem; }
    :global(.md-code) { break-inside: avoid; }
    @page { margin: 18mm 15mm; }
  }
  .build {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-4);
    /* The room the shell gives a page, so the transcript scrolls inside the
       workspace instead of stretching it and taking the shell's scroll with it. */
    height: var(--content-h);
    min-height: 32rem;
  }
  .build.with-rail {
    grid-template-columns: minmax(0, 1fr) 21rem;
  }
  /* B13 — the explorer takes the first column, at the width the owner dragged
     it to. Every combination is spelled out rather than left to the cascade,
     because a grid that silently loses a column drops a panel off screen. */
  .build.with-files {
    grid-template-columns: var(--explorer-w, 17.5rem) minmax(0, 1fr);
  }
  .build.with-files.with-rail {
    grid-template-columns: var(--explorer-w, 17.5rem) minmax(0, 1fr) 21rem;
  }
  /* B18 — the rewind preflight takes a column of its own, so the transcript it
     is about stays on screen behind it. */
  @media (min-width: 64rem) {
    .build.with-panel {
      grid-template-columns: minmax(0, 1fr) minmax(20rem, 26rem);
    }
    .build.with-rail.with-panel {
      grid-template-columns: minmax(0, 1fr) 21rem minmax(20rem, 26rem);
    }
    .build.with-files.with-panel {
      grid-template-columns: var(--explorer-w, 17.5rem) minmax(0, 1fr) minmax(18rem, 24rem);
    }
    .build.with-files.with-rail.with-panel {
      grid-template-columns:
        var(--explorer-w, 17.5rem) minmax(0, 1fr) 21rem minmax(18rem, 24rem);
    }
  }
  .files-slot {
    position: relative;
    min-height: 0;
    min-width: 0;
    display: flex;
  }
  .files-slot > :global(.code-explorer) {
    flex: 1;
    min-height: 0;
    min-width: 0;
  }
  /* The divider is the full height of the column and sits *between* the two,
     so the hit area is the gap rather than a sliver of the panel. */
  .files-resize {
    position: absolute;
    top: 0;
    bottom: 0;
    right: calc(var(--space-4) / -2 - 2px);
    width: 9px;
    cursor: col-resize;
    background: none;
    border: 0;
    border-radius: 999px;
  }
  .files-resize::after {
    content: "";
    position: absolute;
    inset: 0 4px;
    border-radius: 999px;
    background: transparent;
    transition: background 0.12s ease;
  }
  .files-resize:hover::after,
  .files-resize:focus-visible::after,
  .files-resize.active::after {
    background: var(--accent-border, var(--border));
  }
  .files-resize:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  @media (prefers-reduced-motion: reduce) {
    .files-resize::after {
      transition: none;
    }
  }
  .main {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    gap: var(--space-3);
  }
  .rail-slot {
    min-height: 0;
    display: flex;
  }
  .rail-slot > :global(*) {
    flex: 1;
    min-height: 0;
  }
  .rail-scrim {
    position: fixed;
    inset: 0;
    z-index: 90;
    border: 0;
    background: var(--overlay);
  }

  .build-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .repo-slot {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
  }
  .repo-button {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 650;
    padding: 0.3rem 0.7rem;
    cursor: pointer;
    max-width: 22rem;
  }
  .repo-button:hover {
    border-color: var(--accent-border);
  }
  .repo-button:focus-visible {
    outline: 2px solid var(--focus-ring);
  }
  .repo-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .repo-warning {
    font-size: var(--text-xs);
    color: var(--warn);
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
  }
  /* BUG-22 — the conversation menu, identical to Chat's so the action lives in
     the same place on both conversation surfaces. */
  .conversation-menu { position: relative; display: inline-block; }
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
    font-size: var(--text-sm);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--r-sm);
    text-align: left;
    cursor: pointer;
  }
  .conversation-menu .menu button:hover:not(:disabled) { background: var(--accent-soft); }
  .conversation-menu .menu button:disabled { color: var(--text-3); cursor: default; }
  /* BUG-24 — the parked turn's live status line. */
  .parked {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin: 0 0 0.5rem;
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--warn-border);
    border-radius: var(--r-sm);
    background: var(--warn-soft);
  }
  .parked p {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--warn);
  }
  .parked.continuing {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  .parked.continuing p { color: var(--accent); }
  .project-picker {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    min-width: 0;
  }


  .plan-slot {
    flex: 0 0 auto;
    margin-bottom: var(--space-3);
  }
  .thread {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding-bottom: var(--space-3);
  }
  .turn {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .user-message {
    align-self: flex-end;
    max-width: min(80%, 44rem);
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: .5rem;
  }
  .from-you {
    background: var(--accent);
    color: var(--text-inverse);
    border-radius: 1.15rem 1.15rem 0.3rem 1.15rem;
    padding: 0.65rem 0.9rem;
    box-shadow: var(--shadow-1);
  }
  .mode-tag {
    display: inline-block;
    font-size: var(--text-2xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    opacity: 0.85;
    margin-bottom: 0.25rem;
  }
  .from-raiker {
    align-self: flex-start;
    max-width: min(88%, 48rem);
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .answer {
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: 1.15rem 1.15rem 1.15rem 0.3rem;
    padding: 0.65rem 0.9rem;
  }
  .bubble-text {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .muted {
    color: var(--text-3);
  }
  .working {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-sm);
    font-weight: 650;
  }
  .pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    animation: build-pulse 1.2s ease-in-out infinite;
  }
  @keyframes build-pulse {
    0%,
    100% {
      opacity: 0.35;
    }
    50% {
      opacity: 1;
    }
  }
  .governance {
    border-top: 1px dashed var(--border);
    padding-top: 0.45rem;
  }
  .governance summary {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    cursor: pointer;
    font-size: var(--text-xs);
    font-weight: 650;
    color: var(--text-3);
    list-style: none;
  }
  .governance summary::-webkit-details-marker {
    display: none;
  }
  .governance ol {
    margin: 0.45rem 0 0;
    padding-left: 0;
    list-style: none;
    display: grid;
    gap: 0.35rem;
  }
  .phase {
    font-size: var(--text-xs);
    font-weight: 650;
    color: var(--accent);
  }
  .governance ol ul {
    margin: 0.1rem 0 0;
    padding-left: 1rem;
    font-size: var(--text-sm);
    color: var(--text-2);
  }

  .decisions {
    border: 1px solid var(--warn-border);
    background: var(--warn-soft);
    border-radius: var(--r-md);
    padding: var(--space-3);
    display: grid;
    gap: var(--space-2);
  }
  .decisions h2 {
    margin: 0;
    font-size: var(--text-md);
    color: var(--warn);
  }
  .decisions-lead {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-2);
    line-height: 1.5;
  }
  .decision {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.55rem 0.7rem;
  }
  .decision-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .decision-title {
    font-size: var(--text-sm);
    font-weight: 650;
  }
  .decision-meta {
    margin: 0.2rem 0 0.5rem;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .decision-actions {
    display: flex;
    gap: 0.35rem;
    flex-wrap: wrap;
  }
  /* BUG-271 — the reviewer's own diff, monospaced because it is one, and kept
     inside the panel's width so a long line scrolls rather than widening it. */
  .decision-edit {
    display: grid;
    gap: 0.35rem;
    margin-top: 0.5rem;
  }
  .decision-edit .textarea {
    width: 100%;
    font-family: var(--font-mono, ui-monospace, monospace);
    font-size: var(--text-sm);
    white-space: pre;
    overflow-x: auto;
  }

  .turn-attachments { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.4rem; }
  .response-actions { display: inline-flex; align-items: center; gap: 0.15rem; }
  .copy-message {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    margin-top: var(--space-2);
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--r-sm);
    color: var(--text-3);
    cursor: pointer;
    padding: 0;
  }
  .copy-message:hover { color: var(--text-1); border-color: var(--border); }
  .copy-message.copied { color: var(--ok); }
  .line-notice {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-3);
    line-height: 1.5;
  }
  .error-line {
    color: var(--danger);
    font-size: var(--text-sm);
    margin: 0.35rem 0 0;
  }
  .standing-compact { display: none; }
  .error {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--danger);
  }
  .stopped-line {
    margin: 0 0 0.4rem;
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .project-required,
  .project-boundary {
    margin: 0.35rem 0 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  /* Deliberately not `--danger`: nothing has failed, the owner simply has not
     chosen yet. Red here competes with real problems on the same screen. */
  .project-required { color: var(--text-2); font-weight: 600; }
  .project-boundary strong { color: var(--text-1); }

  .context-wrap { position: relative; }
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

  /* Compact screens preserve the transcript width and float background work as
     an isolated right-side drawer. */
  @media (max-width: 63.9rem) {
    .build,
    .build.with-rail,
    .build.with-files,
    .build.with-files.with-rail {
      grid-template-columns: minmax(0, 1fr);
      height: var(--content-h);
      min-height: 32rem;
    }
    /* B13 — below the split the explorer is a sheet from the left, mirroring
       the background-work drawer on the right. Same pattern, opposite edge, so
       neither can be mistaken for the other. */
    .files-slot.drawer {
      position: fixed;
      inset: 0 auto 0 0;
      z-index: 100;
      width: min(20rem, 88vw);
      padding: var(--space-3);
      background: var(--surface);
      border-right: 1px solid var(--border);
      box-shadow: var(--shadow-2);
      transition: transform var(--motion-shell) var(--ease-shell);
    }
    .rail-slot.drawer {
      position: fixed;
      inset: 0 0 0 auto;
      z-index: 100;
      width: min(21rem, 90vw);
      padding: var(--space-3);
      background: var(--surface);
      border-left: 1px solid var(--border);
      box-shadow: var(--shadow-2);
      transition: transform var(--motion-shell) var(--ease-shell);
    }
    .build-header { align-items: center; gap: var(--space-2); }
    .repo-button { max-width: 100%; min-height: 2.75rem; padding-inline: .6rem; }
    .header-actions { width: 100%; flex-wrap: nowrap; justify-content: flex-end; }
    .rail-label { display: none; }
    .thread :global(.empty-body) { display: none; }
    .thread :global(.empty) { padding-block: var(--space-5); }
    :global(.command-pane:not(.expanded)) { display: none; }
    /* Build carries six controls on the left where Chat has four, so its left
       group wraps to a second row rather than compressing off the screen. The
       bar used to hide the project picker below this width while still printing
       "Select a project to start." underneath and keeping Send disabled — an
       instruction pointing at a control that was not on the screen, with no
       other route to it in Build. What a narrow window may lose is information
       (the context ring, the environment badge); what gates sending stays. */
    :global(.composer-build .bar-left) { flex-wrap: wrap; }
    .project-picker { max-width: 10rem; }
    .project-picker :global(.bar-select) { min-width: 0; }
    .context-wrap, :global(.composer-build .environment-badge) { display: none; }
    .standing-wide { display: none; }
    .standing-compact { display: inline; }
    /* Build's mode picker has no equivalent in Chat, so its compact form lives
       here rather than in the shared composer. */
    :global(.composer-build .mode-trigger) {
      width: 2.75rem;
      height: 2.75rem;
      padding: 0;
      justify-content: center;
    }
    :global(.composer-build .mode-trigger > span),
    :global(.composer-build .mode-trigger > svg:last-child) { display: none; }
  }
</style>
