<script lang="ts">
  /**
   * UX-MODEL-01 — Model details, out of the Models page.
   *
   * What a profile's connection, capacity and limits are, and the three things
   * an owner can do about them. The page still owns the actions — reconnecting
   * opens its sign-in dialog, and disconnecting and configuring capacity go
   * through its handlers — so this draws and reports, and holds no state of
   * its own beyond what it is handed.
   */
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import { api, ApiError } from "../../api";
  import type { ModelCapacitiesView, ModelProfile } from "../../apiTypes";
  import { profileLabel, providerName } from "../../format";
  import { modelName } from "../../modelPresentation";

  let {
    profile,
    capacities,
    disconnecting,
    onclose,
    onreconnect,
    ondisconnect,
    onchanged,
  }: {
    profile: ModelProfile;
    capacities: ModelCapacitiesView | null;
    /** A disconnect for this profile is in flight. */
    disconnecting: boolean;
    onclose: () => void;
    onreconnect: (profile: ModelProfile) => void;
    ondisconnect: (profile: ModelProfile) => void;
    /** A saved change the page should read back (the context override). */
    onchanged: () => void | Promise<void>;
  } = $props();

  // ── Context-length override ──────────────────────────────────────────
  let capacityTokens = $state("");
  let capacityReason = $state("");
  let capacityBusy = $state(false);
  let capacityNote = $state("");
  async function saveCapacity(clear: boolean) {
    const tokens = clear ? null : Number(capacityTokens);
    if (!clear && (tokens === null || !Number.isInteger(tokens) || tokens < 1024)) {
      capacityNote = "Enter a whole number of at least 1,024 tokens.";
      return;
    }
    if (!clear && capacityReason.trim() === "") {
      capacityNote = "Say why: it is kept in the override history.";
      return;
    }
    capacityBusy = true;
    capacityNote = "";
    try {
      await api.setModelCapacity(profile.profile_id, profile.model, tokens, clear ? "Cleared" : capacityReason.trim());
      capacityNote = clear ? "Override cleared." : "Saved. Turns and compaction use this window.";
      capacityTokens = "";
      capacityReason = "";
      await onchanged();
    } catch (e) {
      capacityNote = e instanceof ApiError ? `Could not save (${e.reasonCode ?? e.status})` : "Could not save.";
    } finally {
      capacityBusy = false;
    }
  }

  // ── Server check (local-server checks) ─────────────────────────────
  const SELF_HOSTED = new Set(["ollama", "lm-studio", "llama.cpp", "mlx", "openai-compatible"]);
  const checkable = $derived(SELF_HOSTED.has(profile.provider) && !!profile.model && !profile.model.includes("<"));
  type ServerCheck = Awaited<ReturnType<typeof api.checkModelServer>>;
  let check = $state<ServerCheck | null>(null);
  let checking = $state(false);
  let checkError = $state("");
  const VERDICT: Record<string, string> = {
    native: "Works: the model calls tools natively.",
    as_text: "Returned as text: the server is not parsing tool calls.",
    not_called: "Not called: the model answered without using the tool.",
    refused: "Refused: the server would not accept tools.",
    unavailable: "Could not reach the server to check.",
  };
  async function runCheck() {
    checking = true;
    checkError = "";
    try {
      check = await api.checkModelServer(profile.profile_id, profile.model);
    } catch (e) {
      checkError = e instanceof ApiError ? `Could not check (${e.reasonCode ?? e.status})` : "Could not check.";
    } finally {
      checking = false;
    }
  }

  function contextCapacity(profile: ModelProfile): string {
    if (!profile.context_window_tokens) {
      return "Not reported by this runtime. Refresh its model catalogue or configure an exact fallback before relying on a percentage.";
    }
    const source =
      profile.context_window_source === "owner"
        ? "Administrator override"
        : profile.context_window_source === "provider"
          ? "Reported by the provider runtime"
          : "Configured in Raiker";
    return `${new Intl.NumberFormat().format(profile.context_window_tokens)} tokens · ${source}`;
  }

  const capacityEntry = $derived(
    capacities?.entries.find(
      (entry) => entry.profile_id === profile.profile_id && entry.model === profile.model,
    ),
  );
</script>

<div
  class="details-overlay"
  role="presentation"
  onclick={(event) =>
    event.target === event.currentTarget && onclose()}
