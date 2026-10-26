<script lang="ts">
  /**
   * QUI-F07 / QUI-P04 — the accounts on one connection, each named by the owner.
   *
   * Every connection has its default account; the owner can name it ("Work
   * Gmail") and add another ("Personal Gmail"). Each account has its own
   * credential, pasted once and never shown again. A write names the account it
   * uses, and the approval card says which.
   */
  import Icon from "./Icon.svelte";
  import { ApiError } from "../api";
  import { contract } from "../generated/apiContract";
  import type { StoreConnector } from "../generated/apiContract";
  import { askConfirm } from "../confirm.svelte";

  let {
    connector,
    onchanged,
  }: {
    connector: StoreConnector;
    /** Read the connection again after a change. */
    onchanged: () => Promise<void> | void;
  } = $props();

  let busy = $state(false);
  let error = $state<string | null>(null);
  let renaming = $state<string | null>(null);
  let renameText = $state("");
  let connecting = $state<string | null>(null);
  let secret = $state("");
  let adding = $state(false);
  let newLabel = $state("");

  const ERRORS: Record<string, string> = {
    connector_account_label_taken: "Another account here already has that name.",
    connector_account_limit: "This connection already has as many accounts as Raiker keeps.",
    connector_account_unknown: "That account is no longer here.",
    connector_vault_key_unset: "Raiker's credential store is not set up on this computer yet.",
  };

  /**
   * A connection with one account and no credential asks for it at once: the
   * owner just added it to connect it. Further accounts ask on **Connect**.
   */
  function asking(account: StoreConnector["accounts"][number]): boolean {
    if (connecting !== null) return connecting === account.account_id;
    return account.is_default && account.auth_status === "not_connected" && connector.accounts.length === 1;
  }

  async function run(step: () => Promise<unknown>): Promise<boolean> {
    busy = true;
    error = null;
    try {
      await step();
      await onchanged();
      return true;
    } catch (e) {
      const code = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      error = ERRORS[code] ?? "That did not work. Nothing was changed.";
      return false;
    } finally {
      busy = false;
    }
  }

  async function rename(accountId: string) {
    const label = renameText.trim();
    if (!label) return;
    if (await run(() => contract.renameConnectorAccount(connector.connector_id, accountId, { label }))) renaming = null;
  }

  async function connect(accountId: string) {
    const values: Record<string, string> = connector.auth_type === "oauth2" ? { access_token: secret } : { api_key: secret };
    if (await run(() => contract.setConnectorAccountCredentials(connector.connector_id, accountId, { values }))) {
      secret = "";
      connecting = null;
    }
  }

  async function add() {
    const label = newLabel.trim();
    if (!label) return;
    if (await run(() => contract.addConnectorAccount(connector.connector_id, { label }))) {
      newLabel = "";
      adding = false;
    }
  }

  async function remove(accountId: string, label: string) {
    const sure = await askConfirm({
      title: `Remove ${label}?`,
      body: "Its credential is deleted. Raiker can no longer act as this account.",
      confirmLabel: "Remove account",
      danger: true,
    });
    if (sure) await run(() => contract.removeConnectorAccount(connector.connector_id, accountId));
  }
</script>

