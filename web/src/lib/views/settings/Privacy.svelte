<script lang="ts">
  /**
   * Privacy — what Raiker keeps, and what leaves this machine.
   *
   * REM-SET-PRIVACY — this page was one control. It answered a real question
   * (BUG-215: is the model's working written to disk?) and nothing else, under a
   * heading that named the whole subject. An owner arriving at *Privacy* to find
   * out what Raiker holds about them, or what has left the machine, met a single
   * toggle about reasoning traces and a page that looked complete.
   *
   * The fix is not a longer slogan. "Everything stays on this machine" would be
   * shorter and would be false the moment a hosted provider is connected. What
   * this page owes an owner is an **inventory**: what is retained locally and
   * where the control for it lives, and what leaves — to whom, carrying what,
   * and whether it can happen at all right now.
   *
   * The outbound half is read from the capability gates rather than written
   * here, so it cannot drift from what the runtime will actually permit: a row
   * says "available" only because the same read the Permissions page uses says
   * so, in the same words.
   */
  import { onMount } from "svelte";
  import { api } from "../../api";
  import type { CapabilityGate } from "../../apiTypes";
  import { capabilityLabel, isAvailable } from "../../capabilityModel";
  import { rowSummary } from "../../permissionLanguage";

  let { settings, save }: {
    settings: Record<string, unknown>;
    save: (p: Record<string, unknown>) => void;
  } = $props();

  const retainReasoning = $derived(settings["privacy.retain_reasoning"] === true);

  let gates = $state<CapabilityGate[] | null>(null);
  let gatesError = $state(false);

  onMount(async () => {
    try {
      gates = await api.capabilityGates();
    } catch {
      // An unread gate list is unknown, not empty: the table says so rather
      // than printing a shorter inventory that reads as a smaller footprint.
      gatesError = true;
    }
  });

  /**
   * What leaves, and with it.
   *
   * One row per capability that can put your content on somebody else's
   * machine. `carries` is deliberately specific — "data" would be the slogan
   * this page is replacing.
   */
  const EGRESS = [
    {
      capability: "hosted_model_runtime",
      carries:
        "Your prompt, the attachments you add and as much of the conversation as the turn needs.",
      destination: "The hosted provider whose model you chose.",
      where: "#/models",
      whereLabel: "Models",
    },
    {
      capability: "image_generation",
      carries: "The prompt, and the picture you selected when you ask for an edit.",
      destination: "The image provider behind the model you chose in Design.",
      where: "#/models",
      whereLabel: "Models",
    },
    {
      capability: "web_fetch",
      carries:
        "The address Raiker requests. Nothing of the conversation travels with it unless the address itself contains it.",
      destination: "The site at that address, and any redirect your rules allow.",
      where: "#/settings?tab=web-access",
      whereLabel: "Web access",
    },
    {
      capability: "external_channel_runtime",
      carries: "The message Raiker sends, and the conversation it replies in.",
      destination: "The messaging account and conversation you paired.",
      where: "#/extensions?tab=channels",
      whereLabel: "Channels",
    },
    {
      capability: "git_push_execution",
      carries: "The files and commit history in the repository being pushed.",
      destination: "The git remote the repository is configured with.",
      where: "#/settings?tab=git-credential",
      whereLabel: "Git credentials",
    },
    {
      capability: "mcp_connector_runtime",
      carries: "The arguments of each tool call Raiker makes to that server.",
      destination: "The MCP server, which may be on this machine or elsewhere.",
      where: "#/extensions?tab=mcp",
      whereLabel: "MCP servers",
    },
    {
      capability: "telemetry_export",
      carries: "The audit records you choose to export.",
      destination: "The telemetry destination you configured.",
      where: "#/observe",
      whereLabel: "Observability",
    },
  ];

  interface EgressRow {
    capability: string;
    label: string;
    carries: string;
    destination: string;
    where: string;
    whereLabel: string;
    /** The same sentence the Permissions page prints, or unknown. */
    state: string;
    possible: boolean | null;
  }

  const egress = $derived<EgressRow[]>(
    EGRESS.map((entry) => {
      const gate = (gates ?? []).find((g) => g.capability === entry.capability);
      return {
        ...entry,
        label: capabilityLabel(entry.capability),
        state:
          gates === null
            ? gatesError
              ? "Unknown — permissions not read"
              : "Reading permissions…"
            : gate === undefined
              ? "Not in this build"
              : rowSummary(gate, isAvailable(gate)),
        possible: gates === null || gate === undefined ? null : isAvailable(gate),
      };
    }),
  );

  /** What is written to this machine, and the page that governs each of them. */
  const RETAINED = [
    {
      what: "Conversations and their turns",
      detail: "Every message, tool call and result, in the encrypted store.",
      where: "#/search-chat",
      whereLabel: "Threads",
    },
    {
      what: "The model's working",
      detail: "Only when the setting below is on. Never exported, never searched.",
      where: "#/settings?tab=privacy",
      whereLabel: "the control below",
    },
    {
      what: "Approved memories",
      detail: "Facts you approved, with their source, scope and expiry.",
      where: "#/memory",
      whereLabel: "Memory",
    },
    {
      what: "Checkpoints",
      detail: "Snapshots of files Raiker changed, so a change can be rewound.",
      where: "#/checkpoints",
      whereLabel: "Checkpoints",
    },
    {
      what: "Audit events",
      detail: "What was proposed, approved, refused and run, with provenance.",
      where: "#/activity",
      whereLabel: "Activity",
    },
    {
      what: "Generated images",
      detail: "The pictures and the prompts that made them, filed by project.",
      where: "#/design",
      whereLabel: "Design",
    },
  ];
