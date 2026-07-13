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

  // ── Prompt-eye motion layer ────────────────────────────────────────────────
  // The resting identity is the exact brand mark Γ_ (drawn with the same
  // strokes as the favicon/app icons). Animated dual-eye expressions are a
  // motion behaviour of the large lock-screen character only; the shell never
  // changes, and reduced motion keeps the eye at rest permanently.
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
  <header class="lock-header">
    <span class="brand">
      <img src="/favicon.svg" alt="" width="44" height="44" />
      <span>RAIKER</span>
    </span>
    <ThemeToggle />
  </header>

  <main class="lock-layout" aria-busy={isVerifying}>
    <section class="hero">
      <!-- The Raiker governed core: same artwork as the production icon, with
           only the inner prompt-eye glyph as a separate (animatable) layer. -->
      <div class="core">
        <svg viewBox="0 0 512 512" role="img" aria-label="Raiker">
          <defs>
            <radialGradient id="hero-orb" cx="38%" cy="30%" r="85%">
              <stop offset="0" stop-color="#39465e" />
              <stop offset="0.45" stop-color="#131b2b" />
              <stop offset="1" stop-color="#04060c" />
            </radialGradient>
            <linearGradient id="hero-silver" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#ffffff" />
              <stop offset="0.5" stop-color="#dbe3ec" />
              <stop offset="1" stop-color="#96a3b5" />
            </linearGradient>
            <linearGradient id="hero-darkseg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#333f54" />
              <stop offset="1" stop-color="#070b13" />
            </linearGradient>
            <linearGradient id="hero-ringmetal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#d6dde6" />
              <stop offset="1" stop-color="#8492a6" />
            </linearGradient>
            <filter id="hero-blur6" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="6" /></filter>
            <filter id="hero-blur10" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="10" /></filter>
            <filter id="hero-shadow" x="-25%" y="-25%" width="150%" height="160%">
              <feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="#0a1524" flood-opacity="0.35" />
            </filter>
          </defs>
          <g filter="url(#hero-shadow)">
            <path d="M107 199c24-72 83-126 157-143 35-8 70-6 103 4l-57 69c-17-3-35-2-52 2-38 9-69 35-86 69z" fill="url(#hero-darkseg)" stroke="#05080f" stroke-width="3" />
            <path d="M379 92c48 34 81 86 90 145 5 33 2 65-8 95l-79-42c4-15 5-31 3-47-5-34-22-64-48-85z" fill="url(#hero-silver)" stroke="#0c1526" stroke-width="3" />
            <path d="M455 348c-27 55-76 98-135 116-31 9-63 11-93 5l35-83c15 1 30-1 44-5 34-10 63-33 81-62z" fill="url(#hero-darkseg)" stroke="#05080f" stroke-width="3" />
            <path d="M207 463c-61-14-113-52-145-104-17-27-27-58-29-89l89 12c3 15 8 29 16 42 18 30 47 52 80 62z" fill="url(#hero-silver)" stroke="#0c1526" stroke-width="3" />
            <path d="M39 248c4-62 32-119 78-159 24-21 52-36 83-44l8 90c-14 5-27 13-38 23-26 23-42 55-44 90z" fill="url(#hero-darkseg)" stroke="#05080f" stroke-width="3" />
            <circle cx="256" cy="256" r="139" fill="url(#hero-ringmetal)" stroke="#0a1322" stroke-width="10" />
            <circle cx="256" cy="256" r="126" fill="none" stroke="#3d9bff" stroke-width="9" opacity="0.9" filter="url(#hero-blur6)" />
            <path d="M150 310a120 120 0 0 0 90 62" fill="none" stroke="#7cc2ff" stroke-width="10" stroke-linecap="round" opacity="0.9" filter="url(#hero-blur6)" />
            <circle cx="256" cy="256" r="118" fill="url(#hero-orb)" stroke="#0a111d" stroke-width="6" />
            <circle cx="256" cy="256" r="114" fill="none" stroke="#6ab5ff" stroke-width="3.5" opacity="0.55" />
            <ellipse cx="212" cy="178" rx="86" ry="52" fill="#ffffff" opacity="0.17" filter="url(#hero-blur10)" />
            {#if eyeGlyph === REST_GLYPH}
              <g data-eye="Γ_" transform="translate(256, 256) scale(0.84) translate(-256, -256)" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <g stroke="#8fc6ff" stroke-width="34" opacity="0.6" filter="url(#hero-blur6)">
                  <path d="M250 220H195v65" />
                  <path d="M285 307h40" />
                </g>
                <g stroke="#ffffff">
                  <path d="M250 220H195v65" stroke-width="31" />
                  <path d="M285 307h40" stroke-width="25" />
                </g>
              </g>
            {:else}
              <g data-eye={eyeGlyph}>
                <text class="eye eye-glow" x="256" y="252" text-anchor="middle" dominant-baseline="central">{eyeGlyph}</text>
                <text class="eye" x="256" y="252" text-anchor="middle" dominant-baseline="central">{eyeGlyph}</text>
              </g>
            {/if}
          </g>
        </svg>
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
  .core .eye-glow {
    fill: #8fc6ff;
    opacity: 0.6;
    filter: url(#hero-blur6);
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
