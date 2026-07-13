<script lang="ts">
  import { api, auth, getToken, setToken, ApiError } from "../../api";

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
      await api.deleteAccount();
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

<h2>Account</h2>

{#if notice}
  <p class="notice notice-danger" role="alert">{notice.text}</p>
{/if}

<section class="card">
  <h3>Profile</h3>
  <p class="sub">Username: <strong>{status.username}</strong></p>
  <label>
    Display name
    <input
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
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    max-width: 22rem;
    margin-top: var(--space-2);
  }
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
