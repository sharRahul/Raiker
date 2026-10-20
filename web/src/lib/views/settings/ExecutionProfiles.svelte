<script lang="ts">
  /**
   * PA-D02 — Settings → Execution profiles.
   *
   * The only place a profile is made, changed, activated or bound to a
   * project. A goal pins the version it was accepted under; changing a profile
   * here writes the next version, and goals running under the old one pause at
   * a safe boundary until Resume rechecks them against it. Every field on this
   * page is enforced when a goal's step is filed and again when it runs.
   */
  import { onMount } from "svelte";
  import PageState from "../../components/PageState.svelte";
  import { ApiError, api } from "../../api";
  import { contract } from "../../generated/apiContract";
  import type { ExecutionProfileList, ExecutionProfileView } from "../../generated/apiContract";
  import type { ProjectView } from "../../apiTypes";
  import { goalRefusal, profileSummary } from "../../goalPresentation";

  let data = $state<ExecutionProfileList | null>(null);
  let projects = $state<ProjectView[]>([]);
  let loadError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busy = $state(false);
  let editing = $state<string | null>(null);
  let draft = $state({ name: "", allow_local: true, allow_hosted: true, providers: "", memory_to_hosted: false, max_step_runs: 10, max_cost_usd: "" });

  async function load() {
    try {
      data = await contract.listExecutionProfiles();
      loadError = null;
    } catch (err) {
      loadError = err instanceof Error ? err.message : "Could not load execution profiles.";
    }
    try {
      const list = await api.projects();
      projects = list.projects.filter((p) => !p.is_archived);
    } catch {
      projects = [];
    }
  }
  onMount(load);

  function reason(err: unknown): string | null {
    return err instanceof ApiError ? err.reasonCode : null;
  }

  function said(paused: number, what: string) {
    notice = paused ? `${what} ${paused} running goal${paused === 1 ? " was" : "s were"} paused until you resume ${paused === 1 ? "it" : "them"}.` : what;
  }

  async function create(template: string) {
    busy = true;
    notice = null;
    try {
      const made = await contract.createExecutionProfile({ template });
      said(made.goals_paused, `Created ${made.profile?.name ?? "a profile"}.`);
      await load();
    } catch (err) {
      notice = goalRefusal(reason(err));
    } finally {
      busy = false;
    }
  }

  function edit(profile: ExecutionProfileView) {
    editing = profile.profile_id;
    draft = {
      name: profile.name,
      allow_local: profile.allow_local,
      allow_hosted: profile.allow_hosted,
      providers: profile.allowed_providers.join(", "),
      memory_to_hosted: profile.memory_to_hosted,
      max_step_runs: profile.max_step_runs,
      max_cost_usd: profile.max_cost_usd == null ? "" : String(profile.max_cost_usd),
    };
  }

  async function save(profile: ExecutionProfileView, event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    notice = null;
    const cost = draft.max_cost_usd.trim();
    try {
      const changed = await contract.updateExecutionProfile(profile.profile_id, {
        base_version: profile.version,
        name: draft.name.trim(),
        allow_local: draft.allow_local,
        allow_hosted: draft.allow_hosted,
        allowed_providers: draft.providers.split(",").map((p) => p.trim()).filter(Boolean),
        memory_to_hosted: draft.allow_hosted && draft.memory_to_hosted,
        max_step_runs: Number(draft.max_step_runs),
        max_cost_usd: cost ? Number(cost) : null,
      });
      editing = null;
      said(changed.goals_paused, `Saved version ${changed.profile?.version ?? ""}.`);
      await load();
    } catch (err) {
      notice = goalRefusal(reason(err));
      if (reason(err) === "execution_profile_version_stale") await load();
    } finally {
      busy = false;
    }
  }

  async function activate(profileId: string) {
    busy = true;
    notice = null;
    try {
      const changed = await contract.setActiveExecutionProfile({ profile_id: profileId });
      said(changed.goals_paused, `${changed.profile?.name ?? "The profile"} is now active for new goals.`);
      await load();
    } catch (err) {
      notice = goalRefusal(reason(err));
    } finally {
      busy = false;
    }
  }

  async function bindProject(projectId: string, profileId: string) {
    busy = true;
    notice = null;
    try {
      const changed = await contract.bindProjectExecutionProfile(projectId, { profile_id: profileId || null });
      said(changed.goals_paused, profileId ? "Bound to the project." : "The project uses the active profile again.");
      await load();
    } catch (err) {
      notice = goalRefusal(reason(err));
    } finally {
      busy = false;
    }
  }

  const bindingFor = (projectId: string) => data?.project_bindings.find((b) => b.project_id === projectId)?.profile_id ?? "";
</script>

