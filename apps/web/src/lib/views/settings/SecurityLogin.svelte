<script lang="ts">
  import { api, auth, getToken, setToken, ApiError } from "../../api";
  import type { CredentialLifecycle, McpFinding, SecurityHealth } from "../../apiTypes";

  // Security & Login settings section: Vault Key configuration (masked + reveal +
  // status pill + elevated re-auth to save) and MFA enrollment. Exercises the
  // governed backend directly; no fabricated state.
  let vaultState = $state<string>("missing");
  let mfaEnrolled = $state(false);
  let requireMfaForVault = $state(false);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  // Vault key editor
  let keyInput = $state("");
  let revealed = $state(false);

  // A Fernet key is 32 random bytes, URL-safe base64 encoded (44 chars ending in
  // "="). Generating one client-side (Web Crypto) mirrors
  // `Fernet.generate_key()` so a user without the CLI can produce a valid key
  // instead of guessing the format (FIX-07). The key never leaves the browser
  // until the user chooses to save it through the governed, elevated flow below.
  function generateVaultKey() {
    const bytes = new Uint8Array(32);
    crypto.getRandomValues(bytes);
    let binary = "";
    for (const b of bytes) binary += String.fromCharCode(b);
    keyInput = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_");
    revealed = true;
    notice = { kind: "ok", text: "Generated a valid Fernet key. Review it, then confirm your password and Save key." };
  }
  let elevatePassword = $state("");
  let mfaForVault = $state("");
  let busy = $state(false);

  // MFA enrollment
  let enrollUri = $state<string | null>(null);
  let activateCode = $state("");

  // Password reset
  let oldPassword = $state("");
  let newPassword = $state("");

  // Active device sessions
  let sessions = $state<
    Array<{ session_id: string; created_at: string; last_seen_at: string | null; current: boolean; revoked: boolean }>
  >([]);
  let credentials = $state<CredentialLifecycle[]>([]);
  let findings = $state<McpFinding[]>([]);
  let health = $state<SecurityHealth[]>([]);
  let breachPassword = $state("");
  let breachOptIn = $state(false);

  async function load() {
    try {
      const s = await api.settings();
      vaultState = s.status.vault;
      mfaEnrolled = s.status.mfa_enrolled;
      requireMfaForVault = Boolean(
        (s.settings as Record<string, unknown>)["security.require_mfa_for_vault"],
      );
    } catch {
      notice = { kind: "error", text: "Could not load security settings." };
    }
    await loadSessions();
    try {
      [credentials, findings, health] = await Promise.all([
        api.securityCredentials(), api.securityFindings(), api.securityHealth(),
      ]);
    } catch {
      // Security posture stays unavailable rather than fabricating a healthy state.
    }
  }

  async function scanSecurity() {
    try { findings = await api.scanSecurity(); }
    catch (e) { notice = { kind: "error", text: message(e, "Could not run the local security scan.") }; }
  }

  async function checkHealth() {
    try { health = await api.checkSecurityHealth(); findings = await api.securityFindings(); }
    catch (e) { notice = { kind: "error", text: message(e, "Could not run the health check.") }; }
  }

  async function verifyCredential(provider: string) {
    try {
      const updated = await api.verifySecurityCredential(provider);
      credentials = credentials.map((row) => row.provider === provider ? updated : row);
    } catch (e) { notice = { kind: "error", text: message(e, "Replacement is not verified.") }; }
  }

  async function checkBreach() {
    try {
      findings = await api.checkPasswordBreach(breachPassword, breachOptIn);
      breachPassword = "";
    } catch (e) { notice = { kind: "error", text: message(e, "Could not check the breach corpus.") }; }
  }

  async function loadSessions() {
    try {
      sessions = (await auth.listDeviceSessions()).filter((s) => !s.revoked);
    } catch {
      sessions = [];
    }
  }

  async function changePassword() {
    notice = null;
    try {
      await auth.changePassword(oldPassword, newPassword);
      oldPassword = "";
      newPassword = "";
      notice = { kind: "ok", text: "Password changed. Other sessions were signed out." };
      await loadSessions();
    } catch (e) {
      notice = { kind: "error", text: message(e, "Could not change password.") };
    }
  }

  async function revokeSession(id: string) {
    try {
      await auth.revokeDeviceSession(id);
      await loadSessions();
    } catch (e) {
      notice = { kind: "error", text: message(e, "Could not revoke the session.") };
    }
  }

  function message(e: unknown, fallback: string): string {
    if (e instanceof ApiError && e.reasonCode) return `${fallback} (${e.reasonCode})`;
    return fallback;
  }

  async function saveVaultKey() {
    notice = null;
    busy = true;
    const control = getToken();
    try {
      const { token: elevated } = await auth.elevate(elevatePassword);
      setToken(elevated);
      const result = await api.setVaultKey(keyInput, mfaForVault || undefined);
      vaultState = result.state;
      keyInput = "";
      elevatePassword = "";
      mfaForVault = "";
      notice = { kind: "ok", text: "Vault key saved." };
    } catch (e) {
      const invalid = e instanceof ApiError && e.reasonCode === "connector_vault_key_invalid";
      notice = {
        kind: "error",
        text: invalid
          ? "That is not a valid Fernet key. Use “Generate key” or a 44-character URL-safe base64 key — a plain passphrase will not work."
          : message(e, "Could not save the vault key."),
      };
    } finally {
      setToken(control);
      busy = false;
    }
  }

  async function clearVaultKey() {
    notice = null;
    busy = true;
    const control = getToken();
    try {
      const { token: elevated } = await auth.elevate(elevatePassword);
      setToken(elevated);
      const result = await api.clearVaultKey();
      vaultState = result.state;
      elevatePassword = "";
      notice = { kind: "ok", text: "Vault key cleared. Connectors now fail closed." };
    } catch (e) {
      notice = { kind: "error", text: message(e, "Could not clear the vault key.") };
    } finally {
      setToken(control);
      busy = false;
    }
  }

  async function startEnroll() {
    notice = null;
    try {
      const { provisioning_uri } = await auth.enrollMfa();
      enrollUri = provisioning_uri;
    } catch (e) {
      notice = { kind: "error", text: message(e, "Could not start MFA enrollment.") };
    }
  }

  async function activate() {
    notice = null;
    try {
      await auth.activateMfa(activateCode);
      mfaEnrolled = true;
      enrollUri = null;
      activateCode = "";
      notice = { kind: "ok", text: "MFA is now active." };
    } catch (e) {
      notice = { kind: "error", text: message(e, "Invalid verification code.") };
    }
  }

  async function toggleRequireMfa() {
    const next = !requireMfaForVault;
    try {
      const current = await api.settings();
      await api.putSettings({
        ...current.settings,
        "security.require_mfa_for_vault": next,
      });
      requireMfaForVault = next;
    } catch (e) {
      notice = { kind: "error", text: message(e, "Could not update the policy.") };
    }
  }

  load();
