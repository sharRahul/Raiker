<script lang="ts">
  /**
   * First launch, after the secure opening boundary.
   *
   * The boundary above this screen is unchanged and deliberately so: runtime
   * reachability, encrypted-store availability, owner registration versus
   * unlock, and bootstrap verification all still happen before the workspace
   * mounts, and none of them is collapsed into a generic failure.
   *
   * After it, nothing asks an owner to understand infrastructure before they
   * have used the product once. `firstRun.ts` holds the ordering and the
   * wording; this file draws it.
   */
  import { onMount, tick } from "svelte";
  import { api } from "../api";
  import { providerName } from "../format";
  import { listCatalogue } from "../providerConnections";
  import type {
    ModelProfile,
    ModelReadinessView,
    SetupCheck,
    SetupState,
    SetupSystemReadiness,
    SetupVerification,
  } from "../apiTypes";
  import { modelName } from "../modelPresentation";
  import { drawsImages } from "../modelReadiness.svelte";
  import { setModels } from "../models.svelte";
  import {
    CHECK_STATE_LABELS,
    PRIVACY_CHOICES,
    recommendedPath,
    nextStage,
    previousStage,
    SETUP_STAGE_LABELS,
    stagesFor,
    visibleStage,
  } from "../firstRun";
  import ProviderMatrix from "../components/ProviderMatrix.svelte";
  import Icon from "../components/Icon.svelte";
  import Logo from "../components/Logo.svelte";
  import type { IconName } from "../icons";

  /** `desktop` when the installer already checked this computer (DIST-05). */
  let distribution = $state<string | null>(null);
  const stages = $derived(stagesFor(distribution));
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

  /**
   * BUG-331 — the step is drawn from `/api/setup` at once. `/api/models` asks
   * every provider and local runtime and is the slow read (seconds with a
   * dozen local models), so the providers fill in when it answers instead of
   * the whole screen reading *Preparing your setup…* until it does.
   */
  let profilesLoading = $state(true);

  async function load() {
    try {
      // The installation's provenance is a local read; a host that cannot
      // answer it is treated as one with no installer step, which keeps the
      // device and installation checks rather than skipping them.
      const [state, update] = await Promise.all([api.setup(), api.hostUpdate().catch(() => null)]);
      distribution = update?.installation?.distribution ?? null;
      setup = state;
      backupTarget = state.backup_target ?? "";
    } catch {
      error = "Setup could not be loaded.";
      profilesLoading = false;
      return;
    }
    try {
      const view = await api.models();
      profiles = view.profiles;
      // A model the owner already chose — here earlier, or as the global model
      // on Models before coming back — is a choice, not "decide later". Without
      // this the step offered only "Decide later" and Ready then claimed no
      // model was set up while Chat answered with one.
      const chosen =
        setup && !setup.model_deferred && setup.selected_model ? setup.selected_model : view.current_model;
      if (chosen) picked = modelName(chosen);
      if (setup && !setup.selected_model && view.current_profile_id && view.current_model) {
        setup = await api.updateSetup(body({
          selected_profile_id: view.current_profile_id,
          selected_model: view.current_model,
          model_deferred: false,
        }));
      }
    } catch {
      error = "The providers could not be listed. Reload to try again, or decide later.";
    } finally {
      profilesLoading = false;
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
      // The composer every work surface mounts reads the shared store. Without
      // this, Ready → Chat opened on the model selected before setup, with no
      // readiness check, beside the one the owner had just chosen and checked.
      setModels(view);
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
    // Choosing a model here is the owner's own act, so its first reachability
    // check is taken now, as **Test** would take it. The server takes a first
    // check by itself only for a provider with a saved connection, and a local
    // runtime has none: without this, the first turn after setup was refused
    // with "No readiness check exists for this exact model".
    try {
      await api.checkModelReadiness(profileId, model);
    } catch {
      // The outcome is on the model's own row; setup carries on either way.
    }
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
    await save({ status: "in_progress", stage: after("privacy"), privacy_mode });
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
  // REM-MODEL-01 — "could Raiker reach this" is answered in one place, never
  // here from `configured` and `provider_detected`, which call a provider whose
  // key the last check rejected usable.
  const imageReady = $derived(drawsImages(profiles));

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
      route: "#/new-chat",
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
  // Quiet UI — a sentence only when something is missing.
  const finishNote = $derived(modelChosen ? "" : "Chat and Build have nothing to answer with yet.");

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
  const stage = $derived(visibleStage(stageOf(setup), stages));
  const after = (current: typeof stage) => nextStage(stages, current);
  const before = (current: typeof stage) => previousStage(stages, current);
  /** BUG-332 — what each provider said when its models were last listed here. */
  let catalogueRefusals = $state<Record<string, string | null>>({});
  const candidate = $derived(recommendedPath(profiles, catalogueRefusals));
  /**
   * BUG-332 — a stored key is a claim, not a connection. Before a hosted
   * provider is recommended as connected, it is asked once what it serves; an
   * identity-linked key with no workspace answers that it needs one, and the
   * recommendation says so instead of offering models nobody can list.
   */
  const unconfirmed = $derived(
    candidate !== null &&
      candidate.action === "choose" &&
      !(candidate.profileId in catalogueRefusals) &&
      profiles.find((profile) => profile.profile_id === candidate.profileId)?.off_machine === true,
  );
  const recommended = $derived(unconfirmed ? null : candidate);
  let confirming = $state<string | null>(null);
  $effect(() => {
    if (!unconfirmed || candidate === null || confirming === candidate.profileId) return;
    const profileId = candidate.profileId;
    confirming = profileId;
    void listCatalogue(profileId).then((outcome) => {
      catalogueRefusals = {
        ...catalogueRefusals,
        [profileId]: outcome.ok
          ? outcome.list.status === "available"
            ? null
            : (outcome.list.reason_code ?? "provider_unavailable")
          : (outcome.reasonCode ?? "provider_unreachable"),
      };
    });
  });

  /** Open the providers and put the cursor in the field the recommendation names. */
  async function addWorkspace() {
    const label = recommended ? `${providerName(recommended.provider)} workspace ID` : "";
    showAllProviders = true;
    // The field appears once the row has asked its provider again, so look for
    // it for a moment rather than once.
    for (let attempt = 0; attempt < 30; attempt += 1) {
      await tick();
      const field = document.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`);
      if (field) {
        field.focus();
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  /** The full matrix opens by itself only when there is nothing to recommend. */
  let showAllProviders = $state(false);
  /** The provider whose picker the recommendation asked to open (BUG-344). */
  let pickerRequest = $state<string | null>(null);
  const allProvidersOpen = $derived(showAllProviders || (recommended === null && !unconfirmed));

  /*
   * DIST-05 — This device. Measured by the host, locally; the answer says what
   * the machine can run and never makes a dedicated GPU a requirement.
   */
  let system = $state<SetupSystemReadiness | null>(null);
  let systemError = $state("");
  async function loadSystem() {
    systemError = "";
    try { system = await api.setupSystem(); }
    catch { systemError = "This device could not be checked. You can continue and check again from Diagnostics."; }
  }

  /*
   * DIST-06 — Check. Every mandatory component from inside the running host,
   * then, when a model is chosen, one real request to it — the same readiness
   * check the Model stage and the Models page take. The request is the owner's
   * act: it runs when this stage opens or when they press Check again.
   */
  let verification = $state<SetupVerification | null>(null);
  let modelCheck = $state<ModelReadinessView | null>(null);
  let verifying = $state(false);
  let verifyError = $state("");
  async function runVerification() {
    verifying = true;
    verifyError = "";
    modelCheck = null;
    try {
      verification = await api.verifySetup();
      const state = setup;
      if (state && !state.model_deferred && state.selected_profile_id && state.selected_model) {
        try { modelCheck = await api.checkModelReadiness(state.selected_profile_id, state.selected_model); }
        catch { modelCheck = null; }
      }
    } catch {
      verifyError = "The installation check could not run. Open Diagnostics for details.";
    } finally {
      verifying = false;
    }
  }
  const mandatoryFailed = $derived(verification !== null && verification.failed.length > 0);

  $effect(() => {
    if (stage === "system" && system === null && systemError === "") void loadSystem();
    if (stage === "verify" && verification === null && !verifying && verifyError === "") void runVerification();
  });

  const stateLabel = (check: SetupCheck) => CHECK_STATE_LABELS[check.state];

  onMount(load);
</script>

{#snippet checkList(checks: SetupCheck[], label: string)}
  <ul class="checks" aria-label={label}>
    {#each checks as check (check.id)}
      <li class={`check ${check.state}`}>
        <span class="check-state">{stateLabel(check)}</span>
        <strong>{check.label}</strong>
        <span class="check-detail">{check.detail}</span>
        {#if check.remedy}<span class="check-remedy">{check.remedy}</span>{/if}
      </li>
    {/each}
  </ul>
{/snippet}

<section class="setup-shell" aria-labelledby="setup-title">
  <!-- A focused sheet, without the app's navigation around it (App.svelte):
       where you are, how far there is to go, and nothing else competing. -->
  <header class="setup-top">
    <span class="setup-brand"><Logo size={28} /><span>Set up Raiker</span></span>
    <ol class="stage-rail" aria-label="Setup progress">
      {#each stages as railStage, index}
        <li
          class:active={stage === railStage}
          class:done={stages.indexOf(stage) > index}
          aria-current={stage === railStage ? "step" : undefined}
        >
          <span class="seg" aria-hidden="true"></span><strong>{labels[railStage]}</strong>
        </li>
      {/each}
    </ol>
  </header>

  <div class="setup-content">
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if setup === null}
      <h2 id="setup-title">Preparing your setup…</h2>
    {:else if stage === "system"}
      <header>
        <h2 id="setup-title">What this computer can run</h2>
      </header>
      {#if systemError}
        <p class="note" role="alert">{systemError}</p>
      {:else if system === null}
        <p class="note" role="status" aria-live="polite">Checking this device…</p>
      {:else}
        {@render checkList(system.checks, "Device checks")}
        <div class="recommended">
          <p class="eyebrow">Local models on this device</p>
          <strong>About {system.recommended_local_model.parameters} parameters</strong>
          <span>{system.recommended_local_model.note} A model this size is {system.recommended_local_model.download} to download. Nothing is downloaded unless you choose a model.</span>
        </div>
        <dl class="summary">
          <div><dt>Your data</dt><dd class="path">{system.locations.data}</dd></div>
          <div><dt>Backups</dt><dd class="path">{system.locations.backups}</dd></div>
        </dl>
        {#if !system.ready}
          <p class="error" role="alert">This device does not meet a requirement above. Raiker may not work correctly until it is fixed.</p>
        {/if}
      {/if}
      <div class="actions">
        <button class="quiet" onclick={() => save({ stage: before("system") })}>Back</button>
        <button class="primary" disabled={busy} onclick={() => save({ status: "in_progress", stage: after("system") })}>Continue</button>
      </div>
    {:else if stage === "model"}
      <header>
        <h2 id="setup-title">Choose how Raiker should think</h2>
        <!-- FIRST-04 — connect, then discover, then choose a default. What a
             provider serves is discovered once and available everywhere; there
             is no step in between where models are kept or withheld. -->
      </header>
      {#if profilesLoading || unconfirmed}
        <!-- BUG-331 — the step is here; the providers are still answering. -->
        <p class="note providers-loading" role="status" aria-live="polite">
          {unconfirmed && candidate
            ? `Asking ${providerName(candidate.provider)} what it serves…`
            : "Looking for the providers and runtimes this device can reach…"}
        </p>
      {:else if recommended !== null}
        <!-- FIRST-05 — the easiest true path first, the matrix on request. -->
        <div class="recommended">
          <p class="eyebrow">Recommended</p>
          <strong>{recommended.label}</strong>
          <span>{recommended.detail}</span>
          {#if recommended.action === "workspace" && picked === null}
            <!-- BUG-332 — the one thing that stands between this key and its
                 models, with the field it names focused. -->
            <button class="primary choose" onclick={() => void addWorkspace()}>Add the workspace ID</button>
          {:else if !allProvidersOpen && picked === null}
            <!-- The recommendation asks for a model; the picker that answers it
                 is in the providers below, so it opens them — and, BUG-344, that
                 provider's picker, rather than a second "Choose a model". -->
            <button
              class="primary choose"
              onclick={() => {
                pickerRequest = recommended?.profileId ?? null;
                showAllProviders = true;
              }}>Choose a model</button>
          {/if}
        </div>
      {/if}
      {#if !profilesLoading && !unconfirmed && !allProvidersOpen}
        <div class="actions">
          <button class="quiet" onclick={() => (showAllProviders = true)}>Other options</button>
        </div>
      {/if}
      {#if !profilesLoading && !unconfirmed && allProvidersOpen}
        <ProviderMatrix
          {profiles}
          {chatProfiles}
          onchanged={() => void loadProfiles()}
          onselected={(profileId, model) => void chooseModel(profileId, model)}
          oncatalogue={(profileId, reasonCode) =>
            (catalogueRefusals = { ...catalogueRefusals, [profileId]: reasonCode })}
          openPickerFor={pickerRequest}
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
        <!-- FIRST-07 — one question about where content travels. "Local-first"
             and "Balanced" read as a second authority system standing beside
             Permissions, which they are not. -->
        <h2 id="setup-title">Where may Raiker send model requests?</h2>
      </header>
      <div class="choice-list">
        {#each PRIVACY_CHOICES as choice (choice.mode)}
          <button aria-label={choice.label} disabled={busy} onclick={() => choosePrivacy(choice.mode)}>
            <strong>{choice.label}</strong><span>{choice.detail}</span>
          </button>
        {/each}
      </div>
      <div class="actions"><button class="quiet" onclick={() => save({ stage: before("privacy") })}>Back</button></div>
    {:else if stage === "verify"}
      <header>
        <h2 id="setup-title">Checking your installation</h2>
      </header>
      {#if verifyError}
        <p class="error" role="alert">{verifyError}</p>
      {:else if verification === null || verifying}
        <p class="note" role="status" aria-live="polite">Checking…</p>
      {:else}
        {@render checkList(verification.checks, "Installation checks")}
        {#if modelCheck}
          <ul class="checks" aria-label="Model request">
            <li class={`check ${modelCheck.ready ? "pass" : "warn"}`}>
              <span class="check-state">{modelCheck.ready ? "Ready" : "Not ready"}</span>
              <strong>Request to {modelName(modelCheck.model)}</strong>
              <span class="check-detail">{modelCheck.summary}</span>
              {#if !modelCheck.ready && modelCheck.remediation}<span class="check-remedy">{modelCheck.remediation}</span>{/if}
            </li>
          </ul>
        {/if}
        {#if mandatoryFailed}
          <p class="error" role="alert">A required part is not working. <a href="#/diagnostics">Open Diagnostics</a> for the details, or reinstall Raiker.</p>
        {/if}
      {/if}
      <div class="actions">
        <button class="quiet" onclick={() => save({ stage: before("verify") })}>Back</button>
        <button class="quiet" disabled={verifying} onclick={() => void runVerification()}>Check again</button>
        <button class="primary" disabled={busy || verifying} onclick={() => save({ status: "in_progress", stage: "finish" })}>{mandatoryFailed ? "Continue anyway" : "Continue"}</button>
      </div>
    {:else}
      <header>
        <!-- REM-LAUNCH-01 — a readiness claim scoped to what was actually set
             up. This said "Your Raiker is ready" above a summary that could read
             "Decide later" on the very next line. -->
        <h2 id="setup-title">{finishHeading}</h2>
        {#if finishNote}<p>{finishNote}</p>{/if}
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
              <p class="mode-missing" title={action.missing}>
                <a href={action.remedy}>{action.remedyLabel}</a>
              </p>
            {/if}
          </div>
        {/each}
      </div>
      {#if setup.backup_verified_at}
        <p class="note">Backup verified at {setup.backup_target}.</p>
      {:else if wantsBackup}
        <!-- FIRST-08 — backup is offered, never a step in the way. Nothing
             claims a backup exists until an encrypted snapshot is verified. -->
        <label>Backup folder<input bind:value={backupTarget} placeholder="Full path to a local, removable or NAS folder" /></label>
        <div class="actions">
          <button class="quiet" onclick={() => (wantsBackup = false)}>Cancel</button>
          <button class="primary" disabled={busy || !backupTarget.trim()} onclick={createBackup}>Create and verify backup</button>
        </div>
      {/if}
      <div class="actions">
        <button class="quiet" onclick={() => save({ stage: before("finish") })}>Back</button>
        {#if !setup.backup_verified_at && !wantsBackup}
          <button class="quiet" onclick={() => (wantsBackup = true)}>Set up backup</button>
        {/if}
        <button class="primary" disabled={busy} onclick={() => finish("#/home")}>Start using Raiker</button>
      </div>
    {/if}
  </div>
</section>

<style>
  /* One focused column. The Setup window before sign-in has the same shape
     (desktop/static/setup.css), so installing and setting up read as one flow. */
  .setup-shell { width: min(52rem, 100%); margin: 0 auto; display: grid; align-content: start; gap: clamp(1.5rem, 4vw, 2.5rem); padding: clamp(1rem, 4vw, 2.5rem) clamp(1rem, 4vw, 3rem) var(--space-6); }
  /* Where you are stays in view while the model list under it is scrolled. */
  /* An opaque band the full width of the window, so the model list scrolls
     under it rather than through it. */
  .setup-top { position: sticky; top: 0; z-index: 1; display: grid; gap: var(--space-4); padding: var(--space-3) 0 var(--space-4); background: var(--bg); box-shadow: 0 0 0 100vmax var(--bg); clip-path: inset(0 -100vmax); border-bottom: 1px solid transparent; }
  .setup-brand { display: flex; align-items: center; gap: .6rem; color: var(--text-1); font-size: var(--text-sm); font-weight: 750; }
  /* Scoped to the rail: the check and goal lists below are lists too. */
  .stage-rail { list-style: none; margin: 0; padding: 0; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: .5rem; }
  .stage-rail li { display: grid; gap: .45rem; min-width: 0; color: var(--text-3); }
  .stage-rail li strong { color: inherit; font-size: var(--text-xs); font-weight: 650; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .seg { display: block; height: 4px; border-radius: 4px; background: var(--neutral-border); transition: background .3s ease; }
  .stage-rail li.done .seg { background: var(--accent); }
  .stage-rail li.active .seg { background: linear-gradient(90deg, var(--accent), var(--brand)); }
  .stage-rail li.active { color: var(--accent); } .stage-rail li.done:not(.active) { color: var(--text-2); }
  .setup-content { min-width: 0; display: grid; align-content: start; gap: var(--space-4); animation: setup-rise .35s ease both; }
  @keyframes setup-rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
  @media (prefers-reduced-motion: reduce) { .setup-content { animation: none; } }
  header { max-width: 45rem; } /* Shared `.eyebrow` sets size, weight, caps and tracking. First run keeps
     the mono face and a little more room under it. */
  .eyebrow { margin: 0 0 .4rem; font-family: var(--font-mono); }
  h2 { margin: 0; color: var(--text-1); font-size: clamp(1.7rem, 4vw, 2.6rem); } header p:last-child { color: var(--text-2); line-height: 1.6; }
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
  .recommended .choose { justify-self: start; margin-top: var(--space-2); }
  .recommended { display: grid; gap: .25rem; padding: var(--space-4); border: 1px solid var(--accent-border); border-radius: var(--r-lg); background: var(--accent-soft); }
  .optional { display: grid; gap: var(--space-2); padding-top: var(--space-3); border-top: 1px solid var(--border); }
  label { display: grid; gap: var(--space-2); max-width: 36rem; color: var(--text-1); } input { padding: .75rem .9rem; border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--surface); color: var(--text-1); }
  .summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); margin: 0; } .summary div { padding: var(--space-3); border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--sunken); } dt { color: var(--text-3); font-family: var(--font-mono); font-size: var(--text-2xs); text-transform: uppercase; } dd { margin: .35rem 0 0; color: var(--text-1); }
  .actions { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; } .quiet, .primary { width: max-content; border-radius: var(--r-pill); padding: .55rem .9rem; font: inherit; font-size: var(--text-sm); font-weight: 750; cursor: pointer; text-decoration: none; }
  .quiet { border: 1px solid var(--neutral-border); background: var(--surface); color: var(--text-2); } .primary { border: 1px solid var(--accent-border); background: var(--accent); color: white; } .error { color: var(--danger); }
  /* DIST-05/06 — check rows say their state in words, with colour as a second
     cue. Flat rows on one surface rather than a card per check: a dozen boxed
     rows read as a dozen problems even when every one of them passed. */
  .checks { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  .checks { gap: 0; border: 1px solid var(--neutral-border); border-radius: var(--r-lg); background: var(--surface); overflow: hidden; }
  .check { display: grid; grid-template-columns: .5rem minmax(0, 1fr) auto; align-items: baseline; column-gap: var(--space-3); row-gap: .1rem; padding: .7rem var(--space-4); }
  .check + .check { border-top: 1px solid var(--border); }
  .check::before { content: ""; width: .5rem; height: .5rem; border-radius: 50%; background: var(--success); align-self: center; grid-row: 1; }
  .check.warn::before { background: var(--warning); } .check.fail::before { background: var(--danger); } .check.info::before { background: var(--neutral-border); }
  .check > strong { grid-column: 2; grid-row: 1; font-size: var(--text-sm); }
  .check-state { grid-column: 3; grid-row: 1; font-family: var(--font-mono); font-size: var(--text-2xs); text-transform: uppercase; color: var(--text-3); }
  .check.warn .check-state { color: var(--warning); } .check.fail .check-state { color: var(--danger); }
  .check-detail, .check-remedy { grid-column: 2 / 4; color: var(--text-3); }
  .check-remedy { color: var(--text-1); font-weight: 600; }
  .path { font-family: var(--font-mono); font-size: var(--text-xs); overflow-wrap: anywhere; }
  @media (max-width: 760px) { .modes, .start-work { grid-template-columns: 1fr; } .stage-rail li strong { display: none; } .stage-rail li.active strong { display: block; } .summary { grid-template-columns: 1fr; } }
</style>
