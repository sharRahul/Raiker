<script lang="ts">
  import type { CapabilityGate } from "../apiTypes";
  import { capabilityLabel, isAvailable, isDecisionMode, isReady } from "../capabilityModel";
  import { behaviourCopy, rowSummary } from "../permissionLanguage";

  let {
    gates,
    total = gates.length,
  }: {
    gates: CapabilityGate[];
    /** Every governed capability, so the summary can say what it is a summary of. */
    total?: number;
  } = $props();

  /*
   * NEW-PERM-03 — what the agent may do with this capability, said only as far
   * as the page has actually been told.
   *
   * This returned `Direct` for every mode that was not `deny` or `ask`, which
   * quietly included a mode that is missing, misspelt, or newer than this
   * build: an unrecognised value was rendered as the *most permissive* verdict
   * the table can print. Unknown is not evidence of permission. It is now its
   * own answer, and `allow` and `auto` are told apart in the page's own words
   * rather than collapsed into one invented one.
   *
   * Availability and readiness come from the shared helpers, so this table
   * resolves "is it on" the same way the registry row below it does — including
   * a capability that is on because nothing is stored against it, which this
   * copy of the rule used to read as Off.
   */
  /**
   * What this table says the agent carries.
   *
   * REM-PERM-02 — the mode words come from the one owner vocabulary now. This
   * table used to say **Ask** and **Denied** while the control three rows below
   * it said **Ask me** and **Never** about the same stored value, so one policy
   * had two names on one screen (and `DECISION_MODE_COPY` was a third, unused,
   * waiting to be picked up).
   *
   * The three verdicts that are *not* modes stay as they are: unavailable, not
   * ready and unrecognised are different facts about whether the capability can
   * run at all, not different answers to "what happens when Raiker wants to".
   */
  function agentAuthority(gate: CapabilityGate): string {
    if (!isAvailable(gate)) return "Unavailable";
    if (!isReady(gate)) return "Not ready";
    if (!isDecisionMode(gate.decision_mode)) return "Unknown";
    return behaviourCopy(gate.decision_mode).label;
  }

  /** Nothing is carried for a capability that cannot run, whatever is configured. */
  function isBlocked(gate: CapabilityGate): boolean {
    return [behaviourCopy("deny").label, "Unavailable", "Not ready", "Unknown"].includes(
      agentAuthority(gate),
    );
  }

  /*
   * The owner's own two answers, in the words the rest of the page uses for
   * them. This column said `Enabled` and `Auto-approved` — a third vocabulary
   * for facts the row below already states as `On · Automatic`, which is how a
   * summary comes to look like it disagrees with the thing it summarises.
   */
  function ownerControl(gate: CapabilityGate): string {
    return rowSummary(gate, isAvailable(gate));
  }
</script>

