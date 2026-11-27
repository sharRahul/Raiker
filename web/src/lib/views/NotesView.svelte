<script lang="ts">
  /**
   * Raiker Notes — a linked-Markdown notebook, Obsidian's way of working
   * inside Raiker.
   *
   * The folder is the owner's (an Obsidian vault opens as is): notes, folders,
   * `[[links]]`, `#tags`, properties, backlinks, unlinked mentions, a local
   * graph, daily notes and search operators all behave as Obsidian's do. What
   * Raiker adds: saving never overwrites a change made elsewhere, an unlinked
   * mention becomes a link in one click, renaming rewrites every link, Raiker's
   * memory is a folder of notes you can edit, and Chat can read your notes.
   */
  import { onMount, tick } from "svelte";

  import { api } from "../api";
  import Markdown from "../components/Markdown.svelte";
  import { failure } from "../errorCopy";
  import { noteHref, noteToMarkdown, openLinkQuery, radialLayout, suggestNotes } from "../notes";

  type Index = Awaited<ReturnType<typeof api.notes.list>>;
  type Note = Awaited<ReturnType<typeof api.notes.read>>;
  type Backlinks = Awaited<ReturnType<typeof api.notes.backlinks>>;
  type Graph = Awaited<ReturnType<typeof api.notes.graph>>;
  type Hit = Awaited<ReturnType<typeof api.notes.search>>[number];

  let index = $state<Index | null>(null);
  let note = $state<Note | null>(null);
  let draft = $state("");
  let saved = $state("");
  let mode = $state<"edit" | "read">("read");
  let backlinks = $state<Backlinks | null>(null);
  let graph = $state<Graph | null>(null);
  let query = $state("");
  let hits = $state<Hit[] | null>(null);
  let problem = $state<string | null>(null);
  let conflict = $state(false);
  let status = $state("");
  let creating = $state(false);
  let newName = $state("");
  let renaming = $state(false);
  let renameTo = $state("");
  let editor = $state<HTMLTextAreaElement | null>(null);
  let suggestions = $state<string[]>([]);
  let linkStart = $state(-1);
  let saveTimer: ReturnType<typeof setTimeout> | null = null;

  const names = $derived(index ? index.notes.map((item) => item.path.replace(/\.md$/i, "")) : []);
  const folders = $derived.by(() => {
    const grouped = new Map<string, Index["notes"]>();
    for (const item of index?.notes ?? []) {
      const folder = item.path.includes("/") ? item.path.slice(0, item.path.lastIndexOf("/")) : "";
      grouped.set(folder, [...(grouped.get(folder) ?? []), item]);
    }
    return [...grouped].sort(([a], [b]) => (a === "" ? -1 : b === "" ? 1 : a.localeCompare(b)));
  });
  const dirty = $derived(note !== null && draft !== saved);
  const layout = $derived(note && graph ? radialLayout(note.path, graph.nodes.map((node) => node.path)) : {});

  function params(): URLSearchParams {
    const hash = window.location.hash;
    return new URLSearchParams(hash.includes("?") ? hash.slice(hash.indexOf("?") + 1) : "");
  }

  async function loadIndex(): Promise<void> {
    try {
      index = await api.notes.list();
    } catch (error) {
      problem = failure("Notes could not be read", "Nothing was changed.", "Check the notes folder in Memory › Controls, then reload.", error);
    }
  }

  async function open(path: string): Promise<void> {
    if (dirty) await save();
    problem = null; conflict = false; renaming = false;
    try {
      const resolved = path.toLowerCase().endsWith(".md") ? path : (await api.notes.resolve(path, note?.path ?? "")).path;
      if (!resolved) {
        // Following a link to a note that does not exist creates it, as in Obsidian.
        await create(path);
        return;
      }
      note = await api.notes.read(resolved);
      draft = saved = note.content;
      [backlinks, graph] = await Promise.all([api.notes.backlinks(note.path), api.notes.graph(note.path, 1)]);
      const heading = params().get("heading");
      if (heading) await tick(), document.getElementById(`h-${heading}`)?.scrollIntoView();
    } catch (error) {
      problem = failure("The note could not be opened", "Nothing was changed.", "Pick it again from the list.", error);
    }
  }

  async function save(force = false): Promise<void> {
    if (!note || (!dirty && !force)) return;
    if (saveTimer) clearTimeout(saveTimer);
    try {
      const next = await api.notes.save(note.path, draft, note.mtime);
      note = next; saved = next.content; conflict = false; status = "Saved";
      backlinks = await api.notes.backlinks(next.path);
      void loadIndex();
    } catch (error) {
      if (String((error as { reason_code?: string })?.reason_code ?? error).includes("note_changed_elsewhere")) {
        conflict = true;
        status = "";
      } else {
        problem = failure("The note was not saved", "Your text is still here.", "Try saving again.", error);
      }
    }
  }

  async function keepMine(): Promise<void> {
    if (!note) return;
    const fresh = await api.notes.read(note.path);
    note = { ...note, mtime: fresh.mtime };
    await save(true);
  }

  async function reloadTheirs(): Promise<void> {
    if (!note) return;
    note = await api.notes.read(note.path);
    draft = saved = note.content; conflict = false;
  }

  function edited(): void {
    status = "";
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => void save(), 900);
    const open = editor ? openLinkQuery(draft, editor.selectionStart) : null;
    linkStart = open?.start ?? -1;
    suggestions = open ? suggestNotes(names, open.query) : [];
  }

  async function pick(name: string): Promise<void> {
    if (!editor || linkStart < 0) return;
    const caret = editor.selectionStart;
    const after = draft.slice(caret);
    const closing = after.startsWith("]]") ? "" : "]]";
    const short = name.includes("/") && names.filter((n) => n.split("/").pop() === name.split("/").pop()).length === 1 ? name.split("/").pop()! : name;
    draft = draft.slice(0, linkStart) + short + closing + after;
    suggestions = []; linkStart = -1;
    await tick();
    const position = draft.length - after.length;
    editor.focus();
    editor.setSelectionRange(position, position);
    edited();
  }

  function keydown(event: KeyboardEvent): void {
    if ((event.ctrlKey || event.metaKey) && event.key === "s") {
      event.preventDefault();
      void save();
    } else if (event.key === "Escape") {
      suggestions = [];
    } else if (event.key === "Enter" && suggestions.length > 0) {
      event.preventDefault();
      void pick(suggestions[0]);
    }
  }

  async function create(name: string): Promise<void> {
    const path = name.trim();
    if (!path) return;
    try {
      const made = await api.notes.create(path, `# ${path.split("/").pop()}\n\n`);
      creating = false; newName = "";
      await loadIndex();
      window.location.hash = noteHref(made.path);
      mode = "edit";
    } catch (error) {
      problem = failure("The note was not created", "Nothing was changed.", "Use a name without # | ^ : [ ], or open the note that already has it.", error);
    }
  }

  async function today(): Promise<void> {
    try {
      const daily = await api.notes.daily();
      await loadIndex();
      window.location.hash = noteHref(daily.path);
    } catch (error) {
      problem = failure("Today's note could not be opened", "Nothing was changed.", "Try again.", error);
    }
  }

  async function rename(): Promise<void> {
    if (!note || !renameTo.trim()) return;
    const folder = note.path.includes("/") ? note.path.slice(0, note.path.lastIndexOf("/") + 1) : "";
    const target = renameTo.includes("/") ? renameTo.trim() : folder + renameTo.trim();
    try {
      const moved = await api.notes.rename(note.path, target);
      renaming = false;
      status = moved.links_updated ? `Renamed; ${moved.links_updated} note${moved.links_updated === 1 ? "" : "s"} relinked` : "Renamed";
      await loadIndex();
      window.location.hash = noteHref(moved.path);
    } catch (error) {
      problem = failure("The note was not renamed", "Nothing was changed.", "Pick a name no other note in that folder has.", error);
    }
  }

  async function trash(): Promise<void> {
    if (!note) return;
    try {
      const where = await api.notes.trash(note.path);
      status = `Moved to ${where.trashed}`;
      note = null; backlinks = null; graph = null;
      await loadIndex();
    } catch (error) {
      problem = failure("The note was not moved to the trash", "Nothing was changed.", "Try again.", error);
    }
  }

  async function linkMention(source: string, line: number): Promise<void> {
    if (!note) return;
    try {
      await api.notes.linkMention(source, line, note.path);
      backlinks = await api.notes.backlinks(note.path);
      graph = await api.notes.graph(note.path, 1);
    } catch (error) {
      problem = failure("The mention was not linked", "Nothing was changed.", "Open that note and link it there.", error);
    }
  }

  async function search(): Promise<void> {
    const text = query.trim();
    hits = text ? await api.notes.search(text).catch(() => []) : null;
  }

  async function route(): Promise<void> {
    const p = params();
    const wanted = p.get("note");
    const searched = p.get("search");
    if (searched !== null) {
      query = searched;
      await search();
    }
    if (wanted && wanted !== note?.path) await open(wanted);
  }

  onMount(() => {
    void loadIndex().then(route);
    const onHash = () => void route();
    window.addEventListener("hashchange", onHash);
    return () => {
      window.removeEventListener("hashchange", onHash);
      if (saveTimer) clearTimeout(saveTimer);
    };
  });
