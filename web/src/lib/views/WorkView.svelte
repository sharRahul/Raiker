<script lang="ts">
  /**
   * Quiet UI — everything the owner has going, on one page.
   *
   * Threads, Tasks and Projects were three rail rows answering one question.
   * The Library (QUI-F15) is the fifth tab: what all that work made.
   * They are tabs of this page now; each tab is the page it used to be, and
   * the old addresses (`#/tasks`, `#/projects`, `#/search-chat`) open the
   * matching tab (`nav.ts`, ROUTE_ALIASES).
   */
  import TabStrip from "../components/TabStrip.svelte";
  import type { ProjectsList } from "../apiTypes";
  import { HUB_TABS } from "../nav";
  import GoalsView from "./GoalsView.svelte";
  import LibraryView from "./LibraryView.svelte";
  import ProjectsView from "./ProjectsView.svelte";
  import SearchChatView from "./SearchChatView.svelte";
  import TasksView from "./TasksView.svelte";

  let {
    tab = "threads",
    sessionId = null,
    projects = null,
    taskId = null,
    onchanged = () => {},
  }: {
    tab?: string;
    sessionId?: string | null;
    projects?: ProjectsList | null;
    taskId?: string | null;
    onchanged?: () => void;
  } = $props();

  const LABELS: Record<string, string> = { threads: "Threads", goals: "Goals", tasks: "Tasks", projects: "Projects", library: "Library" };
  const tabs = HUB_TABS.work.map((id) => ({ id, label: LABELS[id] ?? id }));

  function selectTab(next: string) {
    window.location.hash = `#/work?tab=${encodeURIComponent(next)}`;
  }
</script>

<TabStrip {tabs} selected={tab} onselect={selectTab} label="Work" />
<div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
  {#if tab === "goals"}
    <GoalsView />
  {:else if tab === "tasks"}
    <TasksView {sessionId} {projects} {taskId} />
  {:else if tab === "projects"}
    <ProjectsView {onchanged} />
  {:else if tab === "library"}
    <LibraryView />
  {:else}
    <SearchChatView />
  {/if}
</div>
