<script lang="ts">
  import type { CapabilityGate } from "../apiTypes";

  let { gates }: { gates: CapabilityGate[] } = $props();

  function agentAuthority(gate: CapabilityGate): "Direct" | "Ask" | "Denied" | "Unavailable" {
    if (gate.state !== "enabled_runtime") return "Unavailable";
    if (gate.decision_mode === "deny") return "Denied";
    if (gate.decision_mode === "ask") return "Ask";
    return "Direct";
  }

  function ownerControl(gate: CapabilityGate): string {
    if (gate.state !== "enabled_runtime") return "Off";
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
</section>

<style>
  .authority-matrix { margin:var(--space-4) 0; border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); overflow:hidden; }
  .matrix-intro { display:flex; align-items:center; justify-content:space-between; gap:var(--space-4); padding:var(--space-4); border-bottom:1px solid var(--border); background:linear-gradient(100deg, var(--surface), var(--accent-soft)); }
  .eyebrow { margin:0 0 .18rem; color:var(--accent); font-size:.66rem; font-weight:750; letter-spacing:.12em; text-transform:uppercase; }
  h2 { margin:0; font-size:.95rem; font-weight:650; }
  .delegation-rail { display:flex; align-items:center; gap:.42rem; color:var(--text-2); font-size:.66rem; white-space:nowrap; }
  .delegation-rail i { width:2.4rem; height:1px; background:var(--accent); position:relative; }
  .delegation-rail i::after { content:""; position:absolute; right:-1px; top:-3px; border-left:5px solid var(--accent); border-top:3px solid transparent; border-bottom:3px solid transparent; }
  .matrix-scroll { overflow-x:auto; }
  table { width:100%; border-collapse:collapse; font-size:.76rem; }
  th, td { padding:.58rem var(--space-4); text-align:left; border-bottom:1px solid var(--border); }
  tbody tr:last-child th, tbody tr:last-child td { border-bottom:0; }
  thead th { color:var(--text-2); font-size:.65rem; letter-spacing:.06em; text-transform:uppercase; }
  tbody th { font-weight:600; }
  code { color:var(--text-2); font-family:var(--font-mono); font-size:.7rem; }
  .authority-state { font-weight:700; color:var(--ok); }
  .authority-state.ask { color:var(--warn); }
  .authority-state.blocked { color:var(--text-2); }
  @media (max-width:640px) { .matrix-intro { align-items:flex-start; flex-direction:column; } }
</style>
