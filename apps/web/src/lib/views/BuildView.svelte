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
  import BuildSidePanel from "../components/BuildSidePanel.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import RepoConnector from "../components/RepoConnector.svelte";
  import { api, ApiError, streamPrompt } from "../api";
  import type {
    AgentResponse,
    ApprovalView,
    CodeRepo,
    CodeReposView,
    ModelProfile,
    ProjectsList,
    StreamEvent,
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
  import { humanize, providerName, relativeTime } from "../format";
  import { approvalBadge } from "../statusMaps";
  import { collectText, groupPhases, summarizeEvent } from "../turnPhases";
  import { thinkingSteps } from "../chatPresentation";

  let {
    projects = null,
    onProjectsChanged,
  }: { projects?: ProjectsList | null; onProjectsChanged?: () => void } = $props();

  interface BuildTurn {
    id: number;
    prompt: string;
    mode: BuildMode;
    events: StreamEvent[];
    response: AgentResponse | null;
    streaming: boolean;
    error: string | null;
  }

  let promptText = $state("");
  let turns = $state<BuildTurn[]>([]);
  let streaming = $state(false);
  let sessionId = $state<string | null>(null);
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
  const modeSpec = $derived(buildMode(mode));

  // ── Repository ───────────────────────────────────────────────────────
  let repos = $state<CodeReposView | null>(null);
  let reposOpen = $state(false);
  const activeRepo = $derived<CodeRepo | null>(
    repos?.repos.find((repo) => repo.repo_id === repos?.selected_repo_id) ?? null,
  );

  // ── Side rail ────────────────────────────────────────────────────────
  let railOpen = $state(true);

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

  let profiles = $state<ModelProfile[]>([]);
  let modelProfile = $state("");
  const selectedProfile = $derived(profiles.find((profile) => profile.selected) ?? null);

  onMount(() => {
    void loadRepos();
    void loadProfiles();
    void syncModeFromRuntime();
  });

  async function loadRepos() {
    try {
      repos = await api.codeRepos();
    } catch {
      // The workspace still works without a repository; the panel says so.
      repos = null;
    }
  }

  async function loadProfiles() {
    try {
      const models = await api.models();
      profiles = models.chat_profiles ?? models.profiles.filter((profile) => profile.configured);
    } catch {
      // Prompting still works with the server's own default profile.
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

  async function submit() {
    const text = promptText.trim();
    if (text === "" || streaming) return;
    const preamble = repoPreamble(activeRepo);
    // The preamble is prepended here, not server-side, so the transcript shows
    // the exact text the turn received.
    const sent = preamble === "" ? text : `${preamble}\n\n${text}`;
    const sentMode = mode;
    turns = [
      ...turns,
      { id: nextId++, prompt: sent, mode: sentMode, events: [], response: null, streaming: true, error: null },
    ];
    const turn = turns[turns.length - 1];
    promptText = "";
    streaming = true;
    void scrollToEnd();
    try {
      await streamPrompt(
        {
          text: sent,
          session_id: sessionId ?? undefined,
          model_profile: modelProfile || undefined,
          planning_mode: buildMode(sentMode).planningMode ?? undefined,
          // A local repository rides the turn as a real workspace-path
          // attachment, resolved and bounded server-side like any other.
          attachments:
            activeRepo?.kind === "local" && activeRepo.local_subpath
              ? [{ type: "path" as const, path: activeRepo.local_subpath }]
              : undefined,
        },
        (event) => {
          if (event.kind === "final" && event.response !== null) {
            turn.response = event.response;
            sessionId = event.response.session_id;
            window.dispatchEvent(new Event("raiker:chats-changed"));
            void applyPendingProject();
            void loadApprovals();
          } else {
            turn.events = [...turn.events, event];
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
      void scrollToEnd();
    }
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
      await api.resolveApproval(approval.approval_id, {
        approve,
        reason: approve ? "accepted in the Build workspace" : "rejected in the Build workspace",
      });
      approvalNotice = approve
        ? "Decision recorded. Raiker re-governs the action before anything runs."
        : "Rejection recorded.";
      await loadApprovals();
    } catch (error) {
      approvalNotice =
        error instanceof ApiError
          ? `The decision was not accepted (${error.reasonCode ?? error.status}).`
          : "The decision could not be recorded.";
    } finally {
      approvalBusy = null;
    }
  }

  function answerText(turn: BuildTurn): string {
    const streamed = collectText(turn.events);
    return streamed.trim() !== "" ? streamed : (turn.response?.message ?? "");
  }
</script>

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
        {#if projects && projects.projects.length > 0}
          <label class="project-picker">
            <span class="sr-only">Project for this chat</span>
            <select
              class="bar-select"
              value={projectId}
              aria-label="Project for this chat"
              onchange={(event) => void onProjectPicked((event.currentTarget as HTMLSelectElement).value)}
            >
              <option value="">No project</option>
              {#each projects.projects as project (project.project_id)}
                <option value={project.project_id}>{project.name}</option>
              {/each}
            </select>
          </label>
        {/if}
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
        <article class="turn">
          <div class="from-you">
            <span class="mode-tag">{buildMode(turn.mode).label}</span>
            <p class="bubble-text">{turn.prompt}</p>
          </div>

          <div class="from-raiker">
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

            {#if answer !== ""}
              <div class="answer"><p class="bubble-text">{answer}</p></div>
            {:else if !turn.streaming && turn.error === null && turn.response !== null}
              <div class="answer"><p class="bubble-text muted">(No answer text was returned.)</p></div>
            {/if}

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
            Accepting records your decision. Raiker re-governs the action before anything runs — a recorded decision is
            never treated as permission it already had.
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
        <label for="build-prompt" class="sr-only">Describe the change</label>
        <textarea
          id="build-prompt"
          bind:this={promptEl}
          bind:value={promptText}
          onkeydown={onKeydown}
          rows="3"
          placeholder={activeRepo === null
            ? "Describe what you want built…"
            : `Describe the change in ${activeRepo.label}…`}
          title="Enter to send, Shift+Enter for a new line, Shift+Tab to change mode"
          disabled={streaming}
        ></textarea>

        <p class="mode-detail">{modeSpec.detail}</p>
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

        <div class="composer-bar">
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

          <div class="bar-right">
            <select
              class="bar-select"
              bind:value={modelProfile}
              disabled={streaming}
              aria-label="Model for this turn"
            >
              <option value="">
                {selectedProfile !== null
                  ? `${providerName(selectedProfile.provider)} · ${selectedProfile.model}`
                  : "Selected model"}
              </option>
              {#each profiles as profile (profile.profile_id)}
                <option value={profile.profile_id}>
                  {providerName(profile.provider)} · {profile.model}
                </option>
              {/each}
            </select>

            <button
              type="submit"
              class="btn btn-primary send"
              disabled={streaming || promptText.trim() === ""}
            >
              <Icon name={streaming ? "clock" : "send"} size={15} />
              {streaming ? "Working…" : "Send"}
            </button>
          </div>
        </div>
      </div>
      <p class="shortcut-hint">Shift+Tab changes mode · Enter sends · Shift+Enter adds a line</p>
    </form>
  </div>

  {#if railOpen}
    <div id="build-rail" class="rail-slot">
      <BuildSidePanel
        projectId={projects?.active_project_id ?? null}
        {projects}
        onclose={() => (railOpen = false)}
      />
    </div>
  {/if}
</div>

<style>
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
  .project-picker {
    display: inline-flex;
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
  .from-you {
    align-self: flex-end;
    max-width: min(80%, 44rem);
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

  .composer {
    display: grid;
    gap: 0.3rem;
  }
  .composer-card {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-1);
    padding: 0.75rem 0.85rem 0.6rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .composer-card:focus-within {
    border-color: var(--accent-border);
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
    min-height: 3.2rem;
  }
  .composer-card textarea::placeholder {
    color: var(--text-3);
  }
  .mode-detail {
    margin: 0;
    font-size: 0.76rem;
    color: var(--text-2);
    line-height: 1.5;
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
  .composer-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border-top: 1px solid var(--border);
    padding-top: 0.5rem;
    flex-wrap: wrap;
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
  }
  .bar-select {
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.25rem 0.4rem;
    border-radius: var(--r-md);
    max-width: 15rem;
  }
  .bar-select:hover:not(:disabled) {
    background: var(--neutral-soft);
  }
  .bar-select:focus-visible {
    outline: 2px solid var(--focus-ring);
  }
  .send {
    min-width: 6.5rem;
  }
  .shortcut-hint {
    margin: 0;
    text-align: right;
    font-size: 0.72rem;
    color: var(--text-3);
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
  }
</style>
