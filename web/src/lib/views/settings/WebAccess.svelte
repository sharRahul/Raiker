<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import PageState from "../../components/PageState.svelte";
  import type { WebBlocklistProbe as BlocklistProbe } from "../../apiTypes";
  import type { ThreatFeeds } from "../../generated/apiContract";

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
  let feeds = $state<ThreatFeeds | null>(null);
  let updating = $state(false);
  let loadError = $state<string | null>(null);
  let draft = $state("");
  let note = $state("");
  let addError = $state<string | null>(null);
  let busy = $state(false);

  let probe = $state("");
  let probeResult = $state<BlocklistProbe | null>(null);

  // DEC-21 — which of the three sources a matching rule is in, so the owner
  // knows whether removing it is theirs to do here.
  const RULE_SOURCE: Record<string, string> = {
    built_in: "built into Raiker",
    environment: "set by RAIKER_WEB_EGRESS_BLACKLIST",
    yours: "on your list below",
  };
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
    if (key === "known_site_not_flaggable") {
      return `${draft.trim()} is a known site and is never flagged. Raiker flags only sites a public threat feed registers as malicious.`;
    }
    if (key === "blocklist_regex_invalid") {
      return `That regular expression will not compile: ${detail.split(":").slice(1).join(":")}`;
    }
    return RULE_ERROR[key] ?? "That rule could not be understood.";
  }

  async function load(): Promise<void> {
    try {
      loadError = null;
      data = await api.webBlocklist();
      // The feeds are their own card: one that cannot load never hides the page.
      feeds = await api.threatFeeds().catch(() => null);
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

  async function updateFeeds(): Promise<void> {
    updating = true;
    try {
      feeds = await api.refreshThreatFeeds();
    } finally {
      updating = false;
    }
  }

  // A reason code is for the record; the owner reads what it means.
  function feedError(code: string): string {
    if (/^(fetch_failed|egress_denied)/.test(code)) {
      return "Could not reach the feed from this computer. The last copy, if any, is still used.";
    }
    if (code.startsWith("redirect_refused")) return "The feed tried to send Raiker elsewhere, so it was not read.";
    if (code.startsWith("http_error")) return `The feed answered with an error (${code.split(":")[1] ?? "?"}).`;
    return "The last update failed. The last copy, if any, is still used.";
  }

  function updated(at: number | null): string {
    if (!at) return "Not downloaded yet";
    return `Updated ${new Date(at * 1000).toLocaleString()}`;
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
      Raiker reads any public web page and searches with DuckDuckGo, with no account
      or key. It flags only sites a public threat feed registers as malicious, with
      an alert where you read the answer. Known sites, and the services you sign in
      to, are never flagged.
    </p>
  </header>

  {#if loadError}
    <PageState state="error" title="Couldn't load web access settings" detail={loadError} />
  {:else if !data}
    <PageState state="loading" title="Loading web access settings…" />
  {:else}
    <!-- Stated before the editable list, because it is the part that is *not*
         editable and the part that actually stops a fetch reaching your own
         network. An owner who empties the list below should know what remains.

         REM-SET-WEB — and it now answers the question the old wording left
         open: whether there is a grant, an approval or a setting that lifts it.
         There is not, and saying so is cheaper than letting an owner go looking
         for one. -->
    <div class="guard card" role="note">
      <strong>Private networks are always refused</strong>
      <p>{data.address_guard.description}</p>
      <p class="guard-grant">
        {data.address_guard.editable
          ? "This can be changed below."
          : "No setting on this page and no approval lifts it — a private service is reached by you, not by Raiker."}
      </p>
    </div>

    {#if feeds}
      <div class="card" data-testid="threat-feeds">
        <div class="card-head">
          <h3>Known malicious sites</h3>
          <button class="btn btn-sm" type="button" onclick={updateFeeds} disabled={updating}>
            {updating ? "Updating…" : "Update now"}
          </button>
        </div>
        <p class="lead">
          Matched on this computer: the address you read is never sent anywhere to be
          checked. Refreshed daily while Raiker runs.
        </p>
        <ul class="feeds">
          {#each feeds.feeds as feed (feed.id)}
            <li>
              <div>
                <strong>{feed.name}</strong>
                <span class="kind">{feed.what}</span>
              </div>
              <div class="feed-state">
                <span>{feed.entries.toLocaleString()} {feed.entries === 1 ? "entry" : "entries"}</span>
                <span class="kind">{updated(feed.fetched_at)}</span>
                {#if feed.last_error}
                  <span class="error" role="status" title={feed.last_error}>{feedError(feed.last_error)}</span>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
        <p class="kind never">
          Never flagged: {feeds.authenticated_sites.length + feeds.known_sites.length} known
          and signed-in sites, GitHub, Google and Slack among them. One page on such a
          site that a feed lists is still flagged, as that page.
        </p>
      </div>
    {/if}

    <div class="card">
      <h3>Your own flags</h3>
      <!-- REM-SET-WEB — the effective total, which is what a fetch is actually
           evaluated against. The three sources below add up to it, so an owner
           who deletes one of their own rules can see that the number the
           runtime uses moved with it. -->
      <p class="effective" role="status">
        <strong>{data.stored.length}</strong> of your own{data.environment.length > 0
          ? `, ${data.environment.length} from this host's environment`
          : ""}.
      </p>
      <p class="lead">
        Optional. Raiker reads a site you flag and tells you, in the conversation, that
        it is on this list; a known site cannot be flagged. A domain also covers its
        subdomains. You can also use a wildcard
        (<code>*.ads.example.com</code>), an IP address, an IP range
        (<code>10.0.0.0/8</code>), or a regular expression
        (<code>/^tracker[0-9]+\./</code>).
      </p>

      <form class="add-row" onsubmit={add}>
        <label class="field-label" for="blocklist-rule">Site to flag</label>
        <input
          id="blocklist-rule"
          class="input"
          bind:value={draft}
          placeholder="example.com, *.ads.example.com, 10.0.0.0/8, /pattern/"
          aria-describedby={addError ? "blocklist-rule-error" : undefined}
          aria-invalid={addError ? "true" : undefined}
        />
        <input class="input note" bind:value={note} placeholder="Note (optional)" aria-label="Note" />
        <button class="btn btn-primary" type="submit" disabled={busy || !draft.trim()}>Flag</button>
      </form>
      {#if addError}
        <p class="error" id="blocklist-rule-error" role="alert">{addError}</p>
      {/if}

      {#if data.stored.length === 0}
        <p class="empty">
          Nothing of your own. The feeds above are what Raiker flags.
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
                aria-label={`Remove flag from ${rule.rule}`}>Remove</button
              >
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="card">
      <h3>Check a site</h3>
      <p class="lead">
        Answers what Raiker would do with a host, without contacting it.
      </p>
      <form class="add-row" onsubmit={test}>
        <label class="field-label" for="blocklist-probe">Hostname or address</label>
        <input id="blocklist-probe" class="input" bind:value={probe} placeholder="docs.python.org" />
        <button class="btn" type="submit" disabled={probing || !probe.trim()}>Check</button>
      </form>
      {#if probeResult}
        <div class="probe" class:blocked={!probeResult.allowed} role="status">
          <p>
            <strong>{probeResult.host}</strong>
            {probeResult.allowed ? (probeResult.rule ? "is read, with an alert" : "is reachable") : "is refused"}
            {#if probeResult.addresses.length}
              <span class="addresses">→ {probeResult.addresses.join(", ")}</span>
            {/if}
          </p>
          <!-- DEC-21 — the reason in words and the rule that said it, never
               only a reason code. -->
          {#if probeResult.allowed && probeResult.rule}
            <p class="why">On your flagged sites as <code>{probeResult.rule}</code>.</p>
          {/if}
          {#if !probeResult.allowed}
            {#if probeResult.rule}
              <p class="why">
                Matched <code>{probeResult.rule}</code>, {RULE_SOURCE[probeResult.rule_source ?? ""] ??
                  "a rule in force"}.
              </p>
            {:else if probeResult.explanation}
              <!-- A matched rule is the whole reason; the general sentence is
                   for a refusal no rule on this page made. -->
              <p class="why">{probeResult.explanation}</p>
            {/if}
          {/if}
        </div>
      {/if}
    </div>

    <!-- REM-SET-WEB — this was a card of the same weight as the editable list
         above it, which made deployment configuration read as policy an owner
         could change here and then find they could not. It is read-only detail
         now: folded away, marked as read-only, and each source says who can
         actually change it rather than only that this page cannot. -->
    {#if data.environment.length || data.builtin.length}
      <details class="card fixed-card">
        <summary>
          <span>Set outside this app</span>
          <span class="read-only">Read-only · {data.environment.length + data.builtin.length}</span>
        </summary>
        <p class="lead">
          These apply as well as the rules above. They are part of how this Raiker was
          started, so they cannot be added or removed from this page.
        </p>
        {#if data.environment.length}
          <p class="source"><code>{data.environment_variable}</code></p>
          <p class="remedy">
            Flagged like your own sites. Changed by whoever starts Raiker on this
            machine, by setting this variable before launch.
          </p>
          <ul class="fixed">
            {#each data.environment as rule (rule)}<li><code>{rule}</code></li>{/each}
          </ul>
        {/if}
        <p class="source">Built in · always refused</p>
        <p class="remedy">
          These name this machine's own network and cloud metadata services, so they
          are refused like a private address rather than flagged. Part of this build.
        </p>
        <ul class="fixed">
          {#each data.builtin as rule (rule)}<li><code>{rule}</code></li>{/each}
        </ul>
      </details>
    {/if}
  {/if}
</section>

<style>
  .section-heading h2 { margin: 0; }
  .section-heading p { color: var(--text-2); margin: 0.3rem 0 var(--space-5); }
  .card { margin-bottom: var(--space-4); }
  .card h3 { margin: 0 0 0.3rem; font-size: var(--text-lg); }
  .lead, .empty { color: var(--text-2); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
  .guard { border: 1px solid var(--accent-border); }
  .guard strong { display: block; margin-bottom: 0.25rem; }
  .guard p { color: var(--text-2); font-size: var(--text-sm); margin: 0; }
  .guard-grant { margin-top: 0.35rem !important; color: var(--text-3) !important; }
  .effective { font-size: var(--text-sm); color: var(--text-2); margin: 0 0 var(--space-2); }
  .effective strong { color: var(--text-1); }
  .fixed-card summary {
    display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3);
    cursor: pointer; font-size: var(--text-lg); font-weight: 600;
  }
  .fixed-card[open] summary { margin-bottom: var(--space-3); }
  .read-only { color: var(--text-3); font-size: var(--text-xs); font-weight: 400; }
  .remedy { color: var(--text-2); font-size: var(--text-sm); margin: 0.2rem 0 0; }
  /* FIXED-416 — a wrapping flex row, not a `1fr 1fr auto` grid: a `1fr` track
     will not shrink below its content's minimum, and an `<input>` defaults to
     about twenty characters, which pushes Settings past a 768px viewport — an
     overflow the shell absorbs, so it is invisible on the page itself. The fields share the
     space while there is space and drop to their own lines when there is not,
     the button never stretches to fill a column it was only borrowing, and
     `min-width: 0` is what lets a field actually shrink rather than merely
     being asked to. */
  .card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .card-head h3 {
    margin: 0;
  }
  .feeds {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  .feeds li {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-2) 0;
    border-top: 1px solid var(--border);
  }
  .feeds li > div {
    display: grid;
    gap: 0.15rem;
  }
  .feed-state {
    text-align: right;
    font-size: var(--text-sm);
  }
  .never {
    margin: var(--space-3) 0 0;
  }
  .feeds .kind,
  .never.kind {
    margin-left: 0;
  }
  .add-row { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: end; }
  .add-row .field-label { flex: 1 0 100%; margin: 0; }
  .add-row .input { flex: 1 1 12rem; min-width: 0; }
  .add-row .btn { flex: 0 0 auto; }
  .error { color: var(--danger); font-size: var(--text-sm); margin: var(--space-2) 0 0; }
  .rules, .fixed { list-style: none; margin: var(--space-3) 0 0; padding: 0; display: grid; gap: 0.4rem; }
  .rules li { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3);
    padding: var(--row-y) var(--row-x); border: 1px solid var(--border); border-radius: var(--r-sm); }
  .kind, .note-text { color: var(--text-2); font-size: var(--text-xs); margin-left: var(--space-3); }
  .probe { margin: var(--space-3) 0 0; font-size: var(--text-sm); display: grid; gap: var(--space-1); }
  .probe p { margin: 0; }
  .probe.blocked > p:first-child { color: var(--danger); }
  .probe .why { color: var(--text-2); }
  .addresses { color: var(--text-2); font-family: var(--font-mono); font-size: var(--text-xs); }
  .source { color: var(--text-3); font-size: var(--text-xs); margin: var(--space-3) 0 0; }
  .fixed li { color: var(--text-2); font-size: var(--text-sm); }
  @media (max-width: 40rem) { .add-row { grid-template-columns: 1fr; } }
</style>
