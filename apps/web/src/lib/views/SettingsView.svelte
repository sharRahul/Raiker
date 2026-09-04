<script lang="ts">
  import { onMount } from "svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import { applyUiPrefs } from "../prefs.svelte";
  import General from "./settings/General.svelte";
  import Notification from "./settings/Notification.svelte";
  import Personalisation from "./settings/Personalisation.svelte";
  import SecurityLogin from "./settings/SecurityLogin.svelte";
  import Privacy from "./settings/Privacy.svelte";
  import Account from "./settings/Account.svelte";
  import Runtime from "./settings/Runtime.svelte";
  import WebAccess from "./settings/WebAccess.svelte";
  import GitCredential from "./settings/GitCredential.svelte";
  import Updates from "./settings/Updates.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import Icon from "../components/Icon.svelte";
  import { SETTINGS_SECTIONS as SECTIONS } from "../settingsSections";

  let { principal = "—", tab = "general" }: { principal?: string; tab?: string } = $props();


  let active = $derived<string>(SECTIONS.some((section) => section.id === tab) ? tab : "general");
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
  let dirty = $state(false);
  let dirtySections = $state<string[]>([]);

  async function load() {
    loadError = null;
    try {
      const s = await api.settings();
      // FIXED-85 — an edit made while this read was in flight must survive it.
      // The controls render before the read resolves, so a fast owner (or a
      // second load triggered by a re-mount) could choose a value, watch the
      // control show it, and then have the arriving snapshot overwrite it
      // underneath — leaving the page dirty with the *old* value and saving
      // that on the next Save. Server values are the base; unsaved edits are
      // reapplied on top, and `serverSettings` still records what the server
      // actually holds so Discard and the failure rollback stay honest.
      const unsaved = dirty ? changedFromServer() : {};
      settings = { ...s.settings, ...unsaved };
      serverSettings = { ...s.settings };
      status = s.status;
    } catch (e) {
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  /** The keys the owner has changed since the last confirmed server snapshot. */
  function changedFromServer(): Record<string, unknown> {
    const changed: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(settings)) {
      if (JSON.stringify(serverSettings[key]) !== JSON.stringify(value)) changed[key] = value;
    }
    return changed;
  }

  function save(patch: Record<string, unknown>) {
    settings = { ...settings, ...patch };
    dirty = true;
    if (!dirtySections.includes(active)) dirtySections = [...dirtySections, active];
    saveState = "idle";
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
      dirty = false;
      dirtySections = [];
    } catch (e) {
      settings = { ...serverSettings };
      saveState = "error";
      saveDetail =
        e instanceof ApiError
          ? `Couldn't save (${e.status}). Your change was rolled back.`
          : "Couldn't save. Your change was rolled back.";
    }
  }

  function discard() {
    settings = { ...serverSettings };
    dirty = false;
    dirtySections = [];
    saveState = "idle";
    saveDetail = null;
  }

  function selectSection(id: string) {
    active = id;
    window.location.hash = `#/settings?tab=${encodeURIComponent(id)}`;
  }

  onMount(load);
</script>

<!-- The topbar already says "Settings" and lists what is here. Repeating both
     as a heading and a sentence made this the one page that named itself twice
     before showing anything — Models, Tasks and Extensions all open with a
     single guide link instead, and this now matches them. The heading stays for
     the landmark; the sentence's job belongs to the guide. -->
<header class="settings-header">
  <h2 class="sr-only">Settings</h2>
  <GuideLink route="settings" />
</header>

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
    {#each ["Personal", "System"] as group}
      <div class="rail-section" role="group" aria-label={`${group} settings`}>
        <p class="rail-group">{group}</p>
        {#each SECTIONS.filter((section) => section.group === group) as section (section.id)}
          <button
            type="button"
            class="rail-item"
            class:active={active === section.id}
            aria-current={active === section.id ? "page" : undefined}
            onclick={() => selectSection(section.id)}
          >
            <Icon name={section.icon} size="md" /><span>{section.label}</span>{#if dirtySections.includes(section.id)}<span class="dirty-dot" aria-label="Unsaved changes"></span>{/if}
          </button>
        {/each}
      </div>
    {/each}
  </nav>

  <div class="section-body">
    {#if active === "general"}
      <General {settings} {save} />
    {:else if active === "notification"}
      <Notification {settings} {save} />
    {:else if active === "personalisation"}
      <Personalisation {settings} {save} />
    {:else if active === "security"}
      <SecurityLogin />
    {:else if active === "privacy"}
      <Privacy {settings} {save} />
    {:else if active === "account"}
      <Account {settings} {save} {status} />
    {:else if active === "web-access"}
      <WebAccess />
    {:else if active === "git-credential"}
      <GitCredential />
    {:else if active === "updates"}
      <Updates />
    {:else}
      <Runtime {principal} {settings} {save} />
    {/if}
    {#if dirty}
      <div class="save-bar" role="region" aria-label="Unsaved settings changes">
        <strong>You have unsaved changes</strong>
        <div><button class="btn btn-ghost" type="button" onclick={discard}>Discard changes</button><button class="btn btn-primary" type="button" onclick={push}>Save changes</button></div>
      </div>
    {/if}
  </div>
</div>

<style>
  .settings-header { margin-bottom: var(--space-4); }
  .save-status {
    min-height: 0;
    margin-bottom: var(--space-3);
  }
  .save-status .notice {
    margin: 0;
  }
  .settings-layout {
    display: grid;
    grid-template-columns: minmax(12rem, 14rem) minmax(0, 1fr);
    gap: var(--space-6);
    align-items: start;
    max-width: 78rem;
  }
  .section-rail {
    display: flex;
    flex-direction: column;
    gap: 2px;
    position: sticky;
    top: var(--space-4);
  }
  .rail-section { display: grid; gap: 2px; }
  .rail-section + .rail-section { margin-top: var(--space-4); }
  .rail-item {
    text-align: left;
    display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: .55rem;
    min-height: 44px; padding: var(--space-2) var(--space-3);
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
  .rail-group { margin: var(--space-2) var(--space-3); color: var(--text-3); font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .09em; }
  .dirty-dot { width: .45rem; height: .45rem; border-radius: 50%; background: var(--warning); }
  .save-bar { position: sticky; bottom: var(--space-3); z-index: 5; width: 100%; margin-top: var(--space-5); padding: var(--space-3) var(--space-4); display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); border: 1px solid var(--accent-border); border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-2); }
  .save-bar div { display: flex; gap: var(--space-2); }
  @media (max-width: 40rem) {
    .settings-layout {
      grid-template-columns: 1fr;
    }
    .section-rail {
      flex-direction: row;
      flex-wrap: wrap;
      position: static;
    }
    .rail-section { width: 100%; }
  }
</style>
