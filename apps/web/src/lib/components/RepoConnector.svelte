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
  import PathPicker from "./PathPicker.svelte";
  import Icon from "./Icon.svelte";
  import { api, ApiError } from "../api";
  import type { CodeMapStatus, CodeRepo, CodeReposView } from "../apiTypes";
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

  // B9 — the code map over the selected repository. Loaded here rather than
  // threaded down from Build, because this panel is where a repository is chosen
  // and the index belongs to whichever one is active.
  let codeMap = $state<CodeMapStatus | null>(null);
  let indexing = $state(false);
  let indexNotice = $state<string | null>(null);

  let source = $state<"local" | "github">("local");
  let localPath = $state("");
  // BUG-251 — the folder can be browsed to. The picker is confined to the
  // workspace and answers with a workspace-relative path, because that is the
  // only shape this field accepts.
  let browsing = $state(false);
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

  $effect(() => {
    // Re-read whenever the repository list changes: selecting a different
    // repository changes which index this panel is describing.
    void view;
    void loadCodeMap();
  });

  async function loadCodeMap() {
    try {
      codeMap = await api.codeMap();
    } catch {
      codeMap = null;
    }
  }

  async function rebuildCodeMap() {
    if (indexing) return;
    indexing = true;
    indexNotice = null;
    try {
      const result = await api.rebuildCodeMap();
      indexNotice = `Indexed ${result.file_count} files and ${result.symbol_count} declarations.`;
      await loadCodeMap();
    } catch (e) {
      indexNotice =
        e instanceof ApiError && e.reasonCode === "code_map_gate_disabled"
          ? "Code map indexing is turned off. Turn it on in Permissions → Workspace."
          : "Could not index this repository.";
    } finally {
      indexing = false;
    }
  }

  /** What the index card says, in one sentence, without claiming more than it knows. */
  function indexSummary(map: CodeMapStatus): string {
    if (!map.enabled) {
      return "Code map indexing is off, so the agent searches this repository by pattern only.";
    }
    if (map.status === "not_indexed") {
      return "Not indexed yet. Build the map so the agent can find a definition instead of grepping for it.";
    }
    if (map.status === "failed") {
      return `Could not be indexed (${humanize(map.reason_code || "unknown")}).`;
    }
    const partial =
      map.status === "partial"
        ? ` Partial — the scan stopped at ${map.limits_hit.map(humanize).join(", ")}.`
        : "";
    return `${map.file_count.toLocaleString()} files, ${map.symbol_count.toLocaleString()} declarations.${partial}`;
  }

  async function connect() {
    if (busy) return;
    busy = true;
    error = null;
    try {
      // Connecting the *first* repository also makes it the active one. An
      // owner who has just named the folder they want to work in has already
      // said which repository this is, and leaving Build on "No repository"
      // until they find a second button reads as the connect having failed.
      // It is deliberately only the first: an existing active repository is a
      // choice, and adding a second one must never silently move the work.
      const adopt = (view?.repos.length ?? 0) === 0;
      let connected: string | null = null;
      if (source === "local") {
        connected = (await api.connectLocalRepo(localPath.trim())).repo_id;
        localPath = "";
      } else {
        connected = (
          await api.connectGithubRepo(owner.trim(), repo.trim(), branch.trim() || undefined)
        ).repo_id;
        owner = "";
        repo = "";
        branch = "";
      }
      if (adopt && connected !== null) await api.selectCodeRepo(connected);
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
      <Icon name="x" size="sm" />
    </button>
  </header>

  {#if view !== null && view.repos.length > 0}
    <ul class="repo-list">
      {#each view.repos as item (item.repo_id)}
        <li class="repo" class:selected={item.selected}>
          <span class="repo-icon" aria-hidden="true">
            <Icon name={item.kind === "github" ? "branch" : "folder"} size="sm" />
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
              <Icon name="x" size="sm" />
            </button>
          </span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if codeMap !== null}
    <section class="code-map" aria-label="Code map">
      <div class="code-map-body">
        <span class="code-map-title">
          <Icon name="search" size="sm" />
          Code map · {codeMap.repository}
        </span>
        <span class="code-map-detail" class:warn={!codeMap.enabled || codeMap.status === "failed"}>
          {indexSummary(codeMap)}
        </span>
        {#if codeMap.enabled && codeMap.status !== "not_indexed" && codeMap.updated_at}
          <span class="code-map-detail">Updated {codeMap.updated_at}</span>
        {/if}
        {#if indexNotice !== null}<span class="code-map-detail" role="status">{indexNotice}</span>{/if}
      </div>
      <button
        type="button"
        class="btn btn-soft btn-sm"
        disabled={indexing || !codeMap.enabled}
        onclick={rebuildCodeMap}
      >
        {indexing ? "Indexing…" : codeMap.status === "not_indexed" ? "Build index" : "Rebuild index"}
      </button>
    </section>
  {/if}

  <div class="source-toggle chip-row" role="group" aria-label="Repository source">
    <button type="button" class="chip" aria-pressed={source === "local"} onclick={() => (source = "local")}>
      <Icon name="folder" size="sm" /> Local folder
    </button>
    <button type="button" class="chip" aria-pressed={source === "github"} onclick={() => (source = "github")}>
      <Icon name="branch" size="sm" /> GitHub
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
        <span class="path-field">
          <input
            class="input"
            bind:value={localPath}
            placeholder="projects/my-app"
            disabled={busy}
            required
          />
          <button type="button" class="btn btn-sm" disabled={busy} onclick={() => (browsing = true)}>
            Browse…
          </button>
        </span>
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

{#if browsing}
  <PathPicker
    title="Choose a folder in the workspace"
    insideWorkspace
    onchoose={(path) => { localPath = path; browsing = false; }}
    onclose={() => (browsing = false)}
  />
{/if}

<style>
  .path-field { display: flex; gap: var(--space-2); align-items: center; }
  .path-field .input { flex: 1; min-width: 0; }
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
    font-size: var(--text-md);
  }
  header p {
    margin: 0.25rem 0 0;
    max-width: 60ch;
    color: var(--text-2);
    font-size: var(--text-sm);
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
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--text-1);
    overflow-wrap: anywhere;
  }
  .repo-detail {
    font-size: var(--text-xs);
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
    font-size: var(--text-2xs);
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .code-map {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 0.55rem 0.65rem;
    background: var(--raised);
  }
  .code-map-body {
    display: grid;
    gap: 0.15rem;
    min-width: 0;
  }
  .code-map-title {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--text-1);
  }
  .code-map-detail {
    font-size: var(--text-xs);
    color: var(--text-3);
    overflow-wrap: anywhere;
  }
  .code-map-detail.warn {
    color: var(--warn);
  }
  .connect-form {
    display: grid;
    gap: var(--space-3);
    justify-items: start;
  }
  .field {
    display: grid;
    gap: 0.3rem;
    font-size: var(--text-sm);
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
    font-size: var(--text-xs);
  }
  .github-fields {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-3);
    width: 100%;
  }
  .hint {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-3);
    line-height: 1.5;
    max-width: 72ch;
  }
  .hint.blocked {
    color: var(--warn);
  }
  .error {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--danger);
  }
  @media (max-width: 42rem) {
    .github-fields {
      grid-template-columns: 1fr;
    }
  }
</style>