<section class="accounts" aria-labelledby={`accounts-${connector.connector_id}`}>
  <h3 id={`accounts-${connector.connector_id}`}>Accounts</h3>
  <ul>
    {#each connector.accounts as account (account.account_id)}
      <li>
        <div class="line">
          {#if renaming === account.account_id}
            <form class="inline" onsubmit={(event) => { event.preventDefault(); void rename(account.account_id); }}>
              <label class="sr-only" for={`rename-${account.account_id}`}>Name for this account</label>
              <input id={`rename-${account.account_id}`} class="input" bind:value={renameText} maxlength="60" />
              <button type="submit" class="btn btn-soft btn-sm" disabled={busy || !renameText.trim()}>Save</button>
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => (renaming = null)}>Cancel</button>
            </form>
          {:else}
            <span class="name">{account.label}</span>
            {#if account.is_default}<span class="pill">Default</span>{/if}
            <span class="status" data-status={account.auth_status}>
              {#if account.auth_status === "connected"}<Icon name="check" size="sm" /> Connected
              {:else if account.auth_status === "reauth_required"}<Icon name="warning" size="sm" /> Sign in again
              {:else}Not connected{/if}
            </span>
            <span class="actions">
              <button
                type="button"
                class="btn btn-ghost btn-sm"
                onclick={() => { renaming = account.account_id; renameText = account.label; }}
                aria-label={`Rename ${account.label}`}
              >Rename</button>
              {#if account.auth_status !== "connected" && !asking(account)}
                <button type="button" class="btn btn-soft btn-sm" onclick={() => { connecting = account.account_id; secret = ""; }}>Connect</button>
              {/if}
              {#if !account.is_default}
                <button
                  type="button"
                  class="btn btn-ghost btn-sm"
                  onclick={() => void remove(account.account_id, account.label)}
                  aria-label={`Remove ${account.label}`}
                >Remove</button>
              {/if}
            </span>
          {/if}
        </div>
        {#if asking(account)}
          <form class="credential" onsubmit={(event) => { event.preventDefault(); void connect(account.account_id); }}>
            <label class="field-label" for={`secret-${account.account_id}`}>
              {connector.auth_type === "oauth2" ? "OAuth access token" : "API key"} for {account.label}
            </label>
            <input id={`secret-${account.account_id}`} class="input" type="password" bind:value={secret} autocomplete="off" />
            <p class="hint">It is encrypted for this profile and never shown again.</p>
            <span class="row">
              <button type="submit" class="btn btn-primary btn-sm" disabled={busy || !secret}>Connect</button>
              {#if connecting !== null}
                <button type="button" class="btn btn-ghost btn-sm" onclick={() => (connecting = null)}>Cancel</button>
              {/if}
            </span>
          </form>
        {/if}
      </li>
    {/each}
  </ul>
  {#if adding}
    <form class="inline add" onsubmit={(event) => { event.preventDefault(); void add(); }}>
      <label class="sr-only" for={`new-account-${connector.connector_id}`}>Name for the new account</label>
      <input
        id={`new-account-${connector.connector_id}`}
        class="input"
        bind:value={newLabel}
        maxlength="60"
        placeholder={`Personal ${connector.display_name}`}
      />
      <button type="submit" class="btn btn-soft btn-sm" disabled={busy || !newLabel.trim()}>Add</button>
      <button type="button" class="btn btn-ghost btn-sm" onclick={() => (adding = false)}>Cancel</button>
    </form>
  {:else}
    <button type="button" class="btn btn-ghost btn-sm add-button" onclick={() => (adding = true)}>
      <Icon name="plus" size="sm" /> Add another account
    </button>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .accounts ul {
    list-style: none;
    margin: 0 0 var(--space-2);
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  .accounts li {
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--border);
  }
  .accounts li:last-child { border-bottom: 0; }
  .line {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
    min-height: 2.25rem;
  }
  .name { font-weight: 600; color: var(--text-1); }
  .pill {
    font-size: var(--text-xs);
    color: var(--text-2);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 0.05rem 0.5rem;
  }
  .status {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .status[data-status="connected"] { color: var(--ok); }
  .status[data-status="reauth_required"] { color: var(--warn); }
  .actions {
    margin-inline-start: auto;
    display: inline-flex;
    gap: var(--space-1);
  }
  .inline {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .inline .input { min-width: 14rem; }
  .credential {
    display: grid;
    gap: var(--space-1);
    margin-top: var(--space-2);
    max-width: 28rem;
  }
  .credential .row { display: inline-flex; gap: var(--space-1); }
  .hint { margin: 0; font-size: var(--text-xs); color: var(--text-3); }
  .add-button { display: inline-flex; align-items: center; gap: 0.3rem; }
  .error { color: var(--danger); font-size: var(--text-sm); margin: var(--space-2) 0 0; }
</style>
