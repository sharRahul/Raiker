<script lang="ts">
  /**
   * RU-17 — Settings › Backups › Move to another machine.
   *
   * A backup opens only on this machine. A move file opens anywhere, with a
   * passphrase the owner chooses here. It carries the workspace key inside
   * its seal, so making one asks for the password (and a code, with two-step
   * sign-in), as rotating that key does. Provider keys stay behind.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import { withFreshMfa } from "../remoteAccess";
  import { exportMoveFile, MIN_PASSPHRASE, moveProblem } from "../move";
  import FormDialog from "./FormDialog.svelte";

  let mfaEnrolled = $state(false);
  let open = $state(false);
  let passphrase = $state("");
  let again = $state("");
  let password = $state("");
  let code = $state("");
  let busy = $state(false);
  let problem = $state<string | null>(null);
  let saved = $state<string | null>(null);

  const mismatch = $derived(again.length > 0 && again !== passphrase);
  const ready = $derived(
    passphrase.length >= MIN_PASSPHRASE && again === passphrase && password.length > 0 && (!mfaEnrolled || code.trim().length >= 6),
  );

  onMount(async () => {
    try {
      mfaEnrolled = (await api.settings()).status.mfa_enrolled;
    } catch {
      mfaEnrolled = false;
    }
  });

  function begin() {
    passphrase = again = password = code = "";
    problem = null;
    open = true;
  }

  async function make() {
    if (!ready) return;
    busy = true;
    problem = null;
    try {
      saved = await withFreshMfa(password, code.trim(), () => exportMoveFile(passphrase));
      open = false;
    } catch (e) {
      problem =
        e instanceof ApiError && e.status === 401
          ? "That password or code was not accepted. No file was made."
          : moveProblem(e);
    } finally {
      busy = false;
      password = code = "";
    }
  }
</script>

<section class="card" aria-labelledby="move-h" data-testid="move-export-card">
  <h2 id="move-h">Move to another machine</h2>
  <p class="sub">
    One file with your account, conversations, memory, notes, tasks, personas and settings, sealed with a passphrase you
    choose. On the new computer, choose <strong>I have a backup</strong> when Raiker first opens. Provider keys are not
    included; you enter them again there.
  </p>
  <div class="row">
    <button type="button" class="btn btn-sm" onclick={begin} data-testid="move-export-open">Make a move file</button>
  </div>
  {#if saved}
    <p class="notice notice-ok" role="status" data-testid="move-export-saved">
      Saved {saved}. Keep it and its passphrase apart; anyone with both can open your Raiker.
    </p>
  {/if}
</section>

{#if open}
  <FormDialog title="Make a move file" onclose={() => (open = false)}>
    <p class="sub">Raiker can't recover a forgotten passphrase. Write it down somewhere other than the file.</p>
    <label>
      Passphrase
      <input type="password" bind:value={passphrase} autocomplete="new-password" minlength={MIN_PASSPHRASE} data-testid="move-passphrase" />
    </label>
    <label>
      Passphrase again
      <input type="password" bind:value={again} autocomplete="new-password" data-testid="move-passphrase-again" />
    </label>
    {#if passphrase.length > 0 && passphrase.length < MIN_PASSPHRASE}
      <p class="hint">At least {MIN_PASSPHRASE} characters.</p>
    {:else if mismatch}
      <p class="hint">The two passphrases differ.</p>
    {/if}
    <label>
      Your Raiker password
      <input type="password" bind:value={password} autocomplete="current-password" data-testid="move-password" />
    </label>
    {#if mfaEnrolled}
      <label>
        Authenticator code
        <input type="text" inputmode="numeric" bind:value={code} autocomplete="one-time-code" />
      </label>
    {/if}
    {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
    <div class="actions">
      <button type="button" class="btn btn-ghost" onclick={() => (open = false)}>Cancel</button>
      <button type="button" class="btn btn-primary" disabled={busy || !ready} onclick={make} data-testid="move-export-make">
        {busy ? "Sealing…" : "Make and save"}
      </button>
    </div>
  </FormDialog>
{/if}

<style>
  .card { margin-top: var(--space-4); }
  .card > h2 { margin: 0 0 var(--space-2); font-size: var(--text-md); font-weight: 650; }
  .sub { color: var(--text-muted); margin: 0 0 var(--space-3); max-width: 62ch; }
  .row { display: flex; gap: var(--space-2); }
  .hint { color: var(--text-muted); font-size: var(--text-sm); margin: 0; }
  label { display: grid; gap: var(--space-1); margin-bottom: var(--space-3); }
  .actions { display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
