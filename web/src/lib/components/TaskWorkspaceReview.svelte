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
  // BD-4 — the conflicting files the owner chose to overwrite, per copy. Off
  // until chosen: Apply never replaces an edit the owner made without asking.
  let overwrite = $state<Record<string, string[]>>({});

  function chosen(item: TaskWorkspaceView): string[] {
    return (overwrite[item.workspace_id] ?? []).filter((path) => (item.conflicts ?? []).includes(path));
  }

  function choose(item: TaskWorkspaceView, path: string, on: boolean) {
    const current = new Set(overwrite[item.workspace_id] ?? []);
    if (on) current.add(path);
    else current.delete(path);
    overwrite = { ...overwrite, [item.workspace_id]: [...current] };
  }

  /** Conflicts still waiting for the owner's decision. */
  function undecided(item: TaskWorkspaceView): string[] {
    const picked = new Set(chosen(item));
    return (item.conflicts ?? []).filter((path) => !picked.has(path));
  }

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

  // A copy can change while this review is not in view: a background run, or
  // another window. Returning to the window or to this address rereads it, so
  // the list is never the one from before the owner looked away.
  $effect(() => {
    const reread = () => {
      if (document.visibilityState === "visible") void load();
    };
    window.addEventListener("focus", reread);
    window.addEventListener("hashchange", reread);
    document.addEventListener("visibilitychange", reread);
    return () => {
      window.removeEventListener("focus", reread);
      window.removeEventListener("hashchange", reread);
      document.removeEventListener("visibilitychange", reread);
    };
  });

  const REFUSALS: Record<string, string> = {
    workspace_review_stale: "The copy changed after you looked. Review the new list and apply again.",
    workspace_promotion_conflict: "A file changed in your project since the copy was made. Nothing was applied. Compare it below and choose Overwrite, or Discard the copy.",
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
    const replaced = chosen(item);
    const title = `Apply ${count(item)} change${count(item) === 1 ? "" : "s"} to ${item.source}?`;
    const ok = await askConfirm(
      replaced.length > 0
        ? {
            title,
            body: `This replaces your own edits to ${replaced.join(", ")} with the copy's version. A backup is kept until the Apply finishes.`,
            confirmLabel: "Overwrite and apply",
            danger: true,
          }
        : { title, confirmLabel: "Apply" },
    );
    if (!ok) return;
    busy = true;
    notice = null;
    try {
      await api.promoteTaskWorkspace(item.workspace_id, {
        created: item.created,
        modified: item.modified,
        deleted: item.deleted,
        overwrite: replaced,
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
      <span>Working in an isolated copy — nothing changes in your project until you Apply.</span>
    </header>
    {#if (item.conflicts ?? []).length > 0}
      <!-- BD-4 — a file the owner changed since the copy was taken is never
           replaced silently. Opening it shows both versions: lines marked −
           are your project now, + the copy. -->
      <div class="conflicts" role="group" aria-label="Changed in your project too">
        <p class="conflict-lead">
          {item.conflicts.length === 1 ? "1 file was" : `${item.conflicts.length} files were`} also changed in your project since the copy was made.
          Open each to compare, then keep yours or overwrite it.
        </p>
        <ul>
          {#each item.conflicts as path (path)}
            <li>
              <span class="mono">{path}</span>
              <label class="overwrite">
                <input
                  type="checkbox"
                  checked={chosen(item).includes(path)}
                  onchange={(event) => choose(item, path, (event.currentTarget as HTMLInputElement).checked)}
                />
                Overwrite with the copy's version
              </label>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
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
                {#if (item.conflicts ?? []).includes(path as string)}<p class="diff-note">Lines marked − are your project now; + is the copy's version.</p>{/if}
                {#if shown.truncated}<p class="diff-note">The diff is long; only its start is shown.</p>{/if}
              {/if}
            {/if}
          </li>
        {/each}
      {/each}
      {#each item.rejected as rejected (rejected.path)}<li class="rejected"><b>Not applied</b> {rejected.path} · {rejected.reason.replaceAll("_", " ")}</li>{/each}
    </ul>
    <div class="actions">
      <button
        class="btn btn-primary btn-sm"
        type="button"
        disabled={busy || count(item) === 0 || undecided(item).length > 0}
        title={undecided(item).length > 0 ? "Choose Overwrite for each file you also changed, or Discard the copy" : undefined}
        onclick={() => void apply(item)}
      >Apply to project</button>
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
  .diff { margin:var(--space-1) 0; padding:var(--space-2); max-height:18rem; overflow:auto; border-radius:var(--r-sm); background:var(--surface-raised); white-space:pre; }
  .diff .add { color:var(--ok); }
  .diff .del { color:var(--danger); }
  .diff .hunk, .diff .meta { color:var(--text-3); }
  .diff-note { margin:var(--space-1) 0; color:var(--text-3); font-family:var(--font-sans); }
  li b { display:inline-block; min-width:6.5rem; color:var(--text-2); font-family:var(--font-sans); font-weight:600; }
  li.rejected { color:var(--warn); }
  .actions { display:flex; gap:var(--space-2); }
  .conflicts { display:grid; gap:var(--space-1); padding:var(--space-2); border:1px solid var(--warn); border-radius:var(--r-sm); }
  .conflicts ul { max-height:none; }
  .conflicts li { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:var(--space-2); }
  .conflict-lead { margin:0; color:var(--text-2); font-size:var(--text-sm); }
  .overwrite { display:inline-flex; align-items:center; gap:.35rem; font-family:var(--font-sans); color:var(--text-2); }
  .mono { font-family:var(--font-mono); }
</style>