<section class="authority-matrix" aria-labelledby="authority-title">
  <div class="matrix-intro">
    <div>
      <p class="eyebrow">Delegated authority · summary, read-only</p>
      <h2 id="authority-title">Owner sets the boundary. The agent inherits less.</h2>
    </div>
    <span class="delegation-rail" aria-hidden="true"><b>Owner</b><i></i><b>Signed turn</b></span>
  </div>
  {#if total > gates.length}
    <!-- A table that stops after eight rows without saying so reads as the whole
         list. It is a summary, and the summary says which eight: the ones that
         carry the most authority right now. -->
    <p class="matrix-note">
      The {gates.length} of {total} capabilities this account configures the most authority for.
      Change any of them in the list below, where all {total} are.
      <!-- NEW-PERM-03 — the heading claimed carried authority, and this table
           reads account configuration. What a turn may actually do is narrowed
           again by the task's own scope and by the runtime's checks at the
           moment it asks, so the summary says which of the two it is. -->
      A task's own scope and the runtime's checks at the moment of use can narrow it further.
    </p>
  {/if}
  <!-- BUG-246 — two presentations of one list, and exactly one of them is in
       the accessibility tree at a time, because `display: none` removes the
       other from it. A three-column table at 390px scrolled its *verdict*
       column off screen, so every row read "Unavail" under Raiker agent: the
       information was reachable, and the answer was the part you had to scroll
       for. Turning the table's own parts into blocks would have kept one DOM
       and lost the table semantics for a screen reader; this keeps both
       readings correct for the width each is offered at. -->
  <div class="matrix-scroll">
    <table>
      <thead><tr><th>Capability</th><th>Owner control</th><th>Raiker agent</th></tr></thead>
      <tbody>
        {#each gates as gate (gate.capability)}
          <tr>
            <!-- REM-PERM-02 — the name first, the identifier under it. A
                 registry key is what an owner exports and quotes in a bug
                 report, not what they read a row by. -->
            <th scope="row">
              <span class="cap-name">{capabilityLabel(gate.capability)}</span>
              <code>{gate.capability}</code>
            </th>
            <td>{ownerControl(gate)}</td>
            <td><span class:ask={agentAuthority(gate) === behaviourCopy("ask").label} class:blocked={isBlocked(gate)} class="authority-state">{agentAuthority(gate)}</span></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <ul class="matrix-cards">
    {#each gates as gate (gate.capability)}
      <li>
        <span class="cap-name">{capabilityLabel(gate.capability)}</span>
        <code>{gate.capability}</code>
        <dl>
          <div><dt>Owner control</dt><dd>{ownerControl(gate)}</dd></div>
          <div>
            <dt>Raiker agent</dt>
            <dd>
              <span
                class:ask={agentAuthority(gate) === behaviourCopy("ask").label}
                class:blocked={isBlocked(gate)}
                class="authority-state">{agentAuthority(gate)}</span
              >
            </dd>
          </div>
        </dl>
      </li>
    {/each}
  </ul>
</section>

<style>
  .authority-matrix { margin:var(--space-4) 0; border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); overflow:hidden; }
  .matrix-intro { display:flex; align-items:center; justify-content:space-between; gap:var(--space-4); padding:var(--space-4); border-bottom:1px solid var(--border); background:linear-gradient(100deg, var(--surface), var(--accent-soft)); }
  h2 { margin:0; font-size:var(--text-md); font-weight:650; }
  .delegation-rail { display:flex; align-items:center; gap:.42rem; color:var(--text-2); font-size:var(--text-2xs); white-space:nowrap; }
  .delegation-rail i { width:2.4rem; height:1px; background:var(--accent); position:relative; }
  .delegation-rail i::after { content:""; position:absolute; right:-1px; top:-3px; border-left:5px solid var(--accent); border-top:3px solid transparent; border-bottom:3px solid transparent; }
  .matrix-scroll { overflow-x:auto; }
  .matrix-note { margin:0 var(--space-4) var(--space-3); color:var(--text-3); font-size:var(--text-sm); }
  table { width:100%; border-collapse:collapse; font-size:var(--text-xs); }
  th, td { padding:.58rem var(--space-4); text-align:left; border-bottom:1px solid var(--border); }
  tbody tr:last-child th, tbody tr:last-child td { border-bottom:0; }
  /* VIS-06 — a column heading, same as the shared `.table th`. This table is
     not built on `.table`, so it carried its own copy of the old styling. */
  thead th { color:var(--text-2); font-size:var(--text-xs); font-weight:650; }
  tbody th { font-weight:600; }
  code { color:var(--text-3); font-family:var(--font-mono); font-size:var(--text-2xs); }
  /* REM-PERM-02 — the name a person reads, above the identifier they quote. */
  .cap-name { display:block; color:var(--text-1); font-weight:650; }
  /* VIS2-16 — a persistent normal state is neutral. Success colour is spent on
     something that just happened or on a decision that was just confirmed; used
     as the standing representation of "connected", "enabled", "verified" or
     "ready" it is on screen constantly, which is the one condition under which
     a colour stops carrying information. Exceptions keep their tone. */
  .authority-state { font-weight:700; color:var(--text-1); }
  .authority-state.ask { color:var(--warn); }
  .authority-state.blocked { color:var(--text-2); }
  /* The stacked reading. Hidden above the breakpoint, and hidden means gone
     from the accessibility tree as well as from the page — so a screen reader
     never meets the same capability twice. */
  .matrix-cards { display:none; }
  @media (max-width:640px) {
    .matrix-intro { align-items:flex-start; flex-direction:column; }
    .matrix-scroll { display:none; }
    .matrix-cards { display:grid; list-style:none; margin:0; padding:0; }
    .matrix-cards li { display:grid; gap:.35rem; padding:var(--space-3) var(--space-4); border-bottom:1px solid var(--border); }
    .matrix-cards li:last-child { border-bottom:0; }
    .matrix-cards dl { display:grid; grid-template-columns:auto minmax(0,1fr); gap:.15rem var(--space-3); margin:0; }
    .matrix-cards dl > div { display:contents; }
    .matrix-cards dt { color:var(--text-2); font-size:var(--text-2xs); letter-spacing:.05em; text-transform:uppercase; align-self:baseline; }
    .matrix-cards dd { margin:0; font-size:var(--text-sm); }
  }
</style>
