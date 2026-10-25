<script lang="ts">
  /**
   * PA-D01 / PA-D06 — Work → Goals.
   *
   * A goal is an outcome the owner can come back to: success criteria, a plan
   * of steps that run as ordinary tasks, and a state the server owns. This page
   * draws exactly what the server sends: the buttons are the goal's own
   * `allowed_actions`, the state and reason are its own, progress is a count of
   * finished steps (never a percentage nobody measured), and the execution
   * profile is shown read-only with a route to Settings — the only place it
   * can be changed.
   */
  import ShowMore from "../components/ShowMore.svelte";
  import { PAGE_SIZE, page } from "../pagination";
  import { onDestroy, onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import PageState from "../components/PageState.svelte";
  import { chatProfiles, modelCatalogues, refreshModels } from "../models.svelte";
  import { ApiError } from "../api";
  import { contract } from "../generated/apiContract";
  import type { ExecutionProfileView, GoalList, GoalView } from "../generated/apiContract";
  import {
    ACTION_LABELS,
    STEP_REASONS,
    STEP_STATE_LABELS,
    VALIDATOR_LABELS,
    budgetLine,
    evidenceLabel,
    goalBadge,
    goalButtons,
    goalRefusal,
    profileSummary,
    stepProgress,
  } from "../goalPresentation";
  import { routeStateFromHash } from "../routeState";
  import { taskDetailHref } from "../taskHistory";
  import { relativeTime } from "../format";

  interface CriterionDraft { text: string; mandatory: boolean; validator: string }
  interface StepDraft { title: string; instruction: string; surface: string; depends_on: number[]; criteria: number[] }

  let list = $state<GoalList | null>(null);
  let shownGoals = $state(PAGE_SIZE);
  let loadError = $state<string | null>(null);
  let selected = $state<GoalView | null>(null);
  let busy = $state(false);
  let notice = $state<string | null>(null);
  let confirmStop = $state(false);
  let confirmNotes = $state<Record<string, string>>({});

  // Intake. A goal starts as a draft and has no permission to run until it is
  // accepted and started, so the form can be generous about what it takes.
  let composing = $state(false);
  let editingId = $state<string | null>(null);
  let title = $state("");
  let objective = $state("");
  let criteria = $state<CriterionDraft[]>([{ text: "", mandatory: true, validator: "steps_finish" }]);
  let steps = $state<StepDraft[]>([{ title: "", instruction: "", surface: "chat", depends_on: [], criteria: [0] }]);
  let formError = $state<string | null>(null);
  // The model every step runs on. Chosen here, judged with your fallbacks by
  // the execution profile when the plan is accepted and before each step runs.
  let modelProfile = $state("");
  let model = $state("");
  const profiles = $derived(chatProfiles());
  const selectedModelProfile = $derived(profiles.find((p) => p.selected) ?? null);

  function reason(err: unknown): string | null {
    return err instanceof ApiError ? err.reasonCode : null;
  }

  async function load() {
    try {
      list = await contract.listGoals();
      loadError = null;
      if (selected) {
        const fresh = list.goals.find((g) => g.goal_id === selected?.goal_id);
        if (fresh) selected = fresh;
      }
    } catch (err) {
      loadError = err instanceof Error ? err.message : "Could not load goals.";
    }
  }

  async function open(goalId: string) {
    confirmStop = false;
    notice = null;
    try {
      selected = await contract.readGoal(goalId);
      // The list card reads the same goal; keep it from saying "Working" while
      // the detail beside it says the goal settled.
      const fresh = selected;
      if (list) list = { ...list, goals: list.goals.map((g) => (g.goal_id === fresh.goal_id ? fresh : g)) };
    } catch (err) {
      notice = goalRefusal(reason(err), "This goal could not be opened.");
    }
  }

  function openFromHash() {
    const id = routeStateFromHash(window.location.hash).recordId;
    if (id && id.startsWith("goal_")) void open(id);
  }

  let timer: ReturnType<typeof setInterval> | null = null;
  onMount(() => {
    void load().then(openFromHash);
    void refreshModels();
    window.addEventListener("hashchange", openFromHash);
    // A running goal moves on the host's tick; reading it back every few
    // seconds keeps the page true without a stream the server does not have.
    timer = setInterval(() => {
      if (selected && ["running", "waiting"].includes(selected.status) && !busy) void open(selected.goal_id);
    }, 5000);
  });
  onDestroy(() => {
    window.removeEventListener("hashchange", openFromHash);
    if (timer) clearInterval(timer);
  });

  function resetForm() {
    editingId = null;
    title = "";
    objective = "";
    criteria = [{ text: "", mandatory: true, validator: "steps_finish" }];
    steps = [{ title: "", instruction: "", surface: "chat", depends_on: [], criteria: [0] }];
    modelProfile = "";
    model = "";
    formError = null;
  }

  function startNew() {
    resetForm();
    composing = true;
  }

  function editDraft(goal: GoalView) {
    const cIndex = new Map(goal.criteria.map((c, i) => [c.criterion_id, i]));
    const sIndex = new Map(goal.steps.map((s, i) => [s.step_id, i]));
    editingId = goal.goal_id;
    modelProfile = goal.model_profile ?? "";
    model = goal.model ?? "";
    title = goal.title;
    objective = goal.objective;
    criteria = goal.criteria.map((c) => ({ text: c.text, mandatory: c.mandatory, validator: c.validator }));
    steps = goal.steps.map((s) => ({
      title: s.title,
      instruction: s.instruction,
      surface: s.surface,
      depends_on: s.depends_on.map((d) => sIndex.get(d) ?? -1).filter((d) => d >= 0),
      criteria: s.criterion_ids.map((c) => cIndex.get(c) ?? -1).filter((c) => c >= 0),
    }));
    formError = null;
    composing = true;
  }

  function toggle(list: number[], value: number): number[] {
    return list.includes(value) ? list.filter((v) => v !== value) : [...list, value].sort((a, b) => a - b);
  }

  function removeCriterion(index: number) {
    criteria = criteria.filter((_, i) => i !== index);
    steps = steps.map((s) => ({
      ...s,
      criteria: s.criteria.filter((c) => c !== index).map((c) => (c > index ? c - 1 : c)),
    }));
  }

  function removeStep(index: number) {
    steps = steps
      .filter((_, i) => i !== index)
      .map((s) => ({ ...s, depends_on: s.depends_on.filter((d) => d !== index).map((d) => (d > index ? d - 1 : d)) }));
  }

  /** The picked model, or the one the picker shows as selected — never a `<model>` placeholder. */
  function chosenModel(): { model_profile?: string; model?: string } {
    if (modelProfile && model) return { model_profile: modelProfile, model };
    const shown = selectedModelProfile;
    if (shown && shown.model && !shown.model.includes("<")) return { model_profile: shown.profile_id, model: shown.model };
    return {};
  }

  async function submitPlan(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    formError = null;
    const body = {
      title: title.trim(),
      objective: objective.trim(),
      criteria: criteria.filter((c) => c.text.trim()).map((c) => ({ ...c, text: c.text.trim() })),
      steps: steps.map((s) => ({ ...s, title: s.title.trim(), instruction: s.instruction.trim() })),
      ...chosenModel(),
    };
    try {
      const goal = editingId && selected
        ? await contract.updateGoalPlan(editingId, { ...body, base_revision: selected.revision })
        : await contract.createGoal(body);
      composing = false;
      resetForm();
      selected = goal;
      await load();
    } catch (err) {
      formError = goalRefusal(reason(err), "The plan could not be saved.");
    } finally {
      busy = false;
    }
  }

  async function act(action: string) {
    if (!selected) return;
    if (action === "stop" && !confirmStop) {
      confirmStop = true;
      return;
    }
    busy = true;
    notice = null;
    const goalId = selected.goal_id;
    const body = { base_revision: selected.revision };
    try {
      if (action === "stop") {
        const stopped = await contract.stopGoal(goalId, body);
        selected = stopped.goal;
        notice = `Stopped. ${stopped.steps_done} step${stopped.steps_done === 1 ? "" : "s"} had finished; ${stopped.tasks_stopped} running task${stopped.tasks_stopped === 1 ? " was" : "s were"} stopped.`;
      } else {
        const calls: Record<string, typeof contract.acceptGoal> = {
          accept: contract.acceptGoal,
          start: contract.startGoal,
          pause: contract.pauseGoal,
          resume: contract.resumeGoal,
          archive: contract.archiveGoal,
        };
        selected = await calls[action](goalId, body);
      }
      confirmStop = false;
      await load();
    } catch (err) {
      notice = goalRefusal(reason(err));
      if (reason(err) === "goal_revision_stale") await open(goalId);
    } finally {
      busy = false;
    }
  }

  async function confirmCriterion(criterionId: string) {
    if (!selected) return;
    busy = true;
    notice = null;
    try {
      selected = await contract.confirmGoalCriterion(selected.goal_id, criterionId, {
        base_revision: selected.revision,
        note: confirmNotes[criterionId] ?? "",
      });
      await load();
    } catch (err) {
      notice = goalRefusal(reason(err));
    } finally {
      busy = false;
    }
  }

  const activeProfile = $derived<ExecutionProfileView | null>(list?.active_profile ?? null);
  const stepTitles = $derived(new Map((selected?.steps ?? []).map((s) => [s.step_id, s.title])));
</script>

<div class="goals">
  <header class="goals-head">
    <div>
      <h2>Goals</h2>
      <p class="muted">An outcome Raiker works toward across sessions. Each step runs as an ordinary task, under the same permissions and approvals.</p>
    </div>
    <button type="button" class="btn btn-primary btn-sm" onclick={startNew} disabled={busy}>New goal</button>
  </header>

  <p class="profile-line" data-testid="goal-profile-line">
    {#if activeProfile}
      <strong>Runs under {activeProfile.name}</strong> — {profileSummary(activeProfile)}
    {:else}
      <strong>No execution profile yet.</strong> A goal can be drafted now and accepted once one is chosen.
    {/if}
    <a href="#/settings?tab=execution-profiles">{activeProfile ? "Change in Settings" : "Choose one in Settings"}</a>
  </p>

  {#if composing}
    <form class="card goal-form" onsubmit={submitPlan} aria-labelledby="goal-form-h">
      <h3 id="goal-form-h" class="kicker">{editingId ? "Edit draft" : "New goal"}</h3>
      <label>Outcome <input bind:value={title} maxlength="120" required placeholder="Plan a weekend in Lisbon" /></label>
      <label>What a good result looks like <textarea bind:value={objective} maxlength="4000" rows="2"></textarea></label>

      <div class="model-row" role="group" aria-label="Goal model">
        <span>Steps run on</span>
        <ModelPicker {profiles} catalogues={modelCatalogues()} selectedProfile={selectedModelProfile} bind:profileId={modelProfile} bind:model />
        {#if !chosenModel().model}<span class="muted small">Choose a model before you accept the plan.</span>{/if}
      </div>

      <fieldset>
        <legend>Success criteria</legend>
        {#each criteria as criterion, index (index)}
          <div class="row">
            <input aria-label={`Criterion ${index + 1} text`} bind:value={criterion.text} maxlength="300" placeholder="An itinerary with three options" />
            <select aria-label={`How criterion ${index + 1} is met`} bind:value={criterion.validator}>
              {#each Object.entries(VALIDATOR_LABELS) as [value, label] (value)}<option {value}>{label}</option>{/each}
            </select>
            <label class="inline"><input type="checkbox" aria-label={`Criterion ${index + 1} is required`} bind:checked={criterion.mandatory} /> Required</label>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => removeCriterion(index)} aria-label={`Remove criterion ${index + 1}`}>Remove</button>
          </div>
        {/each}
        <button type="button" class="btn btn-sm" onclick={() => (criteria = [...criteria, { text: "", mandatory: true, validator: "owner_confirms" }])} disabled={criteria.length >= 12}>Add criterion</button>
      </fieldset>

      <fieldset>
        <legend>Steps</legend>
        {#each steps as step, index (index)}
          <div class="step-draft">
            <div class="row">
              <span class="step-no">{index + 1}</span>
              <input aria-label={`Step ${index + 1} title`} bind:value={step.title} maxlength="120" placeholder="Research" required />
              <select aria-label={`Step ${index + 1} works in`} bind:value={step.surface}>
                <option value="chat">Chat</option>
                <option value="build">Build</option>
              </select>
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => removeStep(index)} aria-label={`Remove step ${index + 1}`}>Remove</button>
            </div>
            <textarea aria-label={`Step ${index + 1} instruction`} bind:value={step.instruction} maxlength="4000" rows="2" placeholder="What this step should do" required></textarea>
            {#if index > 0}
              <div class="chips" role="group" aria-label={`Step ${index + 1} runs after`}>
                <span class="muted">Runs after</span>
                {#each Array.from({ length: index }, (_, i) => i) as before (before)}
                  <label class="inline"><input type="checkbox" aria-label={`Step ${index + 1} runs after step ${before + 1}`} checked={step.depends_on.includes(before)} onchange={() => (step.depends_on = toggle(step.depends_on, before))} /> Step {before + 1}</label>
                {/each}
              </div>
            {/if}
            {#if criteria.length}
              <div class="chips" role="group" aria-label={`Step ${index + 1} counts toward`}>
                <span class="muted">Counts toward</span>
                {#each criteria.map((_, i) => i) as ci (ci)}
                  <label class="inline"><input type="checkbox" aria-label={`Step ${index + 1} counts toward criterion ${ci + 1}`} checked={step.criteria.includes(ci)} onchange={() => (step.criteria = toggle(step.criteria, ci))} /> Criterion {ci + 1}</label>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
        <button type="button" class="btn btn-sm" onclick={() => (steps = [...steps, { title: "", instruction: "", surface: "chat", depends_on: steps.length ? [steps.length - 1] : [], criteria: [] }])} disabled={steps.length >= 12}>Add step</button>
      </fieldset>

      {#if formError}<p class="error" role="alert">{formError}</p>{/if}
      <div class="actions">
        <button type="submit" class="btn btn-primary btn-sm" disabled={busy || !title.trim()}>{editingId ? "Save draft" : "Save as draft"}</button>
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => { composing = false; resetForm(); }}>Cancel</button>
      </div>
      <p class="muted small">Saving makes a draft. Nothing runs until you accept the plan and start it.</p>
    </form>
  {/if}

  {#if loadError}
    <PageState state="error" title="Couldn't load goals" detail={loadError} />
  {:else if list === null}
    <PageState state="loading" title="Loading goals…" />
  {:else if list.goals.length === 0 && !composing}
    <div class="card">
      <EmptyState icon="tasks" title="No goals yet" body="Describe an outcome, how you will know it is done, and the steps toward it.">
        {#snippet action()}<button type="button" class="btn btn-primary" onclick={startNew}>New goal</button>{/snippet}
      </EmptyState>
    </div>
  {:else}
    <div class="layout">
      <div class="goal-column">
      <ul class="goal-list" aria-label="Goals">
        {#each page(list.goals, shownGoals) as goal (goal.goal_id)}
          {@const badge = goalBadge(goal.status)}
          <li>
            <button type="button" class="card card-interactive goal-card" class:selected={selected?.goal_id === goal.goal_id} onclick={() => open(goal.goal_id)} aria-current={selected?.goal_id === goal.goal_id}>
              <span class="goal-title">{goal.title}</span>
              <Badge variant={badge.variant} label={badge.label} />
              <span class="muted small">{stepProgress(goal)}{goal.reason_text ? ` · ${goal.reason_text}` : ""}</span>
            </button>
          </li>
        {/each}
      </ul>
      <ShowMore total={list.goals.length} shown={Math.min(shownGoals, list.goals.length)} noun="goals" onmore={() => (shownGoals += PAGE_SIZE)} />
      </div>

      {#if selected}
        {@const badge = goalBadge(selected.status)}
        <section class="card detail" aria-labelledby="goal-detail-h" data-testid="goal-detail">
          <header class="detail-head">
            <h3 id="goal-detail-h">{selected.title}</h3>
            <Badge variant={badge.variant} label={badge.label} />
          </header>
          {#if selected.reason_text}
            <p class="reason" role="status">{selected.reason_text}{selected.reason_detail && selected.reason === "profile_blocks_model" ? `: ${selected.reason_detail}` : ""}.
              {#if ["profile_blocks_model", "no_execution_profile", "profile_changed"].includes(selected.reason)}<a href="#/settings?tab=execution-profiles">Open Settings</a>{/if}
            </p>
          {/if}
          {#if selected.objective}<p>{selected.objective}</p>{/if}
          <p class="small muted">Steps run on {selected.model ?? "no model yet — edit the plan to choose one"}.</p>

          <div class="actions" role="group" aria-label="Goal actions">
            {#if selected.allowed_actions.includes("edit")}
              <button type="button" class="btn btn-sm" onclick={() => selected && editDraft(selected)} disabled={busy}>Edit plan</button>
            {/if}
            {#each goalButtons(selected) as action (action)}
              <button type="button" class="btn btn-sm" class:btn-primary={action === "accept" || action === "start" || action === "resume"} class:btn-danger={action === "stop" && confirmStop} onclick={() => act(action)} disabled={busy}>
                {action === "stop" && confirmStop ? "Stop every step now" : ACTION_LABELS[action]}
              </button>
            {/each}
          </div>
          {#if selected.status === "running" || selected.status === "waiting"}
            <p class="muted small">Pause starts nothing new and parks steps not yet started; a step already running finishes its current turn. Stop stops every step.</p>
          {/if}
          {#if notice}<p class="notice" role="alert">{notice}</p>{/if}

          <h4>Success criteria</h4>
          <ul class="criteria">
            {#each selected.criteria as criterion (criterion.criterion_id)}
              {@const evidence = evidenceLabel(criterion.evidence_kind)}
              <li>
                <span class="mark" aria-hidden="true">{evidence ? "✓" : "○"}</span>
                <span><strong>{criterion.text}</strong>{criterion.mandatory ? "" : " (optional)"}
                  <span class="muted small"> — {evidence ? `${evidence}${criterion.evidence_note ? `: ${criterion.evidence_note}` : ""}` : VALIDATOR_LABELS[criterion.validator] ?? criterion.validator}</span>
                </span>
                {#if !evidence && selected.allowed_actions.includes("confirm")}
                  <span class="confirm">
                    <input aria-label={`Note for ${criterion.text}`} placeholder="Note (optional)" maxlength="300" bind:value={confirmNotes[criterion.criterion_id]} />
                    <button type="button" class="btn btn-sm" onclick={() => confirmCriterion(criterion.criterion_id)} disabled={busy}>Confirm met</button>
                  </span>
                {/if}
              </li>
            {/each}
          </ul>

          <h4>Steps <span class="muted small">{stepProgress(selected)}</span></h4>
          <ol class="steps">
            {#each selected.steps as step (step.step_id)}
              <li>
                <span class="step-title">{step.title}</span>
                <span class="muted small">{step.surface === "build" ? "Build" : "Chat"} · {STEP_STATE_LABELS[step.state] ?? step.state}{step.reason && STEP_REASONS[step.reason] ? ` — ${STEP_REASONS[step.reason]}` : ""}</span>
                {#if step.depends_on.length}<span class="muted small">After {step.depends_on.map((d) => stepTitles.get(d) ?? d).join(", ")}</span>{/if}
                {#if step.task_id}<a class="small" href={taskDetailHref(step.task_id)}>Open its task</a>{/if}
              </li>
            {/each}
          </ol>

          <h4>Boundary and budget</h4>
          <p class="small">
            {#if selected.profile}
              <strong>{selected.profile.name}</strong> (version {selected.profile.version}{selected.profile_source === "project" ? ", this project's profile" : ""}) — {profileSummary(selected.profile)}
              {#if !selected.profile_current}<span class="warn"> Settings has changed it since this goal was accepted.</span>{/if}
            {:else}
              Chosen when the plan is accepted, from Settings.
            {/if}
          </p>
          {#if selected.status !== "draft"}<p class="small">{budgetLine(selected)}</p>{/if}
          {#if selected.providers_used.length}
            <p class="small">Answered by: {selected.providers_used.join(", ")}{selected.providers_outside_profile.length ? "" : " — all within the profile"}.</p>
          {/if}
          {#if selected.providers_outside_profile.length}
            <p class="warn small" role="alert">Outside the profile: {selected.providers_outside_profile.join(", ")}.</p>
          {/if}

          {#if selected.events.length}
            <details>
              <summary>History</summary>
              <ul class="history">
                {#each selected.events as event, index (index)}
                  <li><span class="muted small">{relativeTime(event.created_at)}</span> {event.kind.replace(/^goal_/, "").replaceAll("_", " ")}</li>
                {/each}
              </ul>
            </details>
          {/if}
        </section>
      {:else}
        <p class="muted pick">Choose a goal to see its criteria, steps and budget.</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .goals { display: grid; gap: var(--space-4); }
  .goals-head { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; flex-wrap: wrap; }
  .goals-head h2 { margin: 0; }
  .profile-line { margin: 0; display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: baseline; }
  .goal-form { display: grid; gap: 0.75rem; }
  .goal-form label { display: grid; gap: 0.25rem; }
  .model-row { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; }
  .goal-form label.inline, .chips label { display: inline-flex; gap: 0.3rem; align-items: center; }
  fieldset { border: 1px solid var(--border); border-radius: var(--r-md); padding: 0.75rem; display: grid; gap: 0.5rem; min-width: 0; }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
  .row input { flex: 1 1 12rem; min-width: 0; }
  .step-draft { display: grid; gap: 0.4rem; padding-bottom: 0.5rem; border-bottom: 1px dashed var(--border); }
  .step-no { font-weight: 600; min-width: 1.5rem; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; }
  .actions { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  .layout { display: grid; grid-template-columns: minmax(14rem, 20rem) minmax(0, 1fr); gap: 1rem; align-items: start; }
  @media (max-width: 760px) { .layout { grid-template-columns: minmax(0, 1fr); } }
  .goal-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.5rem; }
  /* QUI-L12 — list rows are at least 64 px, the same height across Work. */
  .goal-card { width: 100%; min-height: 64px; text-align: left; display: grid; gap: 0.3rem; justify-items: start; align-content: center; }
  .goal-card.selected { outline: 2px solid var(--accent); }
  .goal-title { font-weight: 600; overflow-wrap: anywhere; }
  .detail { display: grid; gap: 0.6rem; min-width: 0; }
  .detail-head { display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; }
  .detail-head h3 { margin: 0; overflow-wrap: anywhere; }
  .detail h4 { margin: 0.5rem 0 0; }
  .criteria, .steps, .history { margin: 0; padding-left: 1.2rem; display: grid; gap: 0.4rem; }
  .criteria { list-style: none; padding-left: 0; }
  .criteria li { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: baseline; }
  .mark { width: 1rem; }
  .confirm { display: inline-flex; gap: 0.4rem; flex-wrap: wrap; }
  .steps li { display: grid; gap: 0.15rem; }
  .step-title { font-weight: 600; }
  .muted { color: var(--text-2); }
  .small { font-size: var(--text-sm); }
  .reason { margin: 0; font-weight: 600; }
  .warn { color: var(--warn-text); }
  .error, .notice { margin: 0; }
  .error { color: var(--danger); }
  .pick { margin: 0; }
</style>
