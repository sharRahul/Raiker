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
  import { onMount, tick } from "svelte";
  import { rememberSurfaceModel, surfaceModel } from "../surfaceModel.svelte";
  import Badge from "../components/Badge.svelte";
  import ApprovalModeControl from "../components/ApprovalModeControl.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import ModelReadinessStrip from "../components/ModelReadinessStrip.svelte";
  import ExecutionEnvironmentBadge from "../components/ExecutionEnvironmentBadge.svelte";
  import BuildSidePanel from "../components/BuildSidePanel.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import ContextMeterPopover from "../components/ContextMeterPopover.svelte";
  import ContextRing from "../components/ContextRing.svelte";
  import Markdown from "../components/Markdown.svelte";
  import RepoConnector from "../components/RepoConnector.svelte";
  import PlanChecklist from "../components/PlanChecklist.svelte";
  import ReasoningBlock from "../components/ReasoningBlock.svelte";
  import ToolActivity from "../components/ToolActivity.svelte";
  import ExportConversationDialog from "../components/ExportConversationDialog.svelte";
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
  import { hasSteps, planFromEvent } from "../agentPlan";
  import { approvalBadge } from "../statusMaps";
  import AttachmentCard from "../components/AttachmentCard.svelte";
  import ComposerAttach from "../components/ComposerAttach.svelte";
  import ComposerAttachPanel from "../components/ComposerAttachPanel.svelte";
  import ComposerChips from "../components/ComposerChips.svelte";
  import SkillLinkNotice from "../components/SkillLinkNotice.svelte";
  import BuildModePicker from "../components/BuildModePicker.svelte";
  import TurnControl from "../components/TurnControl.svelte";
  import CommandOutputPane from "../components/CommandOutputPane.svelte";
  import { createAttachmentStore, type ComposerAttachment } from "../composerAttachments.svelte";
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
    projects = null,
    onProjectsChanged,
    // Build keeps its transcript when the owner navigates away — the view is
    // hidden, not unmounted — so anything it read once would otherwise stay as
    // it was. Knowing when it comes back is what lets repository state (and the
    // code map that follows the selected repository) be re-read rather than
    // shown as it stood before a visit to Permissions.
    visible = true,
  }: {
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
  }

  // BUG-35 — Build carries files too. Same store, same limits, same governed
  // upload path as Chat: a stack trace, a failing screenshot or a spec document
  // is exactly what you want to hand a coding agent, and until now this
  // composer had no way to hand it one.
  const attachStore = createAttachmentStore();
  let attachControl = $state<ComposerAttach | undefined>();
  let attachOpen = $state(false);

  let promptText = $state("");
  let speechLanguage = $state<SpeechLanguage>("auto");
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
  const BUILD_PROJECT_KEY = "raiker.build.project";
  let projectId = $state(readRememberedProject());

  function readRememberedProject(): string {
    try {
      return window.localStorage.getItem(BUILD_PROJECT_KEY) ?? "";
    } catch {
      return "";
    }
  }

  function rememberProject(value: string) {
    try {
      if (value === "") window.localStorage.removeItem(BUILD_PROJECT_KEY);
      else window.localStorage.setItem(BUILD_PROJECT_KEY, value);
    } catch {
      // A blocked storage is a lost preference, never a blocked turn.
    }
  }

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
  let mentionRequest = 0;

  const slashItems = $derived.by<MenuItem[]>(() => {
    const fragment = menuKind === "slash" ? slashFragment(promptText, caret()) : null;
    if (fragment === null) return [];
    return matchCommands("build", fragment).map((command) => ({
      id: command.name,
      label: `/${command.name}`,
      detail: command.summary,
    }));
  });
  const menuItems = $derived(menuKind === "slash" ? slashItems : mentionItems);

  function caret(): number {
    return promptEl?.selectionStart ?? promptText.length;
  }

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

  /** Run one command. Each is a control this surface already has. */
  function runSlashCommand(name: string) {
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

  async function scrollToEnd() {
    await tick();
    // Guarded: jsdom has no scrollTo implementation.
    if (typeof scrollEl?.scrollTo === "function") scrollEl.scrollTo({ top: scrollEl.scrollHeight });
  }

  function newConversation() {
    if (streaming) return;
    audioSessionCoordinator.stopAll("route");
    resetVoiceProvenance();
    turns = [];
    sessionId = null;
    approvals = [];
    plan = null;
    promptEl?.focus();
  }

  // ── Projects ─────────────────────────────────────────────────────────
  async function onProjectPicked(value: string) {
    if (streaming) return;
    projectId = value;
    rememberProject(value);
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
  async function loadApprovals() {
    if (sessionId === null) return;
    try {
      const pending = await api.approvals();
      approvals = pending.filter((approval) => approval.session_id === sessionId);
    } catch {
      approvals = [];
    }
  }

  async function resolve(approval: ApprovalView, approve: boolean) {
    approvalBusy = approval.approval_id;
    approvalNotice = null;
    try {
      const result = await api.resolveApproval(approval.approval_id, {
        approve,
        reason: approve ? "accepted in the Build workspace" : "rejected in the Build workspace",
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

<div class="build" class:with-rail={railOpen && !compactRail}>
  <div class="main" bind:this={buildMainElement}>
    <header class="build-header">
      <div class="repo-slot">
        <button
          type="button"
          class="repo-button"
          onclick={() => (reposOpen = !reposOpen)}
          aria-expanded={reposOpen}
        >
          <Icon name={activeRepo?.kind === "github" ? "branch" : "folder"} size={15} />
          <span class="repo-name">{activeRepo?.label ?? "No repository"}</span>
          <Icon name="chevron-down" size={14} />
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
        <button
          type="button"
          class="btn btn-ghost btn-sm rail-toggle"
          onclick={toggleRail}
          aria-expanded={railOpen}
          aria-controls="build-rail"
        >
          <Icon name="panel" size={15} />
          <span class="rail-label">{railOpen ? "Hide background work" : "Background work"}</span>
        </button>
      </div>
    </header>

    {#if projectNotice}<p class="line-notice" role="status">{projectNotice}</p>{/if}

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
      {#if turns.length === 0}
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
        {@const reasoning = collectReasoning(turn.events)}
        {@const turnSourceList = sourcesForTurn(turnSources, turn.response?.turn_id)}
        <article class="turn">
          <div class="user-message">
            <div class="from-you">
              <span class="mode-tag">{buildMode(turn.mode).label}</span>
              <p class="bubble-text">{turn.prompt}</p>
            </div>
            <!-- C14/B19 — the same three actions Chat carries. A retried prompt
                 is a new turn under the current mode, never a replay of the
                 governed actions the first one took. -->
            {#if turn.prompt !== ""}
              <MessageActions
                text={turn.prompt}
                disabled={streaming}
                onedit={editPrompt}
                onretry={retryPrompt}
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
                  <p><Icon name="approvals" size={14} /> Waiting for approval</p>
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
            <ReasoningBlock text={reasoning} streaming={turn.streaming} />

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
                ><Icon name={copiedTurnId === String(turn.id) ? "check" : "copy"} size={15} /></button>
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
                <summary><Icon name="shield" size={13} /> How this turn was governed</summary>
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
                <a class="btn btn-ghost btn-sm" href="#/approvals">Open in Approvals</a>
              </div>
            </div>
          {/each}
          {#if approvalNotice}<p class="line-notice" role="status">{approvalNotice}</p>{/if}
        </section>
      {/if}
    </div>

    <CommandOutputPane {sessionId} {visible} bind:open={commandPaneOpen} />

    <form
      class="composer"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <div class="composer-card">
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

        <label for="build-prompt" class="sr-only">Describe the change</label>
        <div class="composer-upper">
          <textarea
            id="build-prompt"
            bind:this={promptEl}
            bind:value={promptText}
            oninput={onPromptInput}
            onselect={trackPromptSelection}
            onclick={trackPromptSelection}
            onkeyup={trackPromptSelection}
            onkeydown={onKeydown}
            onblur={() => (menuKind = "none")}
            rows="2"
            placeholder={activeRepo === null
              ? "Describe what you want built…"
              : `Describe the change in ${activeRepo.label}…`}
            title="Enter to send, Shift+Enter for a new line, Shift+Tab to change mode, / for commands, @ to mention a file"
            spellcheck="true"
            lang="en-US"
            disabled={streaming}
          ></textarea>
        </div>

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

        {#if streaming}
          <!-- B17/C13 — while a turn runs, the composer is where it is stopped
               or corrected rather than where the next question is written. -->
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
            <BuildModePicker {mode} onchange={setMode} disabled={streaming} />
            <label class="project-picker" data-selected={projectReady}>
              <Icon name="folder" size={14} />
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
              onchosen={(profileId, chosen) => void rememberSurfaceModel("build", profileId, chosen)}
              disabled={streaming}
            />
            <div class="context-wrap" bind:this={contextControlEl}>
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
              disabled={streaming || attachStore.uploading || promptText.trim() === "" || modelBlocked || !projectReady}
            >
              <Icon name={streaming ? "clock" : "send"} size={15} />
              <span class="send-label">{streaming ? "Working…" : "Send"}</span>
            </button>
          </div>
        </div>
        {#if !projectReady}
          <p class="project-required" role="status">
            Select a project to start. Build reads and writes inside one project;
            it cannot run without one.
          </p>
        {:else}
          <p class="project-boundary" role="status">
            Working in <strong>{selectedProject?.name}</strong>. Build can use this
            project's files, its memory, and account memory.
          </p>
        {/if}
        <p class="shortcut-hint">
          Shift+Tab changes mode · Enter sends · <code>/</code> for commands ·
          <code>@</code> to mention a file ·
          <button type="button" class="hint-link" onclick={() => (shortcutsOpen = !shortcutsOpen)}>
            all shortcuts
          </button>
        </p>
      </div>
    </form>
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
        projectId={projectId || projects?.active_project_id || null}
        {projects}
        onclose={() => closeRail(true)}
      />
    </div>
  {/if}
</div>

<style>
  /* BUG-22 — the print layout, matching Chat's. Save as PDF produces the
     transcript as a document: no chrome, no controls, no split turns. */
  @media print {
    :global(.sidebar), :global(.topbar), :global(.skip-link), .composer,
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
    font-size: 0.82rem;
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
    font-size: 0.74rem;
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
    font-size: 0.86rem;
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
    font-size: 0.82rem;
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
    font-size: 0.66rem;
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
    font-size: 0.78rem;
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
    font-size: 0.76rem;
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
    font-size: 0.76rem;
    font-weight: 650;
    color: var(--accent);
  }
  .governance ol ul {
    margin: 0.1rem 0 0;
    padding-left: 1rem;
    font-size: 0.78rem;
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
    font-size: 0.9rem;
    color: var(--warn);
  }
  .decisions-lead {
    margin: 0;
    font-size: 0.78rem;
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
    font-size: 0.86rem;
    font-weight: 650;
  }
  .decision-meta {
    margin: 0.2rem 0 0.5rem;
    font-size: 0.75rem;
    color: var(--text-3);
  }
  .decision-actions {
    display: flex;
    gap: 0.35rem;
    flex-wrap: wrap;
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
  .composer {
    display: grid;
    gap: 0.3rem;
  }
  /* One composer surface, defined identically in Chat and Build so the two
     conversations are the same instrument in two rooms rather than two
     instruments that resemble each other. */
  .composer-card {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-1);
    transition: border-color 120ms ease, box-shadow 120ms ease;
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
  /* Upper area: textarea on the left, model + effort on the right. Same
     layout as the Chat composer so both surfaces present model selection
     identically. */
  .composer-upper {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }
  .composer-upper textarea {
    flex: 1;
    min-width: 0;
  }
  .composer-card textarea {
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
  .composer-card textarea::placeholder {
    color: var(--text-3);
  }
  .line-notice {
    margin: 0;
    font-size: 0.75rem;
    color: var(--text-3);
    line-height: 1.5;
  }
  .standing-compact { display: none; }
  .error {
    margin: 0;
    font-size: 0.78rem;
    color: var(--danger);
  }
  .stopped-line {
    margin: 0 0 0.4rem;
    font-size: 0.82rem;
    color: var(--text-2);
  }
  .composer-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border-top: 1px solid var(--border);
    padding-top: 0.5rem;
    flex-wrap: wrap;
    position: relative;
  }
  .bar-left {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    min-width: 0;
  }
  .bar-right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    justify-content: flex-end;
    min-width: 0;
  }
  .project-required,
  .project-boundary {
    margin: 0.35rem 0 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .project-required { color: var(--danger); }
  .project-boundary strong { color: var(--text-1); }

  /* Same setting pill as the Chat composer, so the two conversation surfaces
     present their per-turn controls identically. */
  .bar-select {
    border: 1px solid var(--neutral-border);
    background: var(--surface);
    color: var(--text-2);
    font: inherit;
    font-size: 0.76rem;
    font-weight: 600;
    padding: 0.2rem 0.45rem;
    border-radius: var(--r-pill);
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
  .bar-select:focus-visible {
    outline: 2px solid var(--focus-ring);
  }
  .send {
    min-width: 6.5rem;
  }
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
  /* Same hint treatment as Chat: quiet, right-aligned, out of the way. */
  .shortcut-hint {
    margin: 0;
    text-align: right;
    font-size: 0.72rem;
    color: var(--text-3);
    line-height: 1.35;
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

  /* Compact screens preserve the transcript width and float background work as
     an isolated right-side drawer. */
  @media (max-width: 63.9rem) {
    .build,
    .build.with-rail {
      grid-template-columns: minmax(0, 1fr);
      height: var(--content-h);
      min-height: 32rem;
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
    .composer-upper {
      flex-direction: column;
    }
    .build-header { align-items: center; gap: var(--space-2); }
    .repo-button { max-width: 100%; min-height: 2.75rem; padding-inline: .6rem; }
    .header-actions { width: 100%; flex-wrap: nowrap; justify-content: flex-end; }
    .rail-label { display: none; }
    .thread :global(.empty-body) { display: none; }
    .thread :global(.empty) { padding-block: var(--space-5); }
    :global(.command-pane:not(.expanded)) { display: none; }
    .composer { flex-shrink: 0; }
    .composer-card {
      gap: .3rem;
      padding: .55rem .6rem;
      border-radius: 1rem;
      box-shadow: none;
    }
    .composer-card textarea { min-height: 2.25rem; resize: none; }
    .composer-bar { flex-wrap: nowrap; gap: .25rem; padding-top: .4rem; }
    .bar-left, .bar-right { flex-wrap: nowrap; gap: .2rem; }
    .bar-right { margin-left: auto; }
    .project-picker, .context-wrap, .shortcut-hint, :global(.composer-card .environment-badge) { display: none; }
    .standing-wide { display: none; }
    .standing-compact { display: inline; }
    .send {
      width: 2.75rem;
      height: 2.75rem;
      min-width: 2.75rem;
      padding: 0;
      border-radius: 50%;
    }
    .send-label { display: none; }
    :global(.composer-card .model-trigger),
    :global(.composer-card .approval-trigger),
    :global(.composer-card .mode-trigger) { width: 2.75rem; height: 2.75rem; padding: 0; justify-content: center; }
    :global(.composer-card .model-trigger) { min-width: 2.75rem; }
    :global(.composer-card .model-trigger > span),
    :global(.composer-card .model-trigger > svg:last-child),
    :global(.composer-card .approval-trigger > span),
    :global(.composer-card .approval-trigger > svg:last-child),
    :global(.composer-card .mode-trigger > span),
    :global(.composer-card .mode-trigger > svg:last-child) { display: none; }
  }
  @media (max-width: 30rem) {
    .composer-upper {
      flex-direction: column;
    }
  }
</style>
