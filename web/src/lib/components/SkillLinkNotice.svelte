<script lang="ts">
  /**
   * A skill link pasted into the Chat or Build composer.
   *
   * Pasting a published skill's URL almost always means "install this", not
   * "read this to me". This notice offers that, but never performs it on its
   * own: it asks the server to fetch and validate the document first, then
   * shows the skill's real name and description so the decision is made against
   * facts rather than a URL. Nothing is stored until the owner says add.
   *
   * The composer text is untouched either way — declining leaves the prompt
   * exactly as typed.
   */
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { SkillVerification } from "../apiTypes";
  import { findSkillLinks, isArchiveLink, skillLinkLabel } from "../skillLinks";

  let { text = "" }: { text?: string } = $props();

  const links = $derived(findSkillLinks(text));
  const link = $derived(links[0] ?? null);

  let checked = $state<string | null>(null);
  let verified = $state<SkillVerification | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);
  let installed = $state<string | null>(null);
  let dismissed = $state<string[]>([]);

  const showing = $derived(link !== null && !dismissed.includes(link));

  // A new link resets the panel: the previous verdict describes a different
  // document and must not be presented as this one's.
  $effect(() => {
    if (link !== checked) {
      checked = link;
      verified = null;
      error = null;
      installed = null;
    }
  });

  function reason(e: unknown): string {
    if (e instanceof ApiError) {
      const code = e.reasonCode ?? "";
      if (code === "skill_archive_url_unsupported")
        return "A .skill archive can't be imported from a link — download it, then upload it in Extensions → Skills.";
      if (code === "skill_missing_description" || code === "skill_invalid_name")
        return "That document isn't a valid skill.";
      if (code.startsWith("skill_fetch_failed")) return "That link couldn't be read.";
      return code || `Request failed (${e.status})`;
    }
    return "Request failed";
  }

  async function verify() {
    if (link === null) return;
    busy = true;
    error = null;
    try {
      verified = await api.verifySkillUrl(link);
    } catch (e) {
      error = reason(e);
    } finally {
      busy = false;
    }
  }

  async function add() {
    if (link === null) return;
    busy = true;
    error = null;
    try {
      const result = await api.importSkillUrl(link);
      installed = result.skill?.name ?? verified?.name ?? "the skill";
    } catch (e) {
      error = reason(e);
    } finally {
      busy = false;
    }
  }
</script>

{#if showing && link !== null}
  <div class="skill-link" role="status">
    <Icon name="spark" size="sm" />
    <div class="body">
      {#if installed !== null}
        <p><strong>“{installed}”</strong> is installed. <a href="#/extensions?tab=skills">Open Skills</a></p>
      {:else if verified !== null}
        <p>
          <strong>{verified.name}</strong> — {verified.description}
        </p>
        <p class="sub">
          {verified.already_installed
            ? "You already have a skill with this name. Adding it refreshes the stored document."
            : "Verified. Adding it installs the instructions only — no capability, no gate change."}
        </p>
      {:else if isArchiveLink(link)}
        <p>
          That looks like a <code>.skill</code> bundle. Download it, then upload the file in
          <a href="#/extensions?tab=skills">Extensions → Skills</a>.
        </p>
      {:else}
        <p>
          That link looks like a skill (<span class="mono">{skillLinkLabel(link)}</span>). Verify it
          to see what it actually is before installing.
        </p>
      {/if}
      {#if error}<p class="error">{error}</p>{/if}
    </div>
    <div class="actions">
      {#if installed === null && !isArchiveLink(link)}
        {#if verified === null}
          <button type="button" class="btn btn-sm" onclick={verify} disabled={busy}>
            {busy ? "Verifying…" : "Verify skill"}
          </button>
        {:else}
          <button type="button" class="btn btn-sm btn-primary" onclick={add} disabled={busy}>
            {busy ? "Adding…" : "Add to Skills"}
          </button>
        {/if}
      {/if}
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        onclick={() => (dismissed = [...dismissed, link])}
        aria-label="Dismiss skill link suggestion"
      >Dismiss</button>
    </div>
  </div>
{/if}

<style>
  .skill-link {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    border: 1px solid var(--accent-border);
    background: var(--accent-soft);
    border-radius: var(--r-sm);
    padding: 0.45rem 0.6rem;
    margin-bottom: 0.4rem;
    font-size: var(--text-sm);
  }
  .body { flex: 1 1 auto; min-width: 0; }
  .body p { margin: 0; }
  .sub { color: var(--text-3); margin-top: 0.15rem; }
  .error { color: var(--danger); margin-top: 0.15rem; }
  .actions { display: flex; gap: 0.3rem; flex-shrink: 0; flex-wrap: wrap; }
</style>
