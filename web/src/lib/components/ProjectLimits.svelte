<script lang="ts">
  /**
   * QUI-F21 — a project's own permission limits, on the project's page.
   *
   * "May push to this one repository only." Three kinds, each a short list:
   * repositories, sites and connections. Limits only narrow what Permissions
   * already allow for conversations filed in this project; an empty list
   * limits nothing. Choosing the project in the composer puts a conversation
   * under them, and the composer says so.
   */
  import FormDialog from "./FormDialog.svelte";
  import { ApiError } from "../api";
  import { contract } from "../generated/apiContract";
  import type { ProjectLimitsView } from "../generated/apiContract";

  let { projectId }: { projectId: string } = $props();

  let view = $state<ProjectLimitsView | null>(null);
  let editing = $state(false);
  let repositories = $state("");
  let domains = $state("");
  let connections = $state("");
  let error = $state<string | null>(null);
  let busy = $state(false);

  const ERRORS: Record<string, string> = {
    project_limit_repository_invalid: "Write each repository as owner/name, one per line.",
    project_limit_domain_invalid: "Write each site as a domain, like example.com, one per line.",
    project_limit_connection_invalid: "Write each connection by its short name, like gmail, one per line.",
  };

  $effect(() => {
    const id = projectId;
    view = null;
    void contract
      .getProjectLimits(id)
      .then((answer) => {
        if (id === projectId) view = answer;
      })
      .catch(() => {
        view = null;
      });
  });

  function lines(text: string): string[] {
    return text.split(/[\n,]/).map((line) => line.trim()).filter((line) => line !== "");
  }

  function edit() {
    repositories = (view?.limits.repositories ?? []).join("\n");
    domains = (view?.limits.web_domains ?? []).join("\n");
    connections = (view?.limits.connections ?? []).join("\n");
    error = null;
    editing = true;
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    error = null;
    try {
      view = await contract.setProjectLimits(projectId, {
        repositories: lines(repositories),
        web_domains: lines(domains),
        connections: lines(connections),
      });
      editing = false;
    } catch (e) {
      const code = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      error = ERRORS[code] ?? "The limits were not saved. Nothing changed.";
    } finally {
      busy = false;
    }
  }
</script>

<section class="limits" aria-labelledby={`limits-${projectId}`}>
  <div class="head">
    <h3 id={`limits-${projectId}`} class="kicker">Limits</h3>
    <button type="button" class="btn btn-ghost btn-sm" onclick={edit} disabled={view === null}>
      {view && view.summary.length > 0 ? "Change limits" : "Set limits"}
    </button>
  </div>
  {#if view === null}
    <p class="sub">Reading this project's limits…</p>
  {:else if view.summary.length === 0}
    <p class="sub">No limits. Work here follows your permissions.</p>
  {:else}
    <ul class="summary">
      {#each view.summary as line (line)}<li>{line}</li>{/each}
    </ul>
    <p class="sub">These narrow your permissions for chats filed here; they never widen them.</p>
  {/if}
</section>

{#if editing}
  <FormDialog title="Project limits" onclose={() => (editing = false)}>
    <form class="limit-form" onsubmit={save}>
      <p class="sub">One per line. Leave a list empty to not limit that kind.</p>
      <label>
        Repositories it may push to
        <textarea bind:value={repositories} rows="2" placeholder="acme/site"></textarea>
      </label>
      <label>
        Sites it may read
        <textarea bind:value={domains} rows="2" placeholder="docs.example.com"></textarea>
      </label>
      <label>
        Connections it may use
        <textarea bind:value={connections} rows="2" placeholder="github"></textarea>
      </label>
      {#if error}<p class="error" role="alert">{error}</p>{/if}
      <div class="actions">
        <button type="button" class="btn btn-ghost" onclick={() => (editing = false)}>Cancel</button>
        <button type="submit" class="btn btn-primary" disabled={busy}>Save limits</button>
      </div>
    </form>
  </FormDialog>
{/if}

<style>
  .limits { margin-top: var(--space-4); }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .summary {
    margin: var(--space-1) 0;
    padding-inline-start: 1.1rem;
    color: var(--text-1);
  }
  .sub { color: var(--text-2); font-size: var(--text-sm); margin: var(--space-1) 0 0; }
  .limit-form {
    display: grid;
    gap: var(--space-3);
  }
  .limit-form label {
    display: grid;
    gap: var(--space-1);
    font-weight: 600;
    font-size: var(--text-sm);
    color: var(--text-1);
  }
  .limit-form textarea {
    font: inherit;
    font-weight: 400;
    padding: 0.5rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-1);
    resize: vertical;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
  }
  .error { color: var(--danger); font-size: var(--text-sm); margin: 0; }
</style>
