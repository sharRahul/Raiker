<script lang="ts">
  import Badge from "./Badge.svelte";
  import type { ApprovalInfo } from "./apiTypes";
  import { explainReasonCode } from "./reasonCodes";

  let { approval }: { approval: ApprovalInfo } = $props();

  // Pull out resource-like arguments to surface "affected files/resources" prominently.
  const RESOURCE_KEYS = ["path", "paths", "file", "files", "target", "directory", "url"];
  const args = $derived(approval.arguments ?? {});
  const resources = $derived(
    Object.entries(args)
      .filter(([k]) => RESOURCE_KEYS.includes(k))
      .map(([k, v]) => ({ key: k, value: formatValue(v) })),
  );
  // A textual preview/diff if the tool carries one (e.g. write_file content / diff).
  const preview = $derived(pickPreview(args));
  const reasons = $derived(
    approval.reasons.map((r) => explainReasonCode(r) ?? { code: r, plain: r, remediation: null }),
  );

  function formatValue(v: unknown): string {
    if (v === null || v === undefined) return "—";
    if (typeof v === "string") return v;
    return JSON.stringify(v);
  }

  function pickPreview(a: Record<string, unknown>): string | null {
    for (const key of ["diff", "content", "text", "new_text"]) {
      const v = a[key];
      if (typeof v === "string" && v.length > 0) return v;
    }
    return null;
  }
</script>

<section class="proposal" aria-labelledby="proposal-h-{approval.action_id}">
  <header class="proposal-head">
    <h3 id="proposal-h-{approval.action_id}">
      Proposed action: <code>{approval.tool_name}</code>
    </h3>
    <div class="proposal-badges">
      <Badge variant="approval-required" />
      {#if approval.risk_level === "high"}
        <span class="risk risk-high">Risk: high</span>
      {:else if approval.risk_level}
        <span class="risk">Risk: {approval.risk_level}</span>
      {/if}
    </div>
  </header>

  <p class="metadata-note">
    This action was <strong>not executed</strong>. It is waiting for a human approval decision.
  </p>

  {#if resources.length > 0}
    <div class="block">
      <h4>Affected files / resources</h4>
      <ul class="resources">
        {#each resources as r (r.key)}
          <li><span class="rkey">{r.key}</span>: <code>{r.value}</code></li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if reasons.length > 0}
    <div class="block">
      <h4>Why approval is required</h4>
      <ul class="reasons">
        {#each reasons as r (r.code)}
          <li>
            <span class="plain">{r.plain}</span>
            <code class="code">{r.code}</code>
            {#if r.remediation}<span class="remediation">{r.remediation}</span>{/if}
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if preview}
    <div class="block">
      <h4>Preview</h4>
      <pre class="preview">{preview}</pre>
    </div>
  {/if}

  <p class="route-note">
    Approve or deny this from the <strong>Approvals</strong> queue. Resolution is metadata-only —
    it records the decision and never executes the action from this screen.
  </p>
</section>

<style>
  .proposal {
    border: 1px solid #8a6d1f;
    border-radius: 10px;
    background: #1c1809;
    padding: 0.9rem 1.1rem;
    margin-top: 0.75rem;
  }
  .proposal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .proposal-head h3 {
    margin: 0;
    font-size: 0.95rem;
  }
  .proposal-badges {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .risk {
    font-size: 0.75rem;
    border: 1px solid #4a4a52;
    border-radius: 999px;
    padding: 0.1rem 0.5rem;
    color: #d0d0d6;
  }
  .risk-high {
    border-color: #8a2f2f;
    color: #ef9a9a;
  }
  .metadata-note {
    color: #e6c66a;
    font-size: 0.85rem;
  }
  .block {
    margin-top: 0.6rem;
  }
  .block h4 {
    margin: 0 0 0.3rem;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #b9a45f;
  }
  .resources,
  .reasons {
    margin: 0;
    padding-left: 1.1rem;
    font-size: 0.84rem;
  }
  .reasons li {
    margin-bottom: 0.3rem;
  }
  .rkey {
    color: #b0b0b6;
  }
  .plain {
    display: block;
  }
  .code {
    font-size: 0.72rem;
    color: #c79b9b;
  }
  .remediation {
    display: block;
    color: #9a9aa2;
    font-size: 0.78rem;
  }
  code {
    font-family: ui-monospace, monospace;
    color: #e0c98a;
  }
  .preview {
    background: #0e0e11;
    border: 1px solid #33333a;
    border-radius: 6px;
    padding: 0.5rem 0.6rem;
    font-size: 0.78rem;
    color: #cdd6e0;
    max-height: 16rem;
    overflow: auto;
    white-space: pre-wrap;
  }
  .route-note {
    margin-top: 0.7rem;
    font-size: 0.82rem;
    color: #c2c2c9;
  }
</style>
