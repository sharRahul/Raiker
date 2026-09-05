<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../../api";
  import type { LocalModel, ModelProfile } from "../../apiTypes";
  import ProviderLogo from "../../components/ProviderLogo.svelte";

  let {
    provider,
    title,
    format,
    profiles,
    description,
    onchanged,
    ontest,
    ondetails,
    onselect,
    testing = false,
    selecting = false,
    testResult = null,
  }: {
    provider: "llama.cpp" | "mlx";
    title: string;
    format: "gguf" | "mlx";
    profiles: ModelProfile[];
    description: string;
    onchanged?: () => void;
    ontest?: (profile: ModelProfile) => void;
    ondetails?: (profile: ModelProfile) => void;
    onselect?: (profile: ModelProfile) => void;
    testing?: boolean;
    selecting?: boolean;
    testResult?: string | null;
  } = $props();

  let models = $state<LocalModel[] | null>(null);
  let choices = $state<string[]>(["", "", "", ""]);
  let busy = $state(false);
  let scanning = $state(false);
  let notice = $state<string | null>(null);
  let error = $state<string | null>(null);

  const slotCount = $derived(Math.min(4, Math.max(1, profiles.length)));
  const slotIndexes = $derived([0, 1, 2, 3].slice(0, slotCount));
  const selectedCount = $derived(choices.slice(0, slotCount).filter(Boolean).length);

  function isFormat(model: LocalModel): boolean {
    if (model.format) return model.format === format;
    return format === "gguf" && model.primary_path.toLowerCase().endsWith(".gguf");
  }

  async function load() {
    try {
      const library = await api.modelLibrary();
      models = library.models.filter((model) => model.complete && isFormat(model));
      error = null;
    } catch {
      models = [];
      error = "The local model library could not be read.";
    }
  }

  async function scan() {
    scanning = true;
    notice = null;
    error = null;
    try {
      await api.rescanModelLibrary();
      await load();
    } catch {
      error = "Raiker could not scan the folders you approved.";
    } finally {
      scanning = false;
    }
  }

  function choose(index: number, value: string) {
    const next = [...choices];
    next[index] = value;
    choices = next;
  }

  function chosenElsewhere(modelId: string, index: number): boolean {
    return choices.some((choice, choiceIndex) => choiceIndex !== index && choice === modelId);
  }

  async function serve() {
    const selected = choices.slice(0, slotCount).filter(Boolean);
    if (selected.length === 0) return;
    busy = true;
    notice = null;
    error = null;
    try {
      for (let index = 0; index < selected.length; index += 1) {
        const profileId = profiles[index]?.profile_id;
        if (format === "mlx") await api.deployMlxModel(selected[index], profileId);
        else await api.deployLocalModel(selected[index], profileId);
      }
      notice = `${selected.length} ${title} model${selected.length === 1 ? "" : "s"} queued. Track startup in Activity.`;
      onchanged?.();
    } catch {
      error =
        format === "mlx"
          ? "The MLX models could not be started. MLX requires Apple silicon and mlx-lm."
          : "The GGUF models could not be started. llama-server must be installed and on PATH.";
    } finally {
      busy = false;
    }
  }

  onMount(load);
</script>

<article class="local-row framework-row" role="group" aria-label={title} data-provider={provider}>
  <span class="row-logo"><ProviderLogo {provider} size={28} /></span>
  <div class="framework-main">
    <div class="framework-heading">
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      <span class="slot-count">{selectedCount}/{slotCount} selected</span>
    </div>

    <div class="model-slots">
      {#each slotIndexes as index (index)}
        <label>
          <span>Model {index + 1}</span>
          <select
            aria-label={`${title} model ${index + 1}`}
            value={choices[index]}
            disabled={models === null || models.length === 0 || busy}
            onchange={(event) => choose(index, event.currentTarget.value)}
          >
            <option value="">
              {models === null
                ? "Scanning approved folders…"
                : models.length === 0
                  ? `No ${title} model detected`
                  : "None"}
            </option>
            {#each models ?? [] as model (model.model_id)}
              <option
                value={model.model_id}
                disabled={chosenElsewhere(model.model_id, index)}
              >{model.name}</option>
            {/each}
          </select>
        </label>
      {/each}
    </div>

    <div class="framework-actions">
      <button class="btn btn-ghost btn-sm" type="button" onclick={() => ontest?.(profiles[0])} disabled={testing}>
        {testing ? "Testing…" : "Test"}
      </button>
      <button class="btn btn-ghost btn-sm" type="button" onclick={() => ondetails?.(profiles[0])}>Details</button>
      {#if profiles[0] && !profiles[0].selected && profiles[0].model !== "<model>"}
        <button class="btn btn-sm" type="button" onclick={() => onselect?.(profiles[0])} disabled={selecting}>Select</button>
      {/if}
      <button class="btn btn-ghost btn-sm" type="button" onclick={scan} disabled={scanning || busy}>
        {scanning ? "Scanning…" : "Scan folders"}
      </button>
      <button class="btn btn-primary btn-sm" type="button" onclick={serve} disabled={busy || selectedCount === 0}>
        {busy ? "Starting…" : `Serve selected (${selectedCount})`}
      </button>
    </div>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
    {#if testResult}<p class="notice" role="status" data-test-result={profiles[0]?.profile_id}>{testResult}</p>{/if}
  </div>
</article>

<style>
  .local-row {
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
    padding: 0.9rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  .row-logo { display: inline-flex; flex: 0 0 auto; }
  .framework-main { flex: 1; min-width: 0; }
  .framework-heading { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
  h3 { margin: 0; font-size: 0.98rem; }
  .framework-heading p { color: var(--text-3); font-size: 0.78rem; margin: 0.2rem 0 0; }
  .slot-count { color: var(--text-3); font-size: 0.75rem; white-space: nowrap; }
  .model-slots { display: grid; grid-template-columns: repeat(4, minmax(8rem, 1fr)); gap: 0.55rem; margin-top: 0.75rem; }
  label { display: grid; gap: 0.25rem; min-width: 0; color: var(--text-3); font-size: 0.72rem; font-weight: 650; }
  select { width: 100%; min-width: 0; border: 1px solid var(--border); border-radius: var(--r-sm); background: var(--surface-raised); color: var(--text-1); padding: 0.45rem 0.5rem; }
  .framework-actions { display: flex; gap: 0.4rem; justify-content: flex-end; margin-top: 0.65rem; }
  .error, .notice { margin: 0.55rem 0 0; font-size: 0.78rem; }
  .notice { color: var(--text-2); }
  @media (max-width: 900px) { .model-slots { grid-template-columns: repeat(2, minmax(8rem, 1fr)); } }
  @media (max-width: 560px) { .model-slots { grid-template-columns: 1fr; } .framework-heading { display: block; } }
</style>
