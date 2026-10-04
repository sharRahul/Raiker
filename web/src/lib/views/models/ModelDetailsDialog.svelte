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
  import type { ModelCapacitiesView, ModelProfile } from "../../apiTypes";
  import { providerName } from "../../format";
  import { modelName } from "../../modelPresentation";

  let {
    profile,
    capacities,
    disconnecting,
    onclose,
    onreconnect,
    ondisconnect,
    onconfigure,
  }: {
    profile: ModelProfile;
    capacities: ModelCapacitiesView | null;
    /** A disconnect for this profile is in flight. */
    disconnecting: boolean;
    onclose: () => void;
    onreconnect: (profile: ModelProfile) => void;
    ondisconnect: (profile: ModelProfile) => void;
    onconfigure: (profile: ModelProfile) => void;
  } = $props();

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
      <h2 id="model-details-title">{providerName(profile.provider)}</h2>
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
            : "Scheduled when this local runtime is available"}
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
    {#if capacities?.can_override}<button
        class="btn btn-ghost btn-sm"
        onclick={() => onconfigure(profile)}
        >Configure exact capacity</button
      >{/if}
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
</style>
