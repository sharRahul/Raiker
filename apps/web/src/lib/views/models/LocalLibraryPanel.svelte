<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { ModelLibraryView } from "../../apiTypes";

  let library = $state<ModelLibraryView | null>(null);
  let root = $state("");
  let busy = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);

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
  async function deploy(modelId: string) {
    busy = true;
    try {
      await api.deployLocalModel(modelId);
      notice = "Deployment queued. Track it in Activity.";
    } catch {
      error = "Could not queue deployment.";
    } finally {
      busy = false;
    }
  }
  onMount(load);
</script>

<div class="library-layout">
  <section class="library-intro card">
    <div>
      <p class="eyebrow">Local model library</p>
      <h2>Use models already on this device</h2>
      <p>
        Raiker scans only folders you approve. It reads GGUF metadata without
        opening model code, follows no symlinks, and leaves original files where
        they are.
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
      <label
        ><span>Absolute folder path</span><input
          bind:value={root}
          placeholder="D:\Models"
          aria-label="Absolute model folder"
        /></label
      >
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
      <span>{library?.models.length ?? 0}</span>
    </div>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
    {#if library === null}<p class="empty-copy">Loading your model library…</p>
    {:else if library.models.length === 0}<div class="empty-models">
        <strong>No GGUF models indexed</strong><span
          >Add a folder above, or download one from Discover.</span
        >
      </div>
    {:else}<div class="model-grid">
        {#each library.models as model (model.model_id)}<article
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
            <button
              class="btn btn-sm"
              type="button"
              disabled={busy || !model.complete}
              onclick={() => void deploy(model.model_id)}
              >{model.complete ? "Deploy" : "Incomplete"}</button
            >
          </article>{/each}
      </div>{/if}
  </section>
</div>

<style>
  .library-layout {
    --text-muted: var(--text-2);
    display: grid;
    gap: 18px;
  }
  .library-intro {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 24px;
    border-left: 4px solid var(--accent, #2563eb);
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
      700 1.35rem/1 ui-monospace,
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
    font-size: 0.82rem;
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
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
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
    background: #171717;
    color: #fff;
    border-radius: 8px;
    font:
      750 0.78rem ui-monospace,
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
    color: var(--success, #15803d);
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
    .model-card button {
      grid-column: 2;
    }
  }
</style>
