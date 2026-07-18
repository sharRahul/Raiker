<script lang="ts">
  import { onMount } from "svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import { applyUiPrefs } from "../prefs.svelte";
  import General from "./settings/General.svelte";
  import Notification from "./settings/Notification.svelte";
  import Personalisation from "./settings/Personalisation.svelte";
  import Storage from "./settings/Storage.svelte";
  import SecurityLogin from "./settings/SecurityLogin.svelte";
  import Account from "./settings/Account.svelte";

  let { principal = "—" }: { principal?: string } = $props();

  // Only sections the runtime actually backs. Voice, trusted-contact
  // recovery, data-export tooling, and cloud/cache controls have no backend
  // consumer, so they are not presented as settings at all.
  const SECTIONS = [
    { id: "general", label: "General" },
    { id: "notification", label: "Notification" },
    { id: "personalisation", label: "Personalisation" },
    { id: "storage", label: "Storage" },
    { id: "security", label: "Security & Login" },
    { id: "account", label: "Account" },
  ] as const;

  let active = $state<string>("general");
  let settings = $state<Record<string, unknown>>({});
  let status = $state<{ vault: string; mfa_enrolled: boolean; username: string }>({
    vault: "missing",
    mfa_enrolled: false,
    username: "—",
  });
  let loadError = $state<string | null>(null);

  // One serialized save queue. Each write is optimistic in the UI, confirmed
  // by the server, and rolled back to the last server snapshot on failure so
  // a failed write is never silently kept.
  let serverSettings: Record<string, unknown> = {};
  let saveState = $state<"idle" | "saving" | "saved" | "error">("idle");
  let saveDetail = $state<string | null>(null);
  let queue: Promise<void> = Promise.resolve();

  async function load() {
    loadError = null;
    try {
      const s = await api.settings();
      settings = s.settings;
      serverSettings = { ...s.settings };
      status = s.status;
    } catch (e) {
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  function save(patch: Record<string, unknown>) {
    settings = { ...settings, ...patch };
    queue = queue.then(() => push());
  }

  async function push() {
    const snapshot = { ...settings };
    saveState = "saving";
    try {
      await api.putSettings(snapshot);
      serverSettings = snapshot;
      saveState = "saved";
      saveDetail = null;
      applyUiPrefs(snapshot);
    } catch (e) {
      settings = { ...serverSettings };
      saveState = "error";
      saveDetail =
        e instanceof ApiError
          ? `Couldn't save (${e.status}). Your change was rolled back.`
          : "Couldn't save. Your change was rolled back.";
    }
  }

  onMount(load);
</script>

<p class="page-lead">
  Your settings, saved per account. Runtime changes are re-confirmed and enforced server-side —
  this page adds no authority of its own.
</p>

{#if loadError}
  <PageState state="error" title="Couldn't load settings" detail={loadError} />
{/if}

<div class="save-status" aria-live="polite">
  {#if saveState === "saving"}
    <p class="notice" role="status">Saving…</p>
  {:else if saveState === "saved"}
    <p class="notice notice-ok" role="status">All changes saved.</p>
  {:else if saveState === "error"}
    <p class="notice notice-danger" role="alert">{saveDetail}</p>
  {/if}
</div>

<div class="settings-layout">
  <nav class="section-rail" aria-label="Settings sections">
    {#each SECTIONS as section (section.id)}
      <button
        type="button"
        class="rail-item"
        class:active={active === section.id}
        aria-current={active === section.id ? "page" : undefined}
        onclick={() => (active = section.id)}
      >
        {section.label}
      </button>
    {/each}
  </nav>

  <div class="section-body">
    {#if active === "general"}
      <General {settings} {save} {principal} />
    {:else if active === "notification"}
      <Notification {settings} {save} />
    {:else if active === "personalisation"}
      <Personalisation {settings} {save} />
    {:else if active === "storage"}
      <Storage />
    {:else if active === "security"}
      <SecurityLogin />
    {:else}
      <Account {settings} {save} {status} />
    {/if}
  </div>
</div>

<style>
  .save-status {
    min-height: 0;
    margin-bottom: var(--space-3);
  }
  .save-status .notice {
    margin: 0;
  }
  .settings-layout {
    display: grid;
    grid-template-columns: 14rem 1fr;
    gap: var(--space-5);
    align-items: start;
  }
  .section-rail {
    display: flex;
    flex-direction: column;
    gap: 2px;
    position: sticky;
    top: 0;
  }
  .rail-item {
    text-align: left;
    padding: var(--space-2) var(--space-3);
    border: none;
    border-radius: var(--r-sm);
    background: none;
    color: var(--text-1);
    font: inherit;
    cursor: pointer;
  }
  .rail-item:hover {
    background: var(--sunken);
  }
  .rail-item.active {
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 600;
  }
  .section-body {
    min-width: 0;
  }
  @media (max-width: 40rem) {
    .settings-layout {
      grid-template-columns: 1fr;
    }
    .section-rail {
      flex-direction: row;
      flex-wrap: wrap;
      position: static;
    }
  }
</style>
