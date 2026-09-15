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

  /*
   * NEW-ACCOUNT-01 — a control labelled Cancel must not look like it cancelled
   * something irreversible.
   *
   * The confirmation's Cancel only ever hid the form. While a deletion was
   * running it stayed live, so pressing it took the owner back to a page that
   * looked untouched while the account was being destroyed behind it — the one
   * moment in the product where a wrong impression cannot be undone. It is also
   * why the deletion needs a guard of its own: the Permanently delete button was
   * disabled while busy, and a disabled button is a presentation, not a lock.
   *
   * So during the request there is no Cancel. There is a statement of what is
   * happening, and the form stays on screen, because the owner watching an
   * irreversible operation finish is the honest version of this moment.
   */
  /*
   * REM-SET-ACCOUNT — and the half of it that was still open: a lost response.
   *
   * A request that never came back is not a request that failed. The delete had
   * one error path for both, so an owner whose connection dropped after the
   * server had already destroyed the account was told "Could not delete
   * account" and left looking at a Retry for something that had happened. On an
   * irreversible operation that is the worst possible thing to be wrong about.
   *
   * So a refusal the server actually sent is reported as one, and anything else
   * is *asked about* before it is described: `bootstrap-status` answers
   * `can_register: true` only when no account exists, which is the server's own
   * statement that the deletion landed. If the probe cannot reach the host
   * either, the honest answer is that it is unknown — never a retry, because a
   * second delete of an account that is already gone is not the harmless thing
   * a Retry button implies.
   */
  async function deleteAccount() {
    if (busy) return;
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
      // A password the server rejected, or a request it refused: definite, and
      // the account is still here. Restore the session and say so.
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) {
        setToken(control);
        notice = { kind: "error", text: `Could not delete account (${e.status}).` };
        return;
      }
      setToken(null);
      try {
        const { can_register } = await auth.bootstrapStatus();
        if (can_register) {
          // It landed. Nothing here is the owner's account any more.
          window.location.reload();
          return;
        }
        setToken(control);
        notice = { kind: "error", text: "Could not delete account. It is still here." };
      } catch {
        setToken(control);
        notice = {
          kind: "error",
          text:
            "Raiker could not be reached, so whether the account was deleted is " +
            "unknown. Reload this page to find out before trying again.",
        };
      }
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
      <input
        type="password"
        bind:value={deletePassword}
        autocomplete="current-password"
        disabled={busy}
      />
    </label>
    <div class="actions">
      <button type="button" class="btn btn-danger" disabled={busy || !deletePassword} onclick={deleteAccount}>
        {busy ? "Deleting account…" : "Permanently delete"}
      </button>
      {#if !busy}
        <button type="button" class="btn btn-soft" onclick={() => (confirmingDelete = false)}>Cancel</button>
      {/if}
    </div>
    {#if busy}
      <p class="sub deleting" role="status">
        Deleting your account. This cannot be cancelled or undone — Raiker will return to the sign-in
        screen when it is finished.
      </p>
    {/if}
  {/if}
</section>

<style>
  .section-heading { margin-bottom:var(--space-4); }
  .section-heading h2,.card-heading h3 { margin:0; }
  .section-heading p,.card-heading p { color:var(--text-2); margin:.3rem 0 0; }
  .settings-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg); padding:var(--card-pad-y) var(--card-pad-x); margin-bottom:var(--space-4); }
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
  .deleting { margin: var(--space-2) 0 0; }
</style>
