<script lang="ts">
  import { api, auth, getToken, health as runtimeHealth, setToken, ApiError } from "../../api";
  import type { HealthView } from "../../api";
  import type {
    CapabilityContainmentView,
    ContainedSubject,
    CredentialLifecycle,
    McpFinding,
    SecurityHealth,
    StandingGrant,
  } from "../../apiTypes";

  // Security & Login settings section: Vault Key configuration (masked + reveal +
  // status pill + elevated re-auth to save) and MFA enrollment. Exercises the
  // governed backend directly; no fabricated state.
  import FormDialog from "../../components/FormDialog.svelte";
  import {
    APPROVAL_TIMEOUT_CHOICES,
    APPROVAL_TIMEOUT_KEY,
    approvalTimeoutMinutes,
  } from "../../approvalTimeout";

  /*
   * QUI-L09 / QUI-L03 — Security as rows: a label, the current value and one
   * action. The forms behind the actions open in a dialog, one at a time, so
   * the page is a short list rather than five forms open at once.
   */
  type Panel =
    | "password"
    | "mfa"
    | "devices"
    | "encryption"
    | "vault"
    | "scan"
    | "monitored"
    | "grants";
  let panel = $state<Panel | null>(null);
  function openPanel(next: Panel) {
    notice = null;
    panel = next;
  }

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
  // The one-time recovery codes enrollment issues. The server keeps only their
  // hashes, so this is the one moment they can be read; recovering a password
  // from the lock screen without the authenticator needs one of them.
  let backupCodes = $state<string[]>([]);
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
  let storageHealth = $state<HealthView | null>(null);
  // BUG-77 — the same three facts for every capability family: what is
  // contained, why, and the one control that clears it.
  let containment = $state<CapabilityContainmentView | null>(null);
  let containmentBusy = $state("");

  async function loadContainment() {
    try { containment = await api.capabilityContainment(); }
    catch { containment = null; }
  }

  async function containSubject(
    subject: ContainedSubject,
    action: "pause" | "kill" | "resume",
  ) {
    containmentBusy = `${subject.capability}:${subject.subject_id}`;
    try {
      await api.setCapabilityContainment(subject.capability, subject.subject_id, action);
      await loadContainment();
    } catch {
      notice = { kind: "error", text: "That containment change was refused. Reload and try again." };
    } finally {
      containmentBusy = "";
    }
  }
  let breachPassword = $state("");
  let breachOptIn = $state(false);

  // QUI-P06 — how long an unanswered approval waits. The server reads the same
  // key whenever it raises an approval, so this row shows what is in force.
  let approvalTimeout = $state<number | null>(null);
  let timeoutBusy = $state(false);
  async function saveApprovalTimeout(minutes: number) {
    const previous = approvalTimeout;
    timeoutBusy = true;
    notice = null;
    approvalTimeout = minutes;
    try {
      const current = await api.settings();
      await api.putSettings(
        { ...current.settings, [APPROVAL_TIMEOUT_KEY]: minutes },
        current.revision,
        { [APPROVAL_TIMEOUT_KEY]: current.settings[APPROVAL_TIMEOUT_KEY] },
      );
    } catch {
      approvalTimeout = previous;
      notice = { kind: "error", text: "The approval time limit was not saved. Nothing changed." };
    } finally {
      timeoutBusy = false;
    }
  }

  // Scoped standing approval grants (ZT-5): user-owned, expiry-bound, revocable.
  let grants = $state<StandingGrant[]>([]);
  let grantActionType = $state("");
  let grantRiskCeiling = $state("medium");
  let grantScope = $state("*");

  async function loadGrants() {
    try {
      grants = (await api.standingGrants()).grants;
    } catch {
      grants = [];
    }
  }

  async function createGrant() {
    notice = null;
    try {
      await api.createStandingGrant({
        action_type: grantActionType.trim(),
        risk_ceiling: grantRiskCeiling,
        scope_pattern: grantScope.trim() || "*",
      });
      grantActionType = "";
      grantScope = "*";
      notice = { kind: "ok", text: "Standing grant created." };
      await loadGrants();
    } catch (e) {
      notice = { kind: "error", text: message(e, "Could not create the grant.") };
    }
  }

  async function revokeGrant(grantId: string) {
    try {
      await api.revokeStandingGrant(grantId);
      await loadGrants();
    } catch (e) {
      notice = { kind: "error", text: message(e, "Could not revoke the grant.") };
    }
  }

  async function load() {
    try {
      const s = await api.settings();
      vaultState = s.status.vault;
      mfaEnrolled = s.status.mfa_enrolled;
      requireMfaForVault = Boolean(
        (s.settings as Record<string, unknown>)["security.require_mfa_for_vault"],
      );
      approvalTimeout = approvalTimeoutMinutes(s.settings as Record<string, unknown>);
    } catch {
      notice = { kind: "error", text: "Could not load security settings." };
    }
    await loadSessions();
    await loadGrants();
    try {
      void loadContainment();
      [credentials, findings, health] = await Promise.all([
        api.securityCredentials(), api.securityFindings(), api.securityHealth(),
      ]);
    } catch {
      // Security posture stays unavailable rather than fabricating a healthy state.
    }
    try { storageHealth = await runtimeHealth(); }
    catch { storageHealth = null; }
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
      const { provisioning_uri, backup_codes } = await auth.enrollMfa();
      enrollUri = provisioning_uri;
      backupCodes = [...backup_codes];
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

<!--
  REM-SET-SECURITY — four sections, because these are four lifecycles.

  "How do I sign in" and "what may run without asking me" do not change
  together and are not read together, so each lifecycle has its own heading.
  The emergency pause is not here: it is the STOP switch in the context bar,
  on every screen rather than behind a settings tab.
-->
<!--
  REM-SET-SECURITY — four groups, because these are four lifecycles. QUI-L09 —
  each setting is one row; its form opens in a dialog.
-->
{#if notice && panel === null}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

<section class="card" aria-labelledby="security-signin-h">
  <h2 id="security-signin-h">Signing in and devices</h2>
  <div class="setting-row">
    <h3>Password</h3>
    <span class="setting-value">Set</span>
    <button type="button" class="btn btn-sm" onclick={() => openPanel("password")}>Change</button>
  </div>
  <div class="setting-row">
    <h3>Two-step sign-in</h3>
    <span class="setting-value">{mfaEnrolled ? "On" : "Off"}</span>
    <button type="button" class="btn btn-sm" onclick={() => openPanel("mfa")}>{mfaEnrolled ? "Manage" : "Turn on"}</button>
  </div>
  <div class="setting-row">
    <h3>Devices</h3>
    <span class="setting-value">{sessions.length} signed in</span>
    <button type="button" class="btn btn-sm" onclick={() => openPanel("devices")}>Manage</button>
  </div>
</section>

<section class="card" aria-labelledby="security-vault-h">
  <h2 id="security-vault-h">Encryption and the vault</h2>
  <div class="setting-row" data-testid="storage-posture">
    <h3>Encryption</h3>
    <span class="setting-value">{storageHealth === null ? "Unknown" : storageHealth.store === "ok" ? "On" : "Unavailable"}</span>
    <button type="button" class="btn btn-sm" onclick={() => openPanel("encryption")}>Details</button>
  </div>
  <div class="setting-row">
    <h3>Vault key</h3>
    <span class="setting-value">{vaultState === "configured_valid" ? "Set" : "Missing — connections fail closed"}</span>
    <button type="button" class="btn btn-sm" onclick={() => openPanel("vault")}>{vaultState === "configured_valid" ? "Change" : "Set up"}</button>
  </div>
</section>

<section class="card" aria-labelledby="security-findings-h">
  <h2 id="security-findings-h">Findings and monitoring</h2>
  <div class="setting-row">
    <h3>Security scan</h3>
    <span class="setting-value">{findings.length === 0 ? "No findings" : `${findings.length} ${findings.length === 1 ? "finding" : "findings"}`}</span>
    <button type="button" class="btn btn-sm" onclick={() => openPanel("scan")}>Review</button>
  </div>
  <div class="setting-row" data-testid="capability-containment">
    <h3>Monitored capabilities</h3>
    <span class="setting-value">{containment === null ? "Unknown" : containment.subjects.filter((subject) => subject.state !== "active").length === 0 ? "Nothing contained" : `${containment.subjects.filter((subject) => subject.state !== "active").length} contained`}</span>
    <button type="button" class="btn btn-sm" onclick={() => openPanel("monitored")}>Manage</button>
  </div>
</section>

<section class="card" aria-labelledby="security-standing-h">
  <h2 id="security-standing-h">Approvals and standing access</h2>
  <div class="setting-row" data-testid="approval-time-limit">
    <h3 id="approval-time-limit-h">Unanswered approvals expire after</h3>
    <span class="setting-value">Nothing runs without a decision.</span>
    <select
      class="select"
      aria-labelledby="approval-time-limit-h"
      value={approvalTimeout ?? undefined}
      disabled={approvalTimeout === null || timeoutBusy}
      onchange={(event) => void saveApprovalTimeout(Number(event.currentTarget.value))}
    >
      {#each APPROVAL_TIMEOUT_CHOICES as choice (choice.minutes)}
        <option value={choice.minutes}>{choice.label}</option>
      {/each}
    </select>
  </div>
  <div class="setting-row">
    <h3>Standing approval grants</h3>
    <span class="setting-value">{grants.filter((grant) => !grant.revoked).length === 0 ? "None" : `${grants.filter((grant) => !grant.revoked).length} active`}</span>
    <button type="button" class="btn btn-sm" onclick={() => openPanel("grants")}>Manage</button>
  </div>
</section>

{#if panel === "password"}
  <FormDialog title="Change password" onclose={() => (panel = null)}>
      {#if notice}
        <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
      {/if}
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
  </FormDialog>
{:else if panel === "mfa"}
  <FormDialog title="Two-step sign-in" onclose={() => (panel = null)}>
      {#if notice}
        <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
      {/if}
    <p class="sub">An authenticator code (TOTP) in addition to your password.</p>
    {#if !mfaEnrolled}
      {#if enrollUri === null}
        <button type="button" class="btn btn-soft" onclick={startEnroll}>Enroll in MFA</button>
      {:else}
        <p class="sub">Add this to your authenticator app, then enter the current code:</p>
        <code class="uri">{enrollUri}</code>
        {#if backupCodes.length > 0}
          <p class="sub">
            Save these recovery codes somewhere other than this computer. Each works once,
            in place of an authenticator code — including to recover your password from
            the lock screen — and they are not shown again.
          </p>
          <ul class="backup-codes" aria-label="Recovery codes">
            {#each backupCodes as code (code)}<li><code>{code}</code></li>{/each}
          </ul>
        {/if}
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
  </FormDialog>
{:else if panel === "devices"}
  <FormDialog title="Signed-in devices" onclose={() => (panel = null)}>
      {#if notice}
        <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
      {/if}
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
  </FormDialog>
{:else if panel === "encryption"}
  <FormDialog title="Encryption" onclose={() => (panel = null)}>
    {#if storageHealth === null}
      <p class="sub">Storage posture is unavailable right now.</p>
    {:else}
      <div class="posture-grid">
        <div>
          <span class="posture-label">Database</span>
          <strong>{storageHealth.store === "ok" ? "Encrypted" : "Unavailable"}</strong>
        </div>
        <div>
          <span class="posture-label">Key memory</span>
          <strong>
            {storageHealth.cipher_memory_security === "on"
              ? "Locked in memory"
              : storageHealth.memory_security_mode === "off"
                ? "Disabled by user"
                : "Degraded on this host"}
          </strong>
        </div>
      </div>
      <p class="sub posture-detail">
        The workspace remains encrypted at rest. Memory locking is enabled only after an isolated
        host check succeeds.{storageHealth.sqlcipher_version
          ? ` SQLCipher ${storageHealth.sqlcipher_version}.`
          : ""}
      </p>
    {/if}
  </FormDialog>
{:else if panel === "vault"}
  <FormDialog title="Vault key" onclose={() => (panel = null)}>
      {#if notice}
        <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
      {/if}
    <p class="sub">Encrypts the credentials of the services you connect. Without it, linking an account fails closed.</p>
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
      A 44-character key that ends with <code>=</code>. A passphrase will not work; Generate key
      makes one.
    </p>
    <details class="technical">
      <summary>Technical details</summary>
      <p class="sub">
        It is a <strong>Fernet key</strong>: 32 random bytes, URL-safe base64. To make one yourself, run
        <code class="cmd">python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</code>
      </p>
    </details>
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
  </FormDialog>
{:else if panel === "scan"}
  <FormDialog title="Security scan" onclose={() => (panel = null)}>
      {#if notice}
        <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
      {/if}
    {#if credentials.length}
      <ul>{#each credentials as credential}<li>{credential.provider} — {credential.status} <button class="link" onclick={() => verifyCredential(credential.provider)}>Verify replacement</button></li>{/each}</ul>
    {:else}<p class="sub">No verified connector credentials yet.</p>{/if}
    {#if findings.length}<ul>{#each findings as finding}<li>{finding.severity}: {finding.summary}</li>{/each}</ul>{/if}
    {#if health.length}<p class="sub">Latest health state: {health[0].state}</p>{/if}
    <div class="actions"><button class="btn btn-soft" onclick={scanSecurity}>Run local scan</button><button class="btn btn-soft" onclick={checkHealth}>Check health</button></div>
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
  </FormDialog>
{:else if panel === "monitored"}
  <FormDialog title="Monitored capabilities" onclose={() => (panel = null)}>
      {#if notice}
        <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
      {/if}
    {#if containment === null}
      <p class="sub">Containment state is unavailable right now.</p>
    {:else if containment.subjects.length === 0}
      <p class="sub">
        Nothing is contained, and nothing has failed often enough to be watched yet. Subjects
        appear here the first time one is called.
      </p>
    {:else}
      <ul class="containment">
        {#each containment.subjects as subject (subject.capability + subject.subject_id)}
          <li class:contained={subject.state !== "active"}>
            <div class="containment-copy">
              <strong>{subject.label}</strong>
              <span class="sub">{subject.capability_label} · {subject.state}</span>
              {#if subject.reason}<span class="sub">{subject.reason}</span>{/if}
              {#if subject.failure_streak > 0}
                <span class="sub">
                  {subject.failure_streak} consecutive {subject.failure_streak === 1 ? "failure" : "failures"}{
                    subject.last_failure_code ? ` (${subject.last_failure_code})` : ""
                  }
                </span>
              {/if}
            </div>
            <div class="actions">
              {#if subject.state === "active"}
                <button
                  class="btn btn-soft"
                  disabled={containmentBusy === subject.capability + ":" + subject.subject_id}
                  onclick={() => containSubject(subject, "pause")}
                >Pause</button>
                <button
                  class="btn btn-soft"
                  disabled={containmentBusy === subject.capability + ":" + subject.subject_id}
                  onclick={() => containSubject(subject, "kill")}
                >Stop</button>
              {:else}
                <button
                  class="btn btn-soft"
                  disabled={containmentBusy === subject.capability + ":" + subject.subject_id}
                  onclick={() => containSubject(subject, "resume")}
                >Resume</button>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {/if}
    <div class="actions"><button class="btn btn-soft" onclick={loadContainment}>Refresh</button></div>
  </FormDialog>
{:else if panel === "grants"}
  <FormDialog title="Standing approval grants" onclose={() => (panel = null)}>
      {#if notice}
        <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
      {/if}
    <p class="sub">What may run without asking you each time, and how to take it back.</p>
    <div class="grant-form">
      <input
        placeholder="Action type (e.g. write_file)"
        bind:value={grantActionType}
        aria-label="Grant action type"
      />
      <input placeholder="Scope pattern (e.g. coding, *)" bind:value={grantScope} aria-label="Grant scope pattern" />
      <select bind:value={grantRiskCeiling} aria-label="Grant risk ceiling">
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
      <button type="button" class="btn btn-primary btn-sm" disabled={!grantActionType.trim()} onclick={createGrant}>
        Create grant
      </button>
    </div>
    {#if grants.length === 0}
      <p class="sub">No standing grants.</p>
    {:else}
      <ul class="grants">
        {#each grants as g (g.grant_id)}
          <li>
            <span class="grant-desc">
              <strong>{g.action_type}</strong>
              <span class="pill">≤ {g.risk_ceiling}</span>
              <span class="grant-scope">scope: {g.scope_pattern}</span>
              {#if g.revoked}
                <span class="pill pill-danger">Revoked</span>
              {:else}
                <span class="sub">expires {g.expires_at.slice(0, 10)} · used {g.use_count}×</span>
              {/if}
            </span>
            {#if !g.revoked}
              <button type="button" class="btn btn-danger btn-sm" onclick={() => revokeGrant(g.grant_id)}>
                Revoke
              </button>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </FormDialog>
{/if}

<style>
  /* QUI-L03 — a setting is a row: label, current value, one action. */
  .setting-row {
    display: grid;
    grid-template-columns: minmax(10rem, 1fr) minmax(0, 1.4fr) auto;
    align-items: center;
    gap: var(--space-3);
    min-height: 52px;
    border-top: 1px solid var(--border);
  }
  .setting-row:first-of-type {
    border-top: none;
  }
  .setting-row h3 {
    margin: 0;
    font-size: var(--text-sm);
  }
  .setting-value {
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .technical summary {
    cursor: pointer;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  /* REM-SET-SECURITY — four cards where there was one, so they need the gap
     between them that a single card never did. */
  section.card + section.card { margin-top: var(--space-4); }

  .posture-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
    margin-top: var(--space-2);
  }
  .posture-grid > div {
    display: grid;
    gap: 0.25rem;
    padding: var(--space-3);
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .posture-label {
    color: var(--text-2);
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .posture-detail { margin-bottom: 0; }
  @media (max-width: 560px) {
    .posture-grid { grid-template-columns: 1fr; }
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
  .grant-form {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: var(--space-2) 0 var(--space-3);
    align-items: center;
  }
  ul.grants {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  ul.grants li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .grant-desc {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .grant-scope {
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .pill {
    padding: 2px 10px;
    border-radius: 999px;
    font-size: var(--text-sm);
    background: var(--sunken);
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
    background: var(--sunken);
    border-radius: var(--r-md);
    margin: var(--space-2) 0;
  }
  .backup-codes {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
    gap: var(--space-1) var(--space-3);
    margin: var(--space-2) 0;
    padding: var(--space-2) var(--space-3);
    list-style: none;
    background: var(--sunken);
    border-radius: var(--r-md);
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
    font-size: var(--text-sm);
    margin: var(--space-2) 0 0;
    max-width: 34rem;
  }
  .hint code {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm);
    background: var(--sunken);
    padding: 0.05rem 0.3rem;
    border-radius: 4px;
  }
  .technical code.cmd {
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
  ul.containment {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  ul.containment li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  ul.containment li.contained {
    border-color: var(--warn-border);
    background: var(--warn-soft);
  }
  .containment-copy {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }
</style>
