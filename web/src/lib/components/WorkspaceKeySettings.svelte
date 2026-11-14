<script lang="ts">
  /**
   * BUG-354 — Settings › Security › Workspace key.
   *
   * `.raiker/app.key` opens the encrypted database and seals Raiker's own
   * secrets. An owner who thinks it was copied can rotate it here: Raiker takes
   * a verified backup first, re-keys the database, re-seals the secrets and
   * keeps the old key for the backups made with it. Rotation replaces the one
   * secret the workspace has, so it asks for the password (and a code, with
   * two-step sign-in) on a five-minute elevated session.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import { withFreshMfa } from "../remoteAccess";
  import { failure } from "../errorCopy";
  import type { BackupsView, KeyRotated } from "../generated/apiContract";
  import FormDialog from "./FormDialog.svelte";

  // `embedded` renders the rows only, inside a card the page already draws
  // (Settings › Security puts them under Encryption and the vault).
  let { mfaEnrolled = false, embedded = false }: { mfaEnrolled?: boolean; embedded?: boolean } = $props();

  let view = $state<BackupsView | null>(null);
  let loadError = $state<string | null>(null);
  let panel = $state<"rotate" | null>(null);
  /** The retired key the dialog would discard, when it is open for that. */
  let discarding = $state<string | null>(null);
  let password = $state("");
  let code = $state("");
  let busy = $state(false);
  let problem = $state<string | null>(null);
  let rotated = $state<KeyRotated | null>(null);

  async function load() {
    try {
      const answer = await api.backups();
      if (!answer || typeof answer.key_fingerprint !== "string") throw new Error("unexpected_shape");
      view = answer;
      loadError = null;
    } catch (e) {
      loadError = failure("The workspace key could not be read", "Nothing was changed.", "Reload the page.", e);
    }
  }

  /** Backups that open only with a retired key Raiker still keeps. */
  const onRetired = $derived(
    view === null
      ? []
      : view.backups.filter(
          (b) => b.key_fingerprint !== view!.key_fingerprint && (view!.retired_key_fingerprints ?? []).includes(b.key_fingerprint),
        ),
  );
  const ready = $derived(password.length > 0 && (!mfaEnrolled || code.trim().length >= 6));

  function open(fingerprint: string | null = null) {
    password = "";
    code = "";
    problem = null;
    discarding = fingerprint;
    panel = "rotate";
  }

  async function rotate() {
    if (!ready) return;
    busy = true;
    problem = null;
    try {
      rotated = await withFreshMfa(password, code.trim(), () => api.rotateWorkspaceKey());
      panel = null;
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        problem = "That password or code was not accepted. The key was not changed.";
      } else {
        problem = failure("The key was not rotated", "The current key stays in force and nothing was lost.", "Try again, or take a backup first from Settings › Backups.", e);
      }
    } finally {
      busy = false;
      password = "";
      code = "";
    }
  }

  async function discard() {
    const fingerprint = discarding;
    if (!ready || fingerprint === null) return;
    busy = true;
    problem = null;
    try {
      await withFreshMfa(password, code.trim(), () => api.discardRetiredKey(fingerprint));
      panel = null;
      discarding = null;
      await load();
    } catch (e) {
      problem =
        e instanceof ApiError && e.status === 401
          ? "That password or code was not accepted. The retired key is still kept."
          : failure("The retired key was not discarded", "It is still kept.", "Try again.", e);
    } finally {
      busy = false;
      password = "";
      code = "";
    }
  }

  onMount(load);
</script>