<section class="settings-section" aria-labelledby="xprof-h">
  <h2 id="xprof-h">Execution profiles</h2>
  <p class="muted">
    The boundary a goal's work runs under: which models it may reach, whether your personal memory may go to a hosted
    model with it, and its budget. Goals use the active profile, or their project's. A prompt, memory or agent can never
    choose or change one.
  </p>

  {#if loadError}
    <PageState state="error" title="Couldn't load execution profiles" detail={loadError} />
  {:else if data === null}
    <PageState state="loading" title="Loading execution profiles…" />
  {:else}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}

    {#if data.profiles.length === 0}
      <p><strong>No profile yet.</strong> Goals can be drafted, but not accepted, until one exists. Your first profile becomes active.</p>
    {/if}

    <ul class="profiles" aria-label="Profiles">
      {#each data.profiles as profile (profile.profile_id)}
        <li class="card">
          <div class="head">
            <strong>{profile.name}</strong>
            <span class="muted small">version {profile.version}</span>
            {#if data.active_profile_id === profile.profile_id}<span class="pill">Active</span>{/if}
          </div>
          <p class="small">{profileSummary(profile)}</p>
          {#if editing === profile.profile_id}
            <form class="edit" onsubmit={(e) => save(profile, e)}>
              <label>Name <input bind:value={draft.name} maxlength="60" required /></label>
              <label class="inline"><input type="checkbox" bind:checked={draft.allow_local} /> Models on this machine</label>
              <label class="inline"><input type="checkbox" bind:checked={draft.allow_hosted} /> Hosted models</label>
              <label>Only these providers (comma-separated, empty for any) <input bind:value={draft.providers} placeholder="anthropic, ollama" /></label>
              <label class="inline"><input type="checkbox" bind:checked={draft.memory_to_hosted} disabled={!draft.allow_hosted} /> Personal memory may go to a hosted model</label>
              <label>Step runs per goal <input type="number" min="1" max="100" bind:value={draft.max_step_runs} /></label>
              <label>Cost limit per goal, USD (empty for none) <input inputmode="decimal" bind:value={draft.max_cost_usd} /></label>
              <div class="actions">
                <button type="submit" class="btn btn-primary btn-sm" disabled={busy}>Save as version {profile.version + 1}</button>
                <button type="button" class="btn btn-ghost btn-sm" onclick={() => (editing = null)}>Cancel</button>
              </div>
              <p class="muted small">Goals running under version {profile.version} pause at a safe boundary; Resume rechecks them against the new version.</p>
            </form>
          {:else}
            <div class="actions">
              <button type="button" class="btn btn-sm" onclick={() => edit(profile)} disabled={busy}>Edit</button>
              {#if data.active_profile_id !== profile.profile_id}
                <button type="button" class="btn btn-sm" onclick={() => activate(profile.profile_id)} disabled={busy}>Make active</button>
              {/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>

    <h3 class="kicker">Start from a template</h3>
    <ul class="templates" aria-label="Templates">
      {#each data.templates as template (template.template)}
        <li class="card">
          <strong>{template.name}</strong>
          <p class="small">{template.summary}</p>
          <button type="button" class="btn btn-sm" onclick={() => create(template.template)} disabled={busy}>Create {template.name}</button>
        </li>
      {/each}
    </ul>

    {#if projects.length && data.profiles.length}
      <h3 class="kicker">Projects</h3>
      <ul class="bindings" aria-label="Project profiles">
        {#each projects as project (project.project_id)}
          <li>
            <label>{project.name}
              <select value={bindingFor(project.project_id)} onchange={(e) => bindProject(project.project_id, (e.currentTarget as HTMLSelectElement).value)} disabled={busy}>
                <option value="">Use the active profile</option>
                {#each data.profiles as profile (profile.profile_id)}<option value={profile.profile_id}>{profile.name}</option>{/each}
              </select>
            </label>
          </li>
        {/each}
      </ul>
    {/if}
    <p class="muted small">
      A model's placement comes from its profile: a custom OpenAI-compatible endpoint reads as hosted even when it runs on
      this machine, so Private local refuses it.
    </p>
  {/if}
</section>

<style>
  .settings-section { display: grid; gap: var(--space-3); }
  .profiles, .templates, .bindings { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
  .templates { grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); }
  .head { display: flex; gap: 0.5rem; align-items: baseline; flex-wrap: wrap; }
  .pill { border: 1px solid var(--accent-border); background: var(--accent-soft); border-radius: var(--r-pill); padding: 0 0.5rem; font-size: var(--text-xs); }
  .edit { display: grid; gap: 0.5rem; }
  .edit label { display: grid; gap: 0.2rem; }
  .edit label.inline { display: inline-flex; gap: 0.4rem; align-items: center; }
  .bindings label { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
  .actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
  .muted { color: var(--text-2); }
  .small { font-size: var(--text-sm); }
  .notice { margin: 0; font-weight: 600; }
</style>
