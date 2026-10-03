<script lang="ts">
  /**
   * UX-MODEL-02 — one model decision, said as four steps and one next action.
   *
   * "Provider connected", "models discovered", "model selected" and "runtime
   * available" were four facts the owner had to read off different tabs and put
   * in order themselves. The server says them in order (`steps` on the model
   * decision), so this only draws them: the steps before the one that stops the
   * work are done, that one carries the action, and the ones after it are
   * waiting — not failed, because nothing has been asked of them yet.
   *
   * Nothing is derived here. A host that predates the field sends no steps, and
   * then the line is simply absent rather than reconstructed from guesses.
   */
  import Icon from "../../components/Icon.svelte";
  import type { ModelNextAction, ModelReadinessStep } from "../../apiTypes";

  let {
    steps,
    action = null,
    busy = false,
    onaction,
    label,
  }: {
    steps: ModelReadinessStep[];
    action?: ModelNextAction | null;
    busy?: boolean;
    onaction: (action: ModelNextAction) => void;
    /** Whose readiness this is, for assistive technology ("Chat readiness"). */
    label: string;
  } = $props();

  const ICON = {
    done: "check",
    blocked: "warning",
    waiting: "circle",
    unchecked: "clock",
  } as const;

  const WORD = {
    done: "done",
    blocked: "needs you",
    waiting: "waiting",
    unchecked: "not checked yet",
  } as const;
</script>

{#if steps.length > 0}
  <div class="readiness" data-testid="model-readiness-steps">
    <ol aria-label={label}>
      {#each steps as step (step.id)}
        <li data-state={step.state} data-step={step.id}>
          <Icon name={ICON[step.state]} size="sm" />
          <span class="step-label">{step.label}</span>
          <span class="sr-only">— {WORD[step.state]}</span>
        </li>
      {/each}
    </ol>
    {#if action !== null}
      <button
        type="button"
        class="btn btn-sm btn-primary"
        disabled={busy}
        onclick={() => onaction(action)}
      >{busy && action.target === "check" ? "Checking…" : action.label}</button>
    {/if}
  </div>
{/if}

<style>
  .readiness {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.15rem 0.6rem;
  }
  li {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: var(--text-2xs);
    color: var(--text-3);
  }
  /* The resting states stay quiet; only the step that needs a person and the
     ones already passed carry a tone, so the eye lands on the blocked one. */
  li[data-state="done"] {
    color: var(--text-2);
  }
  li[data-state="blocked"] {
    color: var(--warn);
    font-weight: 650;
  }
  li + li::before {
    content: "→";
    margin-right: 0.35rem;
    color: var(--text-3);
  }
</style>
