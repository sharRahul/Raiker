<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { ModelLibraryView } from "../../apiTypes";
  import Icon from "../../components/Icon.svelte";
  import PathPicker from "../../components/PathPicker.svelte";

  let library = $state<ModelLibraryView | null>(null);
  let root = $state("");
  let busy = $state(false);
  // BUG-251 — an approved folder can be browsed to rather than spelled.
  let browsing = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  const ggufModels = $derived(
    (library?.models ?? []).filter(
      (model) => model.format === "gguf" || (!model.format && model.primary_path.toLowerCase().endsWith(".gguf")),
    ),
  );

  const bytes = (value: number) => {
    if (value < 1024 ** 2) return `${Math.max(1, Math.round(value / 1024))} KB`;
    if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
    return `${(value / 1024 ** 3).toFixed(1)} GB`;
  };

  async function load() {
    try {
      library = await api.modelLibrary();
      error = null;
    } catch (e) {
      error =
        e instanceof ApiError
          ? `Library unavailable (${e.status})`
          : "Library unavailable";
    }
  }

  async function addRoot() {
    if (!root.trim()) return;
    busy = true;
    notice = null;
    try {
      await api.addModelLibraryRoot(root.trim());
      root = "";
      await scan();
    } catch (e) {
      error =
        e instanceof ApiError
          ? (e.reasonCode ?? `Could not add folder (${e.status})`)
          : "Could not add folder";
    } finally {
      busy = false;
    }
  }

  async function scan() {
    busy = true;
    notice = null;
    try {
      const result = await api.rescanModelLibrary();
      await load();
      notice = `Found ${result.models.length} local model${result.models.length === 1 ? "" : "s"}.`;
    } catch {
      error = "Could not scan the approved folders.";
    } finally {
      busy = false;
    }
  }

  async function removeRoot(path: string) {
    await api.removeModelLibraryRoot(path);
    await load();
  }
  onMount(load);
</script>

