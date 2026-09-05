<script lang="ts">
  import type { CapabilityGate } from "../apiTypes";

  let {
    gates,
    total = gates.length,
  }: {
    gates: CapabilityGate[];
    /** Every governed capability, so the summary can say what it is a summary of. */
    total?: number;
  } = $props();

  function isReady(gate: CapabilityGate): boolean {
    return Object.values(gate.readiness).every(Boolean);
  }

  function agentAuthority(gate: CapabilityGate): "Direct" | "Ask" | "Denied" | "Unavailable" {
    if (gate.state !== "enabled_runtime" || !isReady(gate)) return "Unavailable";
    if (gate.decision_mode === "deny") return "Denied";
    if (gate.decision_mode === "ask") return "Ask";
    return "Direct";
  }

  function ownerControl(gate: CapabilityGate): string {
    if (gate.state !== "enabled_runtime") return "Off";
    if (!isReady(gate)) return "Not ready";
    return gate.decision_mode === "auto" ? "Auto-approved" : "Enabled";
  }
</script>

<section class="authority-matrix" aria-labelledby="authority-title">
  <div class="matrix-intro">
    <div>
      <p class="eyebrow">Delegated authority</p>
      <h2 id="authority-title">Owner sets the boundary. The agent inherits less.</h2>
    </div>
    <span class="delegation-rail" aria-hidden="true"><b>Owner</b><i></i><b>Signed turn</b></span>
  </div>
  {#if total > gates.length}
    <!-- A table that stops after eight rows without saying so reads as the whole
         list. It is a summary, and the summary says which eight: the ones that
         carry the most authority right now. -->
    <p class="matrix-note">
      The {gates.length} of {total} capabilities the agent currently carries the most authority
      for. All {total} are listed below.
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
            <th scope="row"><code>{gate.capability}</code></th>
            <td>{ownerControl(gate)}</td>
            <td><span class:ask={agentAuthority(gate) === "Ask"} class:blocked={["Denied", "Unavailable"].includes(agentAuthority(gate))} class="authority-state">{agentAuthority(gate)}</span></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <ul class="matrix-cards">
    {#each gates as gate (gate.capability)}
      <li>
        <code>{gate.capability}</code>
        <dl>
          <div><dt>Owner control</dt><dd>{ownerControl(gate)}</dd></div>
          <div>
            <dt>Raiker agent</dt>
            <dd>
              <span
                class:ask={agentAuthority(gate) === "Ask"}
                class:blocked={["Denied", "Unavailable"].includes(agentAuthority(gate))}
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
  .eyebrow { margin:0 0 .18rem; color:var(--accent); font-size:var(--text-2xs); font-weight:750; letter-spacing:.12em; text-transform:uppercase; }
  h2 { margin:0; font-size:var(--text-md); font-weight:650; }
  .delegation-rail { display:flex; align-items:center; gap:.42rem; color:var(--text-2); font-size:var(--text-2xs); white-space:nowrap; }
  .delegation-rail i { width:2.4rem; height:1px; background:var(--accent); position:relative; }
  .delegation-rail i::after { content:""; position:absolute; right:-1px; top:-3px; border-left:5px solid var(--accent); border-top:3px solid transparent; border-bottom:3px solid transparent; }
  .matrix-scroll { overflow-x:auto; }
  .matrix-note { margin:0 var(--space-4) var(--space-3); color:var(--text-3); font-size:var(--text-sm); }
  table { width:100%; border-collapse:collapse; font-size:var(--text-xs); }
  th, td { padding:.58rem var(--space-4); text-align:left; border-bottom:1px solid var(--border); }
  tbody tr:last-child th, tbody tr:last-child td { border-bottom:0; }
  thead th { color:var(--text-2); font-size:var(--text-2xs); letter-spacing:.06em; text-transform:uppercase; }
  tbody th { font-weight:600; }
  code { color:var(--text-2); font-family:var(--font-mono); font-size:var(--text-2xs); }
  .authority-state { font-weight:700; color:var(--ok); }
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
    .matrix-cards dt { color:var(--text-2); font-size:var(--text-2xs); letter-spacing:.06em; text-transform:uppercase; align-self:baseline; }
    .matrix-cards dd { margin:0; font-size:var(--text-sm); }
  }
</style>
