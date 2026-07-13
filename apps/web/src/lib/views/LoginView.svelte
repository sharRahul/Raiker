<script lang="ts">
  import { onMount, tick } from "svelte";
  import { auth, health, ApiError } from "../api";

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
  const heroMessage = $derived.by(() => {
    if (runtimeState === "verification_failed" || runtimeReachable === false) {
      return "I cannot reach my runtime.";
    }
    if (isRegister) return "Hello! I am Raiker. Nice to meet you.";
    if (runtimeReachable === true) return "I am ready when you are.";
    return "";
  });

  // ── Prompt-eye motion layer ────────────────────────────────────────────────
  // The resting identity is the exact brand mark Γ_ (same as favicon/icons).
  // Animated dual-eye expressions are a motion behaviour of the large lock
  // screen character only; the shell never changes, and reduced motion keeps
  // the eye at rest permanently.
  const REST_GLYPH = "Γ_";
  const BLINK_FRAMES = ["TT", "_ _", "Γ Γ", "_ _", "⅂ ⅂", "_ _"];
  const GLANCE_FRAMES: string[][] = [
    ["Γ Γ", "⅂ ⅂"], // side to side
    ["TT", "⟂ ⟂"], // up and down
  ];
  let eyeGlyph = $state(REST_GLYPH);

  onMount(() => {
    void probeRuntime();

    const reduceMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) return;

    let cancelled = false;
    let handle: ReturnType<typeof setTimeout> | undefined;
    const later = (fn: () => void, ms: number) => {
      handle = setTimeout(fn, ms);
    };
    // Long idle rests between short expressions keep the motion restrained.
    const restDelay = () => 9000 + Math.random() * 5000;
    const rest = () => {
      eyeGlyph = REST_GLYPH;
      later(play, restDelay());
    };
    const play = () => {
      if (cancelled) return;
      const blink = Math.random() < 0.7;
      const frames = blink
        ? BLINK_FRAMES
        : GLANCE_FRAMES[Math.floor(Math.random() * GLANCE_FRAMES.length)];
      const stepMs = blink ? 140 : 650;
      let i = 0;
      const stepFrame = () => {
        if (cancelled) return;
        if (i < frames.length) {
          eyeGlyph = frames[i];
          i += 1;
          later(stepFrame, stepMs);
        } else {
          rest();
        }
      };
      stepFrame();
    };
    later(play, restDelay());
    return () => {
      cancelled = true;
      if (handle !== undefined) clearTimeout(handle);
    };
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
  <header class="brand">
    <img src="/favicon.svg" alt="" width="40" height="40" />
    <span>RAIKER</span>
  </header>

  <main class="lock-layout" aria-busy={isVerifying}>
    <section class="hero">
      <!-- The Raiker governed core: the existing shell design, unchanged, with
           only the inner prompt-eye glyph as a separate (animatable) layer. -->
      <div class="core">
        <svg viewBox="0 0 512 512" role="img" aria-label="Raiker">
          <defs>
            <linearGradient id="lock-shell" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#26344d" />
              <stop offset="1" stop-color="#080e19" />
            </linearGradient>
            <radialGradient id="lock-core" cx="42%" cy="35%" r="75%">
              <stop offset="0" stop-color="#263247" />
              <stop offset="0.55" stop-color="#0d1420" />
              <stop offset="1" stop-color="#05080e" />
            </radialGradient>
            <filter id="lock-shadow" x="-20%" y="-20%" width="140%" height="150%">
              <feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#06101f" flood-opacity="0.28" />
            </filter>
          </defs>
          <g filter="url(#lock-shadow)">
            <path d="M107 199c24-72 83-126 157-143 35-8 70-6 103 4l-57 69c-17-3-35-2-52 2-38 9-69 35-86 69z" fill="url(#lock-shell)" />
            <path d="M379 92c48 34 81 86 90 145 5 33 2 65-8 95l-79-42c4-15 5-31 3-47-5-34-22-64-48-85z" fill="url(#lock-shell)" />
            <path d="M455 348c-27 55-76 98-135 116-31 9-63 11-93 5l35-83c15 1 30-1 44-5 34-10 63-33 81-62z" fill="url(#lock-shell)" />
            <path d="M207 463c-61-14-113-52-145-104-17-27-27-58-29-89l89 12c3 15 8 29 16 42 18 30 47 52 80 62z" fill="url(#lock-shell)" />
            <path d="M39 248c4-62 32-119 78-159 24-21 52-36 83-44l8 90c-14 5-27 13-38 23-26 23-42 55-44 90z" fill="url(#lock-shell)" />
            <circle cx="256" cy="256" r="139" fill="#f7f9fc" stroke="#162238" stroke-width="18" />
            <circle cx="256" cy="256" r="109" fill="url(#lock-core)" stroke="#c9d1dc" stroke-width="10" />
            <circle cx="256" cy="256" r="88" fill="none" stroke="#303c50" stroke-width="5" opacity="0.75" />
            <text class="eye" x="256" y="252" text-anchor="middle" dominant-baseline="central">{eyeGlyph}</text>
            <path d="M142 180c18-28 43-50 73-63" fill="none" stroke="#fff" stroke-opacity="0.42" stroke-width="7" stroke-linecap="round" />
          </g>
        </svg>
      </div>
      <p class="hero-message" aria-live="polite">{heroMessage}</p>
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
        <form onsubmit={submitCredentials} aria-describedby="privacy-note">
          <label for="username">Username</label>
          <input
            id="username"
            bind:value={username}
            autocomplete="username"
            required
            disabled={formDisabled}
          />

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
          <button type="submit" class="btn btn-primary submit" disabled={formDisabled} aria-busy={busy}>
            {busy ? (isRegister ? "Creating…" : "Unlocking…") : isRegister ? "Create account" : "Unlock Raiker"}
          </button>
        </form>
        <button type="button" class="link" onclick={switchMode} disabled={formDisabled}>
          {isRegister ? "Return to unlock" : "Create local account"}
        </button>
        <p id="privacy-note" class="privacy">
          Local runtime — your account, credentials, and session stay on this device.
        </p>
      {:else}
        <h1 id="unlock-title">Multi-factor verification</h1>
        <p class="intro">Enter the 6-digit code from your authenticator app.</p>
        <form onsubmit={submitMfa}>
          <label for="mfa-code">Authentication code</label>
          <input
            id="mfa-code"
            bind:value={mfaCode}
            inputmode="numeric"
            autocomplete="one-time-code"
            required
            disabled={formDisabled}
          />
          {#if error}<p class="error" role="alert">{error}</p>{/if}
          <button type="submit" class="btn btn-primary submit" disabled={formDisabled} aria-busy={busy}>
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
      radial-gradient(circle at 30% 22%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 30rem),
      linear-gradient(135deg, var(--surface), var(--bg));
    color: var(--text);
    padding: clamp(1rem, 3vw, 2rem);
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    font-weight: 800;
    letter-spacing: 0.45em;
  }
  .brand img {
    border-radius: 9px;
    filter: drop-shadow(0 0.35rem 0.75rem rgb(0 0 0 / 0.16));
  }
  .lock-layout {
    min-height: calc(100vh - 7rem);
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(22rem, 0.85fr);
    gap: clamp(2rem, 6vw, 5rem);
    align-items: center;
    max-width: 76rem;
    margin: 0 auto;
  }
  .hero {
    text-align: center;
  }
  .core {
    width: min(24rem, 62vw);
    margin: 0 auto var(--space-5);
  }
  .core svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .core .eye {
    font-family: var(--font-mono);
    font-size: 92px;
    font-weight: 700;
    fill: #fff;
  }
  .hero-message {
    font-size: clamp(1.6rem, 4vw, 2.6rem);
    font-weight: 700;
    margin: 0;
    min-height: 1.3em;
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
    font-size: clamp(1.7rem, 4vw, 2.2rem);
    margin: 0 0 var(--space-2);
  }
  .intro,
  .privacy {
    color: var(--text-2);
    text-align: center;
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
  input {
    min-height: 3rem;
    padding: 0 var(--space-3);
    border-radius: 0.75rem;
  }
  .password-row {
    display: flex;
    gap: var(--space-2);
  }
  .password-row input {
    flex: 1;
    min-width: 0;
  }
  .icon-button,
  .submit,
  .link {
    min-height: 44px;
  }
  .icon-button {
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    padding: 0 var(--space-3);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
  }
  .submit {
    margin-top: var(--space-2);
    width: 100%;
  }
  .link {
    width: 100%;
    margin-top: var(--space-3);
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    color: var(--accent);
    cursor: pointer;
  }
  .icon-button:focus-visible,
  .link:focus-visible,
  .verify:focus-visible,
  .error:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .privacy {
    margin: var(--space-3) 0 0;
    font-size: 0.9rem;
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
  @media (max-width: 820px) {
    .lock-layout {
      grid-template-columns: 1fr;
      gap: var(--space-5);
      min-height: auto;
      padding-top: var(--space-6);
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
    .password-row {
      flex-direction: column;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation: none;
    }
  }
</style>
