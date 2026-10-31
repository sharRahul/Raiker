<script lang="ts">
  /**
   * The session's sandbox copy, reviewed before it reaches the project.
   *
   * Commands run in a disposable copy of their folder. Nothing they wrote is in
   * the project until the owner applies it here, and Apply sends back exactly
   * the change set shown: if a command changed the copy after this was read,
   * the server refuses the stale review instead of applying what was not seen.
   */
  import { api, ApiError } from "../api";
  import type { TaskWorkspaceView } from "../apiTypes";
  import { askConfirm } from "../confirm.svelte";

  let { sessionId }: { sessionId: string | null } = $props();

  let workspaces = $state<TaskWorkspaceView[]>([]);
  let busy = $state(false);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  const mine = $derived(
    workspaces.filter(
      (item) =>
        item.session_id === sessionId &&
        item.created.length + item.modified.length + item.deleted.length + item.rejected.length > 0,
    ),
  );

  async function load() {
    if (!sessionId) {
      workspaces = [];
      return;
    }
    try {
      workspaces = (await api.taskWorkspaces()).workspaces;
    } catch {
      workspaces = [];
    }
  }

  $effect(() => {
    void sessionId;
    void load();
  });

  const REFUSALS: Record<string, string> = {
    workspace_review_stale: "The copy changed after you looked. Review the new list and apply again.",
    workspace_promotion_conflict: "A file changed in your project since the copy was made. Nothing was applied.",
    workspace_in_use: "A command is still running in this copy. Wait for it to finish.",
  };

  function count(item: TaskWorkspaceView): number {
    return item.created.length + item.modified.length + item.deleted.length;
  }

  async function apply(item: TaskWorkspaceView) {
    const title = `Apply ${count(item)} change${count(item) === 1 ? "" : "s"} to ${item.source}?`;
    if (!(await askConfirm({ title, confirmLabel: "Apply" }))) return;
    busy = true;
    notice = null;
    try {
      await api.promoteTaskWorkspace(item.workspace_id, {
        created: item.created,
        modified: item.modified,
        deleted: item.deleted,
      });
      notice = { kind: "ok", text: `Applied to ${item.source}.` };
    } catch (e) {
      const reason = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      notice = { kind: "error", text: REFUSALS[reason] ?? "The changes could not be applied. Your project is unchanged." };
    } finally {
      busy = false;
      await load();
    }
  }

  async function discard(item: TaskWorkspaceView) {
    if (!(await askConfirm({ title: "Discard the sandbox copy? Your project stays as it is.", confirmLabel: "Discard", danger: true }))) return;
    busy = true;
    notice = null;
    try {
      await api.discardTaskWorkspace(item.workspace_id);
      notice = { kind: "ok", text: "Sandbox copy discarded. Your project was not changed." };
    } catch (e) {
      const reason = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      notice = { kind: "error", text: REFUSALS[reason] ?? "The copy could not be discarded." };
    } finally {
      busy = false;
      await load();
    }
  }
</script>

{#if notice}<p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>{/if}
{#each mine as item (item.workspace_id)}
  <section class="task-workspace" aria-label="Sandbox changes">
    <header>
      <strong>Sandbox changes · {item.source}</strong>
      <span>Not in your project until you apply them</span>
    </header>
    <ul>
      {#each item.created as path (path)}<li><b>Added</b> {path}</li>{/each}
      {#each item.modified as path (path)}<li><b>Changed</b> {path}</li>{/each}
      {#each item.deleted as path (path)}<li><b>Removed</b> {path}</li>{/each}
      {#each item.rejected as rejected (rejected.path)}<li class="rejected"><b>Not applied</b> {rejected.path} · {rejected.reason.replaceAll("_", " ")}</li>{/each}
    </ul>
    <div class="actions">
      <button class="btn btn-primary btn-sm" type="button" disabled={busy || count(item) === 0} onclick={() => void apply(item)}>Apply to project</button>
      <button class="btn btn-ghost btn-sm danger" type="button" disabled={busy} onclick={() => void discard(item)}>Discard</button>
    </div>
  </section>
{/each}

<style>
  .task-workspace { display:grid; gap:var(--space-2); margin:var(--space-2) 0; padding:var(--space-3); border:1px solid var(--border); border-radius:var(--r-md); background:var(--surface); }
  header { display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:var(--space-2); }
  header span { color:var(--text-3); font-size:var(--text-xs); }
  ul { display:grid; gap:.15rem; margin:0; padding:0; list-style:none; max-height:12rem; overflow:auto; font-family:var(--font-mono); font-size:var(--text-xs); }
  li b { display:inline-block; min-width:6.5rem; color:var(--text-2); font-family:var(--font-sans); font-weight:600; }
  li.rejected { color:var(--warn); }
  .actions { display:flex; gap:var(--space-2); }
</style>
