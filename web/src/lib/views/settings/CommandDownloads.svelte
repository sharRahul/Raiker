<script lang="ts">
  /**
   * Allow-listed downloads for sandboxed commands.
   *
   * Off by default: a sandboxed command has no network at all. On, each run
   * gets its own proxy and may reach only the hosts listed here, over HTTPS —
   * enough for pip, npm, cargo and Git to fetch packages and sources.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { CommandEgressView } from "../../apiTypes";

  let view = $state<CommandEgressView | null>(null);
  let text = $state("");
  let busy = $state(false);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  function hosts(): string[] {
    return text.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean);
  }

  async function load() {
    try {
      view = await api.commandEgress();
      text = view.domains.join("\n");
    } catch {
      view = null;
    }
  }

  async function save(enabled: boolean, domains: string[]) {
    busy = true;
    notice = null;
    try {
      view = await api.setCommandEgress(enabled, domains);
      text = view.domains.join("\n");
      notice = { kind: "ok", text: enabled ? "Downloads allowed for the listed hosts." : "Sandboxed commands have no network." };
    } catch (e) {
      const reason = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      notice = {
        kind: "error",
        text: reason === "egress_domain_invalid" ? "One of the hosts is not a valid domain name." : "The setting could not be saved.",
      };
    } finally {
      busy = false;
    }
  }

  onMount(() => void load());
</script>

{#if view}
  <section class="settings-card" aria-label="Command downloads">
    <div class="card-heading"><h3>Command downloads</h3></div>
    <p>
      Sandboxed commands have no network unless you allow it. When allowed, they can reach only
      these hosts over HTTPS, through a proxy that checks every connection.
    </p>
    <label class="toggle">
      <input
        type="checkbox"
        checked={view.enabled}
        disabled={busy}
        onchange={(event) => void save(event.currentTarget.checked, hosts())}
      />
      <span>Allow downloads from the hosts below</span>
    </label>
    <label>
      <span>Allowed hosts, one per line (<code>*.example.com</code> covers subdomains)</span>
      <textarea rows="6" bind:value={text} disabled={busy}></textarea>
    </label>
    <div class="actions">
      <button class="btn btn-primary btn-sm" type="button" disabled={busy} onclick={() => void save(view?.enabled ?? false, hosts())}>Save hosts</button>
      <button class="btn btn-ghost btn-sm" type="button" disabled={busy} onclick={() => (text = (view?.defaults ?? []).join("\n"))}>Restore package registries</button>
    </div>
    {#if notice}<p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>{/if}
  </section>
{/if}

<style>
  textarea { width: 100%; font-family: var(--font-mono); font-size: var(--text-xs); }
  .actions { display: flex; gap: var(--space-2); }
  .toggle { display: flex; align-items: center; gap: var(--space-2); }
</style>
