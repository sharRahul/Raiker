<script lang="ts">
  /**
   * Extensions → Skills.
   *
   * A skill is instruction text the owner installs: a `SKILL.md` document or a
   * `*.skill` bundle. Installing one adds guidance to the turns it applies to —
   * it grants no capability, opens no gate, and Raiker runs nothing a skill
   * ships. That is why this tab is ordinary owner-scoped CRUD rather than a
   * governed runtime surface, and why the copy says so rather than implying an
   * authority the runtime does not enforce.
   *
   * Every mutation is server-validated: the document's frontmatter, the
   * archive's members, and the size caps are all decided by the API, so a
   * refusal here is a refusal there.
   */
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import Badge from "../components/Badge.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type { SkillView } from "../apiTypes";
  import { relativeTime } from "../format";

  let skills = $state<SkillView[] | null>(null);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let filter = $state<"all" | "active" | "inactive">("all");

  let fileInput = $state<HTMLInputElement | null>(null);
  let importUrl = $state("");
  let renamingId = $state<string | null>(null);
  let renameValue = $state("");
  let expanded = $state<string | null>(null);

  // Build-a-skill: Raiker writes the document, the same reader validates it.
  let buildOpen = $state(false);
  let buildName = $state("");
  let buildDescription = $state("");
  let buildBody = $state("");

  const visible = $derived(
    (skills ?? []).filter((skill) =>
      filter === "all" ? true : filter === "active" ? skill.active : !skill.active,
    ),
  );
  const activeCount = $derived((skills ?? []).filter((skill) => skill.active).length);

  const REASONS: Record<string, string> = {
    skill_invalid_name:
      "The name must be a lowercase slug — letters, digits, dots, dashes, underscores.",
    skill_missing_description:
      "The frontmatter needs a description. It is what decides when the skill applies.",
    skill_missing_skill_md: "The archive has no SKILL.md, so there is nothing to install.",
    skill_not_an_archive: "That file is not a readable .skill archive.",
    skill_empty: "The document is empty.",
    skill_too_large: "That is larger than the 2 MB skill limit.",
    skill_too_many_files: "The archive has too many files.",
    skill_unsafe_member_path:
      "The archive contains a path that would escape its own folder. Refused.",
    skill_unsupported_file_type: "Only SKILL.md documents and .skill bundles can be installed.",
    skill_unsupported_source:
      "Skills can be imported from GitHub over HTTPS. Other sources must be uploaded as a file.",
    skill_archive_url_unsupported:
      "A .skill archive cannot be imported from a link. Download it and upload the file.",
    skill_rename_failed: "That name is already used by another of your skills.",
    unknown_skill: "That skill is no longer installed.",
    invalid_base64: "The file could not be read.",
  };

  function reason(e: unknown): string {
    if (e instanceof ApiError) {
      const code = e.reasonCode ?? "";
      if (REASONS[code]) return REASONS[code];
      if (code.startsWith("skill_fetch_failed"))
        return "That link could not be read. Check it points at a raw SKILL.md.";
      return code || `Request failed (${e.status})`;
    }
    return "Request failed";
  }

  function sourceLabel(skill: SkillView): string {
    switch (skill.source) {
      case "builtin":
        return "Shipped with Raiker";
      case "url":
        return "Imported from a link";
      case "built":
        return "Built here";
      default:
        return "Uploaded";
    }
  }

  async function load() {
    error = null;
    try {
      skills = await api.skills();
    } catch (e) {
      skills = null;
      error = reason(e);
    }
  }

  function readAsBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("read_failed"));
      reader.onload = () => {
        const result = String(reader.result ?? "");
        // A data: URL is "data:<type>;base64,<payload>" — the API wants the payload.
        resolve(result.slice(result.indexOf(",") + 1));
      };
      reader.readAsDataURL(file);
    });
  }

  async function upload(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    busy = "upload";
    error = null;
    notice = null;
    try {
      const encoded = await readAsBase64(file);
      const result = await api.uploadSkill(file.name, encoded);
      notice = `Installed “${result.skill?.name ?? file.name}”.`;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
      input.value = "";
    }
  }

  async function importFromUrl(event: Event) {
    event.preventDefault();
    const url = importUrl.trim();
    if (!url) return;
    busy = "import";
    error = null;
    notice = null;
    try {
      const result = await api.importSkillUrl(url);
      notice = `Verified and installed “${result.skill?.name ?? url}”.`;
      importUrl = "";
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function build(event: Event) {
    event.preventDefault();
    busy = "build";
    error = null;
    notice = null;
    try {
      const result = await api.buildSkill(buildName.trim(), buildDescription.trim(), buildBody);
      notice = `Built “${result.skill?.name ?? buildName.trim()}”.`;
      buildName = "";
      buildDescription = "";
      buildBody = "";
      buildOpen = false;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  function startRename(skill: SkillView) {
    renamingId = skill.skill_id;
    renameValue = skill.name;
  }

  async function commitRename(skill: SkillView) {
    const next = renameValue.trim().toLowerCase();
    if (!next || next === skill.name) {
      renamingId = null;
      return;
    }
    busy = skill.skill_id;
    error = null;
    try {
      await api.renameSkill(skill.skill_id, next);
      renamingId = null;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function toggle(skill: SkillView) {
    busy = skill.skill_id;
    error = null;
    notice = null;
    try {
      await api.setSkillActive(skill.skill_id, !skill.active);
      notice = skill.active
        ? `“${skill.name}” is off. Its instructions are withheld from every turn.`
        : `“${skill.name}” is on.`;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function download(skill: SkillView) {
    busy = skill.skill_id;
    error = null;
    try {
      const blob = await api.downloadSkill(skill.skill_id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${skill.name}.skill`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function remove(skill: SkillView) {
    if (!confirm(`Delete “${skill.name}”? Its document is removed from this workspace.`)) return;
    busy = skill.skill_id;
    error = null;
    notice = null;
    try {
      await api.deleteSkill(skill.skill_id);
      notice = `Deleted “${skill.name}”.`;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  onMount(load);
</script>

<section aria-labelledby="skills-h">
  <div class="header">
    <div>
      <h2 id="skills-h">Skills</h2>
      <p class="page-lead">
        A skill is a <code>SKILL.md</code> document — instructions Raiker follows when the task
        matches. Installing one adds guidance and nothing else: it grants no capability, opens no
        gate, and Raiker never runs code a skill ships. An inactive skill stays here and is withheld
        from every turn.
      </p>
    </div>
    <button type="button" class="btn btn-ghost btn-sm" onclick={load}>
      <Icon name="refresh" size={15} /> Refresh
    </button>
  </div>

  {#if error}<div class="notice notice-danger" role="alert">{error}</div>{/if}
  {#if notice}<div class="notice notice-ok" role="status"><Icon name="check" size={15} /> {notice}</div>{/if}

  <div class="add">
    <div class="add-block">
      <h3>Upload</h3>
      <p>A <code>SKILL.md</code> file, or a <code>.skill</code> bundle up to 2 MB.</p>
      <input
        bind:this={fileInput}
        id="skill-file"
        class="sr-only"
        type="file"
        accept=".skill,.md,.markdown,.zip"
        onchange={upload}
        disabled={busy !== null}
      />
      <button
        type="button"
        class="btn btn-primary btn-sm"
        onclick={() => fileInput?.click()}
        disabled={busy !== null}
      >
        {busy === "upload" ? "Installing…" : "Choose a file"}
      </button>
    </div>

    <form class="add-block" onsubmit={importFromUrl}>
      <h3>Import from a link</h3>
      <p>A GitHub URL pointing at a raw <code>SKILL.md</code>. It is fetched and verified first.</p>
      <div class="row">
        <label class="sr-only" for="skill-url">Skill URL</label>
        <input
          id="skill-url"
          class="input"
          bind:value={importUrl}
          placeholder="https://github.com/owner/repo/blob/main/skills/name/SKILL.md"
          autocomplete="off"
          disabled={busy !== null}
        />
        <button type="submit" class="btn btn-sm" disabled={busy !== null || !importUrl.trim()}>
          {busy === "import" ? "Verifying…" : "Verify and add"}
        </button>
      </div>
    </form>

    <div class="add-block">
      <h3>Build one</h3>
      <p>Write a skill here. It is held to the same contract as an uploaded one.</p>
      <button
        type="button"
        class="btn btn-sm"
        onclick={() => (buildOpen = !buildOpen)}
        aria-expanded={buildOpen}
        disabled={busy !== null}
      >
        {buildOpen ? "Close builder" : "Build a skill"}
      </button>
    </div>
  </div>

  {#if buildOpen}
    <form class="builder" onsubmit={build}>
      <div class="field">
        <label class="field-label" for="build-name">Name</label>
        <input
          id="build-name"
          class="input"
          bind:value={buildName}
          placeholder="release-notes"
          autocomplete="off"
        />
      </div>
      <div class="field">
        <label class="field-label" for="build-description">
          Description — what it does, and when it applies
        </label>
        <input
          id="build-description"
          class="input"
          bind:value={buildDescription}
          placeholder="Draft release notes. Use when cutting a release or summarising a diff."
          autocomplete="off"
        />
      </div>
      <div class="field">
        <label class="field-label" for="build-body">Instructions</label>
        <textarea
          id="build-body"
          class="input body"
          bind:value={buildBody}
          rows="10"
          placeholder="# Release notes&#10;&#10;1. Read the diff since the last tag.&#10;2. Group changes by what a user would notice."
        ></textarea>
      </div>
      <button
        type="submit"
        class="btn btn-primary btn-sm"
        disabled={busy !== null || !buildName.trim() || !buildDescription.trim() || !buildBody.trim()}
      >
        {busy === "build" ? "Building…" : "Build and install"}
      </button>
    </form>
  {/if}

  {#if skills === null && error === null}
    <PageState state="loading" title="Reading installed skills…" />
  {:else if skills !== null}
    <div class="chip-row filters" role="group" aria-label="Filter skills">
      {#each [["all", `All (${skills.length})`], ["active", `Active (${activeCount})`], ["inactive", `Inactive (${skills.length - activeCount})`]] as [id, label] (id)}
        <button
          type="button"
          class="chip"
          onclick={() => (filter = id as typeof filter)}
          aria-pressed={filter === id}
        >{label}</button>
      {/each}
    </div>

    <ul class="list">
      {#each visible as skill (skill.skill_id)}
        <li class="card" class:inactive={!skill.active}>
          <div class="top">
            <div class="name-block">
              {#if renamingId === skill.skill_id}
                <input
                  class="input rename"
                  bind:value={renameValue}
                  onkeydown={(e) => e.key === "Enter" && commitRename(skill)}
                  aria-label="New skill name"
                />
                <button
                  type="button"
                  class="btn btn-sm btn-primary"
                  onclick={() => commitRename(skill)}
                  disabled={busy === skill.skill_id}
                >Save</button>
                <button type="button" class="btn btn-sm" onclick={() => (renamingId = null)}>Cancel</button>
              {:else}
                <span class="name">{skill.name}</span>
                {#if skill.active}
                  <Badge variant="active" label="active" />
                {:else}
                  <Badge variant="idle" label="inactive" />
                {/if}
                {#if skill.version}<span class="version">v{skill.version}</span>{/if}
              {/if}
            </div>
            {#if renamingId !== skill.skill_id}
              <div class="actions">
                <button
                  type="button"
                  class="btn btn-sm"
                  onclick={() => toggle(skill)}
                  disabled={busy === skill.skill_id}
                >{skill.active ? "Deactivate" : "Activate"}</button>
                <button
                  type="button"
                  class="btn btn-sm"
                  onclick={() => startRename(skill)}
                  disabled={busy === skill.skill_id}
                >Rename</button>
                <button
                  type="button"
                  class="btn btn-sm"
                  onclick={() => download(skill)}
                  disabled={busy === skill.skill_id}
                >Download</button>
                <button
                  type="button"
                  class="btn btn-sm btn-danger"
                  onclick={() => remove(skill)}
                  disabled={busy === skill.skill_id}
                >Delete</button>
              </div>
            {/if}
          </div>

          <p class="description">{skill.description}</p>

          <div class="facts">
            <span>{sourceLabel(skill)}</span>
            <span>{skill.file_count === 1 ? "1 file" : `${skill.file_count} files`}</span>
            <span>{Math.max(1, Math.round(skill.byte_size / 1024))} KB</span>
            <span title={skill.updated_at}>updated {relativeTime(skill.updated_at)}</span>
            <button
              type="button"
              class="link"
              onclick={() => (expanded = expanded === skill.skill_id ? null : skill.skill_id)}
              aria-expanded={expanded === skill.skill_id}
            >{expanded === skill.skill_id ? "Hide details" : "Details"}</button>
          </div>

          {#if expanded === skill.skill_id}
            <dl class="property-list">
              <dt>Checksum</dt><dd class="mono">{skill.checksum.slice(0, 16)}…</dd>
              {#if skill.source_ref}
                <dt>Source</dt><dd class="mono break">{skill.source_ref}</dd>
              {/if}
              <dt>Contents</dt>
              <dd>
                <ul class="files">
                  {#each skill.files as file (file)}<li class="mono">{file}</li>{/each}
                </ul>
              </dd>
            </dl>
          {/if}
        </li>
      {:else}
        <li class="empty">
          {skills.length === 0
            ? "No skills installed yet. Upload one, import a link, or build one above."
            : "No skill matches this filter."}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .header h2 { margin: 0 0 0.2rem; }
  .page-lead { max-width: 52rem; }
  .notice { margin-bottom: var(--space-3); }
  .add {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  .add-block {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    padding: var(--space-3) var(--space-4);
  }
  .add-block h3 { margin: 0 0 0.2rem; font-size: 0.9rem; }
  .add-block p { color: var(--text-3); font-size: 0.78rem; margin: 0 0 var(--space-3); }
  .row { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .row .input { flex: 1 1 12rem; min-width: 0; }
  .builder {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    padding: var(--space-4);
    margin-bottom: var(--space-4);
    display: grid;
    gap: var(--space-3);
  }
  .builder .body { font-family: var(--font-mono, monospace); }
  .field { display: grid; gap: 0.25rem; }
  .filters { margin-bottom: var(--space-3); }
  .list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.5rem; }
  .card {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    padding: var(--space-3) var(--space-4);
  }
  .card.inactive { opacity: 0.72; }
  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .name-block { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .name { font-weight: 650; }
  .version { color: var(--text-3); font-size: 0.75rem; }
  .actions { display: flex; gap: 0.3rem; flex-wrap: wrap; }
  .rename { max-width: 16rem; }
  .description { margin: 0.35rem 0 0.4rem; color: var(--text-2); }
  .facts {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    color: var(--text-3);
    font-size: 0.75rem;
    align-items: center;
  }
  .link {
    background: none;
    border: 0;
    color: var(--accent);
    cursor: pointer;
    font: inherit;
    padding: 0;
    text-decoration: underline;
  }
  .files { list-style: none; margin: 0; padding: 0; }
  .break { word-break: break-all; }
  .empty { color: var(--text-3); padding: var(--space-4); }
</style>
