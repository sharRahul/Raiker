<script lang="ts">
  /**
   * UX-MODEL-01 — the Runtime tab's content, out of the Models page.
   *
   * What is serving on this machine, what is on disk, what each surface starts
   * on, the advanced routing that decides what runs when that cannot, and what
   * the runtime is doing now. The page keeps the actions that touch provider
   * connections — testing, selecting, the details dialog — and hands them in,
   * so a slot row here and a provider row on Add do exactly the same thing.
   */
  import { onMount } from "svelte";
  import TabStrip from "../../components/TabStrip.svelte";
  import type { ModelProfile, ModelsView as ModelsData } from "../../apiTypes";
  import AdvancedRouting from "./AdvancedRouting.svelte";
  import SideTaskModels from "./SideTaskModels.svelte";
  import DownloadsPanel from "./DownloadsPanel.svelte";
  import LocalFrameworkRow from "./LocalFrameworkRow.svelte";
  import LlamaEnginePanel from "./LlamaEnginePanel.svelte";
  import LocalLibraryPanel from "./LocalLibraryPanel.svelte";
  import ModelRuntimeSettings from "./ModelRuntimeSettings.svelte";
  import SpeechRuntimePanel from "./SpeechRuntimePanel.svelte";
  import WorkDefaults from "./WorkDefaults.svelte";

  let {
    models,
    revision,
    onreload,
    gguf,
    mlx,
    testing,
    testResults,
    selecting,
    ontest,
    ondetails,
    onselect,
  }: {
    models: ModelsData;
    /** Bumped by the page on every full read (see AdvancedRouting). */
    revision: number;
    onreload: () => Promise<void>;
    /** The llama.cpp slot profiles published on this platform. */
    gguf: ModelProfile[];
    /** The MLX slot profiles; empty off Apple silicon. */
    mlx: ModelProfile[];
    testing: Record<string, true>;
    testResults: Record<string, string>;
    selecting: boolean;
    ontest: (profile: ModelProfile) => void;
    ondetails: (profile: ModelProfile) => void;
    onselect: (profile: ModelProfile) => void;
  } = $props();
  const panels = [
    { id: "serving", label: "Running models" },
    { id: "library", label: "Library" },
    { id: "activity", label: "Activity" },
    { id: "advanced", label: "Advanced" },
  ];
  function requestedPanel(): string {
    if (typeof window === "undefined") return "serving";
    const value = new URLSearchParams(window.location.hash.split("?", 2)[1] ?? "").get("modelsPanel");
    return panels.some(panel => panel.id === value) ? value! : "serving";
  }
  const initialPanel = requestedPanel();
  let panel = $state(initialPanel);
  let visited = $state([initialPanel]);
  function rememberPanel(id: string) {
    panel = id;
    if (!visited.includes(id)) visited = [...visited, id];
  }
  function choosePanel(id: string) {
    const [route, query] = window.location.hash.split("?", 2);
    const params = new URLSearchParams(query);
    params.set("modelsPanel", id);
    rememberPanel(id);
    window.location.hash = `${route}?${params}`;
  }
  onMount(() => {
    const sync = () => { rememberPanel(requestedPanel()); };
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  });
</script>

<!-- Effective model/fallback facts remain visible on every settings section. -->
<WorkDefaults {models} />
<TabStrip tabs={panels} selected={panel} onselect={choosePanel} label="Model settings" />
{#each panels as item (item.id)}
{#if visited.includes(item.id)}
<div role="tabpanel" aria-label={item.label} hidden={panel !== item.id}>
{#if item.id === "serving"}
<!-- Local serving, in the section about runtime rather than
     in the middle of the list of things you could add. The slot rows are
     unchanged; what moved is which question they answer. -->
<div class="local-list local-serving">
  {#if gguf.length > 0}
    <!-- The engine behind the GGUF slots: installed, sized and supervised by
         Raiker, so serving a model needs no manual setup. -->
    <LlamaEnginePanel active={panel === "serving"} onchanged={() => void onreload()} />
    <LocalFrameworkRow
      active={panel === "serving"}
      provider="llama.cpp"
      title="GGUF"
      format="gguf"
      profiles={gguf}
      description="Up to four detected GGUF models, each served in its own slot by the llama.cpp server Raiker runs for you."
      onchanged={() => void onreload()}
      {ontest}
      {ondetails}
      {onselect}
      testing={testing[gguf[0].profile_id] === true}
      {selecting}
      testResult={testResults[gguf[0].profile_id] ?? null}
    />
  {/if}
  {#if mlx.length > 0}
    <LocalFrameworkRow
      active={panel === "serving"}
      provider="mlx"
      title="MLX"
      format="mlx"
      profiles={mlx}
      description="Choose up to four detected MLX models optimized for Apple silicon."
      onchanged={() => void onreload()}
      {ontest}
      {ondetails}
      {onselect}
      testing={testing[mlx[0].profile_id] === true}
      {selecting}
      testResult={testResults[mlx[0].profile_id] ?? null}
    />
  {/if}
  <!-- BUG-256 — dictation's runtime is a local runtime, and it
       belongs beside the others rather than in a category of
       its own. Nothing here is contacted until Save and test. -->
  <SpeechRuntimePanel />
</div>

{:else if item.id === "library"}
  <LocalLibraryPanel active={panel === "library"} />
{:else if item.id === "activity"}
  <DownloadsPanel active={panel === "activity"} />
{:else}
  {#if gguf.length > 0}<ModelRuntimeSettings />{/if}
  <AdvancedRouting {models} {revision} {onreload} />
  <SideTaskModels {models} {onreload} />
{/if}
</div>
{/if}
{/each}

<style>
  [role="tabpanel"] { margin-top: var(--space-4); }
  .local-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
</style>
