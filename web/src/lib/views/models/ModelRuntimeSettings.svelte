<script lang="ts">
  /**
   * One GGUF model's launch settings, with what they would cost before saving.
   *
   * Every field starts on Automatic: Raiker fits GPU layers and context to the
   * memory free right now. Changing a field asks the server for a fresh plan
   * (nothing is saved or started), so the owner sees "18 of 32 layers on the
   * GPU, 6.1 GB" — or "does not fit" — while choosing, not after a failed start.
   */
  import { onDestroy, onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { LocalModel } from "../../apiTypes";
  import type { LocalRuntimeSettingsRequest, ModelRuntimeSettingsView } from "../../generated/apiContract";
  import {
    contextChoices,
    formatBytes,
    formatTokens,
    offloadLabel,
    reasonLabel,
    usage,
    verdictLabel,
  } from "../../llamaRuntime";

  let models = $state<LocalModel[] | null>(null);
  let modelId = $state("");
  let view = $state<ModelRuntimeSettingsView | null>(null);
  let draft = $state<LocalRuntimeSettingsRequest>({});
  let saving = $state(false);
  let notice = $state<string | null>(null);
  let error = $state<string | null>(null);
  let debounce: ReturnType<typeof setTimeout> | null = null;

  const plan = $derived(view?.plan ?? null);
  const maxLayers = $derived(plan ? plan.total_layers + 1 : 100);
  const contexts = $derived(contextChoices(plan?.trained_context));
  const gpuUse = $derived(plan ? usage(plan.gpu_bytes, plan.gpu_budget_bytes) : null);
  const systemUse = $derived(plan ? usage(plan.system_bytes, plan.system_budget_bytes) : null);

  async function loadModels() {
    try {
      const library = await api.modelLibrary();
      models = library.models.filter((model) => model.complete && model.format === "gguf");
      if (!modelId && models.length > 0) await pick(models[0].model_id);
    } catch {
      models = [];
      error = "The local model library could not be read.";
    }
  }

  async function pick(id: string) {
    modelId = id;
    notice = null;
    error = null;
    view = null;
    if (!id) return;
    try {
      view = await api.modelRuntimeSettings(id);
      draft = { ...view.settings };
    } catch (err) {
      error = err instanceof ApiError && err.reasonCode ? reasonLabel(err.reasonCode) : "Settings could not be read.";
    }
  }

  function change(patch: Partial<LocalRuntimeSettingsRequest>) {
    draft = { ...draft, ...patch };
    notice = null;
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => void preview(), 250);
  }

  async function preview() {
    if (!modelId) return;
    try {
      view = await api.previewModelRuntimePlan(modelId, draft);
      error = null;
    } catch (err) {
      error = err instanceof ApiError && err.reasonCode ? reasonLabel(err.reasonCode) : "These settings could not be checked.";
    }
  }

  async function save() {
    if (!modelId) return;
    saving = true;
    try {
      view = await api.saveModelRuntimeSettings(modelId, draft);
      notice = "Saved. A model that is already serving uses these settings when it next starts — press Restart on it to apply them now.";
      error = null;
    } catch (err) {
      error = err instanceof ApiError && err.reasonCode ? reasonLabel(err.reasonCode) : "Settings could not be saved.";
    } finally {
      saving = false;
    }
  }

  function numberOrNull(value: string): number | null {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }

  onMount(() => void loadModels());
  onDestroy(() => {
    if (debounce) clearTimeout(debounce);
  });
</script>

