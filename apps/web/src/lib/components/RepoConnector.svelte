<script lang="ts">
  /**
   * Connect the Build workspace to a repository: a folder already inside this
   * Raiker workspace, or a GitHub `owner/repo` coordinate.
   *
   * Connecting is bookkeeping, not access. The server refuses a local path that
   * resolves outside the workspace, and a GitHub coordinate is recorded without
   * any network call — content still arrives through the brokered `github_read`
   * tool under the `connector_github_runtime` gate. This panel therefore states
   * the gate's real posture instead of implying that connecting granted reads.
   */
  import Icon from "./Icon.svelte";
  import { api, ApiError } from "../api";
  import type { CodeRepo, CodeReposView } from "../apiTypes";
  import { humanize } from "../format";

  let {
    view,
    onchanged,
    onclose,
  }: {
    view: CodeReposView | null;
    onchanged: () => void | Promise<void>;
    onclose: () => void;
  } = $props();

  let source = $state<"local" | "github">("local");
  let localPath = $state("");
  let owner = $state("");
  let repo = $state("");
  let branch = $state("");
  let busy = $state(false);
  let error = $state<string | null>(null);

  const githubReadable = $derived(
    view !== null &&
      !["disabled", "planned", "unknown"].includes(view.github_gate_state) &&
      view.github_decision_mode !== "deny",
  );

  /**
   * Accept the shapes people actually paste. A full URL, an `owner/repo` pair,
   * or a `.git` suffix all resolve to the same coordinate, so pasting the address
   * bar works instead of erroring on punctuation.
   */
  function parseGithubInput(value: string): { owner: string; repo: string } | null {
    const trimmed = value.trim().replace(/^https?:\/\/(www\.)?github\.com\//i, "").replace(/\.git$/i, "");
    const parts = trimmed.split("/").filter(Boolean);
    if (parts.length < 2) return null;
    return { owner: parts[0], repo: parts[1] };
  }

  /**
   * Pasting "owner/repo" — or the whole GitHub URL — into the first field fills
   * both. The value is read from the element rather than the bound state so the
   * split happens on the paste itself, not one keystroke later.
   */
  function onOwnerInput(value: string) {
    const parsed = parseGithubInput(value);
    if (parsed === null) return;
    owner = parsed.owner;
    repo = parsed.repo;
  }

  async function connect() {
    if (busy) return;
    busy = true;
    error = null;
    try {
      if (source === "local") {
        await api.connectLocalRepo(localPath.trim());
        localPath = "";
      } else {
        await api.connectGithubRepo(owner.trim(), repo.trim(), branch.trim() || undefined);
        owner = "";
        repo = "";
        branch = "";
      }
      await onchanged();
    } catch (e) {
      error = connectError(e);
    } finally {
      busy = false;
    }
  }

  function connectError(e: unknown): string {
    if (!(e instanceof ApiError)) return "Could not reach the local runtime.";
    switch (e.reasonCode) {
      case "repo_outside_workspace":
        return "That folder is outside this Raiker workspace, so it was refused.";
      case "repo_not_found":
        return "No folder at that path inside the workspace.";
      case "repo_not_a_directory":
        return "That path is a file. Connect the folder that contains it.";
      case "repo_already_connected":
        return "That repository is already connected.";
      case "invalid_github_repo":
        return "That does not look like an owner/repo coordinate.";
      case "invalid_github_branch":
        return "That branch name has characters GitHub does not allow.";
      default:
        return `Could not connect the repository (${e.reasonCode ?? e.status}).`;
    }
  }

  async function select(repoId: string | null) {
    busy = true;
    error = null;
    try {
      await api.selectCodeRepo(repoId);
      await onchanged();
    } catch {
      error = "Could not change the active repository.";
    } finally {
      busy = false;
    }
  }

  async function disconnect(target: CodeRepo) {
    busy = true;
    error = null;
    try {
      await api.disconnectCodeRepo(target.repo_id);
      await onchanged();
    } catch {
      error = "Could not disconnect that repository.";
    } finally {
      busy = false;
    }
  }
</script>

<section class="connector card" aria-label="Repositories">
  <header>
    <div>
      <h2>Repositories</h2>
      <p>
        Connecting a repository grants nothing. A local folder must sit inside this Raiker workspace, and GitHub
        content is read through the governed connector — never from this page.
      </p>
    </div>
    <button type="button" class="btn btn-ghost btn-sm" onclick={onclose} aria-label="Close repositories">
      <Icon name="x" size={15} />
    </button>
  </header>

  {#if view !== null && view.repos.length > 0}
    <ul class="repo-list">
      {#each view.repos as item (item.repo_id)}
        <li class="repo" class:selected={item.selected}>
          <span class="repo-icon" aria-hidden="true">
            <Icon name={item.kind === "github" ? "branch" : "folder"} size={15} />
          </span>
          <span class="repo-body">
            <span class="repo-label">{item.label}</span>
            <span class="repo-detail">
              {#if item.kind === "local"}
                {item.local_subpath}
                {#if !item.local_exists}
                  · <span class="warn">folder is missing</span>
                {/if}
              {:else}
                GitHub{item.branch ? ` · ${item.branch}` : ""}
                {#if !githubReadable}
                  · <span class="warn">reads are closed</span>
                {/if}
              {/if}
            </span>
          </span>
          <span class="repo-actions">
            {#if item.selected}
              <span class="active-chip">Active</span>
              <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => select(null)}>
                Clear
              </button>
            {:else}
              <button type="button" class="btn btn-soft btn-sm" disabled={busy} onclick={() => select(item.repo_id)}>
                Use
              </button>
            {/if}
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              disabled={busy}
              onclick={() => disconnect(item)}
              aria-label={`Disconnect ${item.label}`}
            >
              <Icon name="x" size={14} />
            </button>
          </span>
        </li>
      {/each}
    </ul>
  {/if}

  <div class="source-toggle chip-row" role="group" aria-label="Repository source">
    <button type="button" class="chip" aria-pressed={source === "local"} onclick={() => (source = "local")}>
      <Icon name="folder" size={14} /> Local folder
    </button>
    <button type="button" class="chip" aria-pressed={source === "github"} onclick={() => (source = "github")}>
      <Icon name="branch" size={14} /> GitHub
    </button>
  </div>

  <form
    class="connect-form"
    onsubmit={(event) => {
      event.preventDefault();
      void connect();
    }}
  >
    {#if source === "local"}
      <label class="field">
        Folder inside this workspace
        <input
          class="input"
          bind:value={localPath}
          placeholder="projects/my-app"
          disabled={busy}
          required
        />
      </label>
      <p class="hint">
        Paths are resolved inside the workspace root. Anything that resolves outside it is refused by the runtime.
      </p>
    {:else}
      <div class="github-fields">
        <label class="field">
          <span class="field-label">Owner</span>
          <input
            class="input"
            bind:value={owner}
            oninput={(event) => onOwnerInput((event.currentTarget as HTMLInputElement).value)}
            placeholder="owner (or paste owner/repo)"
            disabled={busy}
            required
          />
        </label>
        <label class="field">
          <span class="field-label">Repository</span>
          <input class="input" bind:value={repo} placeholder="repository" disabled={busy} required />
        </label>
        <label class="field">
          <span class="field-label">Branch <span class="optional">optional</span></span>
          <input class="input" bind:value={branch} placeholder="main" disabled={busy} />
        </label>
      </div>
      {#if view !== null}
        <p class="hint" class:blocked={!githubReadable}>
          {#if githubReadable}
            GitHub reads run through the governed connector — gate <strong>{humanize(view.github_gate_state)}</strong>,
            decision mode <strong>{view.github_decision_mode}</strong
            >{#if !view.github_token_configured}, and no owner token is configured yet, so reads will fail closed until
              one is{/if}.
          {:else}
            The GitHub connector is closed right now (gate <strong>{humanize(view.github_gate_state)}</strong>, decision
            mode <strong>{view.github_decision_mode}</strong>). You can still connect the repository — reads will fail
            closed until you open the gate in Permissions.
          {/if}
        </p>
      {/if}
    {/if}

    {#if error !== null}<p class="error" role="alert">{error}</p>{/if}

    <button
      class="btn btn-primary btn-sm"
      disabled={busy || (source === "local" ? localPath.trim() === "" : owner.trim() === "" || repo.trim() === "")}
    >
      {busy ? "Connecting…" : "Connect repository"}
    </button>
  </form>
</section>

<style>
  .connector {
    display: grid;
    gap: var(--space-3);
  }
  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  h2 {
    margin: 0;
    font-size: 0.95rem;
  }
  header p {
    margin: 0.25rem 0 0;
    max-width: 60ch;
    color: var(--text-2);
    font-size: 0.8rem;
    line-height: 1.5;
  }
  .repo-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  .repo {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 0.5rem 0.65rem;
    background: var(--raised);
  }
  .repo.selected {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  .repo-icon {
    display: grid;
    place-items: center;
    color: var(--text-3);
  }
  .repo-body {
    display: grid;
    min-width: 0;
    flex: 1;
  }
  .repo-label {
    font-size: 0.85rem;
    font-weight: 650;
    color: var(--text-1);
    overflow-wrap: anywhere;
  }
  .repo-detail {
    font-size: 0.74rem;
    color: var(--text-3);
    overflow-wrap: anywhere;
  }
  .warn {
    color: var(--warn);
  }
  .repo-actions {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }
  .active-chip {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .connect-form {
    display: grid;
    gap: var(--space-3);
    justify-items: start;
  }
  .field {
    display: grid;
    gap: 0.3rem;
    font-size: 0.78rem;
    color: var(--text-2);
    width: 100%;
  }
  /* The "optional" qualifier belongs on the label's own line, so the three
     GitHub fields keep a single shared baseline. */
  .field-label {
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
    min-height: 1.15rem;
  }
  .optional {
    color: var(--text-3);
    font-weight: 400;
    font-size: 0.72rem;
  }
  .github-fields {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-3);
    width: 100%;
  }
  .hint {
    margin: 0;
    font-size: 0.75rem;
    color: var(--text-3);
    line-height: 1.5;
    max-width: 72ch;
  }
  .hint.blocked {
    color: var(--warn);
  }
  .error {
    margin: 0;
    font-size: 0.8rem;
    color: var(--danger);
  }
  @media (max-width: 42rem) {
    .github-fields {
      grid-template-columns: 1fr;
    }
  }
</style>
