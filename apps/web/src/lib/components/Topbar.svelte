<script lang="ts">
  import type { ProjectsList } from "../apiTypes";
  import StopSwitch from "./StopSwitch.svelte";
  import ThemeToggle from "./ThemeToggle.svelte";

  let { title, hint, connecting = false, projects = null, onProjectSelect = undefined }: {
    title: string;
    hint: string;
    connecting?: boolean;
    projects?: ProjectsList | null;
    onProjectSelect?: (projectId: string | null) => void;
  } = $props();
</script>

<header class="topbar">
  <div class="page-id"><h1 class="page-title">{title}</h1><p class="page-hint">{hint}</p></div>
  <div class="status" role="status" aria-live="polite">
    {#if connecting}<span class="pill">Connecting…</span>
    {:else if projects !== null && projects.projects.length > 0}
      <select class="project-select" aria-label="Active project" value={projects.active_project_id ?? ""} onchange={(e) => onProjectSelect?.((e.currentTarget as HTMLSelectElement).value || null)}>
        <option value="">No project</option>{#each projects.projects as p (p.project_id)}<option value={p.project_id}>{p.name}</option>{/each}
      </select>
    {/if}
  </div>
  <div class="controls"><ThemeToggle /><StopSwitch /></div>
</header>

<style>
  .topbar{height:var(--topbar-h);display:flex;align-items:center;gap:var(--space-4);padding:0 var(--space-5);border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0}.page-id{min-width:0}.page-title{font-size:1rem;margin:0;line-height:1.2}.page-hint{font-size:.72rem;color:var(--text-3);margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.status{display:flex;align-items:center;gap:.45rem;margin-left:auto}.pill,.project-select{font-size:.74rem;font-weight:600;padding:.18rem .6rem;border-radius:var(--r-pill);border:1px solid var(--neutral-border);background:var(--neutral-soft);color:var(--text-2)}.controls{display:flex;align-items:center;gap:.5rem}@media(max-width:900px){.page-hint{display:none}}
</style>
