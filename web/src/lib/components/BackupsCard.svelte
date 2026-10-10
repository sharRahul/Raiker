<script lang="ts">
  /**
   * DEC-24 step 5 — backups Raiker makes itself, and restoring one somewhere new.
   *
   * The lock screen's advice for a damaged database is "restore it from a
   * backup", and until now Raiker made none. Each backup here is the database
   * exported encrypted by SQLCipher itself, with the memory files beside it,
   * checked before it is listed. The page says what a backup does *not* hold,
   * which key opens it, and that restoring writes a separate copy — your
   * running workspace is never replaced from this page.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type { BackupRestored, BackupsView, BackupView } from "../generated/apiContract";
  import { relativeTime } from "../format";

  let view = $state<BackupsView | null>(null);
  let loadError = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  let restored = $state<BackupRestored | null>(null);

  // DEC-24 step 5 — what a current backup leaves out. Checkpoint pre-images and
  // uploaded files are copied with the database, because its rows point at them.
  const NOT_INCLUDED: Record<string, string> = {
    event_log: "the audit log",
    attached_folders: "folders you attached to projects",
  };

  /** "12 checkpoint files · 3 uploads", or nothing for a backup that copied none. */
  function filesLabel(backup: BackupView): string {
    const trees = backup.trees ?? {};
    const parts: string[] = [];
    const checkpoints = trees.checkpoints?.files ?? 0;
    const uploads = trees.artifacts?.files ?? 0;
    if (checkpoints) parts.push(`${checkpoints} checkpoint file${checkpoints === 1 ? "" : "s"}`);
    if (uploads) parts.push(`${uploads} upload${uploads === 1 ? "" : "s"}`);
    return parts.length ? ` · ${parts.join(" · ")}` : "";
  }
  const STATE: Record<string, string> = {
    verified: "Verified",
    damaged: "Damaged",
    unreadable: "Needs another key",
    newer: "Made by a newer Raiker",
  };

  async function load() {
    try {
      const answer = await api.backups();
      // FIXED-455's rule: a read whose shape is not what was asked for is a
      // failed read, not a page that throws.
      if (!answer || !Array.isArray(answer.backups)) throw new Error("unexpected_shape");
      view = answer;
      loadError = null;
    } catch (e) {
      loadError = e instanceof ApiError ? `Backups could not be read (${e.status}).` : "Backups could not be read.";
    }
  }

  function size(bytes: number): string {
    return bytes >= 1_048_576 ? `${(bytes / 1_048_576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  function reasonLabel(backup: BackupView): string {
    return backup.reason === "pre_migration" ? "Before an update" : "Taken by you";
  }

  async function act(label: string, run: () => Promise<void>) {
    busy = label;
    notice = null;
    try {
      await run();
    } catch (e) {
      notice = {
        kind: "error",
        text: e instanceof ApiError && e.reasonCode ? `Not done: ${e.reasonCode.replaceAll("_", " ")}.` : "Not done.",
      };
    } finally {
      busy = null;
      await load();
    }
  }

  const backUp = () =>
    act("create", async () => {
      const made = await api.createBackup();
      notice = { kind: "ok", text: `Backed up and verified — ${size(made.size_bytes)}.` };
    });

  const verify = (backup: BackupView) =>
    act(backup.backup_id, async () => {
      const checked = await api.verifyBackup(backup.backup_id);
      notice =
        checked.state === "verified"
          ? { kind: "ok", text: "Verified: it opens with this workspace's key and passes its integrity check." }
          : { kind: "error", text: checked.detail };
    });

  const restore = (backup: BackupView) =>
    act(backup.backup_id, async () => {
      restored = await api.restoreBackup(backup.backup_id);
    });

  const remove = (backup: BackupView) =>
    act(backup.backup_id, async () => {
      await api.deleteBackup(backup.backup_id);
      notice = { kind: "ok", text: "Backup removed." };
    });

  onMount(load);
</script>

<section class="settings-card" aria-labelledby="backups-heading" data-testid="backups-card">
  <div class="card-heading">
    <h3 id="backups-heading">Backups</h3>
    <p>
      A copy of this workspace's database, memory files, checkpoints and uploaded files, checked before it is
      listed. The database is encrypted with this workspace's key; the files are copied as the workspace keeps
      them. Raiker also takes one before an update changes the database, and keeps the last three.
    </p>
  </div>
  <p class="sub">
    Not included: {Object.values(NOT_INCLUDED).join(", ")}. A backup opens only with this workspace's
    key file, <code>.raiker/app.key</code> — keep a copy of that file somewhere safe too, or the backup cannot be read.
  </p>
  <div class="row-actions">
    <button type="button" class="btn btn-primary btn-sm" disabled={busy !== null} onclick={backUp}>
      {busy === "create" ? "Backing up…" : "Back up now"}
    </button>
  </div>
  {#if notice}<p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>{/if}
  {#if restored}
    <div class="restored" role="status" data-testid="backup-restored">
      <p><strong>Restored to a separate workspace.</strong> Your running workspace was not changed.</p>
      <p class="sub">
        It holds {restored.counts.sessions ?? 0} conversations and {restored.counts.approved_memory ?? 0} memories.
        {#if Object.values(restored.deletions_applied ?? {}).some((n) => n > 0)}What you deleted since the backup was deleted from it too.{/if}
        To use it, stop Raiker and start it on that folder:
      </p>
      <code>{restored.command}</code>
    </div>
  {/if}
  {#if loadError}
    <p class="sub" data-testid="backups-unreadable">{loadError}</p>
  {:else if view && view.backups.length === 0}
    <p class="sub">No backups yet.</p>
  {:else if view}
    <ul class="backups">
      {#each view.backups as backup (backup.backup_id)}
        <li data-state={backup.state}>
          <div class="what">
            <strong>{reasonLabel(backup)}</strong>
            <span title={backup.created_at}>{relativeTime(backup.created_at)}</span>
            <span>{size(backup.size_bytes)} · {backup.counts.sessions ?? 0} conversations · {backup.counts.approved_memory ?? 0} memories{filesLabel(backup)}</span>
            <span class="state" data-testid="backup-state">{STATE[backup.state] ?? backup.state}{backup.detail ? ` — ${backup.detail}` : ""}</span>
          </div>
          <div class="row-actions">
            <button type="button" class="btn btn-ghost btn-sm" disabled={busy !== null} onclick={() => verify(backup)}>Verify</button>
            <button type="button" class="btn btn-soft btn-sm" disabled={busy !== null || backup.state !== "verified"} onclick={() => restore(backup)}>Restore to a new folder</button>
            <button type="button" class="btn btn-ghost btn-sm" disabled={busy !== null} aria-label={`Remove backup from ${backup.created_at}`} onclick={() => remove(backup)}>Remove</button>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  /* The Account page's card, which its scoped styles do not reach in here. */
  .settings-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: var(--card-pad-y) var(--card-pad-x); margin-bottom: var(--space-4); }
  .card-heading h3 { margin: 0; }
  .card-heading p { color: var(--text-2); margin: .3rem 0 0; }
  .sub { color: var(--text-2); font-size: var(--text-sm); }
  .row-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .backups { list-style: none; margin: var(--space-3) 0 0; padding: 0; display: grid; gap: var(--space-2); }
  .backups li {
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: var(--space-2);
    border: 1px solid var(--neutral-border); border-radius: var(--r-md); padding: var(--space-2) var(--space-3);
  }
  .what { display: grid; gap: 0.1rem; font-size: var(--text-sm); color: var(--text-2); min-width: 0; }
  .what strong { color: var(--text-1); }
  li[data-state="damaged"] .state, li[data-state="unreadable"] .state, li[data-state="newer"] .state { color: var(--danger); }
  li[data-state="verified"] .state { color: var(--ok, var(--text-2)); }
  .restored { border: 1px solid var(--neutral-border); border-radius: var(--r-md); padding: var(--space-3); margin-top: var(--space-2); }
  .restored code, .sub code { overflow-wrap: anywhere; }
  .restored p { margin: 0 0 var(--space-1); }
</style>
