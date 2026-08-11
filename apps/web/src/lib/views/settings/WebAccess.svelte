<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import PageState from "../../components/PageState.svelte";

  type StoredRule = {
    rule_id: string;
    rule: string;
    kind: string;
    note: string;
    created_at: string;
  };
  type Blocklist = {
    stored: StoredRule[];
    environment: string[];
    environment_variable: string;
    builtin: string[];
    effective_count: number;
    address_guard: { enforced: boolean; editable: boolean; description: string };
  };

  let data = $state<Blocklist | null>(null);
  let loadError = $state<string | null>(null);
  let draft = $state("");
  let note = $state("");
  let addError = $state<string | null>(null);
  let busy = $state(false);

  let probe = $state("");
  let probeResult = $state<{ host: string; allowed: boolean; reason: string; addresses: string[] } | null>(null);
  let probing = $state(false);

  const KIND_LABEL: Record<string, string> = {
    domain: "Domain (and its subdomains)",
    wildcard: "Wildcard",
    regex: "Regular expression",
    address: "IP address",
    network: "IP range",
  };

  // The parser refuses a rule it cannot compile, and says which shape failed.
  // Turning that into a sentence here means the owner fixes it in place rather
  // than reading a reason code.
  const RULE_ERROR: Record<string, string> = {
    blocklist_rule_empty: "Enter a domain, IP address, range, or /pattern/.",
    blocklist_rule_too_long: "That is too long to be a hostname.",
    blocklist_regex_too_long: "That regular expression is too long.",
    blocklist_domain_invalid: "That is not a valid domain name.",
    blocklist_wildcard_invalid: "A wildcard looks like *.ads.example.com.",
    blocklist_network_invalid: "That is not a valid IP range — try 10.0.0.0/8.",
  };

  function ruleError(detail: string): string {
    const key = detail.split(":")[0];
    if (key === "blocklist_regex_invalid") {
      return `That regular expression will not compile: ${detail.split(":").slice(1).join(":")}`;
    }
    return RULE_ERROR[key] ?? "That rule could not be understood.";
  }

  async function load(): Promise<void> {
    try {
      loadError = null;
      data = await api.webBlocklist();
    } catch (error) {
      loadError = error instanceof ApiError ? error.message : String(error);
    }
  }

  async function add(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!draft.trim() || busy) return;
    busy = true;
    addError = null;
    try {
      await api.addWebBlocklistRule(draft.trim(), note.trim());
      draft = "";
      note = "";
      await load();
    } catch (error) {
      addError = error instanceof ApiError ? ruleError(error.reasonCode ?? "") : String(error);
    } finally {
      busy = false;
    }
  }

  async function remove(ruleId: string): Promise<void> {
    busy = true;
    try {
      await api.deleteWebBlocklistRule(ruleId);
      await load();
    } finally {
      busy = false;
    }
  }

  async function test(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!probe.trim() || probing) return;
    probing = true;
    try {
      probeResult = await api.testWebBlocklist(probe.trim());
    } catch (error) {
      probeResult = null;
      loadError = error instanceof ApiError ? error.message : String(error);
    } finally {
      probing = false;
    }
  }

  onMount(load);
</script>

