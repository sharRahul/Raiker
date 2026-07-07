<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import StepUpDialog from "../components/StepUpDialog.svelte";
  import type { StepUpValues } from "../components/StepUpDialog.svelte";
  import { api, ApiError } from "../api";
  import type { RuntimeMode } from "../apiTypes";
  import { explainReasonCode } from "../reasonCodes";
  import {
    applyTheme,
    loadThemeChoice,
    saveThemeChoice,
    type ThemeChoice,
  } from "../theme";

  let { principal = "—" }: { principal?: string } = $props();

  let mode = $state<RuntimeMode | null>(null);
  let loadError = $state<string | null>(null);
  let modeChoice = $state("");
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  type Pending = { kind: "activate_mode"; mode_name: string } | { kind: "disable_mode" };
  let pending = $state<Pending | null>(null);
  let busy = $state(false);
  let dialogError = $state<string | null>(null);

  // Appearance.
  let theme = $state<ThemeChoice>("system");
  const THEME_OPTIONS: { value: ThemeChoice; label: string; hint: string }[] = [
    { value: "light", label: "Light", hint: "Soft pastel light theme" },
    { value: "dark", label: "Dark", hint: "Deep ink dark theme" },
    { value: "system", label: "System", hint: "Follow your OS preference" },
  ];

  function chooseTheme(value: ThemeChoice) {
    theme = value;
    applyTheme(value);
    saveThemeChoice(value);
  }

  async function load() {
    loadError = null;
    try {
      mode = await api.runtimeMode();
      if (mode && modeChoice === "") {
        modeChoice = mode.allowed_modes[0] ?? "";
      }
    } catch (e) {
      mode = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function confirm(values: StepUpValues) {
    if (pending === null) return;
    busy = true;
    dialogError = null;
    try {
      if (pending.kind === "activate_mode") {
        await api.activateRuntimeMode(pending.mode_name, values.reason);
        notice = { kind: "ok", text: `Activated runtime mode ${pending.mode_name}.` };
      } else {
        await api.disableRuntimeMode(values.reason);
        notice = { kind: "ok", text: "Disabled the runtime mode." };
      }
      pending = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      dialogError = explained
        ? `${explained.plain}${explained.remediation ? " " + explained.remediation : ""}`
        : "The change was rejected by the runtime.";
    } finally {
      busy = false;
    }
  }

  onMount(() => {
    theme = loadThemeChoice();
    void load();
  });
</script>

<p class="page-lead">
  Runtime mode, security posture, and appearance. Every runtime change re-confirms your human
  principal and is enforced server-side — this page adds no authority of its own. Capability gates
  and decision modes live on the <a href="#/capabilities">Capabilities</a> page.
</p>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

<section class="card" aria-labelledby="appearance-h">
  <h2 id="appearance-h">Appearance</h2>
  <div class="theme-row" role="radiogroup" aria-label="Theme">
    {#each THEME_OPTIONS as option (option.value)}
      <button
        type="button"
        class="theme-option"
        class:selected={theme === option.value}
        role="radio"
        aria-checked={theme === option.value}
        onclick={() => chooseTheme(option.value)}
      >
        <Icon name={option.value === "light" ? "sun" : option.value === "dark" ? "moon" : "system"} size={17} />
        <span class="theme-name">{option.label}</span>
        <span class="theme-hint">{option.hint}</span>
      </button>
    {/each}
  </div>
</section>

<section class="card" aria-labelledby="runtime-h">
  <h2 id="runtime-h">Runtime mode</h2>
  {#if loadError}
    <p class="error" role="alert">Unavailable: {loadError}</p>
  {:else if mode === null}
    <p class="loading">Loading…</p>
  {:else}
    <div class="mode-row">
      <div>
        <p class="mode-current">
          <code>{mode.mode_name}</code> · {mode.status}
        </p>
        <p class="sub">Activated by {mode.activated_by || "—"}{mode.reason ? ` — ${mode.reason}` : ""}</p>
      </div>
      <div class="mode-controls">
        <label class="sr-only" for="mode-select">Mode to activate</label>
        <select id="mode-select" class="select" bind:value={modeChoice}>
          {#each mode.allowed_modes as m (m)}
            <option value={m}>{m}</option>
          {/each}
        </select>
        <button
          type="button"
          class="btn btn-soft"
          onclick={() => {
            pending = { kind: "activate_mode", mode_name: modeChoice };
            dialogError = null;
          }}
          disabled={modeChoice === ""}
        >
          Activate
        </button>
        <button
          type="button"
          class="btn btn-danger"
          onclick={() => {
            pending = { kind: "disable_mode" };
            dialogError = null;
          }}
        >
          Disable
        </button>
      </div>
    </div>
  {/if}
</section>

<section class="card" aria-labelledby="secrets-h">
  <h2 id="secrets-h">Secrets &amp; redaction</h2>
  <p class="notice notice-warn" role="note">
    <Icon name="lock" size={15} />
    <span>
      <strong>Secret storage is not implemented (deferred).</strong> There is no secret/credential
      store in this local single-user runtime, so there is nothing to enter here.
    </span>
  </p>
  <p class="sub">
    What is enforced today is read-only redaction and a deny-by-default policy: secret-like strings
    (API keys, bearer tokens, passwords, private keys) are redacted from API responses, event logs,
    and approval previews.
  </p>
  <ul class="policy">
    <li>API responses pass through a redaction middleware before leaving the local server.</li>
    <li>Secret-like content in memory/approval payloads is shown as <code>[REDACTED]</code>.</li>
    <li>No capability can read or export raw secrets; sensitive domains stay deferred.</li>
    <li>Provider API keys are read from your environment only and never displayed or stored.</li>
  </ul>
</section>

<section class="card" aria-labelledby="about-h">
  <h2 id="about-h">About this app</h2>
  <p class="sub">
    Raiker's local web app is single-user and loopback-only (<code>127.0.0.1</code>). It talks only
    to the local governed API: every read and mutation flows through the same contracts, policy
    engine, RuntimeAuthority, and append-only audit log as the terminal client. Approval resolution
    is metadata-only — recording a decision never executes the action.
  </p>
</section>

{#if pending !== null}
  <StepUpDialog
    title={pending.kind === "activate_mode" ? `Activate ${pending.mode_name}` : "Disable runtime mode"}
    {principal}
    requireToken={false}
    requireThreatAck={false}
    {busy}
    error={dialogError}
    onConfirm={confirm}
    onCancel={() => {
      pending = null;
      dialogError = null;
    }}
  />
{/if}

<style>
  section.card {
    margin-bottom: var(--space-4);
  }
  .theme-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: var(--space-3);
  }
  .theme-option {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.2rem;
    font: inherit;
    text-align: left;
    color: var(--text-1);
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 0.75rem 0.9rem;
    cursor: pointer;
  }
  .theme-option:hover {
    border-color: var(--accent-border);
  }
  .theme-option.selected {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .theme-name {
    font-weight: 650;
  }
  .theme-hint {
    font-size: 0.76rem;
    color: var(--text-3);
  }
  .mode-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    flex-wrap: wrap;
  }
  .mode-current {
    margin: 0;
    font-size: 0.95rem;
  }
  .mode-controls {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .policy {
    color: var(--text-2);
    font-size: 0.84rem;
    margin: 0.5rem 0 0;
    padding-left: 1.1rem;
  }
  .sub {
    color: var(--text-3);
    font-size: 0.84rem;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
