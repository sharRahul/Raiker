<script lang="ts">
  /**
   * First launch, after the secure opening boundary.
   *
   * The boundary above this screen is unchanged and deliberately so: runtime
   * reachability, encrypted-store availability, owner registration versus
   * unlock, and bootstrap verification all still happen before the workspace
   * mounts, and none of them is collapsed into a generic failure.
   *
   * What changed is everything after it. This used to be
   * `Account → Model → Privacy → Backup → Finish`, which asked an owner to
   * understand infrastructure before they had used the product once: an Account
   * stage after the account was already created, a full provider matrix as the
   * opening move, a backup path requested before first use, and a final button
   * to "Open Workbench" — a place the rest of the product does not call by that
   * name. `firstRun.ts` holds the ordering and the wording; this file draws it.
   */
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { ModelProfile, SetupState } from "../apiTypes";
  import { modelName } from "../modelPresentation";
  import {
    PERMISSIONS_NOTE,
    PRIVACY_CHOICES,
    recommendedPath,
    SETUP_STAGE_LABELS,
    SETUP_STAGES,
    visibleStage,
  } from "../firstRun";
  import ProviderMatrix from "../components/ProviderMatrix.svelte";
  import Icon from "../components/Icon.svelte";
  import type { IconName } from "../icons";

  const stages = SETUP_STAGES;
  const labels = SETUP_STAGE_LABELS;
  let setup: SetupState | null = $state(null);
  let profiles: ModelProfile[] = $state([]);
  let chatProfiles: ModelProfile[] = $state([]);
  let backupTarget = $state("");
  let busy = $state(false);
  let error = $state("");
  /** The model this screen just pinned, so the stage can say so before moving on. */
  let picked = $state<string | null>(null);

  function body(update: Partial<SetupState>) {
    if (!setup) throw new Error("setup_not_loaded");
    return {
      status: update.status ?? setup.status,
      stage: update.stage ?? setup.stage,
      selected_profile_id: update.selected_profile_id === undefined ? setup.selected_profile_id : update.selected_profile_id,
      selected_model: update.selected_model === undefined ? setup.selected_model : update.selected_model,
      model_deferred: update.model_deferred ?? setup.model_deferred,
      privacy_mode: update.privacy_mode === undefined ? setup.privacy_mode : update.privacy_mode,
      backup_mode: update.backup_mode ?? setup.backup_mode,
      backup_target: update.backup_target === undefined ? setup.backup_target : update.backup_target,
      background_service_enabled: update.background_service_enabled ?? setup.background_service_enabled,
    };
  }

  async function load() {
    try {
      [setup, { profiles }] = await Promise.all([api.setup(), api.models()]);
      backupTarget = setup.backup_target ?? "";
    } catch {
      error = "Setup could not be loaded.";
    }
  }

  async function save(update: Partial<SetupState>) {
    busy = true;
    error = "";
    try { setup = await api.updateSetup(body(update)); }
    catch { error = "That setup choice could not be saved."; }
    finally { busy = false; }
  }

  async function loadProfiles() {
    try {
      const view = await api.models();
      profiles = view.profiles;
      // BUG-261 — the picker's switches have to open showing what is already
      // kept offered, or every one of them reads as off.
      chatProfiles = view.chat_profiles ?? [];
    } catch {
      // The rows keep the snapshot they already have rather than emptying: a
      // failed refresh is not evidence that a provider went away.
    }
  }

  /**
   * A row pinned a model. The wizard records the owner's choice on the setup
   * state, but does not jump the stage — the owner may want to connect a second
   * provider before moving on, and a screen that navigates itself out from under
   * a half-finished job is the reason the old one-shot list was frustrating.
   */
  async function chooseModel(profileId: string, model: string) {
    picked = modelName(model);
    await save({
      status: "in_progress",
      selected_profile_id: profileId,
      selected_model: model,
      model_deferred: false,
    });
    await loadProfiles();
  }

  async function deferModel() {
    await save({
      status: "in_progress",
      stage: "privacy",
      model_deferred: picked === null,
    });
  }

  /**
   * FIRST-07 — the answer is about where content may travel, and it says so.
   * Permissions still governs what Raiker may do; these two are not a second
   * authority system, and the old `Local-first` / `Balanced` pair read like one.
   */
  async function choosePrivacy(privacy_mode: "local_first" | "balanced") {
    await save({ status: "in_progress", stage: "finish", privacy_mode });
  }

  /** FIRST-08 — backup is offered at the end, not asked for before first use. */
  let wantsBackup = $state(false);

  /*
   * REM-LAUNCH-01 — the last stage says what is true of *this* setup.
   *
   * It said "Your Raiker is ready" unconditionally, directly above a summary
   * whose own Model row could read "Decide later". A first-run screen is the one
   * place an owner has no other way to check, so a readiness claim there is
   * taken at face value — and the first thing they do with it is press Chat and
   * meet a composer that cannot send.
   *
   * Readiness is per work mode, because the prerequisites differ: Chat and Build
   * need a model to talk to, Design needs a provider that answers with images.
   * Nothing is blocked — exploring a mode with no model connected is how an
   * owner finds out what it is — but an action that cannot do its work yet says
   * so and names the exact page that fixes it, rather than being presented as
   * ready alongside two that are.
   */
  const modelChosen = $derived.by(() => {
    const state: SetupState | null = setup;
    if (state === null) return false;
    return !state.model_deferred && (state.selected_model ?? "") !== "";
  });
  /** A profile Raiker could actually reach: detected locally or connected. */
  function usable(profile: ModelProfile): boolean {
    return (
      profile.connection_configured === true ||
      profile.configured === true ||
      profile.provider_detected === true
    );
  }
  const imageReady = $derived(
    profiles.some(
      (profile) =>
        usable(profile) &&
        ((profile.image_model ?? "") !== "" || (profile.image_models?.length ?? 0) > 0),
    ),
  );

  interface StartAction {
    id: string;
    label: string;
    icon: IconName;
    route: string;
    ready: boolean;
    /** What is missing, and the page that supplies it. Empty when ready. */
    missing: string;
    remedy: string;
    remedyLabel: string;
  }

  const startActions = $derived<StartAction[]>([
    {
      id: "chat",
      label: "Chat",
      icon: "chat",
      route: "#/chat",
      ready: modelChosen,
      missing: modelChosen ? "" : "Needs a model to answer with.",
      remedy: "#/models?tab=add",
      remedyLabel: "Choose a model",
    },
    {
      id: "build",
      label: "Build",
      icon: "code",
      route: "#/build",
      ready: modelChosen,
      missing: modelChosen ? "" : "Needs a model to answer with.",
      remedy: "#/models?tab=add",
      remedyLabel: "Choose a model",
    },
    {
      id: "design",
      label: "Design",
      icon: "design",
      route: "#/design",
      ready: imageReady,
      missing: imageReady ? "" : "Needs a provider that returns images.",
      remedy: "#/models?tab=add",
      remedyLabel: "Connect an image provider",
    },
  ]);

  /** The heading, and the sentence under it, scoped to what is actually set up. */
  const finishHeading = $derived(modelChosen ? "Your Raiker is ready" : "Setup saved");
  const finishNote = $derived(
    modelChosen
      ? "Start where the work is. Everything below stays available in Models, Settings and Permissions."
      : "You chose to decide about a model later, so Chat and Build have nothing to answer with yet. " +
        "Everything else is saved, and you can pick a model whenever you want to.",
  );

  async function createBackup() {
    if (!backupTarget.trim()) return;
    busy = true;
    error = "";
    try {
      const result = await api.createSetupBackup(backupTarget.trim());
      setup = await api.updateSetup(body({
        status: "in_progress",
        stage: "finish",
        backup_mode: "local",
        backup_target: result.setup.backup_target,
      }));
      wantsBackup = false;
    } catch { error = "The backup folder could not be verified. Choose a writable local folder."; }
    finally { busy = false; }
  }

  /**
   * FIRST-09 — finish into work, not administration.
   *
   * The destination is a Work surface the owner just met by name, or Home when
   * they would rather look around first. "Open Workbench" named a place the
   * rest of the product does not call by that name.
   */
  async function finish(route = "#/home") {
    await save({ status: "complete", stage: "finish" });
    window.location.hash = route;
  }

  // A function rather than an inline `setup?.stage`: control-flow analysis
  // narrows the `$state(null)` initializer at this position and would type the
  // access as `never`. The parameter carries the declared type instead.
  const stageOf = (state: SetupState | null) => (state === null ? null : state.stage);
  const stage = $derived(visibleStage(stageOf(setup)));
  const recommended = $derived(recommendedPath(profiles));
  /** The full matrix opens by itself only when there is nothing to recommend. */
  let showAllProviders = $state(false);
  const allProvidersOpen = $derived(showAllProviders || recommended === null);

  onMount(load);
