<script lang="ts">
  /**
   * The agent's plan for this conversation, as a live checklist (B6).
   *
   * Build ran a real agentic loop with nothing showing what it intended to do
   * next, so a long change looked identical whether it was on step two or step
   * nine. This is that spine: ordered steps, one status each, updating as the
   * turn runs and still there after a reload or an approval.
   *
   * It is a *statement*, not a control. Nothing here can start, skip, or
   * reorder a step — the plan is written by the model through the governed
   * `update_plan` tool, and every step it names is governed again when it is
   * actually attempted. Rendering it read-only is what keeps it honest.
   */
  import Icon from "./Icon.svelte";
  import type { IconName } from "../icons";
  import type { AgentPlan, AgentPlanStep } from "../apiTypes";

  let {
    plan,
    collapsed = $bindable(false),
  }: { plan: AgentPlan; collapsed?: boolean } = $props();

  const steps = $derived(plan.steps ?? []);
  const done = $derived(steps.filter((step) => step.status === "completed").length);
  const blocked = $derived(steps.filter((step) => step.status === "blocked").length);
  const current = $derived(steps.find((step) => step.status === "in_progress") ?? null);
  const percent = $derived(steps.length === 0 ? 0 : Math.round((done / steps.length) * 100));

  const MARK: Record<AgentPlanStep["status"], IconName> = {
    completed: "check",
    in_progress: "clock",
    blocked: "warning",
    pending: "circle",
  };
</script>

{#if steps.length > 0}
  <section class="plan" aria-labelledby="plan-heading">
    <header>
      <button
        type="button"
        class="toggle"
        aria-expanded={!collapsed}
        aria-controls="plan-steps"
        onclick={() => (collapsed = !collapsed)}
      >
        <Icon name={collapsed ? "chevron-right" : "chevron-down"} size="sm" />
        <span id="plan-heading">Plan</span>
      </button>
      <span class="count">{done} of {steps.length} done</span>
      <div
        class="progress"
        role="progressbar"
        aria-label="Plan progress"
        aria-valuenow={percent}
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <div style={`width:${percent}%`}></div>
      </div>
    </header>

    {#if collapsed}
      <p class="collapsed-line">
        {#if current}Working on: {current.title}
        {:else if done === steps.length}All steps complete.
        {:else}Not started.{/if}
      </p>
    {:else}
      <ol id="plan-steps">
        {#each steps as step, index (index)}
          <li class={step.status}>
            <span class="marker" aria-hidden="true">
              <Icon name={MARK[step.status] ?? "circle"} size="sm" />
            </span>
            <span class="body">
              <span class="title">{step.title}</span>
              {#if step.note}<span class="note">{step.note}</span>{/if}
            </span>
            <span class="sr-only">{step.status.replace("_", " ")}</span>
          </li>
        {/each}
      </ol>
      {#if blocked > 0}
        <p class="blocked-line" role="status">
          {blocked === 1 ? "1 step is blocked." : `${blocked} steps are blocked.`}
        </p>
      {/if}
    {/if}
  </section>
{/if}

<style>
  .plan {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--raised);
    padding: 0.6rem 0.75rem;
    display: grid;
    gap: 0.5rem;
  }
  header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    cursor: pointer;
    padding: 0;
  }
  .toggle:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .count {
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .progress {
    /* Capped: stretched across a wide workspace the bar reads as a banner
       rather than as the small quantity it is. */
    flex: 0 1 10rem;
    min-width: 3rem;
    height: 4px;
    border-radius: var(--r-pill);
    background: var(--sunken);
    overflow: hidden;
  }
  .progress div {
    height: 100%;
    background: var(--accent);
    transition: width 0.2s ease;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.25rem;
  }
  li {
    display: grid;
    grid-template-columns: 1.1rem 1fr;
    gap: 0.5rem;
    align-items: start;
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .marker {
    display: grid;
    place-items: center;
    color: var(--text-3);
    padding-top: 0.12rem;
  }
  li.completed .marker { color: var(--ok); }
  li.in_progress .marker { color: var(--accent); }
  li.blocked .marker { color: var(--warn); }
  .body { display: grid; gap: 0.1rem; }
  .title { overflow-wrap: anywhere; }
  li.completed .title {
    color: var(--text-3);
    text-decoration: line-through;
  }
  li.in_progress .title {
    color: var(--text-1);
    font-weight: 650;
  }
  .note { font-size: var(--text-xs); color: var(--text-3); }
  .collapsed-line,
  .blocked-line {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .blocked-line { color: var(--warn); }
</style>
