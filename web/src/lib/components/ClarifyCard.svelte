<script lang="ts">
  /**
   * QUI-F02 — a mid-task question, as a card where the conversation parked.
   *
   * The turn asked with `ask_owner_question`, which parks it through the
   * approval transport without being an approval. Chat drew it with the
   * approval card — Decline and Allow once on a multiple-choice question, the
   * blur ApprovalsView keeps a separate branch to avoid. This is that branch in
   * place: one question at a time ("1 of 2"), pick one, pick several or type an
   * answer, **Skip** and **Confirm and continue**. The answer goes through the
   * question's own route, which refuses any label it did not offer, and the
   * turn continues with exactly what was chosen. Nothing is granted.
   *
   * The model wrote the questions and options, so they are rendered as data
   * (Svelte escapes them); the card itself is drawn by the app.
   */
  import { api, ApiError } from "../api";
  import type { OwnerQuestion, OwnerQuestionAnswered } from "../apiTypes";
  import { publishApprovalResolved } from "../approvalResume";
  import { clarifyBody, clarifyText, ownerQuestions, previewFor, type ClarifyReply } from "../clarify";
  import { failure } from "../errorCopy";
  import { shownInline } from "../inlineDecisions.svelte";

  let {
    approvalId,
    questions: given = null,
    sessionId = null,
    disabled = false,
    onAnswered,
  }: {
    approvalId: string;
    /** The questions, when the surface already holds them; otherwise read from the approval. */
    questions?: OwnerQuestion[] | null;
    sessionId?: string | null;
    /** A turn is streaming, so nothing here may start another. */
    disabled?: boolean;
    /** The answer was recorded; `resumable` says whether the parked turn can continue. */
    onAnswered?: (resumable: boolean) => void;
  } = $props();

  let loaded = $state<OwnerQuestion[] | null>(null);
  let unreadable = $state(false);
  const questions = $derived(given ?? loaded ?? []);
  $effect(() => {
    if (given !== null || loaded !== null) return;
    void api
      .approval(approvalId)
      .then((detail) => {
        loaded = ownerQuestions({ tool_name: detail.approval.tool_name, arguments: detail.arguments }) ?? [];
        unreadable = loaded.length === 0;
      })
      .catch(() => (unreadable = true));
  });

  let index = $state(0);
  let replies = $state<ClarifyReply[]>([]);
  let picked = $state<string[]>([]);
  let typed = $state("");
  let sent = $state<string | null>(null);
  let busy = $state(false);
  let problem = $state<string | null>(null);
  const uid = $derived(`clarify-${approvalId}`);

  const current = $derived(questions[Math.min(index, questions.length - 1)]);
  const last = $derived(index >= questions.length - 1);
  const ready = $derived(picked.length > 0 || typed.trim() !== "");
  const open = $derived(!disabled && !busy && sent === null);
  // TOOL-08 — the preview of what was picked; looking is not choosing, so the
  // recommended option is tagged but never pre-selected.
  const preview = $derived(current ? previewFor(current, picked) : null);

  function toggle(label: string): void {
    if (current.multiSelect) {
      picked = picked.includes(label) ? picked.filter((item) => item !== label) : [...picked, label];
    } else {
      picked = [label];
    }
  }

  async function advance(reply: ClarifyReply): Promise<void> {
    const next = [...replies, reply];
    replies = next;
    if (!last) {
      picked = [];
      typed = "";
      index += 1;
      return;
    }
    busy = true;
    problem = null;
    try {
      const result: OwnerQuestionAnswered = await api.answerOwnerQuestion(approvalId, clarifyBody(questions, next));
      sent = clarifyText(questions, next);
      publishApprovalResolved({
        approvalId,
        sessionId: result.resume?.session_id ?? sessionId,
        turnId: result.resume?.turn_id ?? null,
        approved: true,
      });
      onAnswered?.(Boolean(result.resume?.resumable));
    } catch (error) {
      // Back to the first question with nothing kept: the answer was not
      // recorded, so the card must not read as if it had been.
      replies = [];
      picked = [];
      typed = "";
      index = 0;
      problem =
        error instanceof ApiError && error.reasonCode === "question_already_answered"
          ? "This question was already answered, in another tab or on Approvals."
          : failure("Your answer was not sent", "The task is still waiting for it.", "Try again.", error);
    } finally {
      busy = false;
    }
  }

  function confirm(): void {
    if (!ready || !open) return;
    void advance({ picked: [...picked], typed: typed.trim(), skipped: false });
  }

  function skip(): void {
    if (!open) return;
    void advance({ picked: [], typed: "", skipped: true });
  }