</script>

<div class="notes">
  <aside class="files" aria-label="Notes">
    <form class="search" role="search" onsubmit={(event) => { event.preventDefault(); void search(); }}>
      <input type="search" aria-label="Search notes" placeholder="Search — tag:, path:, [status:draft]" bind:value={query} oninput={() => { if (!query.trim()) hits = null; }} />
    </form>
    <div class="file-actions">
      <button type="button" class="btn btn-soft btn-sm" onclick={() => (creating = !creating)}>New note</button>
      <button type="button" class="btn btn-ghost btn-sm" onclick={() => void today()}>Today</button>
    </div>
    {#if creating}
      <form class="new-note" onsubmit={(event) => { event.preventDefault(); void create(newName); }}>
        <!-- svelte-ignore a11y_autofocus -->
        <input type="text" aria-label="New note name" placeholder="Folder/Note name" bind:value={newName} autofocus />
      </form>
    {/if}
    {#if hits !== null}
      <p class="count">{hits.length} result{hits.length === 1 ? "" : "s"}</p>
      <ul>
        {#each hits as hit (hit.path)}
          <li><a href={noteHref(hit.path)} class:active={note?.path === hit.path}><b>{hit.name}</b><small>{hit.snippet}</small></a></li>
        {/each}
      </ul>
    {:else if index}
      {#each folders as [folder, items] (folder)}
        {#if folder}<p class="folder">{folder}</p>{/if}
        <ul>
          {#each items as item (item.path)}
            <li><a href={noteHref(item.path)} class:active={note?.path === item.path}>{item.name}</a></li>
          {/each}
        </ul>
      {/each}
      {#if index.notes.length === 0}<p class="empty">No notes yet. Make one, or open today's.</p>{/if}
      {#if index.tags.length}
        <p class="folder">Tags</p>
        <div class="tags">
          {#each index.tags.slice(0, 30) as tag (tag.tag)}
            <a href={`#/notes?search=${encodeURIComponent(`tag:${tag.tag}`)}`}>#{tag.tag} <small>{tag.count}</small></a>
          {/each}
        </div>
      {/if}
      <p class="root" title={index.root}>{index.root}</p>
    {/if}
  </aside>

  <main class="page">
    {#if problem}<p class="notice notice-danger" role="alert">{problem}</p>{/if}
    {#if note}
      <header class="note-head">
        {#if renaming}
          <form onsubmit={(event) => { event.preventDefault(); void rename(); }}>
            <!-- svelte-ignore a11y_autofocus -->
            <input type="text" aria-label="New name" bind:value={renameTo} autofocus />
            <button type="submit" class="btn btn-soft btn-sm">Rename</button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => (renaming = false)}>Cancel</button>
          </form>
        {:else}
          <h1><button type="button" class="title" title="Rename" onclick={() => { renaming = true; renameTo = note?.name ?? ""; }}>{note.name}</button></h1>
        {/if}
        <div class="head-actions">
          <span class="status" role="status">{dirty ? "Editing…" : status}</span>
          <div class="segmented" role="group" aria-label="View">
            <button type="button" class:on={mode === "read"} aria-pressed={mode === "read"} onclick={() => { void save(); mode = "read"; }}>Read</button>
            <button type="button" class:on={mode === "edit"} aria-pressed={mode === "edit"} onclick={() => (mode = "edit")}>Edit</button>
          </div>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => void trash()}>Move to trash</button>
        </div>
      </header>
      <p class="path">{note.path}</p>
      {#if conflict}
        <div class="notice" role="alert">
          This note changed somewhere else (Obsidian, another tool or a sync) since you opened it.
          <button type="button" class="btn btn-soft btn-sm" onclick={() => void reloadTheirs()}>Use the newer version</button>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => void keepMine()}>Keep mine</button>
        </div>
      {/if}
      {#if Object.keys(note.properties).length}
        <dl class="properties" aria-label="Properties">
          {#each Object.entries(note.properties) as [key, value] (key)}
            <dt>{key}</dt><dd>{Array.isArray(value) ? value.join(", ") : String(value ?? "")}</dd>
          {/each}
        </dl>
      {/if}
      {#if mode === "edit"}
        <div class="editor">
          <textarea
            bind:this={editor}
            bind:value={draft}
            aria-label="Note text"
            spellcheck="true"
            oninput={edited}
            onkeydown={keydown}
            onblur={() => void save()}
          ></textarea>
          {#if suggestions.length}
            <ul class="suggest" role="listbox" aria-label="Link to note">
              {#each suggestions as name (name)}
                <li role="option" aria-selected="false"><button type="button" onmousedown={(event) => { event.preventDefault(); void pick(name); }}>{name}</button></li>
              {/each}
            </ul>
          {/if}
        </div>
      {:else}
        <article class="reading"><Markdown text={noteToMarkdown(draft)} inAppLinks /></article>
      {/if}
    {:else if index}
      <div class="welcome">
        <h1>Notes</h1>
        <p>Write in Markdown and link ideas with <code>[[Note name]]</code>. Tag with <code>#tag</code>. Links work both ways, so every note shows what links to it.</p>
        <p>Raiker keeps its memory here too, in <a href={noteHref("Raiker Memory/Raiker Memory.md")}>Raiker Memory</a>. Edit a fact and Raiker remembers the change. Ask in Chat about anything you wrote, and Raiker can read your notes to answer.</p>
      </div>
    {/if}
  </main>

  {#if note}
    <aside class="context" aria-label="About this note">
      {#if note.headings.length}
        <section><h2>Outline</h2>
          <ul>{#each note.headings as heading (heading.line)}<li style={`padding-left:${(heading.level - 1) * 0.75}rem`}><a href={noteHref(note.path, heading.text)}>{heading.text}</a></li>{/each}</ul>
        </section>
      {/if}
      {#if backlinks}
        <section><h2>Linked mentions <small>{backlinks.linked.length}</small></h2>
          {#if backlinks.linked.length === 0}<p class="empty">No note links here yet.</p>{/if}
          <ul>{#each backlinks.linked as item (`${item.path}:${item.line}`)}<li><a href={noteHref(item.path)}><b>{item.name}</b><small>{item.context}</small></a></li>{/each}</ul>
        </section>
        {#if backlinks.unlinked.length}
          <section><h2>Unlinked mentions <small>{backlinks.unlinked.length}</small></h2>
            <ul>
              {#each backlinks.unlinked as item (`${item.path}:${item.line}`)}
                <li class="mention">
                  <a href={noteHref(item.path)}><b>{item.name}</b><small>{item.context}</small></a>
                  <button type="button" class="btn btn-soft btn-sm" onclick={() => void linkMention(item.path, item.line)}>Link</button>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      {/if}
      {#if graph && graph.nodes.length > 1}
        <section><h2>Local graph</h2>
          <svg viewBox="0 0 260 260" role="img" aria-label={`${note.name} and the ${graph.nodes.length - 1} notes it connects to`}>
            {#each graph.edges as edge (`${edge.source}>${edge.target}`)}
              {#if layout[edge.source] && layout[edge.target]}
                <line x1={layout[edge.source].x} y1={layout[edge.source].y} x2={layout[edge.target].x} y2={layout[edge.target].y} />
              {/if}
            {/each}
            {#each graph.nodes as node (node.path)}
              {#if layout[node.path]}
                <a href={noteHref(node.path)}>
                  <circle cx={layout[node.path].x} cy={layout[node.path].y} r={node.path === note.path ? 7 : 4 + Math.min(node.links_in, 4)} class:centre={node.path === note.path} />
                  <text x={layout[node.path].x} y={layout[node.path].y + 18} text-anchor="middle">{node.name}</text>
                </a>
              {/if}
            {/each}
          </svg>
        </section>
      {/if}
      {#if note.links.some((link) => !link.resolved)}
        <section><h2>Not yet written</h2>
          <ul>{#each [...new Set(note.links.filter((link) => !link.resolved).map((link) => link.target))] as target (target)}<li><a href={noteHref(target)}>{target}</a></li>{/each}</ul>
        </section>
      {/if}
    </aside>
  {/if}
</div>

<style>
  .notes { display:grid; grid-template-columns:minmax(12rem,16rem) minmax(0,1fr) minmax(14rem,18rem); gap:var(--space-4); min-height:70vh; }
  .files, .context { border-right:1px solid var(--border); padding-right:var(--space-3); overflow:auto; }
  .context { border-right:none; border-left:1px solid var(--border); padding:0 0 0 var(--space-3); }
  .files ul, .context ul { list-style:none; margin:0 0 var(--space-3); padding:0; }
  .files a, .context a { display:block; padding:var(--space-1) var(--space-2); border-radius:var(--r-sm); color:var(--text-1); text-decoration:none; overflow-wrap:anywhere; }
  .files a:hover, .files a.active, .context a:hover { background:var(--surface-2, var(--surface)); }
  .files a.active { font-weight:600; }
  small { display:block; color:var(--text-2); font-size:var(--text-xs); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .tags a small { display:inline; }
  .search input, .new-note input { width:100%; box-sizing:border-box; }
  .file-actions { display:flex; gap:var(--space-2); margin:var(--space-2) 0; }
  .folder { margin:var(--space-3) 0 var(--space-1); color:var(--text-2); font-size:var(--text-xs); text-transform:uppercase; letter-spacing:.04em; }
  .tags { display:flex; flex-wrap:wrap; gap:var(--space-1); }
  .tags a { display:inline-block; font-size:var(--text-sm); }
  .root { color:var(--text-2); font-size:var(--text-xs); overflow-wrap:anywhere; margin-top:var(--space-4); }
  .count, .empty, .path { color:var(--text-2); font-size:var(--text-sm); }
  .page { min-width:0; }
  .note-head { display:flex; align-items:center; justify-content:space-between; gap:var(--space-3); flex-wrap:wrap; }
  .note-head h1 { margin:0; font-size:var(--text-2xl, 1.6rem); }
  .title { all:unset; cursor:text; }
  .title:focus-visible { outline:2px solid var(--focus, currentColor); outline-offset:2px; }
  .head-actions { display:flex; align-items:center; gap:var(--space-2); }
  .status { color:var(--text-2); font-size:var(--text-sm); min-width:5rem; text-align:right; }
  .segmented { display:inline-flex; border:1px solid var(--border); border-radius:var(--r-md); overflow:hidden; }
  .segmented button { all:unset; padding:var(--space-1) var(--space-3); cursor:pointer; font-size:var(--text-sm); }
  .segmented button.on { background:var(--surface-2, var(--surface)); font-weight:600; }
  .properties { display:grid; grid-template-columns:max-content 1fr; gap:var(--space-1) var(--space-3); margin:var(--space-3) 0; padding:var(--space-2) var(--space-3); border:1px solid var(--border); border-radius:var(--r-md); font-size:var(--text-sm); }
  .properties dt { color:var(--text-2); }
  .properties dd { margin:0; overflow-wrap:anywhere; }
  .editor { position:relative; }
  textarea { width:100%; min-height:60vh; box-sizing:border-box; font-family:var(--font-mono, ui-monospace, monospace); font-size:var(--text-sm); line-height:1.6; resize:vertical; }
  .suggest { position:absolute; left:var(--space-3); top:var(--space-3); z-index:2; margin:0; padding:var(--space-1); list-style:none; background:var(--surface); border:1px solid var(--border); border-radius:var(--r-md); box-shadow:var(--shadow-md, 0 4px 16px rgb(0 0 0 / .15)); max-width:20rem; }
  .suggest button { all:unset; display:block; width:100%; box-sizing:border-box; padding:var(--space-1) var(--space-2); cursor:pointer; border-radius:var(--r-sm); }
  .suggest button:hover, .suggest li:first-child button { background:var(--surface-2, var(--surface)); }
  .reading { max-width:46rem; line-height:1.7; }
  .context h2 { font-size:var(--text-sm); margin:var(--space-3) 0 var(--space-1); }
  .context h2 small { display:inline; }
  .mention { display:flex; align-items:center; gap:var(--space-1); }
  .mention a { flex:1; min-width:0; }
  svg { width:100%; height:auto; }
  svg line { stroke:var(--border-strong, var(--border)); stroke-width:1; }
  svg circle { fill:var(--text-2); }
  svg circle.centre { fill:var(--accent, var(--text-1)); }
  svg text { fill:var(--text-2); font-size:9px; }
  .welcome { max-width:40rem; }
  @media (max-width: 64rem) {
    .notes { grid-template-columns:minmax(0,1fr); }
    .files, .context { border:none; padding:0; }
    .context { order:3; }
  }
</style>
