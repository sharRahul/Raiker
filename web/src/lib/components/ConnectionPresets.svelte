<script lang="ts">
  /**
   * QUI-P04 — what Raiker may do with one connection, as three presets, and
   * what it last did with it.
   *
   * * **Read only** — the default for a new connection. Reads go ahead under
   *   Permissions; a change is refused, whatever else allows it.
   * * **Ask before changes** — every change waits for you.
   * * **Custom** — Permissions as set, opened at this connection's permission.
   *
   * Following Hermes' connector presets and Muse's per-app *read-only* or *full
   * actions*. A preset only narrows; the runtime enforces it, at the route and
   * again in the connector itself.
   */
  import { untrack } from "svelte";
  import { contract, type ConnectorActivityItem, type StoreConnector } from "../generated/apiContract";
  import { announcePermissionsChanged, onPermissionsChanged } from "../permissionSync";
  import { relativeTime, humanize } from "../format";

  let {
    connector,
    capability = null,
    onchanged,
  }: {
    connector: StoreConnector;
    /** The connection's permission, so Custom opens Permissions at it. */
    capability?: string | null;
    onchanged?: () => void;
  } = $props();

  type Preset = StoreConnector["preset"];
  const PRESETS: ReadonlyArray<{ id: Preset; label: string; detail: string }> = [
    { id: "read_only", label: "Read only", detail: "Reads go ahead under your permissions. Nothing is changed." },
    { id: "ask", label: "Ask before changes", detail: "Every change waits for you, even ones your permissions allow." },
    { id: "custom", label: "Custom", detail: "Your permissions as set, with nothing added." },
  ];

  // What the page shows: the stored preset, until the owner picks another.
  let chosen = $derived<Preset>(connector.preset);
  let busy = $state(false);
  let failure = $state<string | null>(null);
  let activity = $state<ConnectorActivityItem[] | null>(null);
  const uid = `cp-${Math.random().toString(36).slice(2, 8)}`;
  const customHref = $derived(capability ? `#/capabilities?item=${encodeURIComponent(capability)}` : "#/capabilities");

  // Found live: the connection refreshes after a preset is saved, so a second
  // read starts while the first is out, and the older one's answer (or its
  // cancellation) landed last and read as "could not be read". Only the
  // newest read may set what the page says.
  let readSeq = 0;
  async function readActivity(id: string) {
    const seq = ++readSeq;
    try {
      const items = (await contract.connectorActivity(id)).items;
      if (seq === readSeq) activity = items;
    } catch {
      if (seq === readSeq) activity = null;
    }
  }

  $effect(() => {
    const id = connector.connector_id;
    untrack(() => void readActivity(id));
    return onPermissionsChanged((kind) => {
      if (kind === "connections") onchanged?.();
    });
  });

  async function choose(preset: Preset) {
    if (busy || preset === connector.preset) return;
    const before = chosen;
    chosen = preset;
    busy = true;
    failure = null;
    try {
      await contract.setConnectorPreset(connector.connector_id, { preset });
      announcePermissionsChanged("connections");
      onchanged?.();
    } catch {
      chosen = before;
      failure = "That choice was not saved. What Raiker may do is unchanged.";
    } finally {
      busy = false;
    }
  }

  const STATUS: Record<string, string> = {
    completed: "Done",
    failed: "Failed",
    processing: "Running",
  };
</script>

<fieldset class="presets" disabled={busy || !connector.installed}>
  <legend class="sr-only">What Raiker may do with {connector.display_name}</legend>
  {#each PRESETS as preset (preset.id)}
    <label class="preset" class:chosen={chosen === preset.id}>
      <input type="radio" name={`${uid}-preset`} value={preset.id} checked={chosen === preset.id} onchange={() => void choose(preset.id)} />
      <span>
        <strong>{preset.label}</strong>
        <small>{preset.detail}</small>
      </span>
    </label>
  {/each}
</fieldset>
{#if chosen === "custom"}
  <p class="note"><a href={customHref}>Open {connector.display_name} in Permissions</a></p>
{/if}
{#if failure}<p class="note" role="alert">{failure}</p>{/if}

<h4>Recent activity</h4>
{#if activity === null}
  <p class="note">Recent activity could not be read.</p>
{:else if activity.length === 0}
  <p class="note">Nothing yet.</p>
{:else}
  <ul class="activity">
    {#each activity as item, index (index)}
      <li>
        <span>{humanize(item.operation_id)}</span>
        <span class="status">{STATUS[item.status] ?? humanize(item.status)}</span>
        <time datetime={item.started_at}>{relativeTime(item.started_at)}</time>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .presets { border: 0; margin: 0 0 var(--space-2); padding: 0; display: grid; gap: 0.4rem; }
  .preset {
    display: flex; gap: 0.6rem; align-items: flex-start; padding: 0.55rem 0.7rem;
    border: 1px solid var(--border); border-radius: var(--r-md); cursor: pointer; background: var(--surface);
  }
  .preset.chosen { border-color: var(--accent-border); background: var(--accent-soft); }
  .preset span { display: grid; gap: 0.1rem; }
  .preset strong { font-size: var(--text-sm); color: var(--text-1); }
  .preset small { font-size: var(--text-xs); color: var(--text-2); }
  .preset input { margin-top: 0.2rem; }
  .note { margin: 0 0 var(--space-2); font-size: var(--text-sm); color: var(--text-2); }
  h4 { margin: var(--space-3) 0 var(--space-1); font-size: var(--text-sm); color: var(--text-1); }
  .activity { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.25rem; font-size: var(--text-sm); }
  .activity li { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 0.8rem; color: var(--text-1); }
  .status, time { color: var(--text-3); }
</style>
