<script lang="ts">
  import { onDestroy } from "svelte";
  import { api } from "../../api";
  import { openRuntimeInstaller } from "../../runtimeInstall";
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  let {
    onCatalogueChanged,
  }: {
    /** A completed pull changed a runtime catalogue outside the current snapshot. */
    onCatalogueChanged?: (profileIds: string[]) => void;
  } = $props();
  let model = $state("gemma4:31b-cloud");
  let busy = $state<string | null>(null);
  let message = $state<string | null>(null);
  let error = $state<string | null>(null);
  let watching = true;

  onDestroy(() => {
    watching = false;
  });

  const terminal = (state: string) =>
    ["complete", "failed", "cancelled"].includes(state);

  async function watchPull(operationId: string) {
    // Ask once immediately so a fast/local pull updates the picker without a
    // needless two-second wait, then only poll while the operation is active.
    while (watching) {
      try {
        const operation = (await api.modelOperations()).items.find(
          (item) => item.operation_id === operationId,
        );
        if (!operation) return;
        if (operation.state === "complete") {
          onCatalogueChanged?.(["ollama-local-openai-compatible"]);
          message = "Ollama model pulled. Refreshing available models…";
          return;
        }
        if (terminal(operation.state)) return;
      } catch {
        // Activity still carries the durable operation state and can retry the
        // refresh; a transient read failure must not claim that a model exists.
        return;
      }
      await new Promise<void>((resolve) => window.setTimeout(resolve, 2_000));
    }
  }
  async function openInstaller(runtime: string) {
    busy = runtime;
    error = null;
    try {
      // BUG-270 — the provider row offers this too, so the scheme check that
      // guards `window.open` lives in one place rather than in two that drift.
      await openRuntimeInstaller(runtime);
      message = `Opened the official ${runtime === "ollama" ? "Ollama" : "LM Studio"} download. Return here after installation.`;
    } catch {
      error = "Could not open the reviewed vendor download.";
    } finally {
      busy = null;
    }
  }
  async function pull() {
    if (!model.trim()) return;
    if (
      !window.confirm(
        `Pull ${model.trim()} from Ollama? The model may use substantial disk space.`,
      )
    )
      return;
    busy = "pull";
    error = null;
    try {
      const operation = await api.pullOllamaModel(model.trim());
      message = "Ollama pull started. Follow it in Activity.";
      void watchPull(operation.operation_id);
    } catch {
      error = "Could not start the Ollama pull. Check that Ollama is running.";
    } finally {
      busy = null;
    }
  }
</script>

<section class="runtime-setup" aria-labelledby="runtime-setup-title">
  <header>
    <div>
      <p class="eyebrow">Local runtime setup</p>
      <h2 id="runtime-setup-title">Install, connect, or pull</h2>
    </div>
    <p>
      Installers always come from the vendor. Raiker never bundles them or
      accepts their terms for you.
    </p>
  </header>
  <div class="runtime-grid">
    <article>
      <div class="runtime-head">
        <ProviderLogo provider="ollama" size={30} />
        <div>
          <h3>Ollama</h3>
          <p>Simple local model service for Windows, macOS, and Linux.</p>
        </div>
      </div>
      <!-- One emphasis level per card. `Open official installer` and
           `Pull model` both *do* something, and the rest of the product spends
           the ghost variant on inspect-type actions (Test, Details, View
           source) and the solid one on actions that change something. A card
           whose main action read quieter than its subordinate one was the only
           place that rule was inverted. -->
      <button
        class="btn btn-sm"
        type="button"
        onclick={() => void openInstaller("ollama")}
        disabled={busy !== null}
        >{busy === "ollama" ? "Opening…" : "Open official installer"}</button
      >
      <div class="pull-row">
        <label
          ><span>Model to pull</span><input
            bind:value={model}
            aria-label="Ollama model to pull"
          /></label
        ><button
          class="btn btn-sm"
          type="button"
          onclick={() => void pull()}
          disabled={busy !== null || !model.trim()}
          >{busy === "pull" ? "Starting…" : "Pull model"}</button
        >
      </div>
    </article>
    <article>
      <div class="runtime-head">
        <ProviderLogo provider="lm-studio" size={30} />
        <div>
          <h3>LM Studio</h3>
          <p>Desktop model browser with a local OpenAI-compatible server.</p>
        </div>
      </div>
      <button
        class="btn btn-sm"
        type="button"
        onclick={() => void openInstaller("lm-studio-desktop")}
        disabled={busy !== null}
        >{busy === "lm-studio-desktop"
          ? "Opening…"
          : "Open official download"}</button
      ><a href="#local-library"
        >Use models LM Studio already downloaded ↓</a
      >
    </article>
  </div>
  {#if message}<p class="message" role="status">{message}</p>{/if}{#if error}<p
      class="error"
      role="alert"
    >
      {error}
    </p>{/if}
</section>

<style>
  .runtime-setup {
    --text-muted: var(--text-2);
    display: grid;
    gap: 14px;
    margin-bottom: 18px;
  }
  .runtime-setup > header {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 20px;
  }
  .runtime-setup header h2 {
    margin: 2px 0;
  }
  .runtime-setup header > p {
    max-width: 52ch;
    margin: 0;
    color: var(--text-muted);
  }
  .runtime-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .runtime-grid article {
    display: grid;
    gap: 14px;
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 17px;
    background: var(--surface);
  }
  .runtime-head {
    display: flex;
    gap: 12px;
  }
  .runtime-head h3,
  .runtime-head p {
    margin: 0;
  }
  .runtime-head p {
    color: var(--text-muted);
    margin-top: 4px;
  }
  .runtime-head :global(.provider-logo) {
    border-radius: 9px;
  }
  .pull-row {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: end;
    gap: 8px;
    border-top: 1px solid var(--border);
    padding-top: 12px;
  }
  .pull-row label {
    display: grid;
    gap: 5px;
    font-size: 0.78rem;
    font-weight: 650;
  }
  .runtime-grid a {
    font-size: 0.8rem;
    color: var(--accent);
    text-decoration: none;
  }
  .message {
    color: var(--success);
    margin: 0;
  }
  @media (max-width: 760px) {
    .runtime-grid {
      grid-template-columns: 1fr;
    }
    .runtime-setup > header {
      align-items: start;
      flex-direction: column;
    }
  }
</style>