</script>

<section class="setup-shell" aria-labelledby="setup-title">
  <aside class="stage-rail" aria-label="Setup progress">
    <p class="rail-title">Your Raiker</p>
    <ol>
      {#each stages as railStage, index}
        <li class:active={stage === railStage} class:done={stages.indexOf(stage) > index}>
          <span>{index + 1}</span><strong>{labels[railStage]}</strong>
        </li>
      {/each}
    </ol>
  </aside>

  <div class="setup-content">
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if setup === null}
      <h2 id="setup-title">Preparing your setup…</h2>
    {:else if stage === "welcome"}
      <!-- FIRST-03 — the product model before the infrastructure. An owner who
           has not met Chat, Build and Design cannot tell what a provider choice
           is for. FIRST-02 — no Account stage: the account was created on the
           screen before this one. -->
      <header>
        <p class="eyebrow">01 · Welcome</p>
        <h2 id="setup-title">Meet Raiker</h2>
        <p>Your governed AI workspace for Chat, Build and Design. Two short questions and you are working.</p>
      </header>
      <div class="modes">
        <div class="mode"><Icon name="chat" size="md" /><strong>Chat</strong><span>Think something through, with memory, sources and approvals.</span></div>
        <div class="mode"><Icon name="code" size="md" /><strong>Build</strong><span>Work on a repository — plan, change, run, review the diff.</span></div>
        <div class="mode"><Icon name="design" size="md" /><strong>Design</strong><span>Research and generate images against a governed model.</span></div>
      </div>
      <p class="note">{PERMISSIONS_NOTE}</p>
      <div class="actions">
        <button class="primary" disabled={busy} onclick={() => save({ status: "in_progress", stage: "model" })}>Continue</button>
      </div>
    {:else if stage === "model"}
      <header>
        <p class="eyebrow">02 · Model</p>
        <h2 id="setup-title">Choose how Raiker should think</h2>
        <!-- FIRST-04 — connect, then discover, then choose a default. What a
             provider serves is discovered once and available everywhere; there
             is no step in between where models are kept or withheld. -->
        <p>Connect a provider or a runtime once. Every compatible model it serves becomes available in Chat, Build and Design, and you choose which one answers by default.</p>
      </header>
      {#if recommended !== null}
        <!-- FIRST-05 — the easiest true path first, the matrix on request. -->
        <div class="recommended">
          <p class="eyebrow">Recommended</p>
          <strong>{recommended.label}</strong>
          <span>{recommended.detail}</span>
        </div>
      {/if}
      {#if !allProvidersOpen}
        <div class="actions">
          <button class="quiet" onclick={() => (showAllProviders = true)}>Other options</button>
        </div>
      {/if}
      {#if allProvidersOpen}
        <ProviderMatrix
          {profiles}
          {chatProfiles}
          onchanged={() => void loadProfiles()}
          onselected={(profileId, model) => void chooseModel(profileId, model)}
        />
      {/if}
      {#if picked !== null}
        <p class="picked" role="status">{picked} is selected. Next, where model requests may travel.</p>
      {/if}
      <div class="actions">
        <!-- FIRST-06 — this is not the way out of an incomplete flow. Everything
             needed to connect a provider and pick a default is on this screen;
             the Models page is where deeper configuration lives. -->
        <a class="quiet" href="#/models">Advanced setup</a>
        <button class="primary" disabled={busy} onclick={deferModel}>{picked === null ? "Decide later" : "Continue"}</button>
      </div>
    {:else if stage === "privacy"}
      <header>
        <p class="eyebrow">03 · Privacy</p>
        <!-- FIRST-07 — one question about where content travels. "Local-first"
             and "Balanced" read as a second authority system standing beside
             Permissions, which they are not. -->
        <h2 id="setup-title">Where may Raiker send model requests?</h2>
        <p>Permissions still govern what Raiker may do. This is only about where your words go.</p>
      </header>
      <div class="choice-list">
        {#each PRIVACY_CHOICES as choice (choice.mode)}
          <button aria-label={choice.label} disabled={busy} onclick={() => choosePrivacy(choice.mode)}>
            <strong>{choice.label}</strong><span>{choice.detail}</span>
          </button>
        {/each}
      </div>
      <div class="actions"><button class="quiet" onclick={() => save({ stage: "model" })}>Back</button></div>
    {:else}
      <header>
        <p class="eyebrow">04 · {finishHeading === "Your Raiker is ready" ? "Ready" : "Saved"}</p>
        <!-- REM-LAUNCH-01 — a readiness claim scoped to what was actually set
             up. This said "Your Raiker is ready" above a summary that could read
             "Decide later" on the very next line. -->
        <h2 id="setup-title">{finishHeading}</h2>
        <p>{finishNote}</p>
      </header>
      <!-- FIRST-09 — finish into work. The three Work modes the welcome screen
           introduced, as the three things to do next — each saying whether it
           can do its work yet, and naming the page that fixes it if not. -->
      <div class="start-work">
        {#each startActions as action (action.id)}
          <div class="mode-cell" class:unready={!action.ready}>
            <button class="mode-start" disabled={busy} onclick={() => finish(action.route)}>
              <Icon name={action.icon} size="md" />
              <strong>{action.label}</strong>
            </button>
            {#if !action.ready}
              <p class="mode-missing">
                {action.missing}
                <a href={action.remedy}>{action.remedyLabel}</a>
              </p>
            {/if}
          </div>
        {/each}
      </div>
      <dl class="summary">
        <div><dt>Model</dt><dd>{setup.model_deferred ? "Decide later" : setup.selected_model ?? "Not selected"}</dd></div>
        <div><dt>Model requests</dt><dd>{setup.privacy_mode === "local_first" ? "Local only" : "Local, and connected providers"}</dd></div>
        <div><dt>Backup</dt><dd>{setup.backup_verified_at ? "Verified" : "Recommended"}</dd></div>
      </dl>
      <!-- FIRST-08 — backup is recommended, not a stage that stands between an
           owner and their first turn. It is still real: nothing claims a backup
           exists until Raiker has written and verified an encrypted snapshot. -->
      <div class="optional">
        <p class="eyebrow">Optional setup</p>
        {#if setup.backup_verified_at}
          <p class="note">Backup verified at {setup.backup_target}.</p>
        {:else if wantsBackup}
          <label>Local, removable, or NAS folder<input bind:value={backupTarget} placeholder="Full path to a backup folder" /></label>
          <div class="actions">
            <button class="quiet" onclick={() => (wantsBackup = false)}>Cancel</button>
            <button class="primary" disabled={busy || !backupTarget.trim()} onclick={createBackup}>Create and verify backup</button>
          </div>
        {:else}
          <div class="actions">
            <button class="quiet" onclick={() => (wantsBackup = true)}>Set up backup</button>
            <a class="quiet" href="#/settings">Review privacy</a>
            <a class="quiet" href="#/capabilities">Review permissions</a>
          </div>
        {/if}
      </div>
      <div class="actions">
        <button class="quiet" onclick={() => save({ stage: "privacy" })}>Back</button>
        <button class="primary" disabled={busy} onclick={() => finish("#/home")}>Start using Raiker</button>
      </div>
    {/if}
  </div>
</section>

<style>
  .setup-shell { width: min(68rem, 100%); margin: 0 auto; display: grid; grid-template-columns: 13rem minmax(0, 1fr); gap: clamp(1.5rem, 5vw, 4rem); padding: clamp(1rem, 4vw, 3rem); }
  /* Which of the five stages you are on is the one thing worth keeping in
     view while the model list under it is scrolled; the rail used to leave
     with it. */
  .stage-rail { border-right: 1px solid var(--border); padding-right: var(--space-4); position: sticky; top: var(--space-4); align-self: start; }
  .rail-title { margin: 0 0 var(--space-4); color: var(--text-1); font-family: var(--font-serif); font-size: var(--text-xl); }
  ol { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
  li { display: grid; grid-template-columns: 1.7rem 1fr; align-items: center; gap: var(--space-2); color: var(--text-3); }
  li > span { display: grid; place-items: center; width: 1.55rem; height: 1.55rem; border: 1px solid var(--neutral-border); border-radius: 50%; font-family: var(--font-mono); font-size: var(--text-2xs); }
  li.active { color: var(--accent); } li.active > span { background: var(--accent); border-color: var(--accent); color: white; } li.done:not(.active) { color: var(--text-2); }
  .setup-content { min-width: 0; display: grid; align-content: start; gap: var(--space-4); }
  header { max-width: 45rem; } /* Shared `.eyebrow` sets size, weight, caps and tracking. First run keeps
     the mono face and a little more room under it. */
  .eyebrow { margin: 0 0 .4rem; font-family: var(--font-mono); }
  h2 { margin: 0; color: var(--text-1); font-family: var(--font-serif); font-size: clamp(1.7rem, 4vw, 2.6rem); } header p:last-child { color: var(--text-2); line-height: 1.6; }
  .choice-list { display: grid; gap: var(--space-2); } .choice-list button { display: grid; gap: .3rem; padding: var(--space-4); border: 1px solid var(--neutral-border); border-radius: var(--r-lg); background: var(--surface); color: var(--text-2); text-align: left; }
  .choice-list button { cursor: pointer; } .choice-list button:hover { border-color: var(--accent-border); background: var(--accent-soft); } strong { color: var(--text-1); } span { font-size: var(--text-sm); line-height: 1.45; }
  .picked { margin: 0; color: var(--accent); font-size: var(--text-sm); font-weight: 650; }
  /* The three Work modes, drawn the same way in both places they appear: as an
     introduction on the welcome screen and as the first thing to do on the last
     one. Chat, Build and Design are peers, so the grid gives them equal room. */
  .modes, .start-work { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
  .mode, .mode-start { display: grid; justify-items: start; gap: .3rem; padding: var(--space-4); border: 1px solid var(--neutral-border); border-radius: var(--r-lg); background: var(--surface); color: var(--text-2); text-align: left; }
  .mode-start { cursor: pointer; width: 100%; }
  .mode-start:hover { border-color: var(--accent-border); background: var(--accent-soft); }
  /* REM-LAUNCH-01 — the mode stays usable; what it cannot do yet is said under
     it, with the page that supplies the missing piece. Never colour alone. */
  .mode-cell { display: grid; gap: var(--space-2); align-content: start; }
  .mode-cell.unready .mode-start { border-style: dashed; }
  .mode-missing { margin: 0; color: var(--text-3); font-size: var(--text-xs); line-height: 1.45; }
  .mode-missing a { color: var(--accent); font-weight: 650; }
  .note { margin: 0; color: var(--text-3); font-size: var(--text-sm); line-height: 1.5; max-width: 45rem; }
  /* Recommended is one sentence with a reason, not a card competing with the
     matrix below it: the point is that most owners need read no further. */
  .recommended { display: grid; gap: .25rem; padding: var(--space-4); border: 1px solid var(--accent-border); border-radius: var(--r-lg); background: var(--accent-soft); }
  .optional { display: grid; gap: var(--space-2); padding-top: var(--space-3); border-top: 1px solid var(--border); }
  label { display: grid; gap: var(--space-2); max-width: 36rem; color: var(--text-1); } input { padding: .75rem .9rem; border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--surface); color: var(--text-1); }
  .summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); margin: 0; } .summary div { padding: var(--space-3); border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--sunken); } dt { color: var(--text-3); font-family: var(--font-mono); font-size: var(--text-2xs); text-transform: uppercase; } dd { margin: .35rem 0 0; color: var(--text-1); }
  .actions { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; } .quiet, .primary { width: max-content; border-radius: var(--r-pill); padding: .55rem .9rem; font: inherit; font-size: var(--text-sm); font-weight: 750; cursor: pointer; text-decoration: none; }
  .quiet { border: 1px solid var(--neutral-border); background: var(--surface); color: var(--text-2); } .primary { border: 1px solid var(--accent-border); background: var(--accent); color: white; } .error { color: var(--danger); }
  @media (max-width: 760px) { .setup-shell { grid-template-columns: 1fr; } .modes, .start-work { grid-template-columns: 1fr; } .stage-rail { border-right: 0; border-bottom: 1px solid var(--border); padding: 0 0 var(--space-3); overflow-x: auto; } .rail-title { display: none; } ol { display: flex; min-width: max-content; } li { grid-template-columns: auto auto; } .summary { grid-template-columns: 1fr; } }
</style>