>
  <div
    class="details-dialog card"
    role="dialog"
    aria-modal="true"
    aria-labelledby="model-details-title"
    tabindex="-1"
  >
    <button
      class="close"
      aria-label="Close model details"
      onclick={() => onclose()}>×</button
    >
    <p class="eyebrow">Model details</p>
    <div class="details-heading">
      <ProviderLogo provider={profile.provider} size={28} />
      <h2 id="model-details-title">{profileLabel(profile)}</h2>
    </div>
    <dl class="details-grid">
      <div>
        <dt>Selected model</dt>
        <dd>
          <code
            >{profile.selected
              ? modelName(profile.model)
              : "Not selected"}</code
          >
        </dd>
      </div>
      <div>
        <dt>Connection</dt>
        <dd>
          {profile.connection_configured
            ? "Encrypted instance connection saved"
            : "Not configured"}
          <!-- BUG-274 — that a workspace is named, never which one. Here
               rather than on the card: the card carries readiness and nothing
               else by design (BUG-208 slice E), and this is credential
               management, which is what Details already holds. -->
          {#if profile.workspace_configured}
            · workspace named
          {/if}
        </dd>
      </div>
      <div>
        <dt>Context capacity</dt>
        <dd>{contextCapacity(profile)}</dd>
      </div>
      <div>
        <dt>Local refresh</dt>
        <dd>
          {capacities?.sync.find(
            (state) => state.profile_id === profile.profile_id,
          )?.next_refresh_at
            ? `Next check ${capacities.sync.find((state) => state.profile_id === profile.profile_id)?.next_refresh_at}`
            : "Scheduled for when this local model server is available"}
        </dd>
      </div>
      <div>
        <dt>Current context usage</dt>
        <dd>
          No provider context telemetry has been received for this model yet.
        </dd>
      </div>
      <div>
        <dt>Subscription / rate limits</dt>
        <dd>
          Not available through this connection. Raiker only displays daily or
          weekly limits when an authorized provider API exposes them.
        </dd>
      </div>
    </dl>
    {#if profile.connection_configured}
      <div class="details-actions">
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={() => onreconnect(profile)}>Reconnect</button
        >
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          aria-label={`Disconnect ${providerName(profile.provider)}`}
          onclick={() => ondisconnect(profile)}
          disabled={disconnecting}
          >{disconnecting
            ? "Disconnecting…"
            : "Disconnect"}</button
        >
      </div>
    {/if}
    {#if checkable}
      <section class="server-check" aria-labelledby="server-check-h">
        <h3 id="server-check-h">Is this server set up for agent work?</h3>
        <p class="hint">One request with one harmless tool, and the context the server says it is serving. Nothing on the server changes.</p>
        <button type="button" class="btn btn-sm" onclick={() => void runCheck()} disabled={checking}
          >{checking ? "Checking…" : "Check this server"}</button
        >
        {#if checkError}<p class="note" role="alert">{checkError}</p>{/if}
        {#if check}
          <dl class="check-result" aria-label="Server check result">
            <div><dt>Tool calling</dt><dd data-verdict={check.tool_calling}>{VERDICT[check.tool_calling] ?? check.tool_calling}</dd></div>
            <div>
              <dt>Serving context</dt>
              <dd>{check.context_tokens ? `${check.context_tokens.toLocaleString()} tokens` : "Not reported by this server"}</dd>
            </div>
          </dl>
          {#if check.advice.length}
            <ul class="advice">{#each check.advice as line}<li>{line}</li>{/each}</ul>
          {/if}
        {/if}
      </section>
    {/if}
    {#if capacities?.can_override && profile.model && !profile.model.includes("<")}
      <!-- Context-length override: an exact window when the provider does
           not say, or says something wrong. Kept with a reason, in history. -->
      <form class="capacity-form" onsubmit={(e) => { e.preventDefault(); void saveCapacity(false); }}>
        <h3>Context window override</h3>
        <label>
          <span>Tokens</span>
          <input type="number" min="1024" step="1" inputmode="numeric" bind:value={capacityTokens} placeholder={profile.context_window_tokens ? String(profile.context_window_tokens) : "e.g. 65536"} />
        </label>
        <label>
          <span>Why</span>
          <input type="text" maxlength="200" bind:value={capacityReason} placeholder="Verified against the server's settings" />
        </label>
        <div class="capacity-actions">
          <button type="submit" class="btn btn-sm" disabled={capacityBusy}>Save override</button>
          {#if profile.context_window_source === "owner"}
            <button type="button" class="btn btn-ghost btn-sm" disabled={capacityBusy} onclick={() => void saveCapacity(true)}>Clear override</button>
          {/if}
        </div>
        {#if capacityNote}<p class="note" role="status">{capacityNote}</p>{/if}
      </form>
    {/if}
    {#if capacityEntry?.history.length}<details>
        <summary>Administrator override history</summary>
        <ol>
          {#each capacityEntry.history as event}<li>
              {event.action} · {event.context_window_tokens?.toLocaleString() ??
                "cleared"} · {event.recorded_at}{#if event.reason}
                — {event.reason}{/if}
            </li>{/each}
        </ol>
      </details>{/if}
  </div>
</div>

<style>
  /* ── Details modal ── */
  .details-overlay {
    align-items: center;
    background: var(--overlay);
    display: flex;
    inset: 0;
    justify-content: center;
    padding: var(--space-4);
    position: fixed;
    z-index: var(--z-scrim);
  }
  .details-dialog {
    max-width: 42rem;
    position: relative;
    width: min(100%, 42rem);
  }
  .details-heading {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    margin-bottom: 0.9rem;
  }
  .details-dialog h2 {
    margin: 0;
  }
  .close {
    background: transparent;
    border: 0;
    color: var(--text-2);
    cursor: pointer;
    font-size: var(--text-2xl);
    line-height: 1;
    position: absolute;
    right: 0.75rem;
    top: 0.65rem;
  }
  .details-grid {
    display: grid;
    gap: 0.85rem;
    margin: var(--space-4) 0 0;
  }
  .details-grid div {
    border-top: 1px solid var(--border);
    padding-top: 0.65rem;
  }
  .details-grid dt {
    color: var(--text-3);
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .details-grid dd {
    color: var(--text-2);
    line-height: 1.45;
    margin: 0.2rem 0 0;
  }
  .details-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .server-check, .capacity-form { border-top: 1px solid var(--border); margin-top: .9rem; padding-top: .8rem; display: grid; gap: .45rem; }
  .server-check h3, .capacity-form h3 { margin: 0; font-size: var(--text-md); }
  .hint, .note { margin: 0; color: var(--text-3); font-size: var(--text-sm); }
  .check-result { display: grid; gap: .3rem; margin: 0; }
  .check-result div { display: flex; gap: .6rem; }
  .check-result dt { min-width: 8rem; color: var(--text-2); }
  .check-result dd { margin: 0; }
  .advice { margin: 0; padding-left: 1.1rem; font-size: var(--text-sm); }
  .capacity-form label { display: grid; gap: .2rem; font-size: var(--text-sm); }
  .capacity-actions { display: flex; gap: .5rem; }
</style>
