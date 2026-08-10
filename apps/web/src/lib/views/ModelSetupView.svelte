<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { ModelProfile, ModelSetupState } from "../apiTypes";
  import { providerName } from "../format";
  import { modelName } from "../modelPresentation";
  import ProvidersPanel from "./models/ProvidersPanel.svelte";

  let setupState: ModelSetupState | null = $state(null);
  let profiles: ModelProfile[] = $state([]);
  let busy = $state(false);
  let error = $state("");

  const paths = [
    {
      id: "provider",
      label: "Provider",
      detail: "Connect Anthropic, OpenRouter, or another hosted provider.",
    },
    {
      id: "ollama",
      label: "Ollama",
      detail: "Install or connect Ollama and pull a model.",
    },
    {
      id: "lm_studio",
      label: "LM Studio",
      detail: "Install or connect LM Studio and its local server.",
    },
    {
      id: "local_gguf",
      label: "Local GGUF",
      detail: "Find an approved local model and run it with llama.cpp.",
    },
    {
      id: "hugging_face",
      label: "Hugging Face",
      detail: "Search and download a compatible model.",
    },
  ] as const;

  async function load() {
    try {
      const [savedState, models] = await Promise.all([
        api.modelSetup(),
        api.models(),
      ]);
      setupState = savedState;
      profiles = models.profiles;
    } catch {
      error = "Model setup could not be loaded.";
    }
  }

  async function save(update: Partial<ModelSetupState>) {
    if (!setupState) return;
    busy = true;
    error = "";
    try {
      const body = {
        status: update.status ?? setupState.status,
        step: update.step ?? setupState.step,
        path: update.path === undefined ? setupState.path : update.path,
        selected_profile_id:
          update.selected_profile_id === undefined
            ? setupState.selected_profile_id
            : update.selected_profile_id,
        selected_model:
          update.selected_model === undefined
            ? setupState.selected_model
            : update.selected_model,
      } satisfies Omit<
        ModelSetupState,
        "owner_principal_id" | "created_at" | "updated_at"
      >;
      setupState = await api.updateModelSetup(body);
    } catch {
      error = "That setup choice could not be saved.";
    } finally {
      busy = false;
    }
  }

  async function choosePath(path: ModelSetupState["path"]) {
    await save({
      status: "in_progress",
      step: path === "provider" ? "provider" : "model",
      path,
    });
  }

  async function chooseProfile(profile: ModelProfile) {
    await save({
      status: "in_progress",
      step: "review",
      selected_profile_id: profile.profile_id,
      selected_model: profile.model,
    });
  }

  async function skip() {
    await save({ status: "skipped" });
    window.location.hash = "#/home";
  }

  async function finish() {
    await save({ status: "complete", step: "ready" });
    window.location.hash = "#/models";
  }

  onMount(load);
</script>

