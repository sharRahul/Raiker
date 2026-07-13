<script lang="ts">
  import { tick } from "svelte";
  import { auth, ApiError } from "../api";

  type RuntimeState = "locked" | "authenticating" | "verifying" | "verification_failed";

  let {
    onAuthenticated,
    runtimeState = "locked",
  }: {
    onAuthenticated: (principalId: string) => void;
    runtimeState?: RuntimeState;
  } = $props();

  let mode = $state<"login" | "register">("login");
  let step = $state<"credentials" | "mfa">("credentials");
  let username = $state("");
  let password = $state("");
  let confirmPassword = $state("");
  let mfaCode = $state("");
  let ticket = $state("");
  let error = $state<string | null>(null);
  let busy = $state(false);
  let showPassword = $state(false);

  const isRegister = $derived(mode === "register");
  const isVerifying = $derived(runtimeState === "verifying");
  const formDisabled = $derived(busy || isVerifying);
  const heroMessage = $derived(
    runtimeState === "verification_failed"
      ? "I cannot reach my runtime."
      : isRegister
        ? "Hello! I am Raiker. Nice to meet you."
        : "I am ready when you are.",
  );

  function messageFor(e: unknown): string {
    if (e instanceof ApiError) {
      return e.message.includes("Request failed") ? "Authentication failed." : e.message;
    }
    return "Authentication failed.";
  }

  async function switchMode() {
    mode = mode === "login" ? "register" : "login";
    step = "credentials";
    error = null;
    password = "";
    confirmPassword = "";
    mfaCode = "";
    await tick();
    document.getElementById("username")?.focus();
  }

  async function submitCredentials(event: Event) {
    event.preventDefault();
    error = null;
    if (mode === "register" && password !== confirmPassword) {
      error = "Passwords do not match.";
      return;
    }
    busy = true;
    try {
      const result =
        mode === "register"
          ? await auth.register(username, password)
          : await auth.login(username, password);
      if (result.stage === "mfa_required") {
        ticket = result.ticket ?? "";
        step = "mfa";
        await tick();
        document.getElementById("mfa-code")?.focus();
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

<svelte:head>
  <title>Unlock Raiker</title>
</svelte:head>

<div class="lock-screen" class:is-verifying={isVerifying}>
  <header class="brand" aria-label="Raiker">
    <img src="/favicon.svg" alt="" width="44" height="44" />
    <span>RAIKER</span>
  </header>

  <main class="lock-layout" aria-busy={isVerifying}>
    <section class="hero" aria-labelledby="raiker-state">
      <div class="core" aria-hidden="true">
        <img src="/favicon.svg" alt="" />
        <span class="core-eye">Γ_</span>
      </div>
      <h1 id="raiker-state">{heroMessage}</h1>
    </section>

    <section class="panel" aria-labelledby="unlock-title">
      {#if isVerifying}
        <div class="verify" role="status" aria-live="polite">
          <span class="spinner" aria-hidden="true"></span>
          Verifying runtime…
        </div>
      {/if}
      {#if runtimeState === "verification_failed"}
        <p class="error" role="alert">Runtime verification failed. The workspace remains locked.</p>
      {/if}

      {#if step === "credentials"}
        <h2 id="unlock-title">{isRegister ? "Create local account" : "Unlock Raiker"}</h2>
        <p class="intro">Your credentials and session remain on this local Raiker instance.</p>
        <form onsubmit={submitCredentials} aria-describedby="privacy-note">
          <label for="username">Username</label>
          <input id="username" bind:value={username} autocomplete="username" required disabled={formDisabled} />

          <label for="password">Password</label>
          <div class="password-row">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              bind:value={password}
              autocomplete={isRegister ? "new-password" : "current-password"}
              required
              disabled={formDisabled}
            />
            <button
              type="button"
              class="icon-button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              onclick={() => (showPassword = !showPassword)}
              disabled={formDisabled}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>

          {#if isRegister}
            <label for="confirm-password">Confirm password</label>
            <input
              id="confirm-password"
              type="password"
              bind:value={confirmPassword}
              autocomplete="new-password"
              required
              disabled={formDisabled}
            />
          {/if}

          {#if error}<p class="error" role="alert">{error}</p>{/if}
          <button type="submit" class="btn btn-primary submit" disabled={formDisabled}>
            {busy ? (isRegister ? "Creating…" : "Unlocking…") : isRegister ? "Create account" : "Unlock Raiker"}
          </button>
        </form>
        <button type="button" class="link" onclick={switchMode} disabled={formDisabled}>
          {isRegister ? "Return to unlock" : "Create local account"}
        </button>
        <p id="privacy-note" class="privacy">Local runtime · no remember-me or password reset is exposed before authentication.</p>
      {:else}
        <h2 id="unlock-title">Multi-factor verification</h2>
        <p class="intro">Enter the 6-digit code from your authenticator app.</p>
        <form onsubmit={submitMfa}>
          <label for="mfa-code">Authentication code</label>
          <input id="mfa-code" bind:value={mfaCode} inputmode="numeric" autocomplete="one-time-code" required disabled={formDisabled} />
          {#if error}<p class="error" role="alert">{error}</p>{/if}
          <button type="submit" class="btn btn-primary submit" disabled={formDisabled}>
            {busy ? "Verifying…" : "Verify"}
          </button>
        </form>
      {/if}
    </section>
  </main>
</div>

<style>
  .lock-screen {
    min-height: 100vh;
    background:
      radial-gradient(circle at 30% 22%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 30rem),
      linear-gradient(135deg, var(--surface), var(--bg));
    color: var(--text);
    padding: clamp(1rem, 3vw, 2rem);
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 0.9rem;
    font-weight: 800;
    letter-spacing: 0.45em;
  }
  .brand img { filter: drop-shadow(0 0.5rem 1rem rgb(0 0 0 / 0.16)); }
  .lock-layout {
    min-height: calc(100vh - 7rem);
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(22rem, 0.85fr);
    gap: clamp(2rem, 6vw, 5rem);
    align-items: center;
    max-width: 76rem;
    margin: 0 auto;
  }
  .hero { text-align: center; }
  .core { position: relative; width: min(28rem, 68vw); margin: 0 auto var(--space-5); }
  .core img { width: 100%; display: block; filter: drop-shadow(0 1.5rem 2rem rgb(9 18 34 / 0.22)); }
  .core-eye {
    position: absolute;
    inset: 48% auto auto 50%;
    transform: translate(-50%, -50%);
    color: white;
    font-family: var(--font-mono);
    font-size: clamp(2.5rem, 8vw, 5rem);
    font-weight: 800;
    letter-spacing: 0.08em;
    text-shadow: 0 0 1rem rgb(255 255 255 / 0.45);
    animation: eye-rest 12s steps(1, end) infinite;
  }
  .hero h1 { font-size: clamp(2rem, 5vw, 3.4rem); margin: 0; }
  .panel {
    position: relative;
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    border: 1px solid var(--border);
    border-radius: 1.75rem;
    padding: clamp(1.25rem, 4vw, 2.4rem);
    box-shadow: var(--shadow-lg);
    backdrop-filter: blur(18px);
  }
  .panel h2 { text-align: center; font-size: clamp(1.8rem, 4vw, 2.5rem); margin: 0 0 var(--space-2); }
  .intro, .privacy { color: var(--text-2); text-align: center; }
  form { display: flex; flex-direction: column; gap: var(--space-2); margin-top: var(--space-4); }
  label { font-weight: 750; }
  input { min-height: 3rem; padding: 0 var(--space-3); border-radius: 0.9rem; }
  .password-row { display: flex; gap: var(--space-2); }
  .password-row input { flex: 1; min-width: 0; }
  .icon-button, .submit, .link { min-height: 44px; }
  .icon-button { border: 1px solid var(--border); border-radius: 0.9rem; padding: 0 var(--space-3); background: var(--surface); color: var(--text); }
  .submit { margin-top: var(--space-2); width: 100%; }
  .link { width: 100%; margin-top: var(--space-3); background: transparent; border: 1px solid var(--border); border-radius: 0.9rem; color: var(--accent); cursor: pointer; }
  .privacy { margin: var(--space-3) 0 0; font-size: 0.9rem; }
  .error { color: var(--danger); margin: var(--space-2) 0 0; }
  .verify { display: flex; align-items: center; justify-content: center; gap: var(--space-2); margin-bottom: var(--space-3); color: var(--text-2); }
  .spinner { width: 1rem; height: 1rem; border-radius: 999px; border: 2px solid var(--border); border-top-color: var(--accent); animation: spin 900ms linear infinite; }
  @keyframes spin { to { transform: rotate(1turn); } }
  @keyframes eye-rest {
    0%, 54%, 100% { content: "Γ_"; }
    55%, 58% { content: "Γ Γ"; }
    59%, 62% { content: "⅂ ⅂"; }
    63%, 64% { content: "TT"; }
    65%, 66% { content: "_ _"; }
  }
  .core-eye::before { content: "Γ_"; animation: eye-glyph 12s steps(1, end) infinite; }
  .core-eye { font-size: 0; }
  .core-eye::before { font-size: clamp(2.5rem, 8vw, 5rem); }
  @keyframes eye-glyph {
    0%, 54%, 100% { content: "Γ_"; }
    55%, 58% { content: "Γ Γ"; }
    59%, 62% { content: "⅂ ⅂"; }
    63%, 64% { content: "TT"; }
    65%, 66% { content: "_ _"; }
  }
  @media (max-width: 820px) {
    .lock-layout { grid-template-columns: 1fr; gap: var(--space-5); min-height: auto; padding-top: var(--space-6); }
    .core { width: min(18rem, 70vw); }
  }
  @media (max-width: 520px) {
    .brand { letter-spacing: 0.28em; font-size: 0.9rem; }
    .password-row { flex-direction: column; }
  }
  @media (prefers-reduced-motion: reduce) {
    .core-eye::before, .spinner { animation: none; }
  }
</style>
