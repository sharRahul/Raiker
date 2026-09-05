<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import DiffView from "../components/DiffView.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import IdentityChip from "../components/IdentityChip.svelte";
  import PageState from "../components/PageState.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, auth, getToken, setToken, ApiError } from "../api";
  import { alreadyResumedElsewhere, publishApprovalResolved } from "../approvalResume";
  import type { ApprovalDetailView, ApprovalView, OwnerQuestion } from "../apiTypes";
  import { approvalBadge } from "../statusMaps";
  import { capabilityLabel } from "../capabilityModel";
  import { formatTimestamp, humanize, relativeTime } from "../format";
  import { explainReasonCode } from "../reasonCodes";

  let { sessionId = null }: { sessionId?: string | null } = $props();

  // `executed` is the terminal status of an approval the execution relay
  // actually carried out, so it needs its own tab — otherwise the file writes
  // the owner approved would vanish from every filter.
  const FILTERS = ["pending", "approved", "executed", "denied"] as const;
  const RISK_RANK: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
  // BUG-271 — a governed refusal of an edited patch, in the owner's language.
  // A bare reason code as the whole answer is the defect FIXED-01 removed from
  // Models; a review surface must not put one back.
  const EDIT_REFUSALS: Record<string, string> = {
    replacement_patch_empty: "An empty diff is not a change. Write the version you want, or Deny.",
    replacement_patch_unreadable:
      "That is not a unified diff Raiker can read. Each file needs its --- and +++ header.",
    replacement_unchanged: "That is the change as proposed. Approve it, or edit a line first.",
    replacement_widens_targets:
      "That version touches a file this change did not. Ask for it as its own change instead.",
    action_is_not_a_patch: "Only a proposed patch can be edited as text.",
    approval_already_resolved: "This change has already been decided.",
    critical_approval_requires_lifecycle:
      "A critical action keeps the step-up lifecycle and cannot be replaced here.",
  };

  let filter = $state<(typeof FILTERS)[number]>("pending");
  let sort = $state<"risk" | "newest">("risk");
  let approvals = $state<ApprovalView[] | null>(null);
  let loadError = $state<string | null>(null);

  let selected = $state<ApprovalDetailView | null>(null);
  let detailError = $state<string | null>(null);
  let decisionReason = $state("");
  /**
   * B14 — the hunks this reviewer has accepted, or null while they have not
   * narrowed anything.
   *
   * `undefined` and "every hunk" are deliberately different states. `undefined`
   * means the decision is the one approvals have always carried — all of it —
   * and the request omits the field entirely, so no scope is recorded. A list
   * means the reviewer touched a checkbox, even if they re-selected everything.
   */
  let hunkSelection = $state<string[] | undefined>(undefined);
  /**
   * BUG-271 — the reviewer's own version of the proposed patch, while they are
   * writing it. `null` means the editor is closed, which is its resting state:
   * correcting a change is the rarer thing to want, and a textarea holding a
   * diff would otherwise sit under every patch approval.
   */
  let editedPatch = $state<string | null>(null);
  let editError = $state<string | null>(null);
  let busy = $state(false);
  // BUG-62 — an executed action whose result is a row rather than a file carries
  // a receipt, so the notice can point at the thing that now exists.
  let notice = $state<{
    kind: "ok" | "error";
    text: string;
    link?: { href: string; label: string };
  } | null>(null);
  let criticalDecision = $state<"approve" | "deny" | null>(null);
  let criticalReason = $state("");
  let criticalPassword = $state("");
  let criticalMfaCode = $state("");
  let criticalError = $state<string | null>(null);
  let criticalBusy = $state(false);
  // B2 — a decision closes the tool call the model was waiting on, so the turn
  // it parked can pick up from here. Offered rather than automatic: the inbox is
  // not the transcript, and continuing is the owner's call.
  let resumable = $state<{
    approval_id: string;
    session_id: string;
    // ADD-02 — how many calls of the same batch are still queued behind this
    // decision, so the banner can say what continuing will actually do.
    queued_calls: number;
  } | null>(null);
  let resumeBusy = $state(false);

  const orderedApprovals = $derived.by(() => {
    const requestedAt = (approval: ApprovalView) => Date.parse(approval.created_at) || 0;
    const scoped = sessionId
      ? (approvals ?? []).filter((approval) => approval.session_id === sessionId)
      : (approvals ?? []);
    return [...scoped].sort((left, right) => {
      const newestFirst = requestedAt(right) - requestedAt(left);
      if (sort === "newest") return newestFirst || left.approval_id.localeCompare(right.approval_id);
      return (
        (RISK_RANK[right.risk_level] ?? 0) - (RISK_RANK[left.risk_level] ?? 0) ||
        newestFirst ||
        left.approval_id.localeCompare(right.approval_id)
      );
    });
  });

  async function load() {
    loadError = null;
    try {
      approvals = await api.approvals(filter);
    } catch (e) {
      approvals = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function openDetail(id: string) {
    detailError = null;
    decisionReason = "";
    notice = null;
    // B14 — a narrowing belongs to the change it was made on. Carrying one
    // across to the next approval would apply hunk positions from one diff to a
    // completely different one.
    hunkSelection = undefined;
    editedPatch = null;
    editError = null;
    try {
      selected = await api.approval(id);
    } catch (e) {
      selected = null;
      detailError = e instanceof ApiError ? `Could not load approval (${e.status}).` : "Could not load approval.";
    }
  }

  // ADD-22 — a question, not an approval.
  //
  // Rendered from its own branch and answered through its own route, because
  // the one thing this surface must never do is let the two blur: an owner who
  // learns that some entries in the approval queue are harmless multiple-choice
  // questions is an owner who has been taught to click through the queue. The
  // model wrote this text, so it is rendered as data — Svelte escapes it — and
  // the server refuses any label it did not offer.
  const OWNER_QUESTION_TOOL = "ask_owner_question";
  const isQuestion = $derived(selected?.approval.tool_name === OWNER_QUESTION_TOOL);
  const questions = $derived<OwnerQuestion[]>(
    isQuestion && Array.isArray((selected?.arguments as Record<string, unknown>)?.questions)
      ? (((selected?.arguments as Record<string, unknown>).questions as OwnerQuestion[]) ?? [])
      : [],
  );
  let picked = $state<Record<string, string[]>>({});
  let ownWords = $state("");

  function toggle(question: OwnerQuestion, label: string) {
    const current = picked[question.question] ?? [];
    if (question.multiSelect) {
      picked = {
        ...picked,
        [question.question]: current.includes(label)
          ? current.filter((entry) => entry !== label)
          : [...current, label],
      };
    } else {
      picked = { ...picked, [question.question]: [label] };
    }
  }

  const everyQuestionAnswered = $derived(
    questions.length > 0 &&
      questions.every((question) => (picked[question.question] ?? []).length > 0),
  );

  async function answer(useOwnWords: boolean) {
    if (selected === null || busy) return;
    busy = true;
    notice = null;
    try {
      const body = useOwnWords
        ? { response: ownWords.trim() }
        : {
            answers: Object.fromEntries(
              Object.entries(picked)
                .filter(([, labels]) => labels.length > 0)
                .map(([question, labels]) => [question, labels.length > 1 ? labels : labels[0]]),
            ),
          };
      const result = await api.answerOwnerQuestion(selected.approval.approval_id, body);
      notice = {
        kind: "ok",
        text: "Answer sent. The turn continues with what you chose — nothing was approved.",
      };
      resumable =
        result.resume?.resumable && result.resume.session_id
          ? {
              approval_id: result.approval_id,
              session_id: result.resume.session_id,
              queued_calls: 0,
            }
          : null;
      publishApprovalResolved({
        approvalId: result.approval_id,
        sessionId: result.resume?.session_id ?? selected.approval.session_id ?? null,
        turnId: result.resume?.turn_id ?? null,
        approved: true,
      });
      picked = {};
      ownWords = "";
      selected = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      notice = {
        kind: "error",
        text: explained ? `${explained.plain} ${explained.remediation ?? ""}` : "That answer was not accepted.",
      };
    } finally {
      busy = false;
    }
  }

  /**
   * BUG-271 — propose the reviewer's own version instead of this one.
   *
   * Deliberately not an amendment. The server denies the proposal in front of
   * the owner and raises theirs as a **new** approval with its own preview and
   * its own immutable-intent hash; nothing runs until they approve that. The
   * copy says so, because a control that looked like an edit to the decision in
   * front of them would be a promise the boundary cannot keep.
   */
  async function proposeEdit() {
    if (selected === null || busy || editedPatch === null) return;
    busy = true;
    editError = null;
    notice = null;
    try {
      const result = await api.replaceApproval(selected.approval.approval_id, {
        patch: editedPatch,
        reason: decisionReason.trim() || "Replaced by the reviewer's own edit.",
      });
      editedPatch = null;
      await load();
      // Open the replacement first: `openDetail` clears the notice as part of
      // arriving on an approval, so setting it before would show the sentence
      // for as long as one fetch takes and then silently remove it.
      await openDetail(result.replacement_approval_id);
      notice = {
        kind: "ok",
        text: "The proposed change was denied and yours is waiting for your approval. Nothing has run.",
      };
    } catch (e) {
      editError =
        e instanceof ApiError
          ? EDIT_REFUSALS[e.reasonCode ?? ""] ?? `That version was not accepted (${e.status}).`
          : "That version was not accepted.";
    } finally {
      busy = false;
    }
  }

  async function resolve(approve: boolean) {
    if (selected === null || busy) return;
    busy = true;
    notice = null;
    try {
      const result = await api.resolveApproval(selected.approval.approval_id, {
        approve,
        reason: decisionReason.trim() || (approve ? "approved via web UI" : "denied via web UI"),
        // B14 — sent only when the reviewer actually narrowed the change.
        // Accepting all of it is the same decision it has always been, and
        // saying so with an explicit list would record a scope on every
        // approval for no reason.
        ...(approve && hunkSelection !== undefined ? { accepted_hunks: hunkSelection } : {}),
      });
      const receipt = result.execution?.receipt;
      const checkpoint = result.execution?.checkpoint_capture;
      notice = {
        kind: "ok",
        text: result.executes_action
          ? result.execution?.path
            ? checkpoint && !checkpoint.ok
              ? `Executed once — wrote ${result.execution.path}. Change completed — not reversible. ${checkpoint.reason_code}. ${checkpoint.remediation}`
              : `Executed once — wrote ${result.execution.path}. The previous contents were checkpointed.`
            : receipt
              ? `Executed once — “${receipt.title}” now exists.`
              : result.execution?.summary
                ? `Executed once — ${result.execution.summary}`
                : `Executed once: ${result.status}.`
          : `Recorded: ${result.status}. The action was NOT executed (metadata-only).`,
        ...(result.executes_action && receipt
          ? { link: { href: receipt.href, label: receipt.label } }
          : {}),
      };
      resumable =
        result.resume?.resumable && result.resume.session_id
          ? {
              approval_id: result.approval_id,
              session_id: result.resume.session_id,
              queued_calls: result.resume.queued_calls ?? 0,
            }
          : null;
      // BUG-24 — the inbox is where most decisions are actually made, so this is
      // the broadcast that matters most: a Chat or Build tab showing the turn
      // this approval parked picks it up immediately, without a reload. A hint
      // only — the receiving tab re-checks with the server before continuing.
      publishApprovalResolved({
        approvalId: result.approval_id,
        sessionId: result.resume?.session_id ?? selected.approval.session_id ?? null,
        turnId: result.resume?.turn_id ?? null,
        approved: approve,
      });
      selected = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      notice = {
        kind: "error",
        text: explained ? `${explained.plain} ${explained.remediation ?? ""}` : "The decision was rejected.",
      };
    } finally {
      busy = false;
    }
  }

  async function resumeTurn() {
    if (resumable === null || resumeBusy) return;
    resumeBusy = true;
    try {
      const response = await api.resumeAfterApproval(resumable.approval_id);
      // ADD-02 — a continuation can stop on the *next* call of the same batch.
      // Saying so, and reloading the inbox so that decision is actually here,
      // is what makes walking a batch a single flow rather than a hunt for a
      // row that appeared while the owner was reading a success message.
      const next = response.status === "needs_approval" ? response.approval : null;
      notice = {
        kind: "ok",
        text: next
          ? `The agent continued the turn and stopped on the next call in the batch: ${next.message}`
          : `The agent continued the turn: ${response.message}`,
      };
      resumable = null;
      selected = null;
      await load();
    } catch (e) {
      // BUG-24 / ADD-02 — losing the race to continue is a *success*: the turn
      // ran, just not from this button. Walking a batch makes that race routine
      // rather than rare, so reporting it as an error would mean the owner sees
      // a red failure for every decision that the conversation itself picked up.
      if (e instanceof ApiError && alreadyResumedElsewhere(e.reasonCode)) {
        notice = { kind: "ok", text: "The turn was continued in another tab." };
        resumable = null;
        selected = null;
        await load();
        return;
      }
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      notice = {
        kind: "error",
        text: explained
          ? `${explained.plain} ${explained.remediation ?? ""}`
          : "The turn could not be continued.",
      };
    } finally {
      resumeBusy = false;
    }
  }

  function beginCriticalDecision(decision: "approve" | "deny") {
    criticalDecision = decision;
    criticalReason = "";
    criticalPassword = "";
    criticalMfaCode = "";
    criticalError = null;
  }

  async function resolveCritical() {
    if (selected === null || criticalDecision === null || criticalBusy || criticalReason.trim() === "") return;
    if (criticalPassword.trim() === "" && criticalMfaCode.trim() === "") return;
    criticalBusy = true;
    criticalError = null;
    const controlToken = getToken();
    try {
      const { token: elevatedToken } = await auth.elevate(
        criticalPassword.trim() || undefined,
        criticalMfaCode.trim() || undefined,
      );
      setToken(elevatedToken);
      const result = await api.resolveCriticalApproval(selected.approval.approval_id, {
        approve: criticalDecision === "approve",
        reason: criticalReason.trim(),
      });
      notice = {
        kind: "ok",
        text: result.executes_action
          ? "Critical action executed through the governed approval lifecycle."
          : result.status === "denied"
            ? "Critical action was denied."
            : `Critical approval result: ${result.message}.`,
      };
      selected = null;
      criticalDecision = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      criticalError = explained
        ? `${explained.plain} ${explained.remediation ?? ""}`
        : "Step-up verification was rejected.";
    } finally {
      setToken(controlToken);
      criticalBusy = false;
    }
  }

  function setFilter(value: (typeof FILTERS)[number]) {
    filter = value;
    selected = null;
    void load();
  }

  onMount(load);
</script>

<div class="head-row">
  <GuideLink route="approvals" />
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh approvals">
    <Icon name="refresh" size="sm" />
    Refresh
  </button>
</div>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">
    {notice.text}
    {#if notice.link}
      <a href={notice.link.href}>{notice.link.label}</a>
    {/if}
  </p>
{/if}

{#if resumable !== null}
  <div class="notice notice-ok resume-row">
    <span>
      A turn was waiting on this decision. Continuing picks it up where it stopped, so the agent keeps
      what it had already worked out.
      {#if resumable.queued_calls > 0}
        {resumable.queued_calls === 1
          ? "1 more call from the same batch is queued behind it and will need its own decision."
          : `${resumable.queued_calls} more calls from the same batch are queued behind it, each needing its own decision.`}
      {/if}
    </span>
    <span class="resume-actions">
      <button type="button" class="btn btn-primary btn-sm" onclick={resumeTurn} disabled={resumeBusy}>
        {resumeBusy ? "Continuing…" : "Continue the turn"}
      </button>
      <a class="btn btn-ghost btn-sm" href={`#/sessions?session=${encodeURIComponent(resumable.session_id)}`}>
        Open the session
      </a>
    </span>
  </div>
{/if}

<div class="queue-controls">
  <div class="filters" role="tablist" aria-label="Approval status filter">
    {#each FILTERS as f (f)}
      <button
        type="button"
        class="filter-btn"
        class:active={filter === f}
        role="tab"
        aria-selected={filter === f}
        onclick={() => setFilter(f)}
      >
        {f}
      </button>
    {/each}
  </div>
  <label class="sort-control">
    <span class="sr-only">Sort approvals</span>
    <select class="select" aria-label="Sort approvals" bind:value={sort}>
      <option value="risk">Highest risk first</option>
      <option value="newest">Newest first</option>
    </select>
  </label>
</div>

{#if loadError}
  <PageState state="error" title="Couldn't load approvals" detail={loadError} />
{:else if approvals === null}
  <PageState state="loading" title="Loading approvals…" />
{:else if orderedApprovals.length === 0}
  <div class="card">
    <EmptyState
      icon="approvals"
      title={sessionId ? "No approvals for this session" : filter === "pending" ? "Nothing waiting on you" : `No ${filter} approvals`}
      body={filter === "pending"
        ? "When the agent proposes a gated action, it will appear here for your decision."
        : undefined}
    />
  </div>
{:else}
  <div class="card list-card">
    <table class="table">
      <thead>
        <tr>
          <th>Action</th>
          <th>Proposed by</th>
          <th>Capability</th>
          <th>Risk</th>
          <th>Status</th>
          <th>Requested</th>
          <th><span class="sr-only">Open</span></th>
        </tr>
      </thead>
      <tbody>
        {#each orderedApprovals as a (a.approval_id)}
          <tr>
            <td>
              {humanize(a.tool_name)}
              {#if a.queue_total > 1}
                <span class="queue-chip" title="This turn proposed {a.queue_total} tool calls; the rest are queued behind this decision.">
                  Decision {a.queue_position} of {a.queue_total}
                </span>
              {/if}
            </td>
            <td><IdentityChip identity={a.proposed_by} /></td>
            <td>{capabilityLabel(a.capability)}</td>
            <td><Badge variant={a.risk_level === "critical" || a.risk_level === "high" ? "blocked" : "metadata-only"} label={a.risk_level} /></td>
            <td><Badge variant={approvalBadge(a.is_expired ? "expired" : a.status)} label={a.is_expired ? "expired" : a.status} /></td>
            <td title={a.created_at}>{relativeTime(a.created_at)}</td>
            <td>
              <button type="button" class="btn btn-sm" onclick={() => openDetail(a.approval_id)}>
                {a.tool_name === OWNER_QUESTION_TOOL ? "Answer" : "Review"}
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

{#if detailError}
  <p class="error" role="alert">{detailError}</p>
{/if}

{#if selected !== null}
  <section class="card detail" aria-labelledby="approval-detail-h">
    <div class="detail-head">
      <h2 id="approval-detail-h">
        {isQuestion ? "Answer a question" : `Review ${humanize(selected.approval.tool_name)}`}
      </h2>
      <button type="button" class="btn btn-ghost btn-sm" onclick={() => (selected = null)}>
        <Icon name="x" size="sm" />
        Close
      </button>
    </div>

    <p class="notice">{selected.metadata_only_notice}</p>

    <dl class="meta">
      <div><dt>Capability</dt><dd>{capabilityLabel(selected.approval.capability)}</dd></div>
      <div><dt>Risk</dt><dd>{selected.approval.risk_level}</dd></div>
      <div><dt>Session</dt><dd><a class="mono" href={`#/sessions?session=${encodeURIComponent(selected.approval.session_id)}`}>View session</a></dd></div>
      <div><dt>Requested</dt><dd>{relativeTime(selected.approval.created_at)}</dd></div>
      <div><dt>Proposed by</dt><dd><IdentityChip identity={selected.approval.proposed_by} /></dd></div>
      {#if selected.approval.queue_total > 1}
        <div>
          <dt>Batch</dt>
          <dd>
            Decision {selected.approval.queue_position} of {selected.approval.queue_total} —
            the calls after it are queued on this turn and each gets its own decision.
          </dd>
        </div>
      {/if}
      {#if selected.approval.expires_at}
        <div><dt>Expires</dt><dd>{formatTimestamp(selected.approval.expires_at)}</dd></div>
      {/if}
      {#if selected.approval.approved_by}
        <div><dt>Authorized by</dt><dd><IdentityChip identity={selected.approval.approved_by} /></dd></div>
      {/if}
    </dl>

    {#if Object.keys(selected.execution_evidence ?? {}).length > 0}
      <h3>Execution evidence</h3>
      <dl class="meta">
        <div><dt>Principal</dt><dd class="mono">{selected.execution_evidence.principal_id ?? selected.approval.resolved_by ?? "unknown"}</dd></div>
        <div><dt>Exit</dt><dd>{selected.execution_evidence.returncode ?? "n/a"}</dd></div>
        <div><dt>Output</dt><dd>{selected.execution_evidence.stdout_bytes ?? 0} B stdout / {selected.execution_evidence.stderr_bytes ?? 0} B stderr</dd></div>
      </dl>
      {#if selected.execution_evidence.stdout}
        <pre class="diff">{selected.execution_evidence.stdout}</pre>
      {/if}
      {#if selected.execution_evidence.stderr}
        <pre class="diff">{selected.execution_evidence.stderr}</pre>
      {/if}
      {#if selected.execution_evidence.truncated}
        <p class="notice">Output was truncated at the approved bound.</p>
      {/if}
      {#if selected.execution_evidence.output_redacted}
        <p class="notice">Secret-like output was redacted before it entered history.</p>
      {/if}
    {/if}

    {#if selected.approval.is_expired}
      <p class="notice notice-danger" role="alert">
        This approval expired at {formatTimestamp(selected.approval.expires_at)}. The server will not accept a decision.
        Refresh the queue to retrieve the current state.
      </p>
    {/if}

    {#if selected.preview_kind === "file_diff" || selected.preview_kind === "patch"}
      <h3>{selected.preview_kind === "file_diff" ? "Proposed file change" : "Proposed patch"}</h3>
      <!-- B14 — the same reader Build uses, so a change looks the same wherever
           it is decided: added and removed lines told apart, the hunk's own
           line numbers, and long lines scrolling inside the diff. -->
      <!-- B14 — and the reviewer can accept part of it. An approval used to
           govern the whole change set, so wanting two of five hunks meant
           rejecting everything and asking again. -->
      <DiffView
        diff={selected.diff}
        path={selected.diff_path}
        selectable={selected.approval.status === "pending" && !selected.approval.is_expired}
        bind:selection={hunkSelection}
      />
    {:else if selected.preview_kind === "git_change"}
      <!-- B11 — a repository change is reviewed where the decision is made:
           the exact file list and diff a commit would record, or the refs a
           branch moves between. -->
      <h3>Proposed repository change</h3>
      <DiffView diff={selected.diff} path={selected.diff_path} emptyLabel="(nothing to record)" />
    {:else if selected.preview_kind === "checkpoint_restore"}
      <!-- BUG-230 — the rewind is decided on its own preflight: which files go
           back, which are deleted, and which cannot be restored at all. -->
      <h3>Files this restore would rewind</h3>
      {#if selected.diff_path}
        <p class="diff-path mono">{selected.diff_path}</p>
      {/if}
      <pre class="diff">{selected.diff ?? "(nothing to rewind)"}</pre>
    {:else if selected.preview_kind === "connector_request"}
      <h3>Proposed outbound request (redacted)</h3>
      {#if selected.diff_path}
        <p class="diff-path mono">{selected.diff_path}</p>
      {/if}
      <pre class="diff">{selected.diff ?? "{}"}</pre>
    {:else if !isQuestion}
      <h3>Proposed arguments (redacted)</h3>
      <pre class="diff">{JSON.stringify(selected.arguments, null, 2)}</pre>
    {/if}

    {#if isQuestion && selected.approval.status === "pending" && !selected.approval.is_expired}
      <div class="question-block">
        <p class="notice">
          This is a <strong>question</strong>, not an approval. Answering it grants nothing and
          runs nothing — it tells the turn what you meant so it can carry on.
        </p>
        {#each questions as question (question.question)}
          <fieldset class="question">
            <legend>{question.header}</legend>
            <p class="question-text">{question.question}</p>
            {#each question.options as option (option.label)}
              <label class="option">
                <input
                  type={question.multiSelect ? "checkbox" : "radio"}
                  name={`q-${question.question}`}
                  checked={(picked[question.question] ?? []).includes(option.label)}
                  onchange={() => toggle(question, option.label)}
                  disabled={busy}
                />
                <span><strong>{option.label}</strong> — {option.description}</span>
              </label>
            {/each}
          </fieldset>
        {/each}
        <label class="field-label" for="own-words">Or answer in your own words</label>
        <textarea
          id="own-words"
          class="textarea"
          rows="2"
          bind:value={ownWords}
          placeholder="Say something the options do not cover."
          disabled={busy}
        ></textarea>
        <div class="decision-actions">
          <button
            type="button"
            class="btn"
            onclick={() => answer(true)}
            disabled={busy || ownWords.trim() === ""}
          >
            Send my own answer
          </button>
          <button
            type="button"
            class="btn btn-primary"
            onclick={() => answer(false)}
            disabled={busy || !everyQuestionAnswered}
          >
            {busy ? "Sending…" : "Send answer"}
          </button>
        </div>
      </div>
    {:else if selected.approval.status === "pending" && !selected.approval.is_expired && selected.approval.critical}
      <p class="notice notice-danger">This is a critical action. Re-authenticate before the server can resolve it through the human-only critical lifecycle.</p>
      <div class="decision-actions">
        <button type="button" class="btn btn-danger" onclick={() => beginCriticalDecision("deny")} disabled={busy || criticalBusy}>
          Begin critical denial
        </button>
        <button type="button" class="btn btn-primary" onclick={() => beginCriticalDecision("approve")} disabled={busy || criticalBusy}>
          Begin critical approval
        </button>
      </div>
    {:else if selected.approval.status === "pending" && !selected.approval.is_expired}
      <label class="field-label" for="decision-reason">Decision note (optional)</label>
      <textarea
        id="decision-reason"
        class="textarea"
        rows="2"
        bind:value={decisionReason}
        placeholder="Why are you approving or denying this?"
        disabled={busy}
      ></textarea>
      <!-- BUG-271 — a reviewer could narrow a change and could not correct one.
           An edit is a different action, not a smaller one, so it is not a
           third state of this decision: it denies what is here and proposes the
           reviewer's own, which they then approve like any other change. The
           copy says that in the panel rather than leaving it to be discovered. -->
      {#if editedPatch !== null}
        <div class="edit-block">
          <label class="field-label" for="edited-patch">Your version of this change</label>
          <textarea
            id="edited-patch"
            class="textarea mono"
            rows="12"
            bind:value={editedPatch}
            disabled={busy}
            spellcheck="false"
          ></textarea>
          <p class="hint">
            This denies the change above and proposes yours in its place. You will be
            asked to approve it; nothing runs until you do.
          </p>
          {#if editError}<p class="error" role="alert">{editError}</p>{/if}
          <div class="decision-actions">
            <button type="button" class="btn" onclick={() => (editedPatch = null)} disabled={busy}>
              Cancel
            </button>
            <button type="button" class="btn btn-primary" onclick={proposeEdit} disabled={busy}>
              {busy ? "Proposing…" : "Propose as a new change"}
            </button>
          </div>
        </div>
      {:else}
        <div class="decision-actions">
          <button type="button" class="btn btn-danger" onclick={() => resolve(false)} disabled={busy}>
            Deny
          </button>
          {#if selected.preview_kind === "patch" && selected.diff}
            <button
              type="button"
              class="btn btn-ghost"
              onclick={() => (editedPatch = selected!.diff ?? "")}
              disabled={busy}
            >
              Edit…
            </button>
          {/if}
          <button type="button" class="btn btn-primary" onclick={() => resolve(true)} disabled={busy}>
            {busy
              ? selected.executes_on_approval
                ? "Executing…"
                : "Recording…"
              : selected.executes_on_approval
                ? "Approve and execute once"
                : "Approve (record only)"}
          </button>
        </div>
      {/if}
    {:else if selected.approval.is_expired}
      <p class="resolved-note">Expired before a decision was recorded.</p>
    {:else}
      <p class="resolved-note">
        Already resolved: <Badge variant={approvalBadge(selected.approval.status)} label={selected.approval.status} />
      </p>
    {/if}
  </section>
{/if}

{#if criticalDecision !== null}
  <div class="overlay">
    <div class="step-up" role="dialog" aria-modal="true" aria-labelledby="critical-step-up-title" tabindex="-1">
      <h2 id="critical-step-up-title">Step up to {criticalDecision} this critical action</h2>
      <p>Raiker will obtain a short-lived elevated session, then ask the server to re-check this immutable intent.</p>
      <label class="field-label" for="critical-reason">Decision note</label>
      <textarea id="critical-reason" class="textarea" rows="2" bind:value={criticalReason} disabled={criticalBusy}></textarea>
      <label class="field-label" for="critical-password">Password</label>
      <input id="critical-password" class="input" type="password" bind:value={criticalPassword} autocomplete="current-password" disabled={criticalBusy} />
      <label class="field-label" for="critical-mfa">MFA code (optional)</label>
      <input id="critical-mfa" class="input" inputmode="numeric" autocomplete="one-time-code" bind:value={criticalMfaCode} disabled={criticalBusy} />
      <p class="hint">Provide your password or an MFA code. Neither is stored by the browser.</p>
      {#if criticalError}<p class="error" role="alert">{criticalError}</p>{/if}
      <div class="decision-actions">
        <button type="button" class="btn" onclick={() => (criticalDecision = null)} disabled={criticalBusy}>Cancel</button>
        <button type="button" class:btn-danger={criticalDecision === "deny"} class="btn btn-primary" onclick={resolveCritical} disabled={criticalBusy || criticalReason.trim() === "" || (criticalPassword.trim() === "" && criticalMfaCode.trim() === "")}>
          {criticalBusy ? "Verifying..." : criticalDecision === "approve" ? "Approve critical action" : "Deny critical action"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* ADD-22 — a question reads as a question, not as a softer approval. */
  .question {
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    padding: 0.6rem 0.75rem;
    margin: 0.5rem 0;
  }
  .question legend {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.7;
  }
  .question-text {
    margin: 0 0 0.5rem;
    font-weight: 600;
  }
  .option {
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
    padding: 0.25rem 0;
  }
  /* ADD-02 — a batched turn's approvals sit next to unbatched ones in the same
     list, so the position has to read at a glance without shouting: this is
     context for the decision, not a second risk signal. */
  .queue-chip {
    display: inline-block;
    margin-left: var(--space-2);
    padding: 1px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--sunken);
    color: var(--text-2);
    font-size: var(--text-2xs);
    white-space: nowrap;
  }
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  @media (max-width: 720px) {
    .head-row {
      flex-direction: column;
    }
  }
  .filters {
    display: inline-flex;
    gap: 2px;
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 3px;
    margin-bottom: var(--space-4);
  }
  .queue-controls {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .sort-control .select {
    min-width: 10.5rem;
  }
  @media (max-width: 520px) {
    .queue-controls {
      flex-direction: column;
    }
  }
  .filter-btn {
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 600;
    text-transform: capitalize;
    color: var(--text-2);
    background: transparent;
    border: none;
    border-radius: var(--r-pill);
    padding: 0.25rem 0.85rem;
    cursor: pointer;
  }
  .filter-btn.active {
    background: var(--surface);
    color: var(--accent);
    box-shadow: var(--shadow-1);
  }
  .list-card {
    padding: var(--space-2) var(--space-3);
    overflow-x: auto;
  }
  .detail {
    margin-top: var(--space-4);
  }
  .resume-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
  }
  .resume-actions {
    display: inline-flex;
    gap: var(--space-2);
    flex-shrink: 0;
  }
  .detail-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr));
    gap: 0.4rem 1rem;
    margin: var(--space-3) 0;
  }
  .meta div {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.4rem;
    align-items: center;
    min-width: 0;
  }
  .meta dt {
    font-size: var(--text-xs);
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
  }
  .meta dd {
    margin: 0;
    font-size: var(--text-sm);
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .diff-path {
    color: var(--text-2);
    font-size: var(--text-sm);
    margin: 0 0 0.35rem;
  }
  .diff {
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.7rem 0.9rem;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    overflow-x: auto;
    white-space: pre;
    max-height: 24rem;
  }
  .decision-actions {
    display: flex;
    gap: 0.6rem;
    justify-content: flex-end;
    margin-top: var(--space-3);
  }
  .resolved-note {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--text-2);
    margin: var(--space-3) 0 0;
  }
  .overlay {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: var(--overlay);
    z-index: 60;
  }
  .step-up {
    width: min(34rem, calc(100% - 2rem));
    display: grid;
    gap: 0.55rem;
    padding: var(--space-5);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-md);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  .step-up h2, .step-up p { margin: 0; }
  .hint { color: var(--text-3); font-size: var(--text-sm); }
  /* BUG-271 — the reviewer's own diff. Monospaced because it is one, and given
     the same vertical rhythm as the decision note above it so the panel does
     not change shape when the editor opens. */
  .edit-block { display: grid; gap: var(--space-2); }
  .edit-block .textarea { font-family: var(--font-mono, ui-monospace, monospace); }
</style>
