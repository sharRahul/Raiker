<script lang="ts">
  /**
   * The llama.cpp engine Raiker installs and supervises.
   *
   * Answers, in order: is the engine here and which build is it; what this
   * computer has and which backend suits it; what each slot is serving, how
   * it was sized, and whether it is healthy. Install, update and remove are
   * here; so are Stop and Restart for each slot. Nothing on this card reaches
   * the network until the owner presses Install or Check for updates.
   */
  import { onDestroy, onMount, untrack } from "svelte";
  import { api, ApiError } from "../../api";
  import type { ModelOperation } from "../../apiTypes";
  import type { LlamaRuntimeOverview, LlamaUpdateCheck, SlotHealth } from "../../generated/apiContract";
  import {
    BACKEND_LABELS,
    backendLabel,
    formatBytes,
    formatTokens,
    offloadLabel,
    operationReason,
    phaseLabel,
    reasonLabel,
    slotStateLabel,
    slotTone,
  } from "../../llamaRuntime";

  let {
    onchanged,
    active = true,
    revision = 0,
  }: {
    onchanged?: () => void;
    active?: boolean;
    /** Bumped when the page rereads, e.g. after a model was queued to serve in
     *  the GGUF row beside this panel, so the slots here follow it. */
    revision?: number;
  } = $props();

  let overview = $state<LlamaRuntimeOverview | null>(null);
  let operations = $state<ModelOperation[]>([]);
  let backend = $state<string>("auto");
  let busy = $state(false);
  let error = $state<string | null>(null);
  let update = $state<LlamaUpdateCheck | null>(null);
  let confirmRemove = $state(false);
  let timer: ReturnType<typeof setTimeout> | null = null;

  const installing = $derived(
    operations.find((op) => op.kind === "install" && op.target === "llama.cpp" && ["queued", "running", "cancel_requested"].includes(op.state)) ?? null,
  );
  const lastFailure = $derived(
    operations
      .filter((op) => (op.kind === "install" && op.target === "llama.cpp") || op.kind === "deploy")
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0] ?? null,
  );
  const settling = $derived(
    installing !== null ||
      (overview?.slots ?? []).some((slot) => slot.state === "starting" || slot.state === "restarting") ||
      operations.some((op) => op.kind === "deploy" && ["queued", "running"].includes(op.state)),
  );
  const gpu = $derived.by(() => {
    const hw = overview?.hardware;
    if (!hw) return null;
    return hw.gpus.find((item) => item.discrete) ?? hw.gpus[0] ?? null;
  });

  function describe(err: unknown, fallback: string): string {
    if (err instanceof ApiError && err.reasonCode) return reasonLabel(err.reasonCode);
    return fallback;
  }

  async function load(refresh = false) {
    try {
      const [view, ops] = await Promise.all([api.llamaRuntime(refresh), api.modelOperations()]);
      const wasSettling = settling;
      // A host older than this panel, or a partial answer, leaves the card
      // saying it could not read the engine rather than throwing mid-render.
      if (!view?.hardware || !Array.isArray(view.slots) || !view.executable) {
        throw new Error("unreadable engine status");
      }
      overview = view;
      operations = Array.isArray(ops?.items) ? ops.items : [];
      error = null;
      if (wasSettling && !settling) onchanged?.();
    } catch (err) {
      error = describe(err, "The llama.cpp engine status could not be read.");
    }
    schedule();
  }

  function schedule() {
    if (timer) clearTimeout(timer);
    timer = settling ? setTimeout(() => { if (active) void load(); else schedule(); }, 2000) : null;
  }

  async function install() {
    busy = true;
    error = null;
    try {
      await api.installLlamaRuntime(backend as "auto");
      update = null;
      await load();
    } catch (err) {
      error = describe(err, "The install could not be started.");
    } finally {
      busy = false;
    }
  }

  async function checkUpdate() {
    busy = true;
    error = null;
    try {
      update = await api.checkLlamaRuntimeUpdate();
    } catch (err) {
      error = describe(err, "GitHub could not be reached to check for updates.");
    } finally {
      busy = false;
    }
  }

  async function remove() {
    busy = true;
    error = null;
    try {
      overview = await api.uninstallLlamaRuntime();
      confirmRemove = false;
    } catch (err) {
      error = describe(err, "The engine could not be removed.");
    } finally {
      busy = false;
    }
  }

  async function stop(slot: SlotHealth) {
    busy = true;
    try {
      overview = await api.stopLlamaSlot(slot.slot_profile_id);
      onchanged?.();
    } catch (err) {
      error = describe(err, "The model could not be stopped.");
    } finally {
      busy = false;
    }
  }

  async function restart(slot: SlotHealth) {
    busy = true;
    try {
      await api.restartLlamaSlot(slot.slot_profile_id);
      await load();
    } catch (err) {
      error = describe(err, "The model could not be restarted.");
    } finally {
      busy = false;
    }
  }

  function percent(op: ModelOperation): string {
    return op.progress_percent !== null && op.progress_percent !== undefined ? ` ${op.progress_percent}%` : "";
  }

  onMount(() => void load());
  let seenRevision = untrack(() => revision);
  $effect(() => {
    if (revision !== seenRevision) {
      seenRevision = revision;
      untrack(() => void load());
    }
  });
  onDestroy(() => {
    if (timer) clearTimeout(timer);
  });