<div class="library-layout">
  <section class="library-intro card" id="local-library">
    <div>
      <p class="eyebrow">Local model library</p>
      <h2>Use models already on this device</h2>
      <p>
        Raiker scans only folders you approve. It reads GGUF metadata without
        opening model code, follows no symlinks, and leaves original files where
        they are.
      </p>
      <p class="slot-note">
        Up to four models serve at once, each on its own local port, so Chat,
        Build and Design can each use a different one. Which of them serves is
        chosen in the slot rows above — this list is what is on disk.
      </p>
    </div>
    <button class="btn btn-primary" type="button" onclick={scan} disabled={busy}
      >{busy ? "Scanning…" : "Scan now"}</button
    >
  </section>

  <section class="card root-card" aria-labelledby="model-folders-title">
    <div class="section-title">
      <div>
        <p class="eyebrow">Scope</p>
        <h3 id="model-folders-title">Approved folders</h3>
      </div>
      <span>{library?.roots.length ?? 0}</span>
    </div>
    <form
      class="root-form"
      onsubmit={(event) => {
        event.preventDefault();
        void addRoot();
      }}
    >
      <!-- The placeholder is not an example path. `D:\Models` cannot exist on
           macOS or Linux, so on two of the three platforms Raiker ships for it
           was teaching the wrong shape. Browse… beside this field lists the
           host's own folders (BUG-251), which is the right way to offer a
           concrete answer without guessing which machine this is. -->
      <label
        ><span>Absolute folder path</span><input
          bind:value={root}
          placeholder="Full path to a folder of models"
          aria-label="Absolute model folder"
        /></label
      >
      <button type="button" class="btn" onclick={() => (browsing = true)}>
        <Icon name="folder" size="sm" /> Browse
      </button>
      <button class="btn" type="submit" disabled={busy || !root.trim()}
        >Add and scan</button
      >
    </form>
    {#if library?.roots.length}
      <ul class="root-list">
        {#each library.roots as item (item.path)}<li>
            <code>{item.path}</code><button
              class="btn btn-ghost btn-sm"
              type="button"
              onclick={() => void removeRoot(item.path)}>Remove</button
            >
          </li>{/each}
      </ul>
    {:else}<p class="empty-copy">
        No folders approved yet. Raiker will not search the rest of your
        computer.
      </p>{/if}
  </section>

  <section class="models-section" aria-labelledby="local-models-title">
    <div class="section-title">
      <div>
        <p class="eyebrow">Inventory</p>
        <h3 id="local-models-title">Detected GGUF models</h3>
      </div>
      <span>{ggufModels.length}</span>
    </div>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
    {#if library === null}<p class="empty-copy">Loading your model library…</p>
    {:else if ggufModels.length === 0}<div class="empty-models">
        <strong>No GGUF models indexed</strong><span
          >Add a folder above, or download one from Discover.</span
        >
      </div>
    {:else}<div class="model-grid">
        {#each ggufModels as model (model.model_id)}<article
            class="model-card"
            class:incomplete={!model.complete}
          >
            <div class="model-mark">GG</div>
            <div>
              <h4>{model.name}</h4>
              <p>
                {model.architecture} · {model.quantization ??
                  "quantization unknown"}
              </p>
              <small
                >{bytes(model.size_bytes)} · {model.shard_count}/{model.expected_shards}
                file{model.expected_shards === 1 ? "" : "s"}</small
              >
            </div>
            <!-- MODEL-06 — the library answers "what is on disk"; the slot
                 rows above answer "what is serving". Deploy was the one control
                 that crossed the two, so a card here could put a model into a
                 runtime slot without ever showing which slot it took or what it
                 displaced. Serving is chosen where the slots are. -->
            <span class="model-state">{model.complete ? "Ready to serve" : "Incomplete"}</span>
          </article>{/each}
      </div>{/if}
  </section>
</div>

{#if browsing}
  <PathPicker
    title="Choose a model folder"
    start={root}
    onchoose={(path) => { root = path; browsing = false; }}
    onclose={() => (browsing = false)}
  />
{/if}

<style>
  .library-layout {
    --text-muted: var(--text-2);
    display: grid;
    /* BUG-284 — an implicit grid column is `auto`, which sizes to the widest
       item's max-content and refuses to shrink below its min-content. One long
       row inside therefore made this 450px wide in a 366px phone and the whole
       panel drew over the page. `minmax(0, 1fr)` is the same single column that
       is allowed to be narrower than its contents want. */
    grid-template-columns: minmax(0, 1fr);
    gap: 18px;
  }
  /* VIS2-16 — "on disk and complete" is the resting state of every row here,
     so it is plain metadata; the incomplete card already carries its own
     treatment. */
  .model-state {
    align-self: center;
    color: var(--text-3);
    font-size: var(--text-2xs);
    font-weight: 650;
    white-space: nowrap;
  }
  .slot-note {
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  .library-intro {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 24px;
    border-left: 4px solid var(--accent);
  }
  .library-intro h2,
  .section-title h3 {
    margin: 2px 0 6px;
  }
  .library-intro p {
    max-width: 72ch;
    margin: 0;
    color: var(--text-muted);
  }
  .root-card {
    padding: 20px;
  }
  .section-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .section-title > span {
    font:
      700 var(--text-xl)/1 ui-monospace,
      monospace;
    color: var(--text-muted);
  }
  .root-form {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 10px;
    align-items: end;
  }
  .root-form label {
    display: grid;
    gap: 6px;
    font-size: var(--text-sm);
    font-weight: 650;
  }
  .root-form input {
    width: 100%;
  }
  .root-list {
    list-style: none;
    padding: 0;
    margin: 14px 0 0;
  }
  .root-list li {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
    border-top: 1px solid var(--border);
    padding: 10px 0;
  }
  .root-list code {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .models-section {
    padding: 4px;
  }
  .model-grid {
    display: grid;
    /* BUG-284 — `minmax(300px, 1fr)` has a hard floor: on a 390px phone the
       track stays 300px inside a ~290px column and the grid bleeds out of the
       panel. `min(300px, 100%)` keeps the 300px preference where there is room
       and lets the track shrink where there is not. */
    grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
    gap: 12px;
  }
  .model-card {
    display: grid;
    grid-template-columns: 42px 1fr auto;
    gap: 12px;
    align-items: center;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    background: var(--surface);
  }
  .model-card h4 {
    margin: 0 0 4px;
  }
  .model-card p,
  .model-card small {
    margin: 0;
    color: var(--text-muted);
  }
  .model-mark {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    background: var(--brand-black);
    color: var(--brand-white);
    border-radius: 8px;
    font:
      750 var(--text-sm) ui-monospace,
      monospace;
  }
  .incomplete {
    opacity: 0.68;
  }
  .empty-models {
    display: grid;
    place-items: center;
    gap: 5px;
    padding: 48px;
    border: 1px dashed var(--border);
    border-radius: 12px;
    color: var(--text-muted);
  }
  .empty-copy {
    color: var(--text-muted);
  }
  .notice {
    color: var(--success);
  }
  @media (max-width: 700px) {
    .library-intro {
      align-items: flex-start;
      flex-direction: column;
    }
    .root-form {
      grid-template-columns: 1fr;
    }
    .model-card {
      grid-template-columns: 42px 1fr;
    }
    .model-state {
      grid-column: 2;
      justify-self: start;
    }
  }
</style>
