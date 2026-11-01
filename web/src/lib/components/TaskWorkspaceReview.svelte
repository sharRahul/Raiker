<script lang="ts">
  /**
   * The session's sandbox copy, reviewed before it reaches the project.
   *
   * The agent's file edits and commands work in one disposable copy of the
   * project. Nothing they wrote is in the project until the owner applies it
   * here, and Apply sends back exactly
   * the change set shown: if a command changed the copy after this was read,
   * the server refuses the stale review instead of applying what was not seen.
   */
  import { api, ApiError } from "../api";
  import type { TaskWorkspaceFileDiff, TaskWorkspaceView } from "../apiTypes";
  import { askConfirm } from "../confirm.svelte";

  // `refresh` changes when a turn ends: the copy moves with every edit, so the
  // list is reread rather than kept from when the session was opened.
  let { sessionId, refresh = 0 }: { sessionId: string | null; refresh?: number } = $props();

  let workspaces = $state<TaskWorkspaceView[]>([]);
  let busy = $state(false);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  // The file whose diff is open, keyed by copy and path, and what it read.
  let open = $state<string | null>(null);
  let shown = $state<TaskWorkspaceFileDiff | null>(null);
  let diffError = $state("");

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
    void refresh;
    void load();
  });

  const REFUSALS: Record<string, string> = {
    workspace_review_stale: "The copy changed after you looked. Review the new list and apply again.",
    workspace_promotion_conflict: "A file changed in your project since the copy was made. Nothing was applied.",
    workspace_in_use: "A command is still running in this copy. Wait for it to finish.",
  };

  async function toggle(item: TaskWorkspaceView, path: string) {
    const key = `${item.workspace_id}:${path}`;
    if (open === key) {
      open = null;
      return;
    }
    open = key;
    shown = null;
    diffError = "";
    try {
      const answer = await api.taskWorkspaceFileDiff(item.workspace_id, path);
      if (open === key) shown = answer;
    } catch {
      if (open === key) diffError = "This file's changes could not be read.";
    }
  }

  function lineClass(line: string): string {
    if (line.startsWith("+++") || line.startsWith("---")) return "meta";
    if (line.startsWith("@@")) return "hunk";
    if (line.startsWith("+")) return "add";
    if (line.startsWith("-")) return "del";
    return "";
  }

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
      {#each [["Added", item.created], ["Changed", item.modified], ["Removed", item.deleted]] as [label, paths] (label)}
        {#each paths as path (path)}
          {@const key = `${item.workspace_id}:${path}`}
          <li>
            <button class="file" type="button" aria-expanded={open === key} onclick={() => void toggle(item, path as string)}><b>{label}</b> {path}</button>
            {#if open === key}
              {#if diffError}<p class="diff-note" role="status">{diffError}</p>
              {:else if !shown}<p class="diff-note">Reading…</p>
              {:else if shown.binary}<p class="diff-note">Not a text file, so there is no line-by-line view.</p>
              {:else}
                <pre class="diff" aria-label={`Changes to ${path}`}>{#each shown.diff.split("\n") as line, index (index)}<span class={lineClass(line)}>{line}
</span>{/each}</pre>
                {#if shown.truncated}<p class="diff-note">The diff is long; only its start is shown.</p>{/if}
              {/if}
            {/if}
          </li>
        {/each}
      {/each}
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
  ul { display:grid; gap:.15rem; margin:0; padding:0; list-style:none; max-height:24rem; overflow:auto; font-family:var(--font-mono); font-size:var(--text-xs); }
  .file { all:unset; cursor:pointer; display:block; width:100%; }
  .file:hover, .file:focus-visible { color:var(--text-1); text-decoration:underline; }
  .diff { margin:var(--space-1) 0; padding:var(--space-2); max-height:18rem; overflow:auto; border-radius:var(--r-sm); background:var(--surface-2); white-space:pre; }
  .diff .add { color:var(--ok); }
  .diff .del { color:var(--danger); }
  .diff .hunk, .diff .meta { color:var(--text-3); }
  .diff-note { margin:var(--space-1) 0; color:var(--text-3); font-family:var(--font-sans); }
  li b { display:inline-block; min-width:6.5rem; color:var(--text-2); font-family:var(--font-sans); font-weight:600; }
  li.rejected { color:var(--warn); }
  .actions { display:flex; gap:var(--space-2); }
</style>