<section class="setup-shell" aria-labelledby="setup-title">
  <div class="progress" aria-label="Model setup progress">
    <span class:active={setupState?.step === "choose_path"}>1</span><i></i><span
      class:active={setupState?.step === "provider" ||
        setupState?.step === "model"}>2</span
    ><i></i><span
      class:active={setupState?.step === "review" ||
        setupState?.step === "ready"}>3</span
    >
  </div>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if setupState === null}
    <h2 id="setup-title">Preparing model setup…</h2>
  {:else if setupState.step === "choose_path"}
    <header>
      <p class="eyebrow">First-run setup</p>
      <h2 id="setup-title">Choose how to run models</h2>
      <p>
        Pick a path now, or skip and return from Models later. Model-backed
        actions stay disabled until an exact model passes its check.
      </p>
    </header>
    <div class="path-grid">
      {#each paths as path}
        <button
          type="button"
          aria-label={path.label}
          disabled={busy}
          onclick={() => choosePath(path.id)}
          ><strong>{path.label}</strong><span>{path.detail}</span></button
        >
      {/each}
    </div>
    <button class="quiet" type="button" disabled={busy} onclick={skip}
      >Skip for now</button
    >
  {:else if setupState.step === "provider"}
    <header>
      <p class="eyebrow">Hosted model</p>
      <h2 id="setup-title">Choose a provider</h2>
      <p>
        Select the exact configured provider/model pair to review. Credentials
        remain in Raiker's protected connection store.
      </p>
    </header>
    <div class="choice-list">
      {#each profiles as profile (`${profile.profile_id}-${profile.model}`)}
        <button
          type="button"
          disabled={busy}
          onclick={() => chooseProfile(profile)}
          ><strong
            >{providerName(profile.provider)} · {modelName(
              profile.model,
            )}</strong
          ><span>{profile.configured ? "Configured" : "Setup required"}</span
          ></button
        >
      {/each}
    </div>
    <button
      class="quiet"
      type="button"
      onclick={() => save({ step: "choose_path" })}>Back</button
    >
  {:else if setupState.step === "model"}
    <header>
      <p class="eyebrow">Local model</p>
      <h2 id="setup-title">
        Set up {paths.find((path) => path.id === setupState?.path)?.label ??
          "a model"}
      </h2>
      <p>
        The installer, library, and download controls for this path appear here.
        You can also continue in Models without losing this step.
      </p>
    </header>
    {#if setupState.path === "ollama" || setupState.path === "lm_studio"}<ProvidersPanel
      />
    {:else if setupState.path === "hugging_face"}<div class="placeholder">
        <strong>Hub catalogue and immutable downloads</strong><span
          >Review format, revision, size, cache reuse, and license before
          downloading.</span
        >
      </div>
    {:else}<div class="placeholder">
        <strong>Owner-approved local folders</strong><span
          >Raiker scans only folders you choose and leaves source GGUF files
          unchanged.</span
        >
      </div>{/if}
    <div class="actions">
      <button
        class="quiet"
        type="button"
        onclick={() => save({ step: "choose_path" })}>Back</button
      ><a
        class="primary"
        href={setupState.path === "hugging_face"
          ? "#/models?tab=huggingface"
          : setupState.path === "local_gguf"
            ? "#/models?tab=local"
            : "#/models?tab=hosted"}>Continue in Models</a
      >
    </div>
  {:else if setupState.step === "review"}
    <header>
      <p class="eyebrow">Review</p>
      <h2 id="setup-title">Check this model</h2>
      <p>{setupState.selected_profile_id} · {setupState.selected_model}</p>
    </header>
    <div class="actions">
      <button
        class="quiet"
        type="button"
        onclick={() => save({ step: "provider" })}>Back</button
      ><button class="primary" type="button" onclick={finish}
        >Finish in Models</button
      >
    </div>
  {:else}
    <header>
      <p class="eyebrow">Ready</p>
      <h2 id="setup-title">Model setup complete</h2>
      <p>
        Raiker will still re-check the exact selected model before model-backed
        work.
      </p>
    </header>
    <a class="primary" href="#/home">Open Workbench</a>
  {/if}
</section>

<style>
  .setup-shell {
    width: min(58rem, 100%);
    margin: 0 auto;
    display: grid;
    gap: var(--space-5);
    padding: clamp(1rem, 4vw, 3rem);
  }
  header {
    max-width: 46rem;
  }
  .eyebrow {
    margin: 0 0 0.35rem;
    color: var(--accent);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  h2 {
    margin: 0;
    color: var(--text-1);
    font-size: clamp(1.5rem, 3vw, 2.2rem);
  }
  header > p:last-child {
    color: var(--text-2);
    line-height: 1.55;
  }
  .progress {
    display: grid;
    grid-template-columns: auto 1fr auto 1fr auto;
    align-items: center;
    width: min(20rem, 100%);
    color: var(--text-3);
  }
  .progress span {
    display: grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    border: 1px solid var(--neutral-border);
    border-radius: 50%;
    font-size: 0.72rem;
    font-weight: 800;
  }
  .progress span.active {
    border-color: var(--accent-border);
    background: var(--accent-soft);
    color: var(--accent);
  }
  .progress i {
    height: 1px;
    background: var(--border);
  }
  .path-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.65rem;
  }
  .path-grid button,
  .choice-list button,
  .placeholder {
    display: grid;
    gap: 0.3rem;
    padding: 1rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-lg);
    background: var(--surface);
    color: var(--text-2);
    text-align: left;
  }
  .path-grid button,
  .choice-list button {
    cursor: pointer;
  }
  .path-grid button:hover,
  .choice-list button:hover {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  strong {
    color: var(--text-1);
  }
  span {
    font-size: 0.8rem;
    line-height: 1.4;
  }
  .choice-list {
    display: grid;
    gap: 0.5rem;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .quiet,
  .primary {
    width: max-content;
    border-radius: var(--r-pill);
    padding: 0.5rem 0.8rem;
    font: inherit;
    font-size: 0.78rem;
    font-weight: 750;
    cursor: pointer;
    text-decoration: none;
  }
  .quiet {
    border: 1px solid var(--neutral-border);
    background: var(--surface);
    color: var(--text-2);
  }
  .primary {
    border: 1px solid var(--accent-border);
    background: var(--accent);
    color: white;
  }
  .error {
    color: var(--danger);
  }
  @media (max-width: 639px) {
    .path-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
