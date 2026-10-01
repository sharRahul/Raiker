<script lang="ts">
  /**
   * UX-PROJ-06 — move a project by choosing where it goes, in the tree it goes into.
   *
   * The destinations are drawn as the hierarchy, indented, so "inside what" is
   * visible. The project and everything under it stay in the list, disabled,
   * with the reason beside them, because a destination that silently vanishes
   * reads as a missing folder. The server still refuses each of these by name;
   * this is the page saying so first, not the page deciding it.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type { ProjectView } from "../apiTypes";
  import { explainReasonCode } from "../reasonCodes";
  import { projectDestinations } from "../projectLifecycle";

  let {
    project,
    projects,
    onclose,
    onmoved,
  }: {
    project: ProjectView;
    projects: ProjectView[];
    onclose: () => void;
    onmoved: () => void;
  } = $props();

  let dialogElement = $state<HTMLDialogElement>();
  // The current parent is where the choice starts, so Move with nothing changed
  // is visibly "no change" rather than a silent move to the top level.
  let chosen = $state<string>("");
  let busy = $state(false);
  let error = $state<string | null>(null);

  const destinations = $derived(projectDestinations(project, projects));
  const unchanged = $derived(chosen === (project.parent_id ?? ""));

  onMount(() => {
    chosen = project.parent_id ?? "";
    const returnFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (dialogElement) {
      if (typeof dialogElement.showModal === "function") dialogElement.showModal();
      else dialogElement.setAttribute("open", "");
    }
    return () => returnFocus?.focus();
  });

  function cancel(event: Event) {
    event.preventDefault();
    if (!busy) onclose();
  }

  async function move() {
    if (busy || unchanged) return;
    busy = true;
    error = null;
    try {
      await api.moveProject(project.project_id, chosen === "" ? null : chosen);
      onmoved();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      error = explained
        ? `${explained.plain} ${explained.remediation ?? ""}`.trim()
        : "Could not move the project.";
    } finally {
      busy = false;
    }
  }
</script>

<dialog class="dialog" bind:this={dialogElement} aria-labelledby="move-title" oncancel={cancel}>
  <header>
    <h2 id="move-title">Move “{project.name}”</h2>
    <button type="button" class="icon-btn" aria-label="Close" onclick={onclose} disabled={busy}
      >×</button
    >
  </header>
  <p class="muted">
    Its chats, files and the projects inside it move with it. Nothing is copied and no folder on
    disk changes.
  </p>

  <fieldset class="destinations">
    <legend>Move into</legend>
    <label class="destination" class:selected={chosen === ""}>
      <input type="radio" name="move-destination" value="" bind:group={chosen} disabled={busy} />
      <span class="name">Top level</span>
      {#if project.parent_id === null}<span class="why">current</span>{/if}
    </label>
    {#each destinations as destination (destination.project.project_id)}
      <label
        class="destination"
        class:selected={chosen === destination.project.project_id}
        class:disabled={destination.blocked !== null}
        style={`--depth: ${destination.depth}`}
      >
        <input
          type="radio"
          name="move-destination"
          value={destination.project.project_id}
          bind:group={chosen}
          disabled={busy || destination.blocked !== null}
        />
        <span class="name">{destination.project.name}</span>
        {#if destination.blocked !== null}
          <span class="why">{destination.blocked}</span>
        {:else if destination.project.project_id === project.parent_id}
          <span class="why">current</span>
        {/if}
      </label>
    {/each}
  </fieldset>

  {#if error !== null}<p class="error" role="alert">{error}</p>{/if}

  <footer>
    <button type="button" class="btn btn-ghost btn-sm" onclick={onclose} disabled={busy}>
      Cancel
    </button>
    <button
      type="button"
      class="btn btn-primary btn-sm"
      onclick={() => void move()}
      disabled={busy || unchanged}
    >
      {busy ? "Moving…" : "Move here"}
    </button>
  </footer>
</dialog>

<style>
  .dialog::backdrop {
    background: var(--overlay);
  }
  .dialog {
    color: var(--text-1);
    width: min(30rem, 100%);
    max-height: min(85vh, 40rem);
    overflow-y: auto;
    display: grid;
    gap: var(--space-3);
    padding: var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-2);
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  header h2 {
    margin: 0;
    font-size: var(--text-base);
    overflow-wrap: anywhere;
  }
  .icon-btn {
    border: 0;
    background: transparent;
    color: var(--text-3);
    font-size: var(--text-xl);
    line-height: 1;
    cursor: pointer;
    padding: 0.1rem 0.35rem;
  }
  .icon-btn:hover {
    color: var(--text-1);
  }
  .muted {
    color: var(--text-2);
    font-size: var(--text-sm);
    margin: 0;
  }
  .destinations {
    display: grid;
    gap: 0.3rem;
    border: 0;
    padding: 0;
    margin: 0;
  }
  .destinations legend {
    font-size: var(--text-sm);
    font-weight: 650;
    padding: 0;
    margin-bottom: 0.3rem;
  }
  .destination {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.45rem 0.65rem;
    padding-left: calc(0.65rem + var(--depth, 0) * 1.1rem);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    cursor: pointer;
    font-size: var(--text-sm);
  }
  .destination.selected {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  .destination.disabled {
    cursor: not-allowed;
    color: var(--text-3);
  }
  .name {
    flex: 1;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .why {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
  }
  .error {
    color: var(--danger);
    font-size: var(--text-sm);
    margin: 0;
  }
</style>
