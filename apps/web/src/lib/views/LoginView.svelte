<script lang="ts">
  import { onMount, tick } from "svelte";
  import { auth, health, ApiError } from "../api";
  import Icon from "../components/Icon.svelte";
  import ThemeToggle from "../components/ThemeToggle.svelte";

  // The lock screen. Guards the whole dashboard: nothing mounts until a full
  // control session exists AND the runtime bootstrap verifies (App.svelte).
  // Password -> (optional) MFA -> authenticated -> runtime verification.
  type RuntimeState = "locked" | "verifying" | "verification_failed";

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

  // Privacy-safe pre-auth reachability: /api/health returns only {status: ok}.
  // null = probe not resolved yet — no state message is shown until real data
  // supports one.
  let runtimeReachable = $state<boolean | null>(null);

  const isRegister = $derived(mode === "register");
  const isVerifying = $derived(runtimeState === "verifying");
  const formDisabled = $derived(busy || isVerifying);

  // State-aware Raiker message. Every branch is backed by real data: the
  // health probe, the post-auth verification result, or the visible register
  // state (local-account creation is always supported by the backend). Task/
  // approval activity has no privacy-safe pre-auth source, so no "working" or
  // "attention" claims are made here.
  const hero = $derived.by(() => {
    if (runtimeState === "verification_failed" || runtimeReachable === false) {
      return {
        title: "I cannot reach my runtime.",
        sub: "Start the local Raiker server, then try again.",
      };
    }
    if (isRegister) return { title: "Hello! I am Raiker.", sub: "Nice to meet you." };
    if (runtimeReachable === true) {
      return { title: "I am ready when you are.", sub: "Unlock me to get started." };
    }
    return null;
  });

  onMount(() => {
    void probeRuntime();
  });

  async function probeRuntime() {
    try {
      await health();
      runtimeReachable = true;
    } catch {
      runtimeReachable = false;
    }
  }

  // Move focus with the state so keyboard/screen-reader users follow the flow.
  $effect(() => {
    if (runtimeState === "verifying") {
      void tick().then(() => document.getElementById("runtime-verify")?.focus());
    } else if (runtimeState === "verification_failed") {
      void tick().then(() => document.getElementById("runtime-failed")?.focus());
    }
  });

  function messageFor(e: unknown): string {
    if (e instanceof ApiError) {
      // Generic by design: never confirm whether the username exists.
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
    showPassword = false;
    await tick();
    document.getElementById("username")?.focus();
  }

  async function submitCredentials(event: Event) {
    event.preventDefault();
    error = null;
    // Client-side convenience only — the server remains authoritative.
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
        busy = false; // before focus: a disabled input cannot receive it
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

<div class="lock-screen">
  <header class="lock-header">
    <span class="brand">
      <span class="brand-mark" role="img" aria-label="Raiker"></span>
      <span>RAIKER</span>
    </span>
    <ThemeToggle />
  </header>

  <main class="lock-layout" aria-busy={isVerifying}>
    <section class="hero">
      <!-- The Raiker governed core: the production rendered icon. Light theme
           shows the floating orb framed by decorative orbit rings; dark theme
           shows the light-tiled icon (self-contained, so the rings are hidden).
           The Γ_ prompt eye is part of the render. -->
      <div class="core">
        <span class="orbit orbit-1" aria-hidden="true"></span>
        <span class="orbit orbit-2" aria-hidden="true"></span>
        <span class="orbit orbit-3" aria-hidden="true"></span>
        <span class="core-img" role="img" aria-label="Raiker"></span>
      </div>
      <div class="hero-message" aria-live="polite">
        {#if hero}
          <h2 class="hero-title">{hero.title}</h2>
          <span class="hero-divider" aria-hidden="true"></span>
          <p class="hero-sub">{hero.sub}</p>
        {/if}
      </div>
    </section>

    <section class="panel" aria-labelledby="unlock-title">
      {#if isVerifying}
        <div class="verify" role="status" id="runtime-verify" tabindex="-1">
          <span class="spinner" aria-hidden="true"></span>
          Verifying runtime…
        </div>
      {/if}
      {#if runtimeState === "verification_failed"}
        <p class="error" role="alert" id="runtime-failed" tabindex="-1">
          Runtime verification failed. The workspace remains locked.
        </p>
      {/if}

      {#if step === "credentials"}
        <h1 id="unlock-title">{isRegister ? "Create local account" : "Unlock Raiker"}</h1>
        <p class="intro">
          {isRegister
            ? "Set up a new local account on this device."
            : "Authenticate to restore interactive control and open the governed workspace."}
        </p>
        <form onsubmit={submitCredentials} aria-describedby="privacy-note">
          <label for="username">Username</label>
          <div class="field">
            <span class="field-icon" aria-hidden="true"><Icon name="user" size={17} /></span>
            <input
              id="username"
              bind:value={username}
              placeholder="Enter your username"
              autocomplete="username"
              required
              disabled={formDisabled}
            />
          </div>

          <label for="password">Password</label>
          <div class="field">
            <span class="field-icon" aria-hidden="true"><Icon name="lock" size={17} /></span>
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              bind:value={password}
              placeholder="Enter your password"
              autocomplete={isRegister ? "new-password" : "current-password"}
              required
              disabled={formDisabled}
            />
            <button
              type="button"
              class="eye-toggle"
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              onclick={() => (showPassword = !showPassword)}
              disabled={formDisabled}
            >
              <Icon name={showPassword ? "eye-off" : "eye"} size={18} />
            </button>
          </div>

          {#if isRegister}
            <label for="confirm-password">Confirm password</label>
            <div class="field">
              <span class="field-icon" aria-hidden="true"><Icon name="lock" size={17} /></span>
              <input
                id="confirm-password"
                type="password"
                bind:value={confirmPassword}
                placeholder="Re-enter your password"
                autocomplete="new-password"
                required
                disabled={formDisabled}
              />
            </div>
          {/if}

          {#if error}<p class="error" role="alert">{error}</p>{/if}
          <button type="submit" class="btn btn-primary submit" disabled={formDisabled} aria-busy={busy}>
            {busy ? (isRegister ? "Creating…" : "Unlocking…") : isRegister ? "Create account" : "Unlock Raiker"}
          </button>
        </form>

        <div class="divider" aria-hidden="true"><span>or</span></div>

        <button type="button" class="secondary" onclick={switchMode} disabled={formDisabled}>
          <Icon name={isRegister ? "user" : "user-plus"} size={18} />
          {isRegister ? "Return to unlock" : "Create local account"}
        </button>

        <div id="privacy-note" class="privacy">
          <span class="privacy-icon" aria-hidden="true"><Icon name="info" size={17} /></span>
          <div>
            <strong>Local runtime</strong>
            <p>Your credentials and session remain on this Raiker instance.</p>
          </div>
        </div>
      {:else}
        <h1 id="unlock-title">Multi-factor verification</h1>
        <p class="intro">Enter the 6-digit code from your authenticator app.</p>
        <form onsubmit={submitMfa}>
          <label for="mfa-code">Authentication code</label>
          <div class="field">
            <span class="field-icon" aria-hidden="true"><Icon name="lock" size={17} /></span>
            <input
              id="mfa-code"
              bind:value={mfaCode}
              inputmode="numeric"
              autocomplete="one-time-code"
              required
              disabled={formDisabled}
            />
          </div>
          {#if error}<p class="error" role="alert">{error}</p>{/if}
          <button type="submit" class="btn btn-primary submit" disabled={formDisabled} aria-busy={busy}>
            {busy ? "Verifying…" : "Verify"}
          </button>
        </form>
      {/if}
    </section>
  </main>

  <!-- Status bar: only items backed by real, privacy-safe pre-auth data. The
       health probe is the sole such source; checkpoint/schedule facts are not
       exposed before authentication, so they are deliberately absent. -->
  <footer class="status-bar">
    <div class="status-item">
      <span
        class="status-dot"
        class:ok={runtimeReachable === true}
        class:bad={runtimeReachable === false}
        aria-hidden="true"
      ></span>
      <div class="status-text">
        <span class="status-label">System status</span>
        <span class="status-value">
          {runtimeReachable === true
            ? "Runtime operational"
            : runtimeReachable === false
              ? "Runtime unreachable"
              : "Checking…"}
        </span>
      </div>
    </div>
  </footer>
</div>

<style>
  .lock-screen {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background:
      radial-gradient(circle at 30% 22%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 30rem),
      linear-gradient(135deg, var(--surface), var(--bg));
    color: var(--text);
    padding: clamp(1rem, 3vw, 2rem);
  }
  .lock-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 0.85rem;
    font-weight: 800;
    letter-spacing: 0.45em;
  }
  .brand-mark {
    width: 44px;
    height: 44px;
    background: center / contain no-repeat url("/raiker-mark.png?v=20260714");
  }
  :global(:root[data-theme="dark"]) .brand-mark {
    background-image: url("/raiker-mark-dark.png?v=20260714");
  }
  :global(:root[data-theme="light"]) .brand-mark {
    background-image: url("/raiker-mark.png?v=20260714");
  }
  @media (prefers-color-scheme: dark) {
    :global(:root:not([data-theme])) .brand-mark {
      background-image: url("/raiker-mark-dark.png?v=20260714");
    }
  }
  .lock-layout {
    flex: 1;
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(22rem, 0.85fr);
    gap: clamp(2rem, 6vw, 5rem);
    align-items: center;
    max-width: 76rem;
    width: 100%;
    margin: 0 auto;
    padding: var(--space-4) 0;
  }
  .hero {
    text-align: center;
  }
  .core {
    position: relative;
    width: min(26rem, 66vw);
    aspect-ratio: 1;
    margin: 0 auto var(--space-5);
    display: grid;
    place-items: center;
  }
  .core-img {
    position: relative;
    z-index: 1;
    width: 86%;
    aspect-ratio: 1;
    display: block;
    background: center / contain no-repeat url("/raiker-hero.png?v=20260714");
    filter: drop-shadow(0 1.4rem 2rem rgb(6 14 26 / 0.28));
  }
  /* Dark theme: the chrome/silver render, which pops on a dark surface. */
  :global(:root[data-theme="dark"]) .core-img {
    background-image: url("/raiker-hero-dark.png?v=20260714");
    filter: drop-shadow(0 1.4rem 2.4rem rgb(0 0 0 / 0.5));
  }
  :global(:root[data-theme="light"]) .core-img {
    background-image: url("/raiker-hero.png?v=20260714");
  }
  @media (prefers-color-scheme: dark) {
    :global(:root:not([data-theme])) .core-img {
      background-image: url("/raiker-hero-dark.png?v=20260714");
      filter: drop-shadow(0 1.4rem 2.4rem rgb(0 0 0 / 0.5));
    }
  }
  /* Decorative concentric orbit rings behind the core (mockup styling). */
  .orbit {
    position: absolute;
    border-radius: 50%;
    border: 1px solid color-mix(in srgb, var(--accent) 32%, transparent);
    opacity: 0.5;
  }
  .orbit-1 {
    width: 100%;
    height: 100%;
  }
  .orbit-2 {
    width: 78%;
    height: 78%;
    border-style: dashed;
    opacity: 0.35;
  }
  .orbit-3 {
    width: 122%;
    height: 122%;
    opacity: 0.28;
  }
  .hero-message {
    min-height: 5.5rem;
  }
  .hero-title {
    font-size: clamp(1.7rem, 4vw, 2.6rem);
    font-weight: 800;
    margin: 0;
  }
  .hero-divider {
    display: block;
    width: 3.5rem;
    height: 3px;
    border-radius: 999px;
    background: var(--accent);
    margin: var(--space-3) auto;
  }
  .hero-sub {
    color: var(--text-2);
    font-size: clamp(1.05rem, 2vw, 1.3rem);
    margin: 0;
  }
  .panel {
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    border: 1px solid var(--border);
    border-radius: 1.5rem;
    padding: clamp(1.25rem, 4vw, 2.4rem);
    box-shadow: var(--shadow-2);
    backdrop-filter: blur(18px);
  }
  .panel h1 {
    text-align: center;
    font-size: clamp(1.7rem, 4vw, 2.1rem);
    margin: 0 0 var(--space-3);
    position: relative;
    padding-bottom: var(--space-3);
  }
  .panel h1::after {
    content: "";
    position: absolute;
    left: 50%;
    bottom: 0;
    transform: translateX(-50%);
    width: 3rem;
    height: 3px;
    border-radius: 999px;
    background: var(--accent);
  }
  .intro {
    color: var(--text-2);
    text-align: center;
    margin: 0;
  }
  form {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }
  label {
    font-weight: 600;
  }
  .field {
    position: relative;
    display: flex;
    align-items: center;
  }
  .field-icon {
    position: absolute;
    left: 0.9rem;
    display: inline-flex;
    color: var(--text-2);
    pointer-events: none;
  }
  .field input {
    flex: 1;
    min-width: 0;
    min-height: 3rem;
    padding: 0 var(--space-3) 0 2.6rem;
    border-radius: 0.75rem;
  }
  .field input#password {
    padding-right: 3rem;
  }
  .eye-toggle {
    position: absolute;
    right: 0.35rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    min-height: 44px;
    border: none;
    border-radius: 0.6rem;
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
  }
  .eye-toggle:hover {
    color: var(--text);
  }
  .submit {
    margin-top: var(--space-3);
    width: 100%;
    min-height: 48px;
    font-weight: 700;
  }
  .divider {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    color: var(--text-2);
    font-size: 0.85rem;
    margin: var(--space-3) 0;
  }
  .divider::before,
  .divider::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--border);
  }
  .secondary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    width: 100%;
    min-height: 48px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    color: var(--text);
    font-weight: 600;
    cursor: pointer;
  }
  .secondary:hover {
    border-color: var(--accent-border);
  }
  .eye-toggle:focus-visible,
  .secondary:focus-visible,
  .verify:focus-visible,
  .error:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .privacy {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-4);
    padding: var(--space-3);
    border-radius: 0.9rem;
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
    font-size: 0.9rem;
  }
  .privacy-icon {
    display: inline-flex;
    color: var(--accent);
    margin-top: 0.1rem;
  }
  .privacy strong {
    color: var(--accent-strong);
  }
  .privacy p {
    margin: 0.15rem 0 0;
    color: var(--text-2);
  }
  .error {
    color: var(--danger);
    margin: var(--space-2) 0 0;
  }
  .verify {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
    color: var(--text-2);
  }
  .spinner {
    width: 1rem;
    height: 1rem;
    border-radius: 999px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    animation: spin 900ms linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(1turn);
    }
  }
  .status-bar {
    background: #0d1420;
    color: #e7ecf3;
    border-radius: 1rem;
    padding: var(--space-3) var(--space-5);
    max-width: 76rem;
    width: 100%;
    margin: var(--space-4) auto 0;
  }
  .status-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  .status-dot {
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 999px;
    background: #8a94a6;
  }
  .status-dot.ok {
    background: #34d399;
  }
  .status-dot.bad {
    background: #f87171;
  }
  .status-text {
    display: flex;
    flex-direction: column;
  }
  .status-label {
    font-size: 0.72rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #97a1b3;
  }
  .status-value {
    font-size: 0.95rem;
  }
  @media (max-width: 820px) {
    .lock-layout {
      grid-template-columns: 1fr;
      gap: var(--space-5);
      padding-top: var(--space-5);
    }
    .core {
      width: min(16rem, 64vw);
    }
  }
  @media (max-width: 520px) {
    .brand {
      letter-spacing: 0.28em;
      font-size: 0.9rem;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation: none;
    }
  }
</style>
