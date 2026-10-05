<script lang="ts">
  import { onMount } from "svelte";
  import BackupsCard from "../../components/BackupsCard.svelte";
  import { auth, getToken, setToken, ApiError } from "../../api";
  import type { AccountDeletionPreview } from "../../generated/apiContract";

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
  let typedUsername = $state("");

  /*
   * DEC-10 step 8 — the confirmation said "sessions, settings and connector
   * credentials" whatever the account held, and nothing about what it would
   * not reach. It now shows the server's own count of what the delete removes
   * (the same selections the purge sweeps by), what it leaves where it is,
   * and asks for the username typed out: the password proves who is asking,
   * the name proves which irreversible thing they meant.
   */
  let preview = $state<AccountDeletionPreview | null>(null);
  let previewError = $state(false);
  const confirmName = $derived(preview?.username || status.username);
  const typedMatches = $derived(typedUsername === confirmName && confirmName !== "");
  const REMOVES: { key: keyof AccountDeletionPreview; one: string; many: string }[] = [
    { key: "conversations", one: "conversation", many: "conversations" },
    { key: "tasks", one: "task or routine", many: "tasks and routines" },
    { key: "projects", one: "project", many: "projects" },
    { key: "memories", one: "memory", many: "memories" },
    { key: "connector_credentials", one: "stored connector credential", many: "stored connector credentials" },
    { key: "mcp_servers", one: "MCP server", many: "MCP servers" },
  ];

  async function beginDelete() {
    confirmingDelete = true;
    typedUsername = "";
    previewError = false;
    try {
      preview = await auth.deletionPreview();
    } catch {
      preview = null;
      previewError = true;
    }
  }

  /*
   * DEC-01 step 5 — the internal account ID, where support can ask for it.
   * Every ordinary page names the owner by display name; this is the one place
   * the key behind it is shown, folded away and explained, so the ID that once
   * reached a model's answer as if it were a name is never mistaken for one.
   */
  let principalId = $state<string | null>(null);
  let copied = $state(false);
  onMount(() => {
    void auth.sessionState().then(
      (who) => (principalId = who.principal_id),
      () => (principalId = null),
    );
  });
  async function copyPrincipalId() {
    if (!principalId) return;
    try {
      await navigator.clipboard.writeText(principalId);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      copied = false;
    }
  }
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
      await auth.deleteAccount(typedUsername);
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

<section class="settings-card">
  <details class="support" data-testid="account-support-details">
    <summary>Support details</summary>
    <p class="sub">
      Raiker files and authorises your work under an internal account ID. It is not your name and
      no ordinary page shows it — share it only if someone helping you with a problem asks for it.
    </p>
    {#if principalId}
      <div class="id-row">
        <code data-testid="account-principal-id">{principalId}</code>
        <button type="button" class="btn btn-soft btn-sm" onclick={copyPrincipalId}>
          {copied ? "Copied" : "Copy ID"}
        </button>
      </div>
    {:else}
      <p class="sub">The account ID could not be read just now.</p>
    {/if}
  </details>
</section>

<BackupsCard />

<section class="card danger-zone">
  <h3>Delete account</h3>
  <p class="sub">
    Permanently removes this account and everything Raiker keeps for it. This cannot be undone.
  </p>
  {#if !confirmingDelete}
    <button type="button" class="btn btn-danger" onclick={beginDelete}>
      Delete my account
    </button>
  {:else}
    <div class="impact" data-testid="account-deletion-impact">
      {#if preview}
        <h4>This removes</h4>
        <ul>
          {#each REMOVES as row (row.key)}
            {@const count = Number(preview[row.key] ?? 0)}
            <li>{count} {count === 1 ? row.one : row.many}</li>
          {/each}
          <li>Your settings, sign-in, devices and permissions</li>
        </ul>
        <h4>This does not remove</h4>
        <ul>
          {#each preview.kept as line (line)}<li>{line}</li>{/each}
        </ul>
      {:else if previewError}
        <p class="sub" role="alert">
          Raiker could not count what this would remove. Everything this account holds will be
          deleted; reload to see the counts before you continue.
        </p>
      {:else}
        <p class="sub">Counting what this removes…</p>
      {/if}
    </div>
    <label>
      <span>Type your username, <strong>{confirmName}</strong>, to confirm</span>
      <input
        class="settings-input"
        bind:value={typedUsername}
        autocomplete="off"
        spellcheck="false"
        disabled={busy}
      />
    </label>
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
      <button type="button" class="btn btn-danger" disabled={busy || !deletePassword || !typedMatches} onclick={deleteAccount}>
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
  .support summary { cursor: pointer; font-weight: 650; }
  .support .sub { margin: .5rem 0 0; max-width: 40rem; }
  .id-row { align-items: center; display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
  .id-row code { background: var(--sunken); border: 1px solid var(--border); border-radius: var(--r-sm); font-size: var(--text-sm); overflow-wrap: anywhere; padding: .3rem .5rem; }
  .impact { margin-top: var(--space-3); }
  .impact h4 { font-size: var(--text-sm); margin: var(--space-3) 0 .25rem; }
  .impact ul { color: var(--text-2); font-size: var(--text-sm); margin: 0; padding-left: 1.2rem; }
</style>