</script>

<section class="engine" aria-labelledby="llama-engine-title">
  <header>
    <div>
      <h3 id="llama-engine-title">llama.cpp engine</h3>
      <p class="sub">Runs GGUF models on this computer. Raiker installs, sizes and watches it for you.</p>
    </div>
    {#if overview}
      {#if overview.installation}
        <span class="badge ok" data-engine-state="managed">{overview.installation.tag} · {backendLabel(overview.installation.backend)}</span>
      {:else if overview.executable.source === "path"}
        <span class="badge" data-engine-state="path">Your own llama-server</span>
      {:else}
        <span class="badge warn" data-engine-state="none">Not installed</span>
      {/if}
    {/if}
  </header>

  {#if overview === null && !error}
    <p class="muted">Checking this computer…</p>
  {:else if overview}
    <dl class="hardware" aria-label="This computer">
      <div><dt>Graphics</dt><dd>{gpu ? `${gpu.name}${gpu.memory_total_bytes ? ` · ${formatBytes(gpu.memory_total_bytes)}` : ""}` : "No GPU for local models"}</dd></div>
      <div><dt>Memory</dt><dd>{formatBytes(overview.hardware.available_memory_bytes)} free of {formatBytes(overview.hardware.total_memory_bytes)}</dd></div>
      <div><dt>Best engine</dt><dd>{backendLabel(overview.hardware.recommended_backend)}</dd></div>
    </dl>
    <p class="reason">{overview.hardware.reason}</p>

    {#if installing}
      <div class="progress" role="status" aria-live="polite">
        <span>{phaseLabel(installing.phase)}{percent(installing)}</span>
        <progress max="100" value={installing.progress_percent ?? undefined}></progress>
        <button class="btn btn-ghost btn-sm" type="button" onclick={() => void api.cancelModelOperation(installing.operation_id).then(() => load())}>Cancel</button>
      </div>
    {:else}
      <div class="actions">
        <label class="backend">
          <span>Engine build</span>
          <select bind:value={backend} disabled={busy} aria-label="Engine build">
            <option value="auto">{BACKEND_LABELS.auto} ({backendLabel(overview.hardware.recommended_backend)})</option>
            {#each overview.hardware.backends as option (option)}
              <option value={option}>{backendLabel(option)}</option>
            {/each}
          </select>
        </label>
        <button class="btn btn-primary btn-sm" type="button" onclick={install} disabled={busy}>
          {overview.installation ? "Reinstall" : "Install llama.cpp"}
        </button>
        {#if overview.installation}
          <button class="btn btn-ghost btn-sm" type="button" onclick={checkUpdate} disabled={busy}>Check for updates</button>
          <button class="btn btn-ghost btn-sm" type="button" onclick={() => (confirmRemove = true)} disabled={busy}>Remove</button>
        {/if}
      </div>
      <p class="fine">
        Downloads the official build from <a href={overview.release_page} target="_blank" rel="noopener noreferrer">ggml-org/llama.cpp on GitHub</a>
        (<a href={overview.license_url} target="_blank" rel="noopener noreferrer">MIT licence</a>), checks it against its published SHA-256
        checksum, and keeps it inside Raiker's data folder. No administrator rights are needed.
      </p>
    {/if}

    {#if update}
      <p class="notice" role="status">
        {update.update_available
          ? `llama.cpp ${update.latest_tag} is available (you have ${update.installed_tag ?? "none"}). Press Reinstall to update; served models restart on their next start.`
          : `You have the latest llama.cpp (${update.latest_tag}).`}
      </p>
    {/if}

    {#if confirmRemove}
      <div class="confirm" role="alertdialog" aria-label="Remove the engine">
        <p>Remove the llama.cpp engine from this computer? Your models stay in your library.</p>
        <button class="btn btn-sm" type="button" onclick={remove} disabled={busy}>Remove</button>
        <button class="btn btn-ghost btn-sm" type="button" onclick={() => (confirmRemove = false)}>Keep</button>
      </div>
    {/if}

    {#if overview.slots.length > 0}
      <ul class="slots" aria-label="Served models">
        {#each overview.slots as slot (slot.slot_profile_id)}
          <li data-slot={slot.slot_profile_id}>
            <div class="slot-head">
              <strong title={slot.model_path}>{slot.model_path.split(/[\\/]/).pop()}</strong>
              <span class="badge {slotTone(slot.state)}">{slotStateLabel(slot.state)}</span>
            </div>
            <p class="plan">
              {offloadLabel(slot.plan)} · {formatTokens(slot.plan.context_size)} context ·
              about {formatBytes(slot.plan.gpu_bytes + slot.plan.system_bytes)} of memory
              {#if slot.restarts > 0}· restarted {slot.restarts}×{/if}
            </p>
            {#if slot.last_error}<p class="warn-text">{reasonLabel(slot.last_error)}</p>{/if}
            <div class="slot-actions">
              <button class="btn btn-ghost btn-sm" type="button" onclick={() => restart(slot)} disabled={busy}>Restart</button>
              <button class="btn btn-ghost btn-sm" type="button" onclick={() => stop(slot)} disabled={busy}>Stop</button>
            </div>
          </li>
        {/each}
      </ul>
    {/if}

    {#each overview.restore_failures as failure (failure.slot_profile_id)}
      <p class="warn-text" role="status">
        {failure.model_path.split(/[\\/]/).pop()} was not started again: {reasonLabel(failure.reason_code)}
      </p>
    {/each}

    {#if lastFailure && lastFailure.state === "failed"}
      <p class="error" role="alert" data-last-failure={lastFailure.kind}>{operationReason(lastFailure)}</p>
    {/if}
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .engine { border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface); padding: 0.9rem; display: grid; gap: 0.6rem; }
  header { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
  h3 { margin: 0; font-size: var(--text-base); }
  .sub, .reason, .fine, .muted, .plan { color: var(--text-3); font-size: var(--text-sm); margin: 0; }
  .fine { font-size: var(--text-xs); }
  .badge { border: 1px solid var(--border); border-radius: 999px; padding: 0.1rem 0.55rem; font-size: var(--text-xs); white-space: nowrap; color: var(--text-2); }
  .badge.ok { border-color: var(--ok-border); color: var(--ok); }
  .badge.busy { color: var(--text-2); }
  .badge.warn, .badge.bad { border-color: var(--danger-border); color: var(--danger); }
  .hardware { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.5rem; margin: 0; }
  .hardware div { min-width: 0; }
  dt { color: var(--text-3); font-size: var(--text-xs); font-weight: 650; }
  dd { margin: 0.1rem 0 0; font-size: var(--text-sm); overflow-wrap: anywhere; }
  .actions { display: flex; gap: 0.45rem; align-items: flex-end; flex-wrap: wrap; }
  .backend { display: grid; gap: 0.2rem; color: var(--text-3); font-size: var(--text-xs); font-weight: 650; }
  select { border: 1px solid var(--border); border-radius: var(--r-sm); background: var(--surface-raised); color: var(--text-1); padding: 0.4rem 0.5rem; }
  .progress { display: flex; gap: 0.6rem; align-items: center; font-size: var(--text-sm); }
  progress { flex: 1; min-width: 6rem; }
  .slots { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.45rem; }
  .slots li { border: 1px solid var(--border); border-radius: var(--r-sm); padding: 0.6rem; display: grid; gap: 0.3rem; }
  .slot-head { display: flex; justify-content: space-between; gap: 0.6rem; align-items: center; min-width: 0; }
  .slot-head strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--text-sm); }
  .slot-actions { display: flex; gap: 0.35rem; justify-content: flex-end; }
  .confirm { display: flex; gap: 0.45rem; align-items: center; flex-wrap: wrap; font-size: var(--text-sm); }
  .confirm p { margin: 0; flex: 1 1 14rem; }
  .error, .warn-text, .notice { margin: 0; font-size: var(--text-sm); }
  .error, .warn-text { color: var(--danger); }
  .notice { color: var(--text-2); }
  @media (max-width: 640px) { .hardware { grid-template-columns: 1fr; } header { display: block; } }
</style>
