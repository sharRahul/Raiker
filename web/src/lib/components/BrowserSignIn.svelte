<script lang="ts">
  /**
   * Connect a mail or calendar account by signing in at the provider, in the
   * owner's own browser. Raiker never sees the password; the provider sends the
   * browser back to this host, and the connection turns "connected".
   */
  import { onDestroy } from "svelte";
  import { api, ApiError } from "../api";

  let {
    connectorId,
    name,
    provider,
    onconnected,
  }: {
    connectorId: string;
    name: string;
    provider: "google" | "microsoft";
    onconnected?: () => void;
  } = $props();

  const PROVIDER_LABEL = { google: "Google", microsoft: "Microsoft" } as const;
  const POLL_MS = 2000;
  const GIVE_UP_MS = 10 * 60 * 1000;

  let phase = $state<"idle" | "waiting" | "needs_client" | "connected">("idle");
  let error = $state<string | null>(null);
  let busy = $state(false);
  let clientId = $state("");
  let clientSecret = $state("");
  let timer: ReturnType<typeof setTimeout> | null = null;
  let started = 0;

  const label = $derived(PROVIDER_LABEL[provider]);

  function stop() {
    if (timer) clearTimeout(timer);
    timer = null;
  }
  onDestroy(stop);

  async function check() {
    try {
      const view = await api.connectorStore();
      const row = view.connectors.find((item) => item.connector_id === connectorId);
      if (row?.auth_status === "connected") {
        stop();
        phase = "connected";
        onconnected?.();
        return;
      }
    } catch {
      // A missed check is retried on the next tick.
    }
    if (Date.now() - started > GIVE_UP_MS) {
      stop();
      phase = "idle";
      error = "The sign-in was not finished in ten minutes. Start it again when you are ready.";
      return;
    }
    timer = setTimeout(() => void check(), POLL_MS);
  }

  async function signIn() {
    busy = true;
    error = null;
    try {
      const started_ = await api.startConnectorSignIn(connectorId);
      window.open(started_.authorize_url, "_blank", "noopener,noreferrer");
      phase = "waiting";
      started = Date.now();
      stop();
      timer = setTimeout(() => void check(), POLL_MS);
    } catch (err) {
      if (err instanceof ApiError && err.reasonCode === "oauth_client_not_configured") {
        phase = "needs_client";
      } else if (err instanceof ApiError && err.reasonCode === "connector_sign_in_needs_loopback") {
        error = "Sign-in works only when Raiker is opened on this computer (127.0.0.1).";
      } else {
        error = `Could not start the ${label} sign-in. Try again.`;
      }
    } finally {
      busy = false;
    }
  }

  async function saveClient() {
    busy = true;
    error = null;
    try {
      await api.saveConnectorOauthClient(provider, clientId.trim(), clientSecret.trim() || undefined);
      clientSecret = "";
      phase = "idle";
      await signIn();
    } catch {
      error = "The client could not be saved. Check the client ID and try again.";
    } finally {
      busy = false;
    }
  }
</script>

<div class="browser-sign-in" role="group" aria-label={`Sign in to ${name}`}>
  {#if phase === "connected"}
    <div class="notice notice-ok" role="status">{name} is connected.</div>
  {:else if phase === "waiting"}
    <p role="status">
      Finish signing in to {label} in your browser. This page updates when you are done.
    </p>
    <div class="step-actions">
      <button class="btn btn-ghost" onclick={() => void signIn()} disabled={busy}>Open the sign-in page again</button>
      <button class="btn btn-ghost" onclick={() => { stop(); phase = "idle"; }}>Cancel</button>
    </div>
  {:else if phase === "needs_client"}
    <p>
      Signing in needs a {label} app registered to your account, once. Raiker then uses it for every
      {label} connection on this computer.
    </p>
    {#if provider === "google"}
      <ol class="steps">
        <li>In Google Cloud Console, create a project and enable the Gmail API and the Google Calendar API.</li>
        <li>Set up the OAuth consent screen as <strong>External</strong> and add yourself as a test user.</li>
        <li>Create an OAuth client ID of type <strong>Desktop app</strong>, then copy its client ID and secret here.</li>
      </ol>
    {:else}
      <ol class="steps">
        <li>In the Microsoft Entra admin center, register an app for <strong>personal and work accounts</strong>.</li>
        <li>Under Authentication, add the <strong>Mobile and desktop</strong> platform with the redirect URI <span class="mono">http://localhost/api/connector-oauth/callback</span>.</li>
        <li>Under API permissions, add Microsoft Graph <span class="mono">Mail.Read</span> and <span class="mono">Calendars.Read</span>, then copy the application (client) ID here.</li>
      </ol>
    {/if}
    <label class="field-label" for={`oauth-client-${connectorId}`}>Client ID</label>
    <input id={`oauth-client-${connectorId}`} class="input" bind:value={clientId} autocomplete="off" />
    {#if provider === "google"}
      <label class="field-label" for={`oauth-secret-${connectorId}`}>Client secret</label>
      <input id={`oauth-secret-${connectorId}`} class="input credential" type="password" bind:value={clientSecret} autocomplete="off" />
      <p class="note">Google issues a secret even for desktop apps and treats it as public. Raiker keeps it encrypted anyway.</p>
    {/if}
    <div class="step-actions">
      <button
        class="btn btn-primary"
        onclick={() => void saveClient()}
        disabled={busy || !clientId.trim() || (provider === "google" && !clientSecret.trim())}
      >{busy ? "Saving…" : `Save and sign in with ${label}`}</button>
      <button class="btn btn-ghost" onclick={() => (phase = "idle")}>Back</button>
    </div>
  {:else}
    <div class="step-actions">
      <button class="btn btn-primary" onclick={() => void signIn()} disabled={busy}>
        {busy ? "Opening…" : `Sign in with ${label}`}
      </button>
    </div>
    <p class="note">Opens {label}'s own sign-in page in your browser. Raiker never sees your password, and reads only.</p>
  {/if}
  {#if error}<div class="notice notice-danger" role="alert">{error}</div>{/if}
</div>

<style>
  .browser-sign-in { display: grid; gap: var(--space-2, 0.5rem); }
  .steps { margin: 0; padding-left: 1.25rem; display: grid; gap: 0.25rem; }
</style>