<section class="settings" aria-labelledby="model-runtime-title">
  <header>
    <h3 id="model-runtime-title">GPU, context and memory</h3>
    <p class="sub">How each GGUF model starts. Automatic fits it to this computer's free memory.</p>
  </header>

  {#if models === null}
    <p class="sub">Reading your models…</p>
  {:else if models.length === 0}
    <p class="sub">Add a folder with GGUF models to your library to adjust how they run.</p>
  {:else}
    <label class="field wide">
      <span>Model</span>
      <select aria-label="Model to configure" value={modelId} onchange={(event) => void pick(event.currentTarget.value)}>
        {#each models as model (model.model_id)}
          <option value={model.model_id}>{model.name}</option>
        {/each}
      </select>
    </label>

    {#if view}
      <div class="grid">
        <label class="field">
          <span>GPU layers</span>
          <select
            aria-label="GPU layers mode"
            value={draft.gpu_layers === null || draft.gpu_layers === undefined ? "auto" : "manual"}
            onchange={(event) => change({ gpu_layers: event.currentTarget.value === "auto" ? null : (plan?.gpu_layers ?? 0) })}
          >
            <option value="auto">Automatic</option>
            <option value="manual">Choose</option>
          </select>
          {#if draft.gpu_layers !== null && draft.gpu_layers !== undefined}
            <input
              type="range"
              min="0"
              max={maxLayers}
              value={draft.gpu_layers}
              aria-label="Number of GPU layers"
              oninput={(event) => change({ gpu_layers: numberOrNull(event.currentTarget.value) })}
            />
            <small>{draft.gpu_layers} of {maxLayers}</small>
          {/if}
        </label>

        <label class="field">
          <span>Context</span>
          <select
            aria-label="Context size"
            value={draft.context_size ? String(draft.context_size) : "auto"}
            onchange={(event) => change({ context_size: event.currentTarget.value === "auto" ? null : numberOrNull(event.currentTarget.value) })}
          >
            <option value="auto">Automatic</option>
            {#each contexts as size (size)}
              <option value={String(size)}>{formatTokens(size)} tokens</option>
            {/each}
          </select>
        </label>

        <label class="field">
          <span>Processor threads</span>
          <input
            type="number"
            min="1"
            max="512"
            placeholder="Automatic"
            aria-label="Processor threads"
            value={draft.threads ?? ""}
            oninput={(event) => change({ threads: numberOrNull(event.currentTarget.value) })}
          />
        </label>

        <label class="field">
          <span>Flash attention</span>
          <select aria-label="Flash attention" value={draft.flash_attention ?? "auto"} onchange={(event) => change({ flash_attention: event.currentTarget.value as "auto" | "on" | "off" })}>
            <option value="auto">Automatic</option>
            <option value="on">On</option>
            <option value="off">Off</option>
          </select>
        </label>

        <label class="field">
          <span>Context memory</span>
          <select aria-label="KV cache precision" value={draft.kv_cache_type ?? "f16"} onchange={(event) => change({ kv_cache_type: event.currentTarget.value as "f16" | "q8_0" | "q4_0" })}>
            <option value="f16">Full precision</option>
            <option value="q8_0">Compact (8-bit)</option>
            <option value="q4_0">Smallest (4-bit)</option>
          </select>
        </label>

        <label class="check">
          <input type="checkbox" checked={draft.allow_overcommit ?? false} onchange={(event) => change({ allow_overcommit: event.currentTarget.checked })} />
          <span>Start even if memory looks short</span>
        </label>
      </div>

      {#if plan}
        <div class="plan" data-verdict={plan.verdict} aria-live="polite">
          <p class="verdict"><strong>{verdictLabel(plan.verdict)}</strong> · {offloadLabel(plan)} · {formatTokens(plan.context_size)} context</p>
          {#if plan.gpu_bytes > 0}
            <div class="mem-row" aria-label="GPU memory">
              <span>GPU {formatBytes(plan.gpu_bytes)} of {formatBytes(plan.gpu_budget_bytes)}</span>
              <span class="bar" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round((gpuUse ?? 0) * 100)} aria-label="GPU memory used"><span class="fill" class:hot={(gpuUse ?? 0) > 0.85} style:width={`${Math.round((gpuUse ?? 0) * 100)}%`}></span></span>
            </div>
          {/if}
          <div class="mem-row" aria-label="System memory">
            <span>Memory {formatBytes(plan.system_bytes)} of {formatBytes(plan.system_budget_bytes)} free</span>
            <span class="bar" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round((systemUse ?? 0) * 100)} aria-label="System memory used"><span class="fill" class:hot={(systemUse ?? 0) > 0.85} style:width={`${Math.round((systemUse ?? 0) * 100)}%`}></span></span>
          </div>
          {#each plan.notes as note (note)}<p class="note">{note}</p>{/each}
          <p class="note">Estimates. Model file {formatBytes(plan.weights_bytes)}, context memory {formatBytes(plan.kv_cache_bytes)}.</p>
        </div>
      {:else if view.plan_error}
        <p class="error">{reasonLabel(view.plan_error)}</p>
      {/if}

      <div class="actions">
        <button class="btn btn-primary btn-sm" type="button" onclick={save} disabled={saving}>{saving ? "Saving…" : "Save settings"}</button>
      </div>
    {/if}
  {/if}
  {#if notice}<p class="notice" role="status">{notice}</p>{/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .settings { border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface); padding: 0.9rem; display: grid; gap: 0.6rem; }
  h3 { margin: 0; font-size: var(--text-base); }
  .sub, .note { color: var(--text-3); font-size: var(--text-sm); margin: 0.15rem 0 0; }
  .note { font-size: var(--text-xs); }
  .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.6rem; }
  .field { display: grid; gap: 0.25rem; color: var(--text-3); font-size: var(--text-xs); font-weight: 650; min-width: 0; }
  .field.wide { max-width: 28rem; }
  .field small { color: var(--text-2); font-weight: 500; }
  select, input[type="number"] { width: 100%; border: 1px solid var(--border); border-radius: var(--r-sm); background: var(--surface-raised); color: var(--text-1); padding: 0.4rem 0.5rem; }
  .check { display: flex; gap: 0.45rem; align-items: center; font-size: var(--text-sm); color: var(--text-2); }
  .plan { border-top: 1px solid var(--border); padding-top: 0.55rem; display: grid; gap: 0.35rem; }
  .plan[data-verdict="insufficient_memory"] .verdict { color: var(--danger); }
  .verdict { margin: 0; font-size: var(--text-sm); }
  .mem-row { display: grid; grid-template-columns: minmax(10rem, auto) 1fr; gap: 0.6rem; align-items: center; font-size: var(--text-xs); color: var(--text-2); }
  .bar { display: block; height: 0.45rem; border-radius: 999px; background: var(--surface-raised); border: 1px solid var(--border); overflow: hidden; }
  .fill { display: block; height: 100%; background: var(--ok); }
  .fill.hot { background: var(--warn); }
  .plan[data-verdict="insufficient_memory"] .fill { background: var(--danger); }
  .actions { display: flex; justify-content: flex-end; }
  .notice, .error { margin: 0; font-size: var(--text-sm); }
  .notice { color: var(--text-2); }
  .error { color: var(--danger); }
  @media (max-width: 760px) { .grid { grid-template-columns: 1fr 1fr; } }
  @media (max-width: 480px) { .grid { grid-template-columns: 1fr; } .mem-row { grid-template-columns: 1fr; } }
</style>