</script>

<section class="card" aria-labelledby="security-h">
  <h2 id="security-h">Security &amp; Login</h2>

  {#if notice}
    <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">
      {notice.text}
    </p>
  {/if}

  <!-- Vault Key -->
  <div class="field">
    <div class="field-head">
      <h3>Connector Vault Key</h3>
      <span
        class="pill"
        class:pill-ok={vaultState === "configured_valid"}
        class:pill-danger={vaultState !== "configured_valid"}
      >
        {vaultState === "configured_valid" ? "Active / Valid" : "Missing / Fail-Closed Active"}
      </span>
    </div>
    <p class="sub">
      Encrypts your stored connector credentials (API keys, OAuth tokens). If missing or invalid,
      all connectors fail closed. Changing it requires re-entering your password.
    </p>
    <label>
      Vault key
      <input
        type={revealed ? "text" : "password"}
        placeholder="44-character Fernet key (URL-safe base64)"
        bind:value={keyInput}
        autocomplete="off"
        spellcheck="false"
        aria-describedby="vault-key-format"
      />
    </label>
    <p id="vault-key-format" class="sub hint">
      Must be a <strong>Fernet key</strong>: 32 random bytes, URL-safe base64 (44 characters, ends with
      <code>=</code>). A passphrase will not work. Generate one below, or run:
      <code class="cmd">python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</code>
    </p>
    <div class="key-tools">
      <button type="button" class="btn btn-soft btn-sm" onclick={generateVaultKey}>Generate key</button>
      <button type="button" class="link" onclick={() => (revealed = !revealed)}>
        {revealed ? "Hide" : "Reveal"}
      </button>
    </div>
    <label>
      Confirm password (elevated re-auth)
      <input type="password" bind:value={elevatePassword} autocomplete="current-password" />
    </label>
    {#if requireMfaForVault && mfaEnrolled}
      <label>
        Authentication code
        <input bind:value={mfaForVault} inputmode="numeric" autocomplete="one-time-code" />
      </label>
    {/if}
    <div class="actions">
      <button type="button" class="btn btn-primary" disabled={busy || !keyInput || !elevatePassword} onclick={saveVaultKey}>
        Save key
      </button>
      <button type="button" class="btn btn-danger" disabled={busy || !elevatePassword} onclick={clearVaultKey}>
        Clear key
      </button>
    </div>
  </div>

  <!-- MFA -->
  <div class="field">
    <div class="field-head">
      <h3>Multi-factor authentication (TOTP)</h3>
      <span class="pill" class:pill-ok={mfaEnrolled}>{mfaEnrolled ? "Enrolled" : "Not enrolled"}</span>
    </div>
    {#if !mfaEnrolled}
      {#if enrollUri === null}
        <button type="button" class="btn btn-soft" onclick={startEnroll}>Enroll in MFA</button>
      {:else}
        <p class="sub">Add this to your authenticator app, then enter the current code:</p>
        <code class="uri">{enrollUri}</code>
        <label>
          Verification code
          <input bind:value={activateCode} inputmode="numeric" autocomplete="one-time-code" />
        </label>
        <button type="button" class="btn btn-primary" disabled={!activateCode} onclick={activate}>
          Activate
        </button>
      {/if}
    {/if}
    <label class="toggle">
      <input type="checkbox" checked={requireMfaForVault} onchange={toggleRequireMfa} disabled={!mfaEnrolled} />
      Require MFA for Vault operations
      {#if !mfaEnrolled}<span class="sub">(enroll in MFA to enable)</span>{/if}
    </label>
  </div>

  <div class="field">
    <div class="field-head"><h3>Credential security</h3></div>
    <p class="sub">Lifecycle status and findings are redacted. Local scans use only configured workspace paths.</p>
    {#if credentials.length}
      <ul>{#each credentials as credential}<li>{credential.provider} — {credential.status} <button class="link" onclick={() => verifyCredential(credential.provider)}>Verify replacement</button></li>{/each}</ul>
    {:else}<p class="sub">No verified connector credentials yet.</p>{/if}
    {#if findings.length}<ul>{#each findings as finding}<li>{finding.severity}: {finding.summary}</li>{/each}</ul>{/if}
    {#if health.length}<p class="sub">Latest health state: {health[0].state}</p>{/if}
    <div class="actions"><button class="btn btn-soft" onclick={scanSecurity}>Run local scan</button><button class="btn btn-soft" onclick={checkHealth}>Check runtime health</button></div>
    <label>
      Password to check
      <input type="password" bind:value={breachPassword} autocomplete="off" />
    </label>
    <label class="toggle">
      <input type="checkbox" bind:checked={breachOptIn} />
      I opt in to a breach check; only the first five SHA-1 characters leave this device.
    </label>
    <button type="button" class="btn btn-soft" disabled={!breachPassword || !breachOptIn} onclick={checkBreach}>
      Check breach corpus
    </button>
  </div>

  <!-- Password reset -->
  <div class="field">
    <div class="field-head"><h3>Password</h3></div>
    <label>
      Current password
      <input type="password" bind:value={oldPassword} autocomplete="current-password" />
    </label>
    <label>
      New password
      <input type="password" bind:value={newPassword} autocomplete="new-password" />
    </label>
    <div class="actions">
      <button type="button" class="btn btn-primary" disabled={!oldPassword || !newPassword} onclick={changePassword}>
        Change password
      </button>
    </div>
    <p class="sub">Changing your password signs out all your other devices.</p>
  </div>

  <!-- Active device sessions -->
  <div class="field">
    <div class="field-head"><h3>Active device sessions</h3></div>
    {#if sessions.length === 0}
      <p class="sub">No active sessions.</p>
    {:else}
      <ul class="sessions">
        {#each sessions as s (s.session_id)}
          <li>
            <span>
              {s.session_id.slice(0, 16)}…
              {#if s.current}<span class="pill pill-ok">This device</span>{/if}
            </span>
            {#if !s.current}
              <button type="button" class="btn btn-danger" onclick={() => revokeSession(s.session_id)}>
                Revoke
              </button>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</section>

<style>
  .field {
    padding: var(--space-3) 0;
    border-top: 1px solid var(--border);
  }
  .field:first-of-type {
    border-top: none;
  }
  .field-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin-top: var(--space-2);
    max-width: 26rem;
  }
  input[type="text"],
  input[type="password"],
  label input:not([type="checkbox"]) {
    padding: var(--space-2) var(--space-3);
  }
  .actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }
  .pill {
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.8rem;
    background: var(--bg-2);
    color: var(--text-2);
  }
  .pill-ok {
    background: color-mix(in oklab, green 20%, transparent);
    color: var(--text-1);
  }
  .pill-danger {
    background: color-mix(in oklab, red 30%, transparent);
    color: var(--text-1);
    font-weight: 600;
  }
  .uri {
    display: block;
    word-break: break-all;
    padding: var(--space-2);
    background: var(--bg-2);
    border-radius: var(--radius-2);
    margin: var(--space-2) 0;
  }
  .link {
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    padding: 0;
  }
  .toggle {
    flex-direction: row;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-3);
    max-width: none;
  }
  .sub {
    color: var(--text-2);
  }
  .hint {
    font-size: 0.82rem;
    margin: var(--space-2) 0 0;
    max-width: 34rem;
  }
  .hint code {
    font-family: var(--font-mono, monospace);
    font-size: 0.78rem;
    background: var(--bg-2);
    padding: 0.05rem 0.3rem;
    border-radius: 4px;
  }
  .hint code.cmd {
    display: block;
    margin-top: var(--space-2);
    padding: var(--space-2);
    word-break: break-all;
    white-space: pre-wrap;
  }
  .key-tools {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-2);
  }
</style>
