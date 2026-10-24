<script lang="ts">
  /**
   * QUI-F09 — undo what Raiker learned, in one place (Memory › Controls).
   *
   * Two lists, each with **Undo**:
   *
   * * **What Raiker has learned to do** — skills Raiker built in this
   *   workspace. Undo turns the skill off; it is kept and can be turned on
   *   again in Connections › Skills, so Undo is itself undoable.
   * * **Approvals you've given** — standing approvals still in force. Undo
   *   revokes one: the next matching action asks again. Revoking cannot be
   *   reversed, so it asks first, in the one confirmation dialog.
   *
   * Memories themselves are on Memories, where each has its own Forget.
   */
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { SkillView, StandingGrant } from "../apiTypes";
  import { askConfirm } from "../confirm.svelte";
  import { failure } from "../errorCopy";
  import { humanize, relativeTime } from "../format";

  let skills = $state<SkillView[] | null>(null);
  let grants = $state<StandingGrant[] | null>(null);
  let problem = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let notice = $state<string | null>(null);

  const learned = $derived((skills ?? []).filter((skill) => skill.source === "built" && skill.active));
  const given = $derived(
    (grants ?? []).filter((grant) => !grant.revoked && Date.parse(grant.expires_at) > Date.now()),
  );

  async function load(): Promise<void> {
    problem = null;
    const [skillRead, grantRead] = await Promise.allSettled([api.skills(), api.standingGrants(false)]);
    skills = skillRead.status === "fulfilled" ? skillRead.value : [];
    grants = grantRead.status === "fulfilled" ? grantRead.value.grants : [];
    if (skillRead.status === "rejected" || grantRead.status === "rejected") {
      problem = "Part of this list could not be read. What is shown is accurate; try again for the rest.";
    }
  }

  onMount(() => void load());

  async function undoSkill(skill: SkillView): Promise<void> {
    busy = skill.skill_id;
    notice = null;
    try {
      await api.setSkillActive(skill.skill_id, false);
      notice = `“${skill.name}” is off. Turn it on again in Connections › Skills.`;
      await load();
    } catch (error) {
      problem = failure(`“${skill.name}” was not turned off`, "It is still in use.", "Try again.", error);
    } finally {
      busy = null;
    }
  }

  async function undoGrant(grant: StandingGrant): Promise<void> {
    const what = humanize(grant.tool_name);
    const ok = await askConfirm({
      title: `Stop allowing ${what} without asking?`,
      body: "The next time Raiker wants to do this, it asks you first. This cannot be undone; you can give the approval again later.",
      confirmLabel: "Revoke",
      danger: true,
    });
    if (!ok) return;
    busy = grant.grant_id;
    notice = null;
    try {
      await api.revokeStandingGrant(grant.grant_id);
      notice = `${what} asks you again from now on.`;
      await load();
    } catch (error) {
      problem = failure("The approval was not revoked", "It is still in force.", "Try again.", error);
    } finally {
      busy = null;
    }
  }
</script>

<section class="controls-section" aria-labelledby="learned-h">
  <div class="section-head"><h3 id="learned-h">What Raiker has learned to do</h3></div>
  {#if skills === null}
    <p class="muted" role="status">Reading skills…</p>
  {:else if learned.length === 0}
    <p class="muted">Nothing yet. Skills Raiker builds in this workspace appear here.</p>
  {:else}
    <ul class="control-list">
      {#each learned as skill (skill.skill_id)}
        <li>
          <div><strong>{skill.name}</strong><span>{skill.description}</span></div>
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy === skill.skill_id} onclick={() => void undoSkill(skill)}>Undo</button>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<section class="controls-section" aria-labelledby="given-h">
  <div class="section-head"><h3 id="given-h">Approvals you've given</h3></div>
  {#if grants === null}
    <p class="muted" role="status">Reading approvals…</p>
  {:else if given.length === 0}
    <p class="muted">None in force. Every action that needs approval asks you each time.</p>
  {:else}
    <ul class="control-list">
      {#each given as grant (grant.grant_id)}
        <li>
          <div>
            <strong>{humanize(grant.tool_name)}</strong>
            <span>
              {grant.scope_pattern ? `On ${grant.scope_pattern} · ` : ""}up to {grant.risk_ceiling} risk · used {grant.use_count}
              {grant.use_count === 1 ? "time" : "times"} · ends {relativeTime(grant.expires_at)}
            </span>
          </div>
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy === grant.grant_id} onclick={() => void undoGrant(grant)}>Undo</button>
        </li>
      {/each}
    </ul>
  {/if}
</section>

{#if notice}<p class="notice" role="status">{notice}</p>{/if}
{#if problem}<p class="problem" role="alert">{problem}</p>{/if}

<style>
  .controls-section{margin:0 0 var(--space-5)}
  .controls-section h3{margin:0 0 var(--space-2);font-size:var(--text-md)}
  .control-list{list-style:none;margin:0;padding:0;display:grid;gap:var(--space-2)}
  .control-list li{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-2) var(--space-3);border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface)}
  .control-list li div{display:grid;gap:.1rem;min-width:0}
  .control-list span{color:var(--text-3);font-size:var(--text-xs)}
  .muted{color:var(--text-3);font-size:var(--text-sm);margin:0}
  .notice{color:var(--text-2);font-size:var(--text-sm)}
  .problem{color:var(--danger);font-size:var(--text-sm)}
</style>