</script>

<header class="section-heading">
  <h2>Privacy</h2>
  <p>What Raiker keeps on this machine, what leaves it, and who decides.</p>
</header>

<section class="settings-card" aria-labelledby="retained-inventory">
  <div class="card-heading">
    <h3 id="retained-inventory">Kept on this machine</h3>
    <p>
      All of it is written to the encrypted store in your workspace. Each one is governed by its
      own page, which is also where it is reviewed, exported or forgotten.
    </p>
  </div>
  <dl class="inventory">
    {#each RETAINED as row (row.what)}
      <div>
        <dt>{row.what}</dt>
        <dd>
          {row.detail}
          <a href={row.where}>{row.whereLabel}</a>
        </dd>
      </div>
    {/each}
  </dl>
  <p class="note">
    <!-- The limit an owner has to know before they rely on deletion. -->
    Forgetting a record removes it from the workspace, not from a backup already written: a backup
    is a copy of the store as it was when it was made. Re-verify a backup after a deletion you
    need to be permanent.
  </p>
</section>

<section class="settings-card" aria-labelledby="outbound-inventory">
  <div class="card-heading">
    <h3 id="outbound-inventory">What can leave this machine</h3>
    <p>
      Each row is a capability, what it would carry, and where it would go. Whether it can happen
      at all is read from your permissions, in the same words
      <a href="#/capabilities">Permissions</a> uses.
    </p>
  </div>
  {#if gatesError}
    <p class="notice" role="status">
      Your permissions could not be read, so this page cannot say which of these are available
      right now. Nothing below is a claim that it is off.
    </p>
  {/if}
  <ul class="egress">
    {#each egress as row (row.capability)}
      <li class:possible={row.possible === true}>
        <div class="egress-head">
          <strong>{row.label}</strong>
          <span class="egress-state">{row.state}</span>
        </div>
        <p class="egress-carries">{row.carries}</p>
        <p class="egress-destination">
          {row.destination}
          <a href={row.where}>{row.whereLabel}</a>
        </p>
      </li>
    {/each}
  </ul>
  <p class="note">
    Nothing leaves for a capability that is off, and nothing leaves without the decision its
    permission asks for. Model requests are also bounded by the egress allowlist the host process
    was started with, which is deliberately not editable from a browser session.
  </p>
</section>

<section class="settings-card" aria-labelledby="retained-working">
  <div class="card-heading">
    <h3 id="retained-working">Retained working</h3>
    <p>
      With Thinking on, Raiker shows the model's own working above its answer while
      the turn runs. This decides whether that working is written to the encrypted
      store so a re-opened conversation still shows it.
    </p>
  </div>

  <label class="toggle">
    <input
      type="checkbox"
      checked={retainReasoning}
      onchange={(e) => save({ "privacy.retain_reasoning": e.currentTarget.checked })}
    />
    <span>
      <strong>Keep the model's working with the turn</strong>
      <small>
        Off by default. The working can restate anything your prompt contained, so
        it is kept only if you ask. It is stored under the same encryption as the
        rest of the conversation, is never added to chat search, and is never
        included in an exported transcript.
      </small>
    </span>
  </label>

  <p class="note">
    Turning this off does not erase working already kept, and it does not hide that
    there was any: a turn whose working was not kept says so in the transcript,
    rather than reading as a turn that never thought.
  </p>
</section>

<style>
  .section-heading { margin-bottom: var(--space-4); }
  .section-heading h2, .card-heading h3 { margin: 0; }
  .section-heading p, .card-heading p { color: var(--text-2); margin: .3rem 0 0; max-width: var(--prose-measure); }
  .settings-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: var(--card-pad-y) var(--card-pad-x);
    margin-bottom: var(--space-4);
  }
  .inventory {
    display: grid;
    grid-template-columns: minmax(10rem, auto) minmax(0, 1fr);
    gap: var(--space-2) var(--space-4);
    margin: var(--space-4) 0 0;
  }
  .inventory > div { display: contents; }
  .inventory dt { color: var(--text-1); font-weight: 600; font-size: var(--text-sm); }
  .inventory dd { margin: 0; color: var(--text-2); font-size: var(--text-sm); line-height: 1.5; }
  .inventory a, .egress-destination a { color: var(--accent); font-weight: 600; margin-left: .35rem; }
  .egress { list-style: none; margin: var(--space-4) 0 0; padding: 0; display: grid; gap: var(--space-3); }
  .egress li {
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  /* A row that can happen right now is marked, in a border rather than a fill:
     this is a list to read, not a status board. */
  .egress li.possible { border-color: var(--accent-border); }
  .egress-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
  .egress-head strong { color: var(--text-1); }
  .egress-state { color: var(--text-3); font-size: var(--text-xs); white-space: nowrap; }
  .egress-carries, .egress-destination { margin: .3rem 0 0; color: var(--text-2); font-size: var(--text-sm); line-height: 1.5; }
  .egress-destination { color: var(--text-3); }
  .toggle {
    display: flex;
    align-items: flex-start;
    gap: .6rem;
    max-width: 40rem;
    margin-top: var(--space-5);
  }
  .toggle span { display: grid; gap: .2rem; }
  .toggle small { color: var(--text-2); line-height: 1.5; }
  .note {
    max-width: var(--prose-measure);
    margin: var(--space-4) 0 0;
    color: var(--text-3);
    font-size: var(--text-sm);
    line-height: 1.55;
  }
  @media (max-width: 600px) {
    .inventory { grid-template-columns: minmax(0, 1fr); gap: var(--space-1); }
    .inventory > div { display: block; margin-bottom: var(--space-3); }
  }
</style>
