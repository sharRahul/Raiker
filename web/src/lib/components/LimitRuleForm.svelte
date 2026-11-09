<script lang="ts">
  /**
   * QUI-P03 / QUI-P05 — **Allow for this task**: the limits, required.
   *
   * The plan: choosing Allow with limits *requires* the limits — where it
   * applies, recipients or sites, how many times, until when, and whether
   * attachments and sensitive content still ask. The draft comes from the
   * server (the action's own targets, this conversation, ten uses, eight
   * hours); the owner can narrow or widen within what the runtime enforces.
   * There is no "Always allow": every rule expires within a week and counts
   * its uses.
   */
  import { contract } from "../generated/apiContract";
  import {
    EXPIRY_CHOICES,
    SCOPE_LABELS,
    formFromLimits,
    formProblem,
    limitRuleReason,
    limitsFromForm,
    type LimitForm,
    type LimitScope,
  } from "../limitRules";
  import type { LimitRuleLimits } from "../generated/apiContract";
  import { ApiError } from "../api";

  let {
    approvalId,
    busy = false,
    onallow,
    oncancel,
  }: {
    approvalId: string;
    busy?: boolean;
    /** Allow this once, then keep the rule with these limits. */
    onallow: (limits: LimitRuleLimits) => void;
    oncancel: () => void;
  } = $props();

  let form = $state<LimitForm | null>(null);
  let hasProject = $state(false);
  let loadError = $state<string | null>(null);
  let problem = $state<string | null>(null);
  const uid = `lr-${Math.random().toString(36).slice(2, 8)}`;

  $effect(() => {
    const id = approvalId;
    void (async () => {
      try {
        const draft = await contract.limitRuleDraft(id);
        form = formFromLimits(draft.limits);
        hasProject = draft.project_id !== null;
      } catch (error) {
        loadError = limitRuleReason(error instanceof ApiError ? error.reasonCode : null);
      }
    })();
  });

  const scopes = $derived(
    (["conversation", "project", "future"] as LimitScope[]).filter((scope) => scope !== "project" || hasProject),
  );

  function submit(event: SubmitEvent) {
    event.preventDefault();
    if (form === null) return;
    problem = formProblem(form);
    if (problem !== null) return;
    onallow(limitsFromForm(form));
  }
</script>

<form class="limit-rule" aria-label="Allow for this task" onsubmit={submit}>
  {#if loadError}
    <p class="note" role="alert">{loadError}</p>
    <div class="actions"><button type="button" class="btn btn-sm" onclick={oncancel}>Back</button></div>
  {:else if form === null}
    <p class="note">Reading what this action reaches…</p>
  {:else}
    <fieldset class="scope">
      <legend>Applies to</legend>
      {#each scopes as scope (scope)}
        <label class="choice">
          <input type="radio" name={`${uid}-scope`} value={scope} bind:group={form.scope} />
          {SCOPE_LABELS[scope]}
        </label>
      {/each}
    </fieldset>
    {#if form.scope !== "conversation"}
      <p class="hint">Applies only in conversations set to <strong>Within limits</strong>.</p>
    {/if}
    <label class="field" for={`${uid}-targets`}>
      Only to
      <input
        id={`${uid}-targets`}
        class="input"
        bind:value={form.targets}
        placeholder={form.scope === "conversation" ? "Anyone this action reaches" : "Recipients, sites or repositories"}
        autocomplete="off"
      />
    </label>
    <div class="row">
      <label class="field small" for={`${uid}-uses`}>
        At most
        <span class="inline"><input id={`${uid}-uses`} class="input" type="number" min="1" max="100" bind:value={form.maxUses} /> times</span>
      </label>
      <label class="field small" for={`${uid}-expiry`}>
        For
        <select id={`${uid}-expiry`} class="select" bind:value={form.expiresHours}>
          {#each EXPIRY_CHOICES as choice (choice.hours)}
            <option value={choice.hours}>{choice.label}</option>
          {/each}
        </select>
      </label>
    </div>
    <label class="check"><input type="checkbox" bind:checked={form.sensitiveAsks} /> Sensitive content still asks</label>
    <label class="check"><input type="checkbox" checked={!form.attachments} onchange={(event) => form && (form.attachments = !event.currentTarget.checked)} /> Attachments still ask</label>
    {#if problem}<p class="note" role="alert">{problem}</p>{/if}
    <div class="actions">
      <button type="button" class="btn btn-sm" onclick={oncancel} disabled={busy}>Back</button>
      <button type="submit" class="btn btn-primary btn-sm" disabled={busy}>Allow and keep these limits</button>
    </div>
  {/if}
</form>

<style>
  .limit-rule { display: grid; gap: 0.55rem; padding-top: 0.2rem; }
  fieldset { border: 0; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0.35rem 0.9rem; align-items: center; }
  legend { font-size: var(--text-sm); font-weight: 600; color: var(--text-1); margin-bottom: 0.25rem; }
  .choice, .check { display: inline-flex; align-items: center; gap: 0.4rem; font-size: var(--text-sm); color: var(--text-1); }
  .field { display: grid; gap: 0.25rem; font-size: var(--text-sm); font-weight: 600; color: var(--text-1); }
  .row { display: flex; flex-wrap: wrap; gap: 0.8rem; }
  .small { min-width: 9rem; }
  .inline { display: inline-flex; align-items: center; gap: 0.4rem; font-weight: 400; }
  .inline .input { width: 5rem; }
  .hint, .note { margin: 0; font-size: var(--text-sm); color: var(--text-2); }
  .actions { display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: flex-end; }
</style>
