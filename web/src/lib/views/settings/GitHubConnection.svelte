<script lang="ts">
  /**
   * ADD-27 GH-19 — Settings → Connections → GitHub.
   *
   * The six states of the specification's §4.2 are shown apart, because a
   * single "Connected" light says nothing about whether the app is installed,
   * the repository is reachable, the credential is usable, the capability is on
   * or this operation is approved. Methods follow, each one a deliberate choice;
   * then repositories, delegations and the permission matrix. A custom App is
   * under Advanced: ordinary onboarding never asks for a Client ID.
   */
  import { onDestroy, onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type {
    GitHubConnection,
    GitHubCredentialView,
    GitHubDiscovery,
    GitHubSignInAttempt,
    GitHubAppValidation,
  } from "../../apiTypes";
  import type { IssueToPrRoutineView, ProjectView } from "../../generated/apiContract";
  import PageState from "../../components/PageState.svelte";
  import { newIdempotencyKey } from "../../idempotency";
  import GitCredential from "./GitCredential.svelte";

  let connection = $state<GitHubConnection | null>(null);
  let discovery = $state<GitHubDiscovery | null>(null);
  let loadError = $state<string | null>(null);
  let busy = $state(false);
  let notice = $state<string | null>(null);
  let attempt = $state<GitHubSignInAttempt | null>(null);
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  let helperUsername = $state("");
  let delegationRepository = $state("");
  let delegationOperations = $state<string[]>(["push", "pull_request"]);
  let delegationPattern = $state("raiker/*");
  let delegationHours = $state(24);
  let delegationBudget = $state<number | null>(null);

  // BUG-339 — the issue-to-pull-request routine: a plan first, then a Build task.
  let routineDelegation = $state("");
  let routineRepo = $state("");
  let routineIssue = $state<number | null>(null);
  let routineBranch = $state("");
  let routineProject = $state("");
  let routineStart = $state("");
  let routinePlan = $state<IssueToPrRoutineView | null>(null);
  let projects = $state<ProjectView[]>([]);
  // BR-02 / BR-D03 — the repository Build is pointed at now is the one the
  // scheduled task is bound to; its runs happen there or not at all.
  let buildRepoLabel = $state<string | null>(null);
  let routineKey = newIdempotencyKey();
  const DECISION_LABEL: Record<string, string> = {
    runs: "Runs",
    runs_under_delegation: "Runs under the delegation",
    asks: "Asks you first",
  };

  let appClientId = $state("");
  let appId = $state("");
  let appCallback = $state("");
  let appKeyPath = $state("");
  let appWebhooks = $state(false);
  let validation = $state<GitHubAppValidation | null>(null);

  const STATES: { key: keyof GitHubConnection["states"]; label: string; yes: string; no: string }[] = [
    { key: "connected_account", label: "GitHub account", yes: "Signed in and checked", no: "No account checked" },
    { key: "application_installed", label: "Raiker app", yes: "Installed", no: "Not installed" },
    { key: "repository_authorised", label: "Repositories", yes: "At least one reachable", no: "None listed yet" },
    { key: "credential_available", label: "Credential", yes: "Ready to lend", no: "Not available" },
    { key: "capability_enabled", label: "Capability", yes: "Push or GitHub turned on", no: "Off in Permissions" },
    { key: "operation_approved", label: "Approval", yes: "An approval or delegation is in force", no: "Each use asks" },
  ];

  const METHOD_LABEL: Record<string, string> = {
    pat: "Personal access token",
    environment: "RAIKER_GITHUB_TOKEN variable",
    gh_cli: "GitHub CLI sign-in",
    os_helper: "Saved Git credential",
    ssh: "SSH key",
    app_user: "GitHub sign-in",
    app_installation: "GitHub App installation",
  };

  /** §14 recovery messages: what happened, in words, and what to do next. */
  const RECOVERY: [RegExp, string][] = [
    [/cancelled/, "Sign-in was cancelled. Nothing was connected."],
    [/access_denied|denied/, "GitHub did not grant access. Try again or use another method."],
    [/installation_(removed|unknown|suspended)/, "The Raiker app isn't installed on this account or organisation. Install it on GitHub."],
    [/repository_not_authorised/, "That repository isn't among the ones the app can see. Choose repositories on GitHub."],
    [/expired/, "Your GitHub sign-in expired. Sign in again."],
    [/credential_rejected/, "Access was revoked at GitHub. Sign in again."],
    [/account_mismatch/, "This credential now belongs to a different GitHub account. Select it again."],
    [/unavailable|not_installed|not_signed_in|helper/, "That credential isn't available on this machine. Choose another."],
    [/github_unreachable/, "Couldn't reach GitHub. Nothing was changed."],
    [/github_app_/, "This GitHub App configuration is incomplete. Check the fields under Advanced."],
    [/not_delegable/, "Merging, deleting branches and changing workflows are never delegated — they ask every time."],
    [/branch_pattern/, "Name a work-branch prefix such as raiker/* — a delegation never reaches the default branch."],
    [/delegation_credential_required|git_token_not_configured/, "Connect GitHub first."],
  ];

  function explain(error: unknown): string {
    const reason = error instanceof ApiError ? (error.reasonCode ?? error.message) : String(error);
    const match = RECOVERY.find(([pattern]) => pattern.test(reason));
    return match ? match[1] : reason;
  }

  async function run(action: () => Promise<unknown>, done?: string): Promise<void> {
    if (busy) return;
    busy = true;
    notice = null;
    try {
      await action();
      if (done) notice = done;
    } catch (error) {
      notice = explain(error);
    } finally {
      busy = false;
    }
  }

  async function load(): Promise<void> {
    try {
      loadError = null;
      connection = await api.github();
    } catch (error) {
      loadError = error instanceof ApiError ? error.message : String(error);
    }
  }

  async function findMethods(): Promise<void> {
    await run(async () => {
      discovery = await api.githubDiscovery();
    });
  }

  function schedulePoll(current: GitHubSignInAttempt): void {
    if (pollTimer) clearTimeout(pollTimer);
    if (current.outcome !== "pending") return;
    const due = current.next_poll_at ? Date.parse(current.next_poll_at) - Date.now() : 5000;
    // Never sooner than GitHub's interval; never parked longer than a minute.
    pollTimer = setTimeout(poll, Math.min(60_000, Math.max(1000, due + 250)));
  }

  async function poll(): Promise<void> {
    if (!attempt) return;
    try {
      attempt = await api.pollGithubSignIn(attempt.attempt_id);
    } catch (error) {
      notice = explain(error);
      attempt = null;
      return;
    }
    if (attempt.outcome === "connected") {
      notice = "Signed in to GitHub.";
      attempt = null;
      await load();
    } else if (attempt.outcome !== "pending") {
      notice = explain(attempt.outcome);
      attempt = null;
    } else {
      schedulePoll(attempt);
    }
  }

  async function signIn(method: "device" | "browser"): Promise<void> {
    await run(async () => {
      attempt = await api.startGithubSignIn(method);
      if (method === "browser" && attempt.authorize_url) {
        window.open(attempt.authorize_url, "_blank", "noopener");
      } else {
        schedulePoll(attempt);
      }
    });
  }

  async function cancelSignIn(): Promise<void> {
    if (!attempt) return;
    if (pollTimer) clearTimeout(pollTimer);
    const id = attempt.attempt_id;
    attempt = null;
    await run(() => api.cancelGithubSignIn(id), "Sign-in was cancelled. Nothing was connected.");
  }

  async function use(method: "gh_cli" | "os_helper" | "ssh", selector: string): Promise<void> {
    await run(async () => {
      connection = await api.addGithubCredential(method, selector);
    }, `${METHOD_LABEL[method]} checked and selected.`);
  }

  async function select(row: GitHubCredentialView): Promise<void> {
    await run(async () => {
      connection = await api.selectGithubCredential(row.credential_id);
    }, `Now using ${row.label}${row.account_login ? ` as @${row.account_login}` : ""}.`);
  }

  async function check(row: GitHubCredentialView): Promise<void> {
    await run(async () => {
      connection = await api.checkGithubCredential(row.credential_id);
    }, "Checked with GitHub.");
  }

  async function disconnect(row: GitHubCredentialView): Promise<void> {
    await run(async () => {
      const outcome = await api.disconnectGithubCredential(row.credential_id);
      await load();
      notice =
        outcome.github === "revoked"
          ? "Disconnected, and GitHub confirmed the access was revoked."
          : outcome.github === "could_not_confirm"
            ? "Disconnected here. GitHub could not confirm the revocation — review authorised apps on GitHub."
            : "Disconnected here. Raiker no longer uses it.";
    });
  }

  async function refreshRepositories(): Promise<void> {
    await run(async () => {
      connection = await api.refreshGithubRepositories();
    }, "Repositories refreshed from GitHub.");
  }

  async function toggleRepository(credentialId: string, repositoryId: string, selected: boolean): Promise<void> {
    await run(async () => {
      connection = await api.selectGithubRepository(repositoryId, credentialId, selected);
    });
  }

  async function delegate(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const repository = delegationRepository.trim().startsWith("github.com/")
      ? delegationRepository.trim()
      : `github.com/${delegationRepository.trim()}`;
    await run(async () => {
      await api.createGithubDelegation({
        repository,
        operations: delegationOperations,
        branch_pattern: delegationPattern.trim() || null,
        expires_in_hours: Number(delegationHours) || 24,
        max_actions: delegationBudget ? Number(delegationBudget) : null,
      });
      await load();
    }, "Delegated. Each use is recorded; revoke it here at any time.");
  }

  async function revokeDelegation(id: string): Promise<void> {
    await run(async () => {
      connection = await api.revokeGithubDelegation(id);
    }, "Delegation revoked, with every share narrowed from it.");
  }

  function routineRepository(): string {
    const delegated = connection?.delegations.find((row) => row.delegation_id === routineDelegation);
    return delegated?.repository ?? routineRepo.trim();
  }

  async function planRoutine(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!routineIssue) return;
    await run(async () => {
      routinePlan = await api.planIssueToPrRoutine({
        repository: routineRepository(),
        issue_number: Number(routineIssue),
        work_branch: routineBranch.trim() || `raiker/issue-${routineIssue}`,
        delegation_id: routineDelegation || null,
      });
      if (!projects.length) projects = (await api.projects()).projects;
      try {
        const repos = await api.codeRepos();
        buildRepoLabel = repos.repos.find((repo) => repo.repo_id === repos.selected_repo_id)?.label ?? null;
      } catch {
        buildRepoLabel = null;
      }
    });
  }

  async function scheduleRoutine(): Promise<void> {
    const plan = routinePlan;
    if (plan === null || !routineProject) return;
    await run(async () => {
      await api.createTask({
        title: plan.title,
        description: plan.description,
        surface: "build",
        project_id: routineProject,
        ...(routineStart ? { scheduled_at: new Date(routineStart).toISOString() } : {}),
      }, routineKey);
      routineKey = newIdempotencyKey();
      routinePlan = null;
    }, "Scheduled as a Build task. Its writes run only under the delegation; anything else waits in Approvals.");
  }

  async function saveApp(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    await run(async () => {
      await api.configureGithubApp({
        client_id: appClientId.trim(),
        app_id: appId.trim() || null,
        callback_url: appCallback.trim() || null,
        private_key: appKeyPath.trim() ? { kind: "file", value: appKeyPath.trim() } : null,
        webhooks_enabled: appWebhooks,
      });
      await load();
    }, "Custom GitHub App saved. Validate it before signing in with it.");
  }

  async function validateApp(): Promise<void> {
    await run(async () => {
      validation = await api.validateGithubApp();
      await load();
    });
  }

  async function removeApp(): Promise<void> {
    await run(async () => {
      connection = await api.removeGithubApp();
      validation = null;
    }, "Custom GitHub App removed.");
  }

  function toggleOperation(operation: string, on: boolean): void {
    delegationOperations = on
      ? [...new Set([...delegationOperations, operation])]
      : delegationOperations.filter((item) => item !== operation);
  }

  let delegable = $derived(
    (connection?.risks ?? []).filter((row) => row.delegable && row.operation !== "read"),
  );

  onMount(load);
  onDestroy(() => {
    if (pollTimer) clearTimeout(pollTimer);
  });
