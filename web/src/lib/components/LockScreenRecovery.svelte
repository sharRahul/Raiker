<script lang="ts">
  /**
   * BUG-323 — restoring a workspace from the lock screen.
   *
   * The lock screen said "restore the database from a backup" and offered no
   * way to: Account, where backups live, needs a sign-in, and a store that will
   * not open cannot sign anybody in. Shown only when the server says the store
   * will not open for a reason a backup can fix — this key does not open it, or
   * a newer Raiker shaped it — and the server re-checks that on every call.
   *
   * Restoring is one deliberate action per backup, with what it does said
   * beside it: the backup is verified, the database that would not open is
   * moved aside into quarantine (kept, not deleted), the copy is switched in,
   * and anything deleted since the backup stays deleted.
   */
  import { onMount } from "svelte";
  import { ApiError, recoveryBackups, recoveryRestore } from "../api";
  import type { BackupView, RecoveryBackupsView, RecoveryRestored } from "../generated/apiContract";
  import { formatTimestamp, relativeTime } from "../format";

  let { onRestored }: { onRestored: (restored: RecoveryRestored) => void } = $props();

  let view = $state<RecoveryBackupsView | null>(null);
  let loadError = $state<string | null>(null);
  let confirming = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let failure = $state<string | null>(null);
  let restored = $state<RecoveryRestored | null>(null);

  const REASONS: Record<string, string> = {
    recovery_loopback_only: "Restoring from here works only in a browser on the machine Raiker runs on.",
    recovery_not_needed: "The workspace opens now — reload this page to sign in.",
    recovery_not_possible: "A backup cannot fix why this workspace will not open.",
    backup_not_verified: "That backup did not verify, so nothing was changed.",
    unknown_backup: "That backup is no longer there.",
  };

  async function load() {
    try {
      const answer = await recoveryBackups();
      if (!answer || !Array.isArray(answer.backups)) throw new Error("unexpected_shape");
      view = answer;
      loadError = null;
    } catch (e) {
      const code = e instanceof ApiError ? e.reasonCode : null;
      loadError = (code && REASONS[code]) ?? "The backups in this workspace could not be listed.";
    }
  }

  function size(bytes: number): string {
    return bytes >= 1_048_576 ? `${(bytes / 1_048_576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  /** Why a backup cannot be restored here, or null when it can. */
  function blocked(backup: BackupView): string | null {
    if (!backup.opens_here) return "Made by a newer Raiker — restore it with that version.";
    if (view && backup.key_fingerprint !== view.key_fingerprint) return "Made with another workspace key.";
    if (backup.state !== "verified") return backup.detail || "Did not verify when last checked.";
    return null;
  }

  async function restore(backup: BackupView) {
    busy = backup.backup_id;
    failure = null;
    try {
      restored = await recoveryRestore(backup.backup_id);
      confirming = null;
      onRestored(restored);
    } catch (e) {
      const code = e instanceof ApiError ? e.reasonCode : null;
      failure = (code && REASONS[code]) ?? "The restore did not complete. Nothing in the workspace was changed.";
      await load();
    } finally {
      busy = null;
    }
  }

  const deletionsApplied = $derived(
    restored ? Object.values(restored.deletions_applied).reduce((sum, n) => sum + n, 0) : 0,
  );

  onMount(load);
</script>

<section class="recovery" aria-labelledby="recovery-heading" data-testid="lock-recovery">
  <h2 id="recovery-heading">Restore from a backup</h2>
  {#if restored}
    <div class="done" role="status" data-testid="lock-recovery-done">
      <p><strong>Restored.</strong> The workspace opens again — sign in below.</p>
      <p class="sub">
        It holds {restored.counts.sessions ?? 0} conversations and {restored.counts.approved_memory ?? 0} memories.
        {#if deletionsApplied > 0}{deletionsApplied} {deletionsApplied === 1 ? "deletion" : "deletions"} made since the backup
          {deletionsApplied === 1 ? "was" : "were"} applied again.{/if}
        The database that would not open is kept in <code>{restored.quarantine}</code>.
      </p>
    </div>
  {:else}
    <p class="sub">
      {view?.reason === "store_schema_newer"
        ? "A newer Raiker last opened this workspace. Start that version again, or go back to a backup this version can open — anything changed since that backup is lost from the workspace, though the newer database is kept."
        : "Restoring puts a verified backup in place of the database that will not open. That database is moved aside, not deleted, and anything you deleted since the backup stays deleted."}
    </p>
    {#if failure}<p class="notice notice-danger" role="alert">{failure}</p>{/if}
    {#if loadError}
      <p class="sub" data-testid="lock-recovery-unreadable">{loadError}</p>
    {:else if view && view.backups.length === 0}
      <p class="sub" data-testid="lock-recovery-none">
        This workspace has no backups. Restore <code>.raiker/app.key</code> if it was replaced, or copy a
        backup you made yourself into place with Raiker stopped.
      </p>
    {:else if view}
      <ul class="backups">
        {#each view.backups as backup (backup.backup_id)}
          {@const why = blocked(backup)}
          <li data-testid="lock-recovery-backup">
            <div class="what">
              <strong>{backup.reason === "pre_migration" ? "Before an update" : "Taken by you"}</strong>
              <span title={formatTimestamp(backup.created_at)}>{relativeTime(backup.created_at)}</span>
              <span>{size(backup.size_bytes)} · {backup.counts.sessions ?? 0} conversations · {backup.counts.approved_memory ?? 0} memories</span>
              {#if why}<span class="blocked">{why}</span>{/if}
            </div>
            {#if !why}
              {#if confirming === backup.backup_id}
                <div class="confirm">
                  <button type="button" class="btn btn-primary btn-sm" disabled={busy !== null} onclick={() => void restore(backup)}>
                    {busy === backup.backup_id ? "Restoring…" : "Restore this backup"}
                  </button>
                  <button type="button" class="btn btn-ghost btn-sm" disabled={busy !== null} onclick={() => (confirming = null)}>Cancel</button>
                </div>
              {:else}
                <button type="button" class="btn btn-soft btn-sm" disabled={busy !== null} onclick={() => (confirming = backup.backup_id)}>
                  Restore…
                </button>
              {/if}
            {/if}
          </li>
        {/each}
      </ul>
    {:else}
      <p class="sub">Reading this workspace's backups…</p>
    {/if}
  {/if}
</section>

<style>
  .recovery { border: 1px solid var(--border); border-radius: var(--r-lg); padding: var(--space-3) var(--space-4); margin: 0 0 var(--space-4); background: var(--surface); }
  .recovery h2 { font-size: var(--text-md); margin: 0 0 var(--space-1); }
  .sub { color: var(--text-2); font-size: var(--text-sm); margin: 0 0 var(--space-2); }
  .sub code, .done code { overflow-wrap: anywhere; }
  .backups { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  .backups li {
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: var(--space-2);
    border: 1px solid var(--neutral-border); border-radius: var(--r-md); padding: var(--space-2) var(--space-3);
  }
  .what { display: grid; gap: 0.1rem; font-size: var(--text-sm); color: var(--text-2); min-width: 0; }
  .what strong { color: var(--text-1); }
  .blocked { color: var(--danger); }
  .confirm { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .done p { margin: 0 0 var(--space-1); }
</style>
