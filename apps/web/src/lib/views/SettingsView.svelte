<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import General from "./settings/General.svelte";
  import Notification from "./settings/Notification.svelte";
  import Personalisation from "./settings/Personalisation.svelte";
  import Voice from "./settings/Voice.svelte";
  import DataControls from "./settings/DataControls.svelte";
  import Storage from "./settings/Storage.svelte";
  import SecurityLogin from "./settings/SecurityLogin.svelte";
  import TrustedContact from "./settings/TrustedContact.svelte";
  import Account from "./settings/Account.svelte";

  let { principal = "—" }: { principal?: string } = $props();

  // The 9-section settings taxonomy. Each section is self-contained; backed
  // controls persist to /api/settings, unbacked ones render "not yet active".
  const SECTIONS = [
    { id: "general", label: "General", comp: General },
    { id: "notification", label: "Notification", comp: Notification },
    { id: "personalisation", label: "Personalisation", comp: Personalisation },
    { id: "voice", label: "Voice", comp: Voice },
    { id: "data", label: "Data Controls", comp: DataControls },
    { id: "storage", label: "Storage", comp: Storage },
    { id: "security", label: "Security & Login", comp: SecurityLogin },
    { id: "trusted", label: "Trusted Contact", comp: TrustedContact },
    { id: "account", label: "Account", comp: Account },
  ] as const;

  let active = $state<string>("general");
  let settings = $state<Record<string, unknown>>({});
  let status = $state<{ vault: string; mfa_enrolled: boolean; username: string }>({
    vault: "missing",
    mfa_enrolled: false,
    username: "—",
  });
  let loadError = $state<string | null>(null);

  async function load() {
    loadError = null;
    try {
      const s = await api.settings();
      settings = s.settings;
      status = s.status;
    } catch (e) {
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  // Merge a patch into the settings blob and persist the whole blob.
  async function save(patch: Record<string, unknown>) {
    const next = { ...settings, ...patch };
    settings = next;
    try {
      await api.putSettings(next);
    } catch {
      // Re-read truth if the server rejected the write; never fabricate success.
      await load();
    }
  }

  onMount(load);
</script>

<p class="page-lead">
  Your settings, saved per account. Runtime changes are re-confirmed and enforced server-side —
  this page adds no authority of its own.
</p>

{#if loadError}
  <p class="notice notice-danger" role="alert">Settings unavailable: {loadError}</p>
{/if}

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
    {:else if active === "voice"}
      <Voice />
    {:else if active === "data"}
      <DataControls {settings} {save} />
    {:else if active === "storage"}
      <Storage {settings} {save} />
    {:else if active === "security"}
      <SecurityLogin />
    {:else if active === "trusted"}
      <TrustedContact {settings} {save} />
    {:else}
      <Account {settings} {save} {status} />
    {/if}
  </div>
</div>

<style>
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
    border-radius: var(--radius-2);
    background: none;
    color: var(--text-1);
    cursor: pointer;
  }
  .rail-item:hover {
    background: var(--bg-2);
  }
  .rail-item.active {
    background: var(--bg-2);
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
