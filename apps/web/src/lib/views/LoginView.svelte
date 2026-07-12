<script lang="ts">
  import { auth, ApiError } from "../api";

  // The lock screen. Guards the whole dashboard: nothing mounts until a full
  // control session exists. Password -> (optional) MFA -> authenticated.
  let { onAuthenticated }: { onAuthenticated: (principalId: string) => void } = $props();

  let mode = $state<"login" | "register">("login");
  let step = $state<"credentials" | "mfa">("credentials");
  let username = $state("");
  let password = $state("");
  let mfaCode = $state("");
  let ticket = $state("");
  let error = $state<string | null>(null);
  let busy = $state(false);

  function messageFor(e: unknown): string {
    if (e instanceof ApiError) {
      return e.message.includes("Request failed") ? "Authentication failed." : e.message;
    }
    return "Authentication failed.";
  }

  async function submitCredentials(event: Event) {
    event.preventDefault();
    error = null;
    busy = true;
    try {
      const result =
        mode === "register"
          ? await auth.register(username, password)
          : await auth.login(username, password);
      if (result.stage === "mfa_required") {
        ticket = result.ticket ?? "";
        step = "mfa";
      } else {
        onAuthenticated(result.principal_id);
      }
    } catch (e) {
      error = messageFor(e);
    } finally {
      busy = false;
    }
  }

  async function submitMfa(event: Event) {
    event.preventDefault();
    error = null;
    busy = true;
    try {
      const result = await auth.verifyMfa(ticket, mfaCode);
      onAuthenticated(result.principal_id);
    } catch (e) {
      error = messageFor(e);
    } finally {
      busy = false;
    }
  }
</script>

<div class="lock-screen">
  <div class="card lock-card">
    <h1>Raiker</h1>
    {#if step === "credentials"}
      <p class="subtitle">
        {mode === "register" ? "Create your local account" : "Sign in to your local workspace"}
      </p>
      <form onsubmit={submitCredentials}>
        <label>
          Username
          <input bind:value={username} autocomplete="username" required />
        </label>
        <label>
          Password
          <input
            type="password"
            bind:value={password}
            autocomplete={mode === "register" ? "new-password" : "current-password"}
            required
          />
        </label>
        {#if error}<p class="error" role="alert">{error}</p>{/if}
        <button type="submit" class="btn btn-primary" disabled={busy}>
          {busy ? "…" : mode === "register" ? "Create account" : "Sign in"}
        </button>
      </form>
      <button
        type="button"
        class="link"
        onclick={() => {
          mode = mode === "login" ? "register" : "login";
          error = null;
        }}
      >
        {mode === "login" ? "Create a new local account" : "I already have an account"}
      </button>
    {:else}
      <p class="subtitle">Enter the 6-digit code from your authenticator app</p>
      <form onsubmit={submitMfa}>
        <label>
          Authentication code
          <input
            bind:value={mfaCode}
            inputmode="numeric"
            autocomplete="one-time-code"
            required
          />
        </label>
        {#if error}<p class="error" role="alert">{error}</p>{/if}
        <button type="submit" class="btn btn-primary" disabled={busy}>
          {busy ? "…" : "Verify"}
        </button>
      </form>
    {/if}
  </div>
</div>

<style>
  .lock-screen {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: var(--bg);
  }
  .lock-card {
    width: 22rem;
    max-width: 90vw;
    padding: var(--space-6);
  }
  h1 {
    margin: 0 0 var(--space-1);
  }
  .subtitle {
    color: var(--text-2);
    margin-bottom: var(--space-4);
  }
  form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  input {
    padding: var(--space-2) var(--space-3);
  }
  .error {
    color: var(--danger);
    margin: 0;
  }
  .link {
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    margin-top: var(--space-3);
    padding: 0;
  }
</style>
