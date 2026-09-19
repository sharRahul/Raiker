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
  import GuideLink from "../components/GuideLink.svelte";
  import Icon from "../components/Icon.svelte";
  import Badge from "../components/Badge.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type { SkillView } from "../apiTypes";
  import { relativeTime } from "../format";
  import { conformanceSummary } from "../skillConformance";
  import { rowTokens, skillCandidates } from "../rowTokens";

  let skills = $state<SkillView[] | null>(null);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let filter = $state<"all" | "active" | "inactive">("all");

  let fileInput = $state<HTMLInputElement | null>(null);
  let importUrl = $state("");
  let renamingId = $state<string | null>(null);
  let renameValue = $state("");
  let commandEditingId = $state<string | null>(null);
  let commandValue = $state("");
  let expanded = $state<string | null>(null);

  // Build-a-skill: Raiker writes the document, the same reader validates it.
  let buildOpen = $state(false);

  /**
   * REM-SKILL-01 — where a skill comes from, chosen before a form appears.
   *
   * `null` is "the add entry is closed"; `"choose"` is "open, and the mode is
   * not decided yet". Keeping those distinct is the point of the row: the page
   * used to show all three forms at once, which is the same as deciding for the
   * owner that they wanted to compare them.
   */
  type AddMode = "choose" | "upload" | "link" | "build";
  const ADD_MODES: ReadonlyArray<{ id: AddMode; label: string; summary: string }> = [
    { id: "upload", label: "From a file", summary: "A SKILL.md or a .skill bundle you already have." },
    { id: "link", label: "From a link", summary: "A raw SKILL.md URL, fetched and verified first." },
    { id: "build", label: "Write one here", summary: "Held to the same contract as an uploaded one." },
  ];
  let addMode = $state<AddMode | null>(null);

  function chooseAddMode(mode: AddMode) {
    addMode = mode;
    // The builder is its own form below the list and already had a toggle, so
    // choosing it opens that rather than duplicating it inside this block.
    buildOpen = mode === "build";
  }

  function closeAdd() {
    addMode = null;
    buildOpen = false;
  }
  let buildName = $state("");
  let buildDescription = $state("");
  let buildBody = $state("");
  let buildCommand = $state("");

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
    skill_invalid_command:
      "Use 1–40 lowercase letters, numbers, or dashes, starting with a letter.",
    skill_command_in_use: "That slash command already loads another skill.",
    skill_provided_by_plugin:
      "This skill comes from a plugin, so it cannot be renamed or deleted here. Revoke the plugin on Extensions → Plugins to remove it.",
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
      // BUG-221 — a contributed skill has to be readable as a plugin's, not as
      // something the owner installed and forgot. The plugin id is the answer to
      // "who put this here", so it is on the row rather than only in Details.
      case "plugin":
        return skill.source_ref ? `Provided by plugin ${skill.source_ref}` : "Provided by a plugin";
      default:
        return "Uploaded";
    }
  }

  const isPluginSkill = (skill: SkillView) => skill.source === "plugin";

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
      const result = await api.buildSkill(
        buildName.trim(), buildDescription.trim(), buildBody, buildCommand.trim(),
      );
      notice = `Built “${result.skill?.name ?? buildName.trim()}”.`;
      buildName = "";
      buildDescription = "";
      buildBody = "";
      buildCommand = "";
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

  function startCommandEdit(skill: SkillView) {
    commandEditingId = skill.skill_id;
    commandValue = skill.command_trigger ?? skill.name;
  }

  async function commitCommand(skill: SkillView) {
    busy = skill.skill_id;
    error = null;
    notice = null;
    try {
      const result = await api.setSkillCommand(skill.skill_id, commandValue.trim() || null);
      notice = result.command_trigger
        ? `/${result.command_trigger} now loads “${skill.name}”. It grants no capability.`
        : `Removed the slash command from “${skill.name}”.`;
      commandEditingId = null;
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
      <!-- Named for the panel's `aria-labelledby`, and not repeated on screen:
           the tab strip above already says "Skills". What a skill *is* moved to
           the guide; what it grants stays here, because a reader who mistakes
           this tab for a permission surface has to be corrected on the page
           rather than in a document they may never open. -->
      <h2 id="skills-h" class="sr-only">Skills</h2>
      <p class="page-lead">Skills grant no capability and run no code.</p>
      <GuideLink section="extensions-and-mcp" label="How skills work" />
    </div>
    <button type="button" class="btn btn-ghost btn-sm" onclick={load}>
      <Icon name="refresh" size="sm" /> Refresh
    </button>
  </div>

  {#if error}<div class="notice notice-danger" role="alert">{error}</div>{/if}
  {#if notice}<div class="notice notice-ok" role="status"><Icon name="check" size="sm" /> {notice}</div>{/if}

  <!--
    REM-SKILL-01 — one way in, and the acquisition mode chosen before a form.

    Three full add forms sat side by side above the installed list: a file
    picker, a URL field with its own submit, and a builder toggle. All three
    were always open, so the page asked the owner to compare three ways of
    getting a skill before they had decided they wanted one — and the installed
    inventory, which is what the tab is for, started below all of it.

    Now: one **Add a skill**, then the three modes as a choice with one line
    each, then only the chosen mode's form. The modes and what each verifies
    are unchanged; what changed is that nothing is on screen until the owner
    has said which of them they mean.
  -->
  <div class="add">
    {#if addMode === null}
      <button
        type="button"
        class="btn btn-primary btn-sm"
        onclick={() => (addMode = "choose")}
        aria-expanded={false}
        disabled={busy !== null}
      >
        <Icon name="plus" size="sm" /> Add a skill
      </button>
    {:else}
      <div class="add-head">
        <h3>Add a skill</h3>
        <button type="button" class="btn btn-ghost btn-sm" onclick={closeAdd}>
          <Icon name="x" size="sm" /> Cancel
        </button>
      </div>
      <div class="modes" role="group" aria-label="Where the skill comes from">
        {#each ADD_MODES as mode (mode.id)}
          <button
            type="button"
            class="mode"
            class:on={addMode === mode.id}
            aria-pressed={addMode === mode.id}
            onclick={() => chooseAddMode(mode.id)}
            disabled={busy !== null}
          >
            <strong>{mode.label}</strong>
            <span>{mode.summary}</span>
          </button>
        {/each}
      </div>

      {#if addMode === "upload"}
        <div class="add-block">
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
      {:else if addMode === "link"}
        <form class="add-block" onsubmit={importFromUrl}>
          <p>
            A GitHub URL pointing at a raw <code>SKILL.md</code>. It is fetched and verified
            first.
          </p>
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
      {/if}
    {/if}
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
        <label class="field-label" for="build-command">Slash command <span class="muted">optional</span></label>
        <input
          id="build-command"
          class="input"
          bind:value={buildCommand}
          placeholder="release-notes"
          autocomplete="off"
        />
        <p class="field-help">Typing this in Chat or Build loads the skill. It never grants permissions.</p>
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
                <!-- The row carried three badges of equal weight: a
                     lifecycle state, a command trigger and a conformance
                     measurement. `rowTokens.ts` decides which of a row's facts
                     is worth a badge, so switched-on, a version, a trigger and
                     a conformant document read as metadata and the eye is left
                     free for the row that needs something. -->
                {@const tokens = rowTokens(skillCandidates(skill, isPluginSkill(skill)))}
                {#each tokens.badges as token (token.label)}
                  <Badge variant={token.variant} label={token.label} />
                {/each}
                {#each tokens.facts as fact (fact)}
                  <span class="row-fact" title={fact === "from plugin" ? "Contributed by an installed plugin" : null}>{fact}</span>
                {/each}
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
                {#if !isPluginSkill(skill)}
                  <button type="button" class="btn btn-sm" onclick={() => startCommandEdit(skill)} disabled={busy !== null} aria-expanded={commandEditingId === skill.skill_id}>
                    {skill.command_trigger ? "Edit command" : "Add command"}
                  </button>
                  <button
                    type="button"
                    class="btn btn-sm"
                    onclick={() => startRename(skill)}
                    disabled={busy === skill.skill_id}
                  >Rename</button>
                {/if}
                <button
                  type="button"
                  class="btn btn-sm"
                  onclick={() => download(skill)}
                  disabled={busy === skill.skill_id}
                >Download</button>
                {#if isPluginSkill(skill)}
                  <!-- Deleting the row would not remove the skill: the plugin's
                       file is still on disk and the next sync restores it.
                       Revoking the plugin is the control that removes it. -->
                  <a class="btn btn-sm" href="#/extensions?tab=plugins">Manage plugin</a>
                {:else}
                  <button
                    type="button"
                    class="btn btn-sm btn-danger"
                    onclick={() => remove(skill)}
                    disabled={busy === skill.skill_id}
                  >Delete</button>
                {/if}
              </div>
            {/if}
          </div>

          {#if commandEditingId === skill.skill_id}
            <form class="command-editor" onsubmit={(event) => { event.preventDefault(); commitCommand(skill); }}>
              <label class="field-label" for={`command-${skill.skill_id}`}>Slash command</label>
              <div class="command-row">
                <span aria-hidden="true">/</span>
                <input id={`command-${skill.skill_id}`} class="input" bind:value={commandValue} placeholder="release-notes" autocomplete="off" />
                <button class="btn btn-sm btn-primary" type="submit" disabled={busy === skill.skill_id}>Save</button>
                {#if skill.command_trigger}
                  <button class="btn btn-sm" type="button" onclick={() => { commandValue = ""; commitCommand(skill); }} disabled={busy === skill.skill_id}>Remove</button>
                {/if}
                <button class="btn btn-sm" type="button" onclick={() => (commandEditingId = null)}>Cancel</button>
              </div>
              <p class="muted command-note">Loads this skill. Permissions stay unchanged.</p>
            </form>
          {/if}

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
            {#if skill.conformance}
              <!-- ADD-21 — measured against the Agent Skills standard and
                   reported, never enforced: a skill that installs today keeps
                   installing. The one field Raiker reads and refuses is
                   `allowed-tools`, and saying so is stronger than ignoring a
                   field its author believes is doing something. -->
              <section class="conformance">
                <h4>
                  Agent Skills standard
                  <a
                    class="link"
                    href={skill.conformance.spec_url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >specification →</a>
                </h4>
                <p class="conformance-summary">{conformanceSummary(skill.conformance)}</p>
                {#if skill.conformance.license || skill.conformance.compatibility}
                  <p class="conformance-fields">
                    {#if skill.conformance.license}<span>License: {skill.conformance.license}</span>{/if}
                    {#if skill.conformance.compatibility}<span>Compatibility: {skill.conformance.compatibility}</span>{/if}
                  </p>
                {/if}
                {#if skill.conformance.findings.length > 0}
                  <ul class="findings">
                    {#each skill.conformance.findings as finding (finding.code + finding.field)}
                      <li class="finding" data-severity={finding.severity}>
                        <span class="finding-field mono">{finding.field}</span>
                        <span class="finding-severity">{finding.severity}</span>
                        <span class="finding-message">{finding.message}</span>
                      </li>
                    {/each}
                  </ul>
                {/if}
                {#if skill.conformance.refused_allowed_tools.length > 0}
                  <p class="conformance-refused">
                    Not pre-approved:
                    <span class="mono">{skill.conformance.refused_allowed_tools.join(", ")}</span>
                  </p>
                {/if}
              </section>
            {/if}
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
            ? "No skills installed yet. Select Add a skill above and choose where it comes from."
            : "No skill matches this filter."}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  /* ADD-21 — the standard-conformance block. Severity is carried by a text
     label as well as by colour, so the row reads the same to a screen reader
     and in a high-contrast theme. */
  .conformance {
    margin: var(--space-3) 0 0;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .conformance h4 {
    margin: 0 0 0.3rem;
    font-size: var(--text-sm);
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .conformance-summary {
    margin: 0 0 0.5rem;
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .conformance-fields {
    margin: 0 0 0.5rem;
    font-size: var(--text-sm);
    color: var(--text-3);
    display: flex;
    gap: 0.9rem;
    flex-wrap: wrap;
  }
  .findings {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .finding {
    display: grid;
    grid-template-columns: auto auto 1fr;
    gap: 0.5rem;
    align-items: baseline;
    font-size: var(--text-sm);
  }
  .finding-field {
    font-weight: 600;
  }
  .finding-severity {
    font-size: var(--text-2xs);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.02rem 0.3rem;
    color: var(--text-3);
    white-space: nowrap;
  }
  .finding[data-severity="error"] .finding-severity {
    color: var(--danger, var(--text-1));
    border-color: var(--danger, var(--border));
  }
  .finding-message {
    color: var(--text-2);
  }
  .conformance-refused {
    margin: 0.5rem 0 0;
    font-size: var(--text-sm);
    color: var(--text-3);
  }
  @media (max-width: 40rem) {
    .finding {
      grid-template-columns: 1fr;
    }
  }

  .header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .header h2 { margin: 0 0 0.2rem; }
  .page-lead { color: var(--text-2); margin: 0 0 0.25rem; max-width: 52rem; }
  .notice { margin-bottom: var(--space-3); }
  /* REM-SKILL-01 — one column, because there is one entry now. It was a
     three-column grid when three forms competed for it. */
  .add {
    display: grid;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    justify-items: start;
  }
  .add .modes,
  .add .add-block,
  .add .add-head { justify-self: stretch; }
  /* REM-SKILL-01 — the mode chooser: three choices at one weight, each with
     the one line that decides between them. */
  .add-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
  .add-head h3 { margin: 0; font-size: var(--text-base); }
  .modes { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: var(--space-2); margin: var(--space-3) 0; }
  .mode {
    display: grid;
    gap: 0.15rem;
    text-align: left;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    color: var(--text-1);
    cursor: pointer;
  }
  .mode.on { border-color: var(--accent-border); background: var(--accent-soft); }
  .mode span { color: var(--text-2); font-size: var(--text-xs); }

  .add-block {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    padding: var(--space-3) var(--space-4);
  }
  .add-block p { color: var(--text-3); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
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
  /* Every fact on a row that did not earn a badge. One weight, so a
     version, a trigger and a provenance note cannot compete with each other or
     with the state beside them. */
  .row-fact { color: var(--text-3); font-size: var(--text-xs); white-space: nowrap; }
  .actions { display: flex; gap: 0.3rem; flex-wrap: wrap; }
  .rename { max-width: 16rem; }
  .command-editor {
    margin-top: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .command-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .command-row .input { flex: 1 1 12rem; min-width: 0; }
  .command-note { margin: 0.35rem 0 0; font-size: var(--text-xs); }
  .description {
    margin: 0.35rem 0 0.4rem;
    color: var(--text-2);
    display: -webkit-box;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    -webkit-line-clamp: 2;
    overflow: hidden;
  }
  .facts {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    color: var(--text-3);
    font-size: var(--text-xs);
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
