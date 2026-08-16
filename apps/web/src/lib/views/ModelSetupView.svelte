<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { ModelProfile, SetupState } from "../apiTypes";
  import { modelName } from "../modelPresentation";
  import ProviderMatrix from "../components/ProviderMatrix.svelte";

  const stages = ["account", "model", "privacy", "backup", "finish"] as const;
  const labels = { account: "Account", model: "Model", privacy: "Privacy", backup: "Backup", finish: "Finish" };
  let setup: SetupState | null = $state(null);
  let profiles: ModelProfile[] = $state([]);
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
      ({ profiles } = await api.models());
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

  async function choosePrivacy(privacy_mode: "local_first" | "balanced") {
    await save({ status: "in_progress", stage: "backup", privacy_mode });
  }

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
    } catch { error = "The backup folder could not be verified. Choose a writable local folder."; }
    finally { busy = false; }
  }

  async function finish() {
    await save({ status: "complete", stage: "finish" });
    window.location.hash = "#/home";
  }

  onMount(load);
</script>

<section class="setup-shell" aria-labelledby="setup-title">
  <aside class="stage-rail" aria-label="Setup progress">
    <p class="rail-title">Your Raiker</p>
    <ol>
      {#each stages as stage, index}
        <li class:active={setup?.stage === stage} class:done={stage === "account" || (setup && stages.indexOf(setup.stage) > index)}>
          <span>{index + 1}</span><strong>{labels[stage]}</strong>
        </li>
      {/each}
    </ol>
  </aside>

  <div class="setup-content">
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if setup === null}
      <h2 id="setup-title">Preparing your setup…</h2>
    {:else if setup.stage === "model"}
      <header>
        <p class="eyebrow">02 · Model connection</p>
        <h2 id="setup-title">Choose where Raiker thinks</h2>
        <p>One row per provider. The three on this device are asked what they are serving; the rest take an API key and then answer with their own catalogue. Nothing is contacted until you ask a row to, and Raiker still runs a readiness check against the exact model before any model-backed work.</p>
      </header>
      <ProviderMatrix
        {profiles}
        onchanged={() => void loadProfiles()}
        onselected={(profileId, model) => void chooseModel(profileId, model)}
      />
      {#if picked !== null}
        <p class="picked" role="status">{picked} is selected. Continue to set your privacy boundary.</p>
      {/if}
      <div class="actions">
        <a class="quiet" href="#/models">Open the full Models page</a>
        <button class="primary" disabled={busy} onclick={deferModel}>{picked === null ? "Decide later" : "Continue"}</button>
      </div>
    {:else if setup.stage === "privacy"}
      <header>
        <p class="eyebrow">03 · Privacy boundary</p>
        <h2 id="setup-title">Choose your privacy boundary</h2>
        <p>This choice explains where content may travel. Permissions still govern every capability separately.</p>
      </header>
      <div class="choice-list">
        <button aria-label="Local-first" disabled={busy} onclick={() => choosePrivacy("local_first")}><strong>Local-first</strong><span>Prefer local models and keep network access off until you explicitly enable it.</span></button>
        <button aria-label="Balanced" disabled={busy} onclick={() => choosePrivacy("balanced")}><strong>Balanced</strong><span>Allow configured hosted models while keeping tool permissions and approvals in force.</span></button>
      </div>
      <div class="actions"><button class="quiet" onclick={() => save({ stage: "model" })}>Back</button></div>
    {:else if setup.stage === "backup"}
      <header>
        <p class="eyebrow">04 · Backup</p>
        <h2 id="setup-title">Create your first backup</h2>
        <p>No backup is configured until Raiker writes and verifies a real encrypted local snapshot.</p>
      </header>
      <label>Local, removable, or NAS folder<input bind:value={backupTarget} placeholder="D:\Raiker Backups" /></label>
      <div class="actions"><button class="quiet" onclick={() => save({ stage: "privacy" })}>Back</button><button class="quiet" onclick={() => save({ stage: "finish", backup_mode: "later" })}>Set up later</button><button class="primary" disabled={busy || !backupTarget.trim()} onclick={createBackup}>Create and verify backup</button></div>
    {:else}
      <header>
        <p class="eyebrow">05 · Ready</p>
        <h2 id="setup-title">Your Raiker is ready</h2>
        <p>Review what is proven now. Deferred choices stay visible in Models and Settings.</p>
      </header>
      <dl class="summary">
        <div><dt>Account</dt><dd>Owner account active</dd></div>
        <div><dt>Model</dt><dd>{setup.model_deferred ? "Decide later" : setup.selected_model ?? "Not selected"}</dd></div>
        <div><dt>Privacy</dt><dd>{setup.privacy_mode === "local_first" ? "Local-first" : "Balanced"}</dd></div>
        <div><dt>Backup</dt><dd>{setup.backup_verified_at ? "Verified" : "Not configured"}</dd></div>
      </dl>
      <div class="actions"><button class="quiet" onclick={() => save({ stage: "backup" })}>Back</button><button class="primary" disabled={busy} onclick={finish}>Open Workbench</button></div>
    {/if}
  </div>
</section>

<style>
  .setup-shell { width: min(68rem, 100%); margin: 0 auto; display: grid; grid-template-columns: 13rem minmax(0, 1fr); gap: clamp(1.5rem, 5vw, 4rem); padding: clamp(1rem, 4vw, 3rem); }
  .stage-rail { border-right: 1px solid var(--border); padding-right: var(--space-4); }
  .rail-title { margin: 0 0 var(--space-4); color: var(--text-1); font-family: var(--font-serif); font-size: 1.15rem; }
  ol { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
  li { display: grid; grid-template-columns: 1.7rem 1fr; align-items: center; gap: var(--space-2); color: var(--text-3); }
  li > span { display: grid; place-items: center; width: 1.55rem; height: 1.55rem; border: 1px solid var(--neutral-border); border-radius: 50%; font-family: var(--font-mono); font-size: .68rem; }
  li.active { color: var(--accent); } li.active > span { background: var(--accent); border-color: var(--accent); color: white; } li.done:not(.active) { color: var(--text-2); }
  .setup-content { min-width: 0; display: grid; align-content: start; gap: var(--space-4); }
  header { max-width: 45rem; } .eyebrow { margin: 0 0 .4rem; color: var(--accent); font-family: var(--font-mono); font-size: .7rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h2 { margin: 0; color: var(--text-1); font-family: var(--font-serif); font-size: clamp(1.7rem, 4vw, 2.6rem); } header p:last-child { color: var(--text-2); line-height: 1.6; }
  .choice-list { display: grid; gap: var(--space-2); } .choice-list button { display: grid; gap: .3rem; padding: var(--space-4); border: 1px solid var(--neutral-border); border-radius: var(--r-lg); background: var(--surface); color: var(--text-2); text-align: left; }
  .choice-list button { cursor: pointer; } .choice-list button:hover { border-color: var(--accent-border); background: var(--accent-soft); } strong { color: var(--text-1); } span { font-size: .82rem; line-height: 1.45; }
  .picked { margin: 0; color: var(--accent); font-size: .85rem; font-weight: 650; }
  label { display: grid; gap: var(--space-2); max-width: 36rem; color: var(--text-1); } input { padding: .75rem .9rem; border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--surface); color: var(--text-1); }
  .summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); margin: 0; } .summary div { padding: var(--space-3); border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--bg-2); } dt { color: var(--text-3); font-family: var(--font-mono); font-size: .7rem; text-transform: uppercase; } dd { margin: .35rem 0 0; color: var(--text-1); }
  .actions { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; } .quiet, .primary { width: max-content; border-radius: var(--r-pill); padding: .55rem .9rem; font: inherit; font-size: .8rem; font-weight: 750; cursor: pointer; text-decoration: none; }
  .quiet { border: 1px solid var(--neutral-border); background: var(--surface); color: var(--text-2); } .primary { border: 1px solid var(--accent-border); background: var(--accent); color: white; } .error { color: var(--danger); }
  @media (max-width: 760px) { .setup-shell { grid-template-columns: 1fr; } .stage-rail { border-right: 0; border-bottom: 1px solid var(--border); padding: 0 0 var(--space-3); overflow-x: auto; } .rail-title { display: none; } ol { display: flex; min-width: max-content; } li { grid-template-columns: auto auto; } .summary { grid-template-columns: 1fr; } }
</style>
