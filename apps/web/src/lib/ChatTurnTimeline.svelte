<script lang="ts">
  import Badge from "./Badge.svelte";
  import ActionProposalCard from "./ActionProposalCard.svelte";
  import type { AgentResponse, StreamEvent } from "./apiTypes";
  import { explainReasonCode } from "./reasonCodes";
  import { collectText, groupPhases, summarizeEvent } from "./turnPhases";

  // Presentational: the parent owns the SSE stream and feeds events + the final response in.
  let {
    events,
    finalResponse = null,
    streaming = false,
  }: { events: StreamEvent[]; finalResponse?: AgentResponse | null; streaming?: boolean } = $props();

  const phases = $derived(groupPhases(events));
  const answerText = $derived(collectText(events));
  const status = $derived(finalResponse?.status ?? (streaming ? "running" : null));

  // For failed/denied turns, try to surface a plain-English reason from the message.
  const denialReason = $derived(
    finalResponse && (finalResponse.status === "denied" || finalResponse.status === "failed")
      ? explainReasonCode(extractCode(finalResponse.message))
      : null,
  );

  function extractCode(message: string): string | null {
    // Messages often embed the machine code (e.g. "Action denied by policy: denied_by_policy").
    const m = message.match(/[a-z][a-z0-9_]+(?::[a-z0-9_]+)?$/);
    return m ? m[0] : null;
  }

  function statusVariant(s: string): "safe" | "blocked" | "needs-approval" {
    if (s === "needs_approval") return "needs-approval";
    if (s === "denied" || s === "failed") return "blocked";
    return "safe";
  }
</script>

<section class="timeline" aria-label="Governed turn timeline">
  <ol class="phases">
    {#each phases as row (row.phase)}
      <li class="phase">
        <div class="phase-head">
          <span class="phase-label">{row.label}</span>
        </div>
        <ul class="phase-events">
          {#each row.events as ev, i (row.phase + "-" + i)}
            <li>{summarizeEvent(ev)}</li>
          {/each}
        </ul>
      </li>
    {/each}
    {#if streaming}
      <li class="phase phase-streaming" aria-live="polite">
        <span class="phase-label">Working…</span>
      </li>
    {/if}
  </ol>

  {#if answerText}
    <div class="answer">
      <h4>Answer</h4>
      <p>{answerText}</p>
    </div>
  {/if}

  {#if finalResponse && status}
    <div class="result" class:result-bad={status === "denied" || status === "failed"}>
      <span class="result-label">Result</span>
      <Badge variant={statusVariant(status)} />
      <span class="result-status">{status}</span>
    </div>

    {#if status === "failed" || status === "denied"}
      <p class="result-message" role="alert">
        {finalResponse.message}
      </p>
      {#if denialReason}
        <p class="result-plain">
          {denialReason.plain}
          {#if denialReason.remediation}<span class="remediation">{denialReason.remediation}</span>{/if}
        </p>
      {/if}
    {:else if finalResponse.message}
      <p class="result-message">{finalResponse.message}</p>
    {/if}

    {#if finalResponse.status === "needs_approval" && finalResponse.approval}
      <ActionProposalCard approval={finalResponse.approval} />
    {/if}
  {/if}
</section>

<style>
  .timeline {
    margin-top: 1rem;
  }
  .phases {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .phase {
    border-left: 2px solid #2d5a82;
    padding: 0.2rem 0 0.2rem 0.75rem;
  }
  .phase-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9cc7ec;
    font-weight: 600;
  }
  .phase-events {
    margin: 0.25rem 0 0;
    padding-left: 1rem;
    font-size: 0.84rem;
    color: #c2c2c9;
  }
  .phase-events li {
    margin-bottom: 0.15rem;
  }
  .phase-streaming .phase-label {
    color: #e6c66a;
  }
  .answer {
    margin-top: 0.9rem;
    border: 1px solid #2a2a2e;
    border-radius: 8px;
    background: #101013;
    padding: 0.6rem 0.85rem;
  }
  .answer h4 {
    margin: 0 0 0.3rem;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #8b8b93;
  }
  .answer p {
    margin: 0;
    white-space: pre-wrap;
  }
  .result {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.8rem;
  }
  .result-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #8b8b93;
  }
  .result-status {
    font-family: ui-monospace, monospace;
    font-size: 0.82rem;
    color: #c2c2c9;
  }
  .result-message {
    margin: 0.4rem 0 0;
    font-size: 0.86rem;
    color: #d4d4da;
  }
  .result-bad ~ .result-message[role="alert"] {
    color: #ef9a9a;
  }
  .result-plain {
    margin: 0.3rem 0 0;
    font-size: 0.84rem;
    color: #d4d4da;
  }
  .remediation {
    display: block;
    color: #9a9aa2;
    font-size: 0.8rem;
  }
</style>