<section class="web-access">
  <header class="section-heading">
    <h2>Web access</h2>
    <p>
      Raiker can read public web pages. This is where you say which destinations it
      may not reach.
    </p>
  </header>

  {#if loadError}
    <PageState state="error" title="Couldn't load web access settings" detail={loadError} />
  {:else if !data}
    <PageState state="loading" title="Loading web access settings…" />
  {:else}
    <!-- Stated before the editable list, because it is the part that is *not*
         editable and the part that actually stops a fetch reaching your own
         network. An owner who empties the list below should know what remains. -->
    <div class="guard card" role="note">
      <strong>Private networks are always refused</strong>
      <p>{data.address_guard.description}</p>
    </div>

    <div class="card">
      <h3>Blocked destinations</h3>
      <p class="lead">
        A domain also covers its subdomains. You can also use a wildcard
        (<code>*.ads.example.com</code>), an IP address, an IP range
        (<code>10.0.0.0/8</code>), or a regular expression
        (<code>/^tracker[0-9]+\./</code>).
      </p>

      <form class="add-row" onsubmit={add}>
        <label class="field-label" for="blocklist-rule">Destination to block</label>
        <input
          id="blocklist-rule"
          class="input"
          bind:value={draft}
          placeholder="example.com, *.ads.example.com, 10.0.0.0/8, /pattern/"
          aria-describedby={addError ? "blocklist-rule-error" : undefined}
          aria-invalid={addError ? "true" : undefined}
        />
        <input class="input note" bind:value={note} placeholder="Note (optional)" aria-label="Note" />
        <button class="btn btn-primary" type="submit" disabled={busy || !draft.trim()}>Block</button>
      </form>
      {#if addError}
        <p class="error" id="blocklist-rule-error" role="alert">{addError}</p>
      {/if}

      {#if data.stored.length === 0}
        <p class="empty">
          Nothing blocked yet. Raiker can reach any public destination that is not on
          this list.
        </p>
      {:else}
        <ul class="rules">
          {#each data.stored as rule (rule.rule_id)}
            <li>
              <div>
                <code>{rule.rule}</code>
                <span class="kind">{KIND_LABEL[rule.kind] ?? rule.kind}</span>
                {#if rule.note}<span class="note-text">{rule.note}</span>{/if}
              </div>
              <button
                class="btn btn-ghost btn-sm"
                type="button"
                onclick={() => remove(rule.rule_id)}
                disabled={busy}
                aria-label={`Unblock ${rule.rule}`}>Unblock</button
              >
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="card">
      <h3>Check a destination</h3>
      <p class="lead">
        Answers whether Raiker would be allowed to reach a host, without contacting it.
      </p>
      <form class="add-row" onsubmit={test}>
        <label class="field-label" for="blocklist-probe">Hostname or address</label>
        <input id="blocklist-probe" class="input" bind:value={probe} placeholder="docs.python.org" />
        <button class="btn" type="submit" disabled={probing || !probe.trim()}>Check</button>
      </form>
      {#if probeResult}
        <p class="probe" class:blocked={!probeResult.allowed} role="status">
          <strong>{probeResult.host}</strong>
          {probeResult.allowed ? "is reachable" : "is refused"}
          {#if !probeResult.allowed}<span class="reason">({probeResult.reason})</span>{/if}
          {#if probeResult.addresses.length}
            <span class="addresses">→ {probeResult.addresses.join(", ")}</span>
          {/if}
        </p>
      {/if}
    </div>

    {#if data.environment.length || data.builtin.length}
      <div class="card">
        <h3>Set outside this app</h3>
        <p class="lead">
          These apply as well and cannot be removed here — they are part of how this
          Raiker was started.
        </p>
        {#if data.environment.length}
          <p class="source"><code>{data.environment_variable}</code></p>
          <ul class="fixed">
            {#each data.environment as rule (rule)}<li><code>{rule}</code></li>{/each}
          </ul>
        {/if}
        <p class="source">Built in</p>
        <ul class="fixed">
          {#each data.builtin as rule (rule)}<li><code>{rule}</code></li>{/each}
        </ul>
      </div>
    {/if}
  {/if}
</section>

<style>
  .section-heading h2 { margin: 0; }
  .section-heading p { color: var(--text-2); margin: 0.3rem 0 var(--space-5); }
  .card { margin-bottom: var(--space-4); }
  .card h3 { margin: 0 0 0.3rem; font-size: var(--text-lg); }
  .lead, .empty { color: var(--text-2); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
  .guard { border-left: 3px solid var(--accent); }
  .guard strong { display: block; margin-bottom: 0.25rem; }
  .guard p { color: var(--text-2); font-size: var(--text-sm); margin: 0; }
  .add-row { display: grid; grid-template-columns: 1fr 1fr auto; gap: var(--space-2); align-items: end; }
  .add-row .field-label { grid-column: 1 / -1; margin: 0; }
  .error { color: var(--danger); font-size: var(--text-sm); margin: var(--space-2) 0 0; }
  .rules, .fixed { list-style: none; margin: var(--space-3) 0 0; padding: 0; display: grid; gap: 0.4rem; }
  .rules li { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3);
    padding: var(--row-y) var(--row-x); border: 1px solid var(--border); border-radius: var(--r-sm); }
  .kind, .note-text { color: var(--text-2); font-size: var(--text-xs); margin-left: var(--space-3); }
  .probe { margin: var(--space-3) 0 0; font-size: var(--text-sm); }
  .probe.blocked { color: var(--danger); }
  .reason, .addresses { color: var(--text-2); font-family: var(--font-mono); font-size: var(--text-xs); }
  .source { color: var(--text-3); font-size: var(--text-xs); margin: var(--space-3) 0 0; text-transform: uppercase; letter-spacing: 0.04em; }
  .fixed li { color: var(--text-2); font-size: var(--text-sm); }
  @media (max-width: 40rem) { .add-row { grid-template-columns: 1fr; } }
</style>