</script>

<section class="github-connection">
  <header class="section-heading">
    <h2>GitHub</h2>
    <p>
      Which GitHub account Raiker works as, how it signs in, which repositories it may
      reach, and what it may do there without asking.
    </p>
  </header>

  {#if loadError}
    <PageState state="error" title="Couldn't load the GitHub connection" detail={loadError} />
  {:else if !connection}
    <PageState state="loading" title="Reading the GitHub connection…" />
  {:else}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}

    <div class="card">
      <h3>Status</h3>
      <p class="lead">Six separate questions. Each one has to be yes before a push runs unprompted.</p>
      <dl class="states" data-testid="github-states">
        {#each STATES as row (row.key)}
          <div class="state-row" class:on={connection.states[row.key]}>
            <dt>{row.label}</dt>
            <dd>{connection.states[row.key] ? row.yes : row.no}</dd>
          </div>
        {/each}
      </dl>
      {#if connection.selected}
        <p class="selected">
          Using <strong>{connection.selected.label}</strong>
          {#if connection.selected.account_login}as <strong>@{connection.selected.account_login}</strong>{/if}
          {#if connection.selected.expires_at}· expires {new Date(connection.selected.expires_at).toLocaleString()}{/if}
        </p>
      {/if}
    </div>

    <div class="card">
      <h3>Connect</h3>
      <p class="lead">
        Pick one. Raiker never switches between them on its own, and each is checked against
        the GitHub account it says it is before it is used.
      </p>
      <div class="actions">
        {#if connection.device_sign_in}
          <button class="btn btn-primary" type="button" onclick={() => signIn("device")} disabled={busy || attempt !== null}>
            Connect GitHub
          </button>
        {/if}
        {#if connection.browser_sign_in}
          <button class="btn" type="button" onclick={() => signIn("browser")} disabled={busy || attempt !== null}>
            Sign in in the browser
          </button>
        {/if}
        <button class="btn" type="button" onclick={findMethods} disabled={busy}>
          Find credentials on this machine
        </button>
      </div>
      {#if !connection.device_sign_in}
        <p class="state">
          GitHub sign-in isn't available in this build yet. Use a credential this machine already has,
          a personal access token, or a custom GitHub App under Advanced.
        </p>
      {/if}

      {#if attempt}
        <div class="attempt" role="status" data-testid="github-device-code">
          {#if attempt.user_code}
            <p>Enter this code at GitHub:</p>
            <p class="code">{attempt.user_code}</p>
            {#if attempt.verification_uri}
              <a class="btn btn-primary" href={attempt.verification_uri} target="_blank" rel="noopener noreferrer">
                Open GitHub
              </a>
            {/if}
            <p class="state">Waiting for GitHub… this page checks no faster than GitHub allows.</p>
          {:else}
            <p>Finish signing in in the tab that opened.</p>
          {/if}
          <button class="btn btn-sm" type="button" onclick={cancelSignIn}>Cancel</button>
        </div>
      {/if}

      {#if discovery}
        <div class="methods" data-testid="github-discovery">
          <div>
            <h4>GitHub CLI sign-in</h4>
            {#if discovery.gh_accounts.length}
              {#each discovery.gh_accounts as account (account.login)}
                <button class="btn btn-sm" type="button" onclick={() => use("gh_cli", account.login)} disabled={busy}>
                  Use @{account.login}{account.active ? " (active)" : ""}
                </button>
              {/each}
            {:else}
              <p class="state">No GitHub CLI sign-in found.</p>
            {/if}
          </div>
          <div>
            <h4>Saved Git credential</h4>
            {#if discovery.credential_helpers.length}
              <form class="row" onsubmit={(event) => { event.preventDefault(); use("os_helper", helperUsername.trim()); }}>
                <label class="field-label" for="helper-user">GitHub username saved in {discovery.credential_helpers.join(", ")}</label>
                <input id="helper-user" class="input" autocomplete="off" bind:value={helperUsername} placeholder="octocat" />
                <button class="btn btn-sm" type="submit" disabled={busy || !helperUsername.trim()}>Use</button>
              </form>
            {:else}
              <p class="state">No Git credential manager is configured.</p>
            {/if}
          </div>
          <div>
            <h4>SSH key</h4>
            {#if discovery.ssh_keys.length}
              {#each discovery.ssh_keys as key (key.fingerprint)}
                <button class="btn btn-sm" type="button" onclick={() => use("ssh", key.path)} disabled={busy}>
                  Use <code>{key.fingerprint}</code>
                </button>
              {/each}
            {:else}
              <p class="state">No SSH key with a public half found in ~/.ssh.</p>
            {/if}
          </div>
        </div>
      {/if}
    </div>

    <div class="card">
      <h3>Credentials</h3>
      {#if connection.credentials.length}
        <ul class="rows" data-testid="github-credentials">
          {#each connection.credentials as row (row.credential_id)}
            <li class="item">
              <div>
                <strong>{METHOD_LABEL[row.method] ?? row.label}</strong>
                {#if row.selected}<span class="badge">In use</span>{/if}
                <span class="detail">
                  {row.account_login ? `@${row.account_login}` : "account not checked yet"} · {row.status}
                  {#if !row.usable}· not available on this machine{/if}
                  {#if row.last_error}· {explain(row.last_error)}{/if}
                </span>
              </div>
              <div class="actions">
                {#if !row.selected}<button class="btn btn-sm" type="button" onclick={() => select(row)} disabled={busy || !row.usable}>Use</button>{/if}
                <button class="btn btn-sm" type="button" onclick={() => check(row)} disabled={busy}>Check</button>
                <button class="btn btn-sm btn-danger" type="button" onclick={() => disconnect(row)} disabled={busy}>Disconnect</button>
              </div>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="state">Nothing connected. Raiker can read public repositories, and cannot push.</p>
      {/if}
    </div>

    <div class="card">
      <h3>Repositories</h3>
      <p class="lead">Asked of GitHub, by repository id, for the credential in use.</p>
      <button class="btn btn-sm" type="button" onclick={refreshRepositories} disabled={busy || !connection.selected}>
        Refresh from GitHub
      </button>
      {#if connection.repositories.length}
        <ul class="rows" data-testid="github-repositories">
          {#each connection.repositories as repo (`${repo.credential_id}:${repo.repository_id}`)}
            <li class="item">
              <label class="check">
                <input
                  type="checkbox"
                  checked={repo.selected}
                  disabled={busy || repo.status !== "available"}
                  onchange={(event) => toggleRepository(repo.credential_id, repo.repository_id, (event.currentTarget as HTMLInputElement).checked)}
                />
                {repo.full_name}
              </label>
              <span class="detail">{repo.private ? "private" : "public"}{repo.status !== "available" ? " · no longer reachable" : ""}</span>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="card">
      <h3>Delegations</h3>
      <p class="lead">
        Work Raiker may do in one repository without asking each time. Nothing else
        stands in for this: a standing decision mode or grant alone never pushes.
        Merging, deleting a branch and changing workflows are never delegated.
      </p>
      {#if connection.delegations.length}
        <ul class="rows" data-testid="github-delegations">
          {#each connection.delegations as row (row.delegation_id)}
            <li class="item">
              <div>
                <strong>{row.repository.replace("github.com/", "")}</strong>
                <span class="detail">
                  {row.operations.join(", ")}{row.branch_pattern ? ` on ${row.branch_pattern}` : ""} ·
                  until {new Date(row.expires_at).toLocaleString()}
                  {#if row.max_actions !== null}· {row.actions_used}/{row.max_actions} used{/if}
                </span>
              </div>
              <button class="btn btn-sm btn-danger" type="button" onclick={() => revokeDelegation(row.delegation_id)} disabled={busy}>Revoke</button>
            </li>
          {/each}
        </ul>
      {/if}
      <form class="delegate" onsubmit={delegate}>
        <label class="field-label" for="delegation-repo">Repository</label>
        <input id="delegation-repo" class="input" list="github-repo-names" bind:value={delegationRepository} placeholder="owner/name" />
        <datalist id="github-repo-names">
          {#each connection.repositories as repo (`${repo.credential_id}:${repo.repository_id}`)}<option value={repo.full_name}></option>{/each}
        </datalist>
        <fieldset class="ops">
          <legend class="field-label">May</legend>
          {#each delegable as row (row.operation)}
            <label class="check">
              <input
                type="checkbox"
                checked={delegationOperations.includes(row.operation)}
                onchange={(event) => toggleOperation(row.operation, (event.currentTarget as HTMLInputElement).checked)}
              />
              {row.label}
            </label>
          {/each}
        </fieldset>
        <label class="field-label" for="delegation-pattern">Branches</label>
        <input id="delegation-pattern" class="input" bind:value={delegationPattern} placeholder="raiker/*" />
        <div class="pair">
          <label class="field-label" for="delegation-hours">Hours</label>
          <input id="delegation-hours" class="input" type="number" min="1" max="720" bind:value={delegationHours} />
          <label class="field-label" for="delegation-budget">At most (actions)</label>
          <input id="delegation-budget" class="input" type="number" min="1" max="1000" bind:value={delegationBudget} placeholder="no limit" />
        </div>
        <button class="btn btn-primary" type="submit" disabled={busy || !delegationRepository.trim() || !delegationOperations.length || !connection.selected}>
          Delegate
        </button>
      </form>
    </div>

    <div class="card">
      <h3>Issue to pull request</h3>
      <p class="lead">
        Hand Raiker one issue to fix on a work branch, as a Build task. You see which
        steps would run before anything is scheduled. Without a delegation every write
        asks you; a merge is never part of it.
      </p>
      <form class="delegate" onsubmit={planRoutine} data-testid="github-issue-routine">
        <label class="field-label" for="routine-delegation">Delegation</label>
        <select id="routine-delegation" class="input" bind:value={routineDelegation}>
          <option value="">None — every write asks</option>
          {#each connection.delegations as row (row.delegation_id)}
            <option value={row.delegation_id}>{row.repository.replace("github.com/", "")} · {row.operations.join(", ")}</option>
          {/each}
        </select>
        {#if !routineDelegation}
          <label class="field-label" for="routine-repo">Repository to work in</label>
          <input id="routine-repo" class="input" list="github-repo-names" bind:value={routineRepo} placeholder="owner/name" />
        {/if}
        <div class="pair">
          <label class="field-label" for="routine-issue">Issue</label>
          <input id="routine-issue" class="input" type="number" min="1" bind:value={routineIssue} placeholder="7" />
          <label class="field-label" for="routine-branch">Work branch</label>
          <input id="routine-branch" class="input" bind:value={routineBranch} placeholder={routineIssue ? `raiker/issue-${routineIssue}` : "raiker/issue-7"} />
        </div>
        <button class="btn" type="submit" disabled={busy || !routineIssue || !(routineDelegation || routineRepo.trim())}>
          Show the plan
        </button>
      </form>
      {#if routinePlan}
        {#if routinePlan.blocked_needs_owner}
          <p class="detail" role="alert">
            The delegation no longer holds ({routinePlan.delegation_problems.join(", ").replaceAll("_", " ")}), so every write would ask you.
          </p>
        {/if}
        <ol class="rows" data-testid="github-issue-routine-plan">
          {#each routinePlan.steps as step (step.step)}
            <li class="item"><span>{step.label}</span><span class="badge">{DECISION_LABEL[step.decision] ?? step.decision}</span></li>
          {/each}
        </ol>
        <p class="detail">Never: {routinePlan.never.map((word) => word.replaceAll("_", " ")).join(", ")}.</p>
        <div class="delegate">
          <label class="field-label" for="routine-project">Project (the repository's local checkout)</label>
          <select id="routine-project" class="input" bind:value={routineProject}>
            <option value="">Choose a project</option>
            {#each projects as project (project.project_id)}<option value={project.project_id}>{project.name}</option>{/each}
          </select>
          <p class="detail" data-testid="github-issue-routine-repository">
            {#if buildRepoLabel}
              Runs in <strong>{buildRepoLabel}</strong> — the repository Build is pointed at now, and only
              there: a run that finds Build pointed at another repository does not start.
            {:else}
              Build is not pointed at a repository. Choose this repository's local checkout in Build first:
              the task runs only in the repository Build is pointed at when you schedule it.
            {/if}
          </p>
          <label class="field-label" for="routine-start">Start (leave empty for the next scheduler tick)</label>
          <input id="routine-start" class="input" type="datetime-local" bind:value={routineStart} />
          <button class="btn btn-primary" type="button" onclick={scheduleRoutine} disabled={busy || !routineProject}>
            Schedule as a Build task
          </button>
        </div>
      {/if}
    </div>

    <div class="card">
      <h3>Permissions</h3>
      <table class="risks" data-testid="github-risks">
        <thead><tr><th scope="col">Operation</th><th scope="col">Risk</th><th scope="col">By default</th><th scope="col">Delegable</th></tr></thead>
        <tbody>
          {#each connection.risks as row (row.operation)}
            <tr>
              <td>{row.label}</td>
              <td>{row.risk === "none" ? "—" : row.risk}</td>
              <td>{row.default.replaceAll("_", " ")}</td>
              <td>{row.delegable ? "yes" : "no"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <details class="card advanced">
      <summary>Personal access token and one-off approvals</summary>
      <GitCredential embedded onchanged={load} />
    </details>

    <details class="card advanced">
      <summary>Advanced (self-hosted): a custom GitHub App</summary>
      <p class="lead">
        Your own GitHub App, for a self-hosted Raiker. Its private key stays where you keep it —
        give a file path readable only by you. Raiker records where it is, not what it is.
      </p>
      {#each connection.apps.filter((app) => app.app_ref === "byo") as app (app.app_ref)}
        <p class="state">
          Configured: <code>{app.client_id}</code>{app.slug ? ` (${app.slug})` : ""} ·
          {app.private_key_configured ? "key set" : "no key"} · {app.webhooks_enabled ? "webhooks on" : "webhooks off"}
        </p>
      {/each}
      <form class="app" onsubmit={saveApp}>
        <label class="field-label" for="app-client">Client ID</label>
        <input id="app-client" class="input" autocomplete="off" bind:value={appClientId} />
        <label class="field-label" for="app-id">App ID</label>
        <input id="app-id" class="input" autocomplete="off" bind:value={appId} />
        <label class="field-label" for="app-callback">Callback URL (for browser sign-in)</label>
        <input id="app-callback" class="input" autocomplete="off" bind:value={appCallback} placeholder="https://raiker.example/api/github/callback" />
        <label class="field-label" for="app-key">Private key file</label>
        <input id="app-key" class="input" autocomplete="off" bind:value={appKeyPath} placeholder="/etc/raiker/github-app.pem" />
        <label class="check"><input type="checkbox" bind:checked={appWebhooks} /> Receive webhooks</label>
        <div class="actions">
          <button class="btn btn-primary" type="submit" disabled={busy || !appClientId.trim()}>Save</button>
          <button class="btn" type="button" onclick={validateApp} disabled={busy}>Validate</button>
          <button class="btn btn-danger" type="button" onclick={removeApp} disabled={busy}>Remove</button>
        </div>
      </form>
      {#if validation}
        <ul class="rows" data-testid="github-app-validation">
          {#each validation.checks as item (item.check)}
            <li class="item"><span>{item.check.replaceAll("_", " ")}</span><span class="detail">{item.result}</span></li>
          {/each}
          {#if validation.excess_permissions.length}
            <li class="item"><span>More permission than Raiker needs</span><span class="detail">{validation.excess_permissions.join(", ")}</span></li>
          {/if}
        </ul>
      {/if}
    </details>
  {/if}
</section>

<style>
  .section-heading h2 { margin: 0; }
  .section-heading p { color: var(--text-2); margin: 0.3rem 0 var(--space-5); }
  .card { margin-bottom: var(--space-4); }
  .card h3 { margin: 0 0 0.3rem; font-size: var(--text-lg); }
  .card h4 { margin: 0 0 var(--space-2); font-size: var(--text-sm); }
  .lead { color: var(--text-2); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
  .state { font-size: var(--text-sm); color: var(--text-2); margin: var(--space-2) 0; }
  .notice { font-size: var(--text-sm); color: var(--text-1); margin: 0 0 var(--space-3); }
  .states { display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: var(--space-2); margin: 0; }
  .state-row { border: 1px solid var(--border); border-radius: var(--r-sm); padding: var(--row-y) var(--row-x); }
  .state-row dt { font-size: var(--text-xs); color: var(--text-3); text-transform: uppercase; letter-spacing: 0.04em; }
  .state-row dd { margin: 0.15rem 0 0; font-size: var(--text-sm); color: var(--text-2); }
  .state-row.on dd { color: var(--text-1); }
  .selected { font-size: var(--text-sm); margin: var(--space-3) 0 0; }
  .actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .attempt { margin-top: var(--space-3); padding: var(--space-3); border: 1px solid var(--border); border-radius: var(--r-sm); display: grid; gap: var(--space-2); justify-items: start; }
  .attempt p { margin: 0; }
  .code { font-family: var(--font-mono); font-size: var(--text-xl); letter-spacing: 0.1em; }
  .methods { display: grid; gap: var(--space-4); margin-top: var(--space-4); }
  .methods .btn { margin: 0 var(--space-2) var(--space-2) 0; }
  .rows { list-style: none; margin: var(--space-3) 0 0; padding: 0; display: grid; gap: var(--space-2); }
  .item { display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
  .item strong { margin-right: var(--space-2); }
  .detail { display: block; color: var(--text-2); font-size: var(--text-xs); }
  .badge { font-size: var(--text-xs); padding: 0 0.4rem; border-radius: var(--r-sm); background: var(--sunken); color: var(--text-2); }
  .check { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); }
  .row, .delegate, .app { display: grid; gap: var(--space-2); }
  .delegate { margin-top: var(--space-4); }
  .ops { border: 0; padding: 0; margin: 0; display: grid; gap: var(--space-1); }
  .pair { display: grid; grid-template-columns: auto minmax(0, 8rem) auto minmax(0, 8rem); gap: var(--space-2); align-items: center; }
  .pair .field-label { margin: 0; }
  .risks { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }
  .risks th, .risks td { text-align: left; padding: 0.3rem var(--space-2); border-bottom: 1px solid var(--border); }
  .risks th { color: var(--text-3); font-weight: 500; font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.04em; }
  .advanced summary { cursor: pointer; font-weight: 600; }
  .advanced[open] summary { margin-bottom: var(--space-3); }
  @media (max-width: 40rem) {
    .pair { grid-template-columns: 1fr; }
    .risks th:nth-child(3), .risks td:nth-child(3) { display: none; }
  }
</style>
