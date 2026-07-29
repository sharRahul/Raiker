<script lang="ts">
  import { auth, getToken, setToken, ApiError } from "../../api";

  let {
    settings,
    save,
    status,
  }: {
    settings: Record<string, unknown>;
    save: (p: Record<string, unknown>) => void;
    status: { username: string };
  } = $props();

  const displayName = $derived((settings["account.display_name"] as string) ?? "");

  let confirmingDelete = $state(false);
  let deletePassword = $state("");
  let busy = $state(false);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  async function deleteAccount() {
    busy = true;
    notice = null;
    const control = getToken();
    try {
      const { token: elevated } = await auth.elevate(deletePassword);
      setToken(elevated);
      await auth.deleteAccount();
      // Account gone — drop the session and return to the lock screen.
      setToken(null);
      window.location.reload();
    } catch (e) {
      setToken(control);
      notice = {
        kind: "error",
        text: e instanceof ApiError ? `Could not delete account (${e.status}).` : "Could not delete account.",
      };
    } finally {
      busy = false;
    }
  }
</script>

<header class="section-heading">
  <h2>Account</h2>
  <p>Manage how your identity appears and control this local account.</p>
</header>

{#if notice}
  <p class="notice notice-danger" role="alert">{notice.text}</p>
{/if}

<section class="settings-card">
  <div class="card-heading"><h3>Profile</h3><p>Your username is fixed; your display name can be changed at any time.</p></div>
  <p class="sub">Username: <strong>{status.username}</strong></p>
  <label>
    <span>Display name</span>
    <small>Shown in greetings and account surfaces. This does not change your sign-in username.</small>
    <input
      class="settings-input"
      aria-label="Display name"
      value={displayName}
      onchange={(e) => save({ "account.display_name": e.currentTarget.value })}
      placeholder="How you want to be shown"
    />
  </label>
</section>

<section class="card danger-zone">
  <h3>Delete account</h3>
  <p class="sub">
    Permanently removes this account, its sessions, settings, and stored connector credentials.
    This cannot be undone.
  </p>
  {#if !confirmingDelete}
    <button type="button" class="btn btn-danger" onclick={() => (confirmingDelete = true)}>
      Delete my account
    </button>
  {:else}
    <label>
      Confirm your password
      <input type="password" bind:value={deletePassword} autocomplete="current-password" />
    </label>
    <div class="actions">
      <button type="button" class="btn btn-danger" disabled={busy || !deletePassword} onclick={deleteAccount}>
        Permanently delete
      </button>
      <button type="button" class="btn btn-soft" onclick={() => (confirmingDelete = false)}>Cancel</button>
    </div>
  {/if}
</section>

<style>
  .section-heading { margin-bottom:var(--space-4); }
  .section-heading h2,.card-heading h3 { margin:0; }
  .section-heading p,.card-heading p { color:var(--text-2); margin:.3rem 0 0; }
  .settings-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg); padding:clamp(1.25rem, 3vw, 2rem); margin-bottom:var(--space-4); }
  label {
    display:grid;
    gap:.3rem;
    max-width:34rem;
    margin-top:var(--space-5);
    font-weight:650;
  }
  label small { color:var(--text-2); font-weight:400; }
  .settings-input { width:100%; min-height:44px; padding:0 .8rem; border:1px solid var(--border-strong); border-radius:var(--r-md); background:var(--surface); color:var(--text-1); font:inherit; box-sizing:border-box; }
  .settings-input:focus-visible { outline:3px solid var(--focus-ring); outline-offset:2px; }
  .actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }
  .danger-zone {
    border: 1px solid var(--danger);
  }
  .sub {
    color: var(--text-2);
  }
</style>
