<script lang="ts">
  /**
   * REM-SET-GIT — scope before secret.
   *
   * This page used to open on a password field. An owner's first act was to
   * paste a credential, and only afterwards could they find out what it would
   * be used for, which host it would be offered to, or how to take it back. The
   * order is now the other way round: the boundary the runtime issues the
   * credential inside is stated first — read from the runtime, not written down
   * again here — then how a credential may be supplied, and the field last.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { GitCredentialStatus } from "../../apiTypes";
  import PageState from "../../components/PageState.svelte";
  import Icon from "../../components/Icon.svelte";

  let status = $state<GitCredentialStatus | null>(null);
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
    <!-- Step one, and the reason this card is above the field rather than below
         it: what the credential is for is a decision, and a decision made after
         the secret has been pasted is not a decision. -->
    <ol class="steps">
      <li class="card step">
        <h3><span class="step-number" aria-hidden="true">1</span> Where it may be used</h3>
        <p class="lead">
          Raiker will only offer this credential to these hosts, for these operations.
          Everything else — reading a public repository, a remote on another forge, a
          redirect that sends git somewhere unexpected — is answered without it.
        </p>
        <dl class="scope">
          <dt>Hosts</dt>
          <dd>
            {#each status.hosts as host (host)}<code>{host}</code>{/each}
          </dd>
          <dt>Operations</dt>
          <dd>
            <ul class="operations">
              {#each status.operations as operation (operation)}<li>{operation}</li>{/each}
            </ul>
          </dd>
          <dt>Each use</dt>
          <dd>Needs your approval, recorded as an action you can read back.</dd>
        </dl>
      </li>

      <li class="card step">
        <h3><span class="step-number" aria-hidden="true">2</span> How it is supplied</h3>
        <p class="lead">
          One supported method, and one that Raiker deliberately does not use.
        </p>
        <ul class="methods">
          <li class="method supported">
            <Icon name="check" size="sm" />
            <div>
              <strong>A scoped GitHub token</strong>
              <p>
                A fine-grained personal access token with <em>Contents: read and write</em>
                on only the repositories you want Raiker to push to. A token scoped to
                one repository can do one repository's worth of damage.
              </p>
            </div>
          </li>
          <li class="method declined">
            <Icon name="info" size="sm" />
            <div>
              <strong>Not this machine's credential manager</strong>
              <p>
                A governed push clears whatever helper this machine has configured
                before it runs. A keychain answers for whichever account signed in
                last, which Raiker cannot name for you, cannot scope, and cannot
                withdraw — so it would be a credential nobody governed.
              </p>
            </div>
          </li>
        </ul>
      </li>

      <li class="card step">
        <h3><span class="step-number" aria-hidden="true">3</span> The token</h3>
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
      </li>
    </ol>

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
  .card h3 { margin: 0 0 0.3rem; font-size: var(--text-lg); display: flex; align-items: center; gap: var(--space-2); }
  .steps { list-style: none; margin: 0; padding: 0; }
  /* The number is the ordering made visible. The reading order is the point of
     this page, so it is stated rather than left to be inferred from position. */
  .step-number {
    flex: 0 0 auto; width: 1.5rem; height: 1.5rem; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    background: var(--sunken); color: var(--text-2);
    font-size: var(--text-xs); font-weight: 600;
  }
  .lead { color: var(--text-2); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
  .state { font-size: var(--text-sm); color: var(--text-2); margin: 0 0 var(--space-2); }
  /* A persistent normal state is neutral. Success colour is spent on
     something that just happened or on a decision that was just confirmed; used
     as the standing representation of "connected", "enabled", "verified" or
     "ready" it is on screen constantly, which is the one condition under which
     a colour stops carrying information. Exceptions keep their tone. */
  .state.ok { color: var(--text-1); }
  .scope { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 0.35rem var(--space-4); margin: 0; }
  .scope dt { color: var(--text-3); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.04em; }
  .scope dd { margin: 0; font-size: var(--text-sm); color: var(--text-1); display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .operations { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.2rem; }
  .methods { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
  .method { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--space-3); align-items: start; }
  .method strong { display: block; }
  .method p { color: var(--text-2); font-size: var(--text-sm); margin: 0.15rem 0 0; }
  .method.declined { color: var(--text-3); }
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
  @media (max-width: 40rem) {
    .row { grid-template-columns: 1fr; }
    .scope { grid-template-columns: 1fr; gap: 0.15rem; }
    .scope dd { margin-bottom: var(--space-2); }
  }
</style>
