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
  import Badge from "../components/Badge.svelte";
  import ApprovalModeControl from "../components/ApprovalModeControl.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import ExecutionEnvironmentBadge from "../components/ExecutionEnvironmentBadge.svelte";
  import ModelCapacityBadge from "../components/ModelCapacityBadge.svelte";
  import BuildSidePanel from "../components/BuildSidePanel.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import ContextMeterPopover from "../components/ContextMeterPopover.svelte";
  import ContextRing from "../components/ContextRing.svelte";
  import Markdown from "../components/Markdown.svelte";
  import RepoConnector from "../components/RepoConnector.svelte";
  import PlanChecklist from "../components/PlanChecklist.svelte";
  import ExportConversationDialog from "../components/ExportConversationDialog.svelte";
  import SourceChips from "../components/SourceChips.svelte";
  import SourceExcerptPanel from "../components/SourceExcerptPanel.svelte";
  import { api, ApiError, streamPrompt, streamResumeAfterApproval } from "../api";
  import {
    alreadyResumedElsewhere,
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
    BUILD_MODES,
    BUILD_WRITE_CAPABILITIES,
    buildMode,
    DEFAULT_BUILD_MODE,
    modeFromDecisionModes,
    nextBuildMode,
    repoPreamble,
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
  import TurnControl from "../components/TurnControl.svelte";
  import { createAttachmentStore, type ComposerAttachment } from "../composerAttachments.svelte";
  import { collectText, groupPhases, summarizeEvent } from "../turnPhases";
  import { thinkingSteps } from "../chatPresentation";
  import {
    citedSourceIds,
    renderableCitations,
    sentenceAround,
    sourcesForTurn,
  } from "../citations";
  import { chatProfiles, refreshModels } from "../models.svelte";

  let {
    projects = null,
    onProjectsChanged,
  }: { projects?: ProjectsList | null; onProjectsChanged?: () => void } = $props();

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
  // `mode` is what the composer shows; `appliedMode` is what the runtime last
  // confirmed. They differ only while a change is in flight or after one was
  // refused, so the composer never claims a posture the server did not accept.
  let mode = $state<BuildMode>(DEFAULT_BUILD_MODE);
  let appliedMode = $state<BuildMode | null>(null);
  // How much is known about the live posture. Kept separate from `appliedMode`
  // so the page stays quiet while the first read is in flight instead of
  // flashing "permissions are set individually" at everyone on load.
  let posture = $state<"loading" | "matched" | "mixed" | "unreadable">("loading");
  let modeBusy = $state(false);
  let modeError = $state<string | null>(null);
  let modeTooltipOpen = $state(false);
  const modeSpec = $derived(buildMode(mode));
  const modeTooltip =
    "Plan produces a structured plan with no file changes. Edit applies precise, context-anchored changes. Auto plans, then executes eligible changes with background monitoring.";

  // ── Repository ───────────────────────────────────────────────────────
  let repos = $state<CodeReposView | null>(null);
  let reposOpen = $state(false);
  const activeRepo = $derived<CodeRepo | null>(
    repos?.repos.find((repo) => repo.repo_id === repos?.selected_repo_id) ?? null,
  );

  // ── Side rail ────────────────────────────────────────────────────────
  let railOpen = $state(false);

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

  // ── Project assignment ───────────────────────────────────────────────
  // A chat can be filed into a project before it exists as a session. The
  // choice is remembered and applied as soon as the first turn creates one, so
  // "file this under X" never silently does nothing.
  let projectId = $state("");
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
  const reasoningEfforts = $derived(
    activeProfile?.supports_reasoning === true && activeProfile.supports_reasoning_effort === true
      ? (activeProfile.reasoning_effort_values ?? [])
      : [],
  );

  onMount(() => {
    void loadRepos();
    void refreshModels();
    void syncModeFromRuntime();
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
    return () => window.removeEventListener("raiker:build-compose", onCompose);
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
   * Read the live decision modes and show the mode they actually represent. If
   * the capabilities disagree (someone set them individually in Permissions),
   * nothing is claimed — the composer says the posture is mixed.
   */
  async function syncModeFromRuntime() {
    try {
      const gates = await api.capabilityGates();
      const observed: Record<string, string> = {};
      for (const gate of gates) {
        if ((BUILD_WRITE_CAPABILITIES as readonly string[]).includes(gate.capability)) {
          observed[gate.capability] = gate.decision_mode;
        }
      }
      const detected = modeFromDecisionModes(observed);
      appliedMode = detected;
      posture = detected === null ? "mixed" : "matched";
      if (detected !== null) mode = detected;
    } catch {
      appliedMode = null;
      posture = "unreadable";
    }
  }

  async function setMode(next: BuildMode) {
    if (modeBusy || next === mode) return;
    const previous = mode;
    mode = next;
    modeBusy = true;
    modeError = null;
    const spec = buildMode(next);
    try {
      for (const capability of BUILD_WRITE_CAPABILITIES) {
        await api.setCapabilityDecisionMode(
          capability,
          spec.decisionMode,
          `Build workspace mode: ${spec.label}`,
        );
      }
      appliedMode = next;
    } catch (error) {
      // Fail visibly rather than showing a posture the runtime did not accept.
      mode = previous;
      modeError =
        error instanceof ApiError && error.status === 403
          ? "Changing the mode needs the runtime gate-manager role. The previous mode is still in effect."
          : "The runtime did not accept that mode. The previous mode is still in effect.";
      await syncModeFromRuntime();
    } finally {
      modeBusy = false;
    }
  }

  function onKeydown(event: KeyboardEvent) {
    // Shift+Tab cycles Plan → Edit → Auto without leaving the prompt.
    if (event.key === "Tab" && event.shiftKey) {
      event.preventDefault();
      void setMode(nextBuildMode(mode));
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
    const text = promptText.trim();
    if (text === "" || streaming || attachStore.uploading) return;
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
    attachStore.clear();
    streaming = true;
    stopping = false;
    void scrollToEnd();
    try {
      await streamPrompt(
        {
          text: sent,
          session_id: sessionId ?? undefined,
          model_profile: modelProfile || undefined,
          model: model || undefined,
          ...(reasoningEfforts.includes(reasoningEffort) ? { reasoning_effort: reasoningEffort } : {}),
          planning_mode: buildMode(sentMode).planningMode ?? undefined,
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

  /** Continue the turn this approval parked, streaming into its own transcript row. */
  async function resumeTurn(approvalId: string, outcomeStatus = "") {
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
      const code = error instanceof ApiError ? error.reasonCode : null;
      if (alreadyResumedElsewhere(code)) {
        // BUG-24 — losing the race is a success: the turn did continue, in the
        // tab that claimed it first. Saying "error" here would be a lie.
        turn.resumeState = "elsewhere";
        turn.resumeNote = "Continued in another tab. Reload to see the result here.";
      } else {
        turn.resumeState = "waiting";
        turn.resumeNote = null;
        turn.error =
          error instanceof ApiError
            ? `The turn could not continue (${code ?? error.status}).`
            : "Could not reach the local runtime to continue the turn.";
      }
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
    turns = [];
    sessionId = null;
    approvals = [];
    plan = null;
    promptEl?.focus();
  }

  // ── Projects ─────────────────────────────────────────────────────────
  async function onProjectPicked(value: string) {
    projectId = value;
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

<div class="build" class:with-rail={railOpen}>
  <div class="main">
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
          onclick={() => (railOpen = !railOpen)}
          aria-expanded={railOpen}
          aria-controls="build-rail"
        >
          <Icon name="panel" size={15} />
          {railOpen ? "Hide background work" : "Background work"}
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
          body={activeRepo === null
            ? "Connect a repository to give Raiker something to work in, or just describe what you want and start from nothing."
            : `Working in ${activeRepo.label}. Describe the change, and pick how much Raiker may do on its own.`}
          serif={true}
        />
      {/if}

      {#each turns as turn (turn.id)}
        {@const answer = answerText(turn)}
        {@const thinking = thinkingSteps(turn.events)}
        {@const turnSourceList = sourcesForTurn(turnSources, turn.response?.turn_id)}
        <article class="turn">
          <div class="user-message">
            <div class="from-you">
              <span class="mode-tag">{buildMode(turn.mode).label}</span>
              <p class="bubble-text">{turn.prompt}</p>
            </div>
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
            {#if turn.streaming}
              <p class="working" role="status">
                <span class="pulse" aria-hidden="true"></span>
                {answer === "" ? "Reading and planning…" : "Writing…"}
              </p>
              {#if thinking.length > 0}
                <details class="thinking">
                  <summary>See what Raiker is thinking</summary>
                  {#each thinking as step (step)}<p>{step}</p>{/each}
                </details>
              {/if}
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
                <button
                  type="button"
                  class="copy-message"
                  class:copied={copiedTurnId === String(turn.id)}
                  onclick={() => void copyAnswer(turn)}
                  aria-label={copiedTurnId === String(turn.id) ? "Response copied" : "Copy response"}
                  title={copiedTurnId === String(turn.id) ? "Response copied" : "Copy response"}
                ><Icon name={copiedTurnId === String(turn.id) ? "check" : "copy"} size={15} /></button>
              {/if}
            {:else if !turn.streaming && turn.error === null && turn.response !== null}
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

    <form
      class="composer"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <div class="composer-card">
        <ComposerChips store={attachStore} disabled={streaming} />
        <SkillLinkNotice text={promptText} />
        <label for="build-prompt" class="sr-only">Describe the change</label>
        <div class="composer-upper">
          <textarea
            id="build-prompt"
            bind:this={promptEl}
            bind:value={promptText}
            onkeydown={onKeydown}
            rows="2"
            placeholder={activeRepo === null
              ? "Describe what you want built…"
              : `Describe the change in ${activeRepo.label}…`}
            title="Enter to send, Shift+Enter for a new line, Shift+Tab to change mode"
            spellcheck="true"
            lang="en-US"
            disabled={streaming}
          ></textarea>
          <div class="upper-controls">
            <ModelPicker bind:profileId={modelProfile} bind:model {profiles} {selectedProfile} disabled={streaming} />
            <ExecutionEnvironmentBadge />
            <ModelCapacityBadge tokens={(profiles.find((profile) => profile.profile_id === modelProfile && (!model || profile.model === model)) ?? selectedProfile)?.context_window_tokens} source={(profiles.find((profile) => profile.profile_id === modelProfile && (!model || profile.model === model)) ?? selectedProfile)?.context_window_source} />
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

        {#if modeError !== null}<p class="error" role="alert">{modeError}</p>{/if}
        {#if modeError === null}
          {#if appliedMode !== null && appliedMode !== mode}
            <p class="line-notice" role="status">Applying {modeSpec.label}…</p>
          {:else if posture === "mixed"}
            <p class="line-notice">
              Write permissions are set individually right now, so this mode describes what will be applied when you
              pick it — not what is in effect.
            </p>
          {:else if posture === "unreadable"}
            <p class="line-notice">
              Raiker could not read the current write permissions, so this mode describes what will be applied when you
              pick it — not what is in effect.
            </p>
          {/if}
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
            <div class="mode-picker" role="group" aria-label="How much Raiker may do">
              {#each BUILD_MODES as option (option.id)}
                <button
                  type="button"
                  class="mode-option"
                  aria-pressed={mode === option.id}
                  disabled={modeBusy || streaming}
                  title={option.summary}
                  onclick={() => setMode(option.id)}
                >
                  {option.label}
                </button>
              {/each}
            </div>
            <button
              type="button"
              class="mode-help"
              aria-label="About Plan, Edit, and Auto modes"
              aria-describedby="build-mode-tooltip"
              onmouseenter={() => (modeTooltipOpen = true)}
              onmouseleave={() => (modeTooltipOpen = false)}
              onfocus={() => (modeTooltipOpen = true)}
              onblur={() => (modeTooltipOpen = false)}
            >
              <Icon name="info" size={14} />
            </button>
            {#if modeTooltipOpen}
              <span id="build-mode-tooltip" class="mode-tooltip" role="tooltip">{modeTooltip}</span>
            {/if}
            {#if projects && projects.projects.length > 0}
              <label class="project-picker">
                <Icon name="folder" size={14} />
                <span class="sr-only">Project for this chat</span>
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
              disabled={streaming || attachStore.uploading || promptText.trim() === ""}
            >
              <Icon name={streaming ? "clock" : "send"} size={15} />
              {streaming ? "Working…" : "Send"}
            </button>
          </div>
        </div>
        <p class="shortcut-hint">Shift+Tab changes mode · Enter sends · Shift+Enter adds a line</p>
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
    <div id="build-rail" class="rail-slot">
      <BuildSidePanel
        projectId={projectId || projects?.active_project_id || null}
        {projects}
        onclose={() => (railOpen = false)}
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
  .thinking {
    font-size: 0.78rem;
    color: var(--text-2);
  }
  .thinking summary {
    cursor: pointer;
    color: var(--text-3);
  }
  .thinking p {
    margin: 0.3rem 0 0;
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
  .upper-controls {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.3rem;
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
  .mode-help {
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
    cursor: help;
  }
  .mode-help:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
  }
  .mode-tooltip {
    position: absolute;
    z-index: 2;
    max-width: min(22rem, calc(100vw - 3rem));
    margin-top: 3.4rem;
    padding: .45rem .6rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-2);
    color: var(--text-2);
    font-size: .76rem;
    line-height: 1.45;
  }
  .line-notice {
    margin: 0;
    font-size: 0.75rem;
    color: var(--text-3);
    line-height: 1.5;
  }
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
  .mode-picker {
    display: inline-flex;
    background: var(--sunken);
    border-radius: var(--r-pill);
    padding: 0.15rem;
    gap: 0.15rem;
  }
  .mode-option {
    border: none;
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: 0.78rem;
    font-weight: 650;
    padding: 0.25rem 0.75rem;
    border-radius: var(--r-pill);
    cursor: pointer;
  }
  .mode-option[aria-pressed="true"] {
    background: var(--surface);
    color: var(--accent);
    box-shadow: var(--shadow-1);
  }
  .mode-option:disabled {
    opacity: 0.6;
    cursor: default;
  }
  .mode-option:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
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

  /* Below the split-view breakpoint the rail stacks under the composer. Pinning
     the workspace to the viewport there would trap the transcript in a short
     inner scroller with the rail hidden below it, so the page scrolls normally
     instead and each section takes the room it needs. */
  @media (max-width: 63.9rem) {
    .build,
    .build.with-rail {
      grid-template-columns: minmax(0, 1fr);
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
</style>
