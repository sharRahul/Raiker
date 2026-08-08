<script lang="ts">
  import type { IdentityView } from "../apiTypes";

  let { identity }: { identity?: IdentityView | null } = $props();
  const view = $derived(identity ?? {
    principal_id: "agent_runtime",
    principal_type: "unknown",
    display_name: "Legacy agent",
    subject: null,
    turn_id: null,
    key_id: null,
    issued_at: null,
    expires_at: null,
    state: "unknown",
  });
  const kind = $derived(view.principal_type === "ai_agent" ? "Agent" : view.principal_type === "human" ? "Human" : "Actor");
</script>

<span class:machine={view.principal_type === "ai_agent"} class="identity-chip" title={view.principal_id}>
  <span class="identity-mark" aria-hidden="true">{view.principal_type === "ai_agent" ? "◇" : "●"}</span>
  <span class="identity-copy">
    <strong>{view.display_name}</strong>
    <small>{kind} · {view.state}</small>
  </span>
</span>

<style>
  .identity-chip { display:inline-flex; align-items:center; gap:.48rem; max-width:100%; padding:.28rem .58rem; border:1px solid var(--neutral-border); border-radius:var(--r-pill); background:var(--neutral-soft); color:var(--text-1); vertical-align:middle; }
  .identity-chip.machine { border-color:var(--accent-border); background:var(--accent-soft); }
  .identity-mark { display:grid; place-items:center; width:1.2rem; height:1.2rem; color:var(--text-2); font-size:.72rem; }
  .machine .identity-mark { color:var(--accent); }
  .identity-copy { display:flex; align-items:baseline; gap:.38rem; min-width:0; }
  strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:.75rem; font-weight:650; }
  small { color:var(--text-2); font-size:.64rem; letter-spacing:.02em; text-transform:uppercase; white-space:nowrap; }
  @media (max-width:520px) { .identity-copy { align-items:flex-start; flex-direction:column; gap:0; } }
</style>