{#snippet rows()}
  {#if loadError}
    <p class="problem" role="alert">{loadError}</p>
  {/if}
  <div class="setting-row">
    <h3>Workspace key</h3>
    <span class="setting-value" data-testid="workspace-key-fingerprint">
      {view === null ? "Reading…" : view.key_fingerprint}
    </span>
    <button type="button" class="btn btn-sm" disabled={view === null || busy} onclick={() => open()}>Rotate</button>
  </div>
  {#if view && (view.retired_key_fingerprints ?? []).length > 0}
    {#each view.retired_key_fingerprints as fingerprint (fingerprint)}
      {@const count = view.backups.filter((b) => b.key_fingerprint === fingerprint).length}
      <div class="setting-row">
        <h3>Retired key</h3>
        <span class="setting-value">{fingerprint} · kept for {count} backup{count === 1 ? "" : "s"}</span>
        <button type="button" class="btn btn-sm btn-ghost" disabled={busy} onclick={() => open(fingerprint)}>Discard</button>
      </div>
    {/each}
  {/if}
  {#if rotated}
    <p class="notice notice-ok" role="status" data-testid="workspace-key-rotated">
      Rotated and verified. The key in use is now {rotated.new_fingerprint}; {rotated.resealed} sealed secret{rotated.resealed === 1 ? " was" : "s were"} re-sealed.
      {#if rotated.backups_on_retired_key.length > 0}
        {rotated.backups_on_retired_key.length} backup{rotated.backups_on_retired_key.length === 1 ? "" : "s"} made before now still need{rotated.backups_on_retired_key.length === 1 ? "s" : ""} the old key, which Raiker keeps until you discard it.
      {/if}
    </p>
  {/if}
{/snippet}

{#if embedded}
  <div class="embedded" data-testid="workspace-key-card">{@render rows()}</div>
{:else}
  <section class="card" aria-labelledby="workspace-key-h" data-testid="workspace-key-card">
    <h2 id="workspace-key-h">Workspace key</h2>
    {@render rows()}
  </section>
{/if}

{#if panel === "rotate"}
  <FormDialog title={discarding ? "Discard the retired key" : "Rotate the workspace key"} onclose={() => (panel = null)}>
    {#if discarding}
      <p class="sub" data-testid="workspace-key-discard-note">
        Backups made with key {discarding} can no longer be verified or restored once it is discarded.
      </p>
    {:else}
    <p class="sub">
      Raiker takes a verified backup, re-keys the database with a new key, re-seals two-step sign-in and other sealed
      secrets, and checks the result. If anything fails, the current key stays in force.
    </p>
    {#if onRetired.length > 0 || (view && view.backups.length > 0)}
      <p class="sub" data-testid="workspace-key-backups-note">
        {view?.backups.length ?? 0} existing backup{(view?.backups.length ?? 0) === 1 ? "" : "s"} will need the current key
        afterwards. Raiker keeps it as a retired key, so they can still be restored as a separate copy.
      </p>
    {/if}
    {/if}
    <label>
      Password
      <input type="password" bind:value={password} autocomplete="current-password" />
    </label>
    {#if mfaEnrolled}
      <label>
        Authenticator code
        <input type="text" inputmode="numeric" bind:value={code} autocomplete="one-time-code" />
      </label>
    {/if}
    {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
    <div class="actions">
      <button type="button" class="btn btn-ghost" onclick={() => (panel = null)}>Cancel</button>
      {#if discarding}
        <button type="button" class="btn btn-danger" disabled={busy || !ready} onclick={discard}>
          {busy ? "Discarding…" : "Discard key"}
        </button>
      {:else}
        <button type="button" class="btn btn-primary" disabled={busy || !ready} onclick={rotate}>
          {busy ? "Rotating…" : "Back up and rotate"}
        </button>
      {/if}
    </div>
  </FormDialog>
{/if}

<style>
  .card > h2 { margin: 0 0 var(--space-2); font-size: var(--text-md); font-weight: 650; }
  .setting-row {
    display: grid;
    grid-template-columns: minmax(10rem, 1fr) minmax(0, 1.4fr) 11.5rem;
    align-items: center;
    gap: var(--space-3);
    min-height: 52px;
    border-top: 1px solid var(--border);
  }
  .card > .setting-row:first-of-type { border-top: none; }
  .setting-row > :last-child { justify-self: end; }
  .setting-row h3 { margin: 0; font-size: var(--text-sm); }
  .setting-value { color: var(--text-2); font-size: var(--text-sm); font-family: var(--font-mono, monospace); overflow-wrap: anywhere; }
  .sub { color: var(--text-2); font-size: var(--text-sm); }
  .problem { margin: var(--space-2) 0 0; color: var(--danger); font-size: var(--text-sm); }
  label { display: grid; gap: var(--space-1); margin-top: var(--space-2); font-size: var(--text-sm); }
  .actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
  @media (max-width: 640px) {
    .setting-row { grid-template-columns: 1fr; padding: var(--space-2) 0; }
    .setting-row > :last-child { justify-self: start; }
  }
</style>
