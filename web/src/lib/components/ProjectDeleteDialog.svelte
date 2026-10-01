<script lang="ts">
  /**
   * UX-PROJ-07 — deleting a project, with what it removes counted first.
   *
   * The delete was a `window.confirm` with one sentence in it. For a managed
   * project that sentence stood in front of removing a folder from disk,
   * every chat filed under it and their checkpoints, and none of it was counted
   * or could be read back afterwards.
   *
   * DEC-04 step 9 decides what stands in front of it now: the effects
   * enumerated from the server's own preview (the same session set the delete
   * removes), the project's name typed, a statement that nothing can be
   * recovered with Export beside it, and — because a managed folder goes with
   * it — a recent step-up. The step-up is the elevated session account
   * deletion already uses; the server refuses a managed delete without one, so
   * this collects the password rather than deciding anything.
   */
  import { onMount } from "svelte";
  import { api, auth, ApiError, getToken, setToken } from "../api";
  import type { ProjectDeletionPreview, ProjectView } from "../apiTypes";
  import { explainReasonCode } from "../reasonCodes";
  import { describeDeletion } from "../projectLifecycle";

  let {
    project,
    onclose,
    ondeleted,
  }: {
    project: ProjectView;
    onclose: () => void;
    ondeleted: () => void;
  } = $props();

  let dialogElement = $state<HTMLDialogElement>();
  let preview = $state<ProjectDeletionPreview | null>(null);
  let loadError = $state<string | null>(null);
  let typedName = $state("");
  let password = $state("");
  let mfaCode = $state("");
  let busy = $state(false);
  let exporting = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);

  const effects = $derived(preview === null ? null : describeDeletion(preview));
  const nameMatches = $derived(typedName.trim() === project.name);
  const stepUpReady = $derived(
    preview === null || !preview.requires_step_up || password !== "" || mfaCode.trim() !== "",
  );
  const ready = $derived(preview !== null && nameMatches && stepUpReady && !busy);

  onMount(() => {
    const returnFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (dialogElement) {
      if (typeof dialogElement.showModal === "function") dialogElement.showModal();
      else dialogElement.setAttribute("open", "");
    }
    void load();
    return () => returnFocus?.focus();
  });

  async function load() {
    loadError = null;
    try {
      preview = await api.projectDeletionPreview(project.project_id);
    } catch (e) {
      loadError =
        e instanceof ApiError && e.status === 404
          ? "This project is no longer here."
          : "Could not read what deleting this project would remove.";
    }
  }

  function cancel(event: Event) {
    event.preventDefault();
    if (!busy) onclose();
  }

  async function exportFirst() {
    if (exporting) return;
    exporting = true;
    notice = null;
    try {
      await api.exportProject(project.project_id);
      notice = "Exported. Check your downloads before deleting.";
    } catch {
      error = "Could not export the project.";
    } finally {
      exporting = false;
    }
  }

  /** Whether the project is still listed — the answer to a response that never came. */
  async function stillThere(): Promise<boolean | null> {
    try {
      const list = await api.projects();
      return list.projects.some((p) => p.project_id === project.project_id);
    } catch {
      return null;
    }
  }

  async function remove() {
    if (!ready || preview === null) return;
    busy = true;
    error = null;
    const control = getToken();
    try {
      if (preview.requires_step_up) {
        const { token } = await auth.elevate(password || undefined, mfaCode.trim() || undefined);
        setToken(token);
      }
      await api.deleteProject(project.project_id, true);
      setToken(control);
      ondeleted();
      return;
    } catch (e) {
      setToken(control);
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) {
        const explained = explainReasonCode(e.reasonCode);
        error =
          e.status === 401
            ? "That password or code was not accepted. Nothing was deleted."
            : explained
              ? `${explained.plain} ${explained.remediation ?? ""}`.trim()
              : `Could not delete (${e.status}). Nothing was deleted.`;
        return;
      }
      // A request that never came back is not a request that failed: ask
      // whether the project is still there before saying anything about it.
      const present = await stillThere();
      if (present === false) {
        ondeleted();
        return;
      }
      error =
        present === true
          ? "Could not delete the project. It is still here."
          : "Raiker could not be reached, so whether the project was deleted is unknown. Reload to find out before trying again.";
    } finally {
      password = "";
      mfaCode = "";
      busy = false;
    }
  }
</script>

