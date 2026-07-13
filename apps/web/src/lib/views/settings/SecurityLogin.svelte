<script lang="ts">
  import { api, auth, getToken, setToken, ApiError } from "../../api";

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
      notice = { kind: "error", text: message(e, "Could not save the vault key.") };
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
        placeholder="••••••••••••"
        bind:value={keyInput}
        autocomplete="off"
      />
    </label>
    <button type="button" class="link" onclick={() => (revealed = !revealed)}>
      {revealed ? "Hide" : "Reveal"}
    </button>
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
</style>