</script>

<section class="clarify" aria-labelledby={`${uid}-q`} data-testid="clarify-card" use:shownInline={approvalId}>
  <header>
    <span class="tag" role="status">{sent === null ? "Waiting for your answer" : "Answered"}</span>
    {#if questions.length > 1 && sent === null}<span class="count">{index + 1} of {questions.length}</span>{/if}
  </header>
  {#if sent !== null}
    <p class="sent" id={`${uid}-q`}>{sent}</p>
  {:else if questions.length === 0}
    <p class="sent" id={`${uid}-q`}>
      {unreadable ? "Raiker could not read this question here. Answer it on Approvals." : "Reading the question…"}
    </p>
    {#if unreadable}<a class="btn btn-ghost btn-sm" href="#/approvals">Open Approvals</a>{/if}
  {:else}
    {#if current.header}<p class="header">{current.header}</p>{/if}
    <p class="question" id={`${uid}-q`}>{current.question}</p>
    {#if current.options.length > 0}
      <div class="options" role={current.multiSelect ? "group" : "radiogroup"} aria-labelledby={`${uid}-q`}>
        {#each current.options as option (option.label)}
          <label class="option" class:chosen={picked.includes(option.label)}>
            <input
              type={current.multiSelect ? "checkbox" : "radio"}
              name={`${uid}-${index}`}
              checked={picked.includes(option.label)}
              disabled={!open}
              onchange={() => toggle(option.label)}
            />
            <span class="label"
              >{option.label}{#if option.recommended}<span class="recommended">Recommended</span>{/if}</span
            >
            {#if option.description}<span class="description">{option.description}</span>{/if}
          </label>
        {/each}
      </div>
      {#if preview}<pre class="preview" aria-label="Preview of your choice" data-testid="clarify-preview">{preview}</pre>{/if}
    {/if}
    <input
      class="typed"
      type="text"
      aria-label={current.options.length > 0 ? "Or type your own answer" : "Your answer"}
      placeholder={current.options.length > 0 ? "Or type your own answer" : "Type your answer"}
      bind:value={typed}
      disabled={!open}
      onkeydown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          confirm();
        }
      }}
    />
    {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
    <div class="actions">
      <button type="button" class="btn btn-ghost btn-sm" disabled={!open} onclick={skip}>Skip</button>
      <button type="button" class="btn btn-primary btn-sm" disabled={!open || !ready} onclick={confirm}
        >{busy ? "Sending…" : last ? "Confirm and continue" : "Next question"}</button>
    </div>
  {/if}
</section>

<style>
  .clarify{padding:var(--space-3);border:1px solid var(--border);border-radius:var(--r-md);background:var(--raised);display:grid;gap:var(--space-2);max-width:36rem}
  header{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2)}
  .tag{font-size:var(--text-xs);font-weight:650;color:var(--accent)}
  .count,.header{font-size:var(--text-xs);color:var(--text-3);margin:0}
  .question{margin:0;font-weight:600;color:var(--text-1)}
  .options{display:grid;gap:var(--space-1)}
  .option{display:grid;grid-template-columns:auto 1fr;column-gap:var(--space-2);align-items:center;padding:.4rem .6rem;border:1px solid var(--border);border-radius:var(--r-sm);cursor:pointer;font-size:var(--text-sm)}
  .option.chosen{border-color:var(--accent);background:var(--accent-soft)}
  .recommended{margin-left:var(--space-2);padding:0 .35rem;border:1px solid var(--accent);border-radius:var(--r-sm);font-size:var(--text-xs);font-weight:600;color:var(--accent)}
  .preview{margin:0;padding:var(--space-2);max-height:14rem;overflow:auto;border:1px solid var(--border);border-radius:var(--r-sm);background:var(--surface);font-family:var(--font-mono);font-size:var(--text-xs);white-space:pre-wrap;color:var(--text-1)}
  .description{grid-column:2;color:var(--text-3);font-size:var(--text-xs)}
  .typed{width:100%;padding:.45rem .6rem;border:1px solid var(--border);border-radius:var(--r-sm);background:var(--surface);color:var(--text-1);font:inherit;font-size:var(--text-sm)}
  .actions{display:flex;justify-content:flex-end;gap:var(--space-2)}
  .sent{margin:0;font-size:var(--text-sm);color:var(--text-1);white-space:pre-line}
  .problem{margin:0;font-size:var(--text-sm);color:var(--danger)}
</style>