<dialog class="dialog" bind:this={dialogElement} aria-labelledby="delete-title" oncancel={cancel}>
  <header>
    <h2 id="delete-title">Delete “{project.name}”</h2>
    <button type="button" class="icon-btn" aria-label="Close" onclick={onclose} disabled={busy}
      >×</button
    >
  </header>

  {#if loadError !== null}
    <p class="error" role="alert">{loadError}</p>
    <button type="button" class="btn btn-sm" onclick={() => void load()}>Try again</button>
  {:else if preview === null || effects === null}
    <p class="muted" role="status">Counting what this would remove…</p>
  {:else}
    <section class="review" aria-labelledby="delete-removes">
      <h3 id="delete-removes">This permanently removes</h3>
      <ul>
        {#each effects.removes as line (line)}<li>{line}</li>{/each}
      </ul>
      {#if effects.keeps.length > 0}
        <h3>This keeps</h3>
        <ul class="keeps">
          {#each effects.keeps as line (line)}<li>{line}</li>{/each}
        </ul>
      {/if}
    </section>

    <p class="irreversible">
      This cannot be undone: Raiker keeps no copy. To keep the conversations, export the project
      first.
    </p>
    <div>
      <button
        type="button"
        class="btn btn-sm"
        onclick={() => void exportFirst()}
        disabled={exporting || busy}
      >
        {exporting ? "Exporting…" : "Export project"}
      </button>
      {#if notice}<span class="ok" role="status">{notice}</span>{/if}
    </div>

    <label class="field">
      <span>Type <strong>{project.name}</strong> to confirm</span>
      <input
        class="input"
        type="text"
        bind:value={typedName}
        autocomplete="off"
        spellcheck="false"
        disabled={busy}
        aria-label="Project name to confirm deletion"
      />
    </label>

    {#if preview.requires_step_up}
      <fieldset class="step-up">
        <legend>Confirm it is you</legend>
        <p class="muted">
          Removing a folder from this computer needs your password again (or an authenticator code).
        </p>
        <label class="field">
          <span>Password</span>
          <input
            class="input"
            type="password"
            bind:value={password}
            autocomplete="current-password"
            disabled={busy}
          />
        </label>
        <label class="field">
          <span>Authenticator code (optional)</span>
          <input
            class="input"
            type="text"
            inputmode="numeric"
            bind:value={mfaCode}
            autocomplete="one-time-code"
            disabled={busy}
          />
        </label>
      </fieldset>
    {/if}

    {#if error !== null}<p class="error" role="alert">{error}</p>{/if}

    <footer>
      <button type="button" class="btn btn-ghost btn-sm" onclick={onclose} disabled={busy}>
        Cancel
      </button>
      <button
        type="button"
        class="btn btn-danger btn-sm"
        onclick={() => void remove()}
        disabled={!ready}
      >
        {busy ? "Deleting…" : "Delete project"}
      </button>
    </footer>
  {/if}
</dialog>

<style>
  .dialog::backdrop {
    background: var(--overlay);
  }
  .dialog {
    color: var(--text-1);
    width: min(34rem, 100%);
    max-height: min(90vh, 48rem);
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
  h3 {
    margin: 0 0 0.35rem;
    font-size: var(--text-sm);
  }
  .review {
    padding: var(--space-3);
    border: 1px solid var(--danger-border);
    border-radius: var(--r-md);
    background: var(--sunken);
    display: grid;
    gap: 0.4rem;
  }
  .review ul {
    margin: 0;
    padding-left: 1.1rem;
    display: grid;
    gap: 0.2rem;
    font-size: var(--text-sm);
    color: var(--text-2);
    overflow-wrap: anywhere;
  }
  .irreversible {
    margin: 0;
    padding-left: 0.6rem;
    border-left: 3px solid var(--danger);
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .field {
    display: grid;
    gap: 0.3rem;
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .field .input {
    width: 100%;
  }
  .step-up {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: var(--space-3);
    margin: 0;
    display: grid;
    gap: var(--space-2);
  }
  .step-up legend {
    font-size: var(--text-sm);
    font-weight: 650;
    padding: 0 0.3rem;
  }
  .muted {
    color: var(--text-2);
    font-size: var(--text-sm);
    margin: 0;
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
  .ok {
    color: var(--ok);
    font-size: var(--text-sm);
    margin-left: var(--space-2);
    font-weight: 600;
  }
</style>
