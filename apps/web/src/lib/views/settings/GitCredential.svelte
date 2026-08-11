<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import PageState from "../../components/PageState.svelte";

  type Grant = {
    grant_id: string;
    scope: string;
    status: string;
    granted_at: string;
    expires_at: string;
    session_id: string | null;
    uses: number;
  };
  type Status = {
    credential_configured: boolean;
    credential_source: string;
    grant: Grant | null;
    scopes: string[];
    grant_seconds: Record<string, number>;
    checked_at: string;
  };

  let status = $state<Status | null>(null);
  let loadError = $state<string | null>(null);
  let token = $state("");
  let busy = $state(false);
  let message = $state<string | null>(null);

  const SCOPE_LABEL: Record<string, string> = {
    once: "Once",
    session: "This session",
  };

  function minutes(seconds: number): string {
    return seconds >= 60 ? `${Math.round(seconds / 60)} min` : `${seconds}s`;
  }

  async function load(): Promise<void> {
    try {
      loadError = null;
      status = await api.gitCredential();
    } catch (error) {
      loadError = error instanceof ApiError ? error.message : String(error);
    }
  }

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!token.trim() || busy) return;
    busy = true;
    message = null;
    try {
      status = await api.putGitCredential(token.trim());
      // Cleared immediately: the field is write-only, and a token left in a form
      // is a token on screen.
      token = "";
      message = "Token stored. Git commands still need your approval each time.";
    } catch (error) {
      message = error instanceof ApiError ? "That does not look like a GitHub token." : String(error);
    } finally {
      busy = false;
    }
  }

  async function grant(scope: string): Promise<void> {
    busy = true;
    message = null;
    try {
      status = await api.grantGitCredential(scope);
      message = null;
    } catch (error) {
      message = error instanceof ApiError ? error.message : String(error);
    } finally {
      busy = false;
    }
  }

  async function revoke(): Promise<void> {
    busy = true;
    status = await api.revokeGitCredential();
    busy = false;
  }

  async function forget(): Promise<void> {
    busy = true;
    status = await api.deleteGitCredential();
    message = "Token removed, and every approval that depended on it withdrawn.";
    busy = false;
  }

  onMount(load);
</script>

<section class="git-credential">
  <header class="section-heading">
    <h2>Git credential</h2>
    <p>
      The token Raiker uses to push. It is stored encrypted on this device and lent
      to a single command at a time.
    </p>
  </header>

  {#if loadError}
    <PageState state="error" title="Couldn't load the git credential" detail={loadError} />
  {:else if !status}
    <PageState state="loading" title="Loading…" />
  {:else}
    <div class="card">
      <h3>GitHub token</h3>
      {#if status.credential_configured}
        <p class="state ok">
          A token is stored{status.credential_source === "environment"
            ? " in this host's environment (RAIKER_GITHUB_TOKEN)"
            : " in this workspace's encrypted vault"}.
        </p>
      {:else}
        <p class="state">
          No token stored. Raiker can read repositories but cannot push.
        </p>
      {/if}
      <p class="lead">
        Raiker never shows a stored token back to you, and never writes it to a log,
        an error, or a command's output — the exact value is removed from everything
        captured while it is in use.
      </p>

      <form class="row" onsubmit={save}>
        <label class="field-label" for="git-token">
          {status.credential_configured ? "Replace token" : "GitHub token"}
        </label>
        <input
          id="git-token"
          class="input"
          type="password"
          autocomplete="off"
          bind:value={token}
          placeholder="ghp_…"
        />
        <button class="btn btn-primary" type="submit" disabled={busy || !token.trim()}>Save</button>
      </form>
      {#if status.credential_configured}
        <button class="btn btn-danger btn-sm forget" type="button" onclick={forget} disabled={busy}>
          Remove stored token
        </button>
      {/if}
      {#if message}<p class="message" role="status">{message}</p>{/if}
    </div>

    <div class="card">
      <h3>Approval for git commands</h3>
      <p class="lead">
        Every git command that needs the token asks first. Approve one command, or a
        working session — a session approval expires on its own, so leaving it on is
        not the same as leaving it on forever.
      </p>

      {#if status.grant}
        <div class="grant" role="status">
          <div>
            <strong>{SCOPE_LABEL[status.grant.scope] ?? status.grant.scope} approved</strong>
            <span class="detail">
              expires {new Date(status.grant.expires_at).toLocaleTimeString()}
              {#if status.grant.uses}· used {status.grant.uses}×{/if}
            </span>
          </div>
          <button class="btn btn-danger btn-sm" type="button" onclick={revoke} disabled={busy}>
            Withdraw
          </button>
        </div>
      {:else}
        <p class="state">Nothing is approved. The next git command will ask.</p>
        <div class="scopes">
          {#each status.scopes as scope (scope)}
            <button
              class="btn"
              type="button"
              onclick={() => grant(scope)}
              disabled={busy || !status.credential_configured}
            >
              Approve {SCOPE_LABEL[scope] ?? scope}
              <span class="ttl">({minutes(status.grant_seconds[scope] ?? 0)})</span>
            </button>
          {/each}
        </div>
        {#if !status.credential_configured}
          <p class="state">Store a token above before approving anything.</p>
        {/if}
      {/if}
    </div>
  {/if}
</section>

<style>
  .section-heading h2 { margin: 0; }
  .section-heading p { color: var(--text-2); margin: 0.3rem 0 var(--space-5); }
  .card { margin-bottom: var(--space-4); }
  .card h3 { margin: 0 0 0.3rem; font-size: var(--text-lg); }
  .lead { color: var(--text-2); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
  .state { font-size: var(--text-sm); color: var(--text-2); margin: 0 0 var(--space-2); }
  .state.ok { color: var(--ok); }
  .row { display: grid; grid-template-columns: 1fr auto; gap: var(--space-2); align-items: end; }
  .row .field-label { grid-column: 1 / -1; margin: 0; }
  .forget { margin-top: var(--space-3); }
  .message { font-size: var(--text-sm); color: var(--text-2); margin: var(--space-3) 0 0; }
  .grant { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3);
    padding: var(--row-y) var(--row-x); border: 1px solid var(--ok-border);
    background: var(--ok-soft); border-radius: var(--r-sm); }
  .grant strong { display: block; }
  .detail, .ttl { color: var(--text-2); font-size: var(--text-xs); }
  .scopes { display: flex; gap: var(--space-2); flex-wrap: wrap; }
  @media (max-width: 40rem) { .row { grid-template-columns: 1fr; } }
</style>
