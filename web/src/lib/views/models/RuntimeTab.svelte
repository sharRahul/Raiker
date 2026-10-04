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
  import type { ModelProfile, ModelsView as ModelsData } from "../../apiTypes";
  import AdvancedRouting from "./AdvancedRouting.svelte";
  import DownloadsPanel from "./DownloadsPanel.svelte";
  import LocalFrameworkRow from "./LocalFrameworkRow.svelte";
  import LocalLibraryPanel from "./LocalLibraryPanel.svelte";
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
</script>

<!-- Local serving, in the section about runtime rather than
     in the middle of the list of things you could add. The slot rows are
     unchanged; what moved is which question they answer. -->
<div class="local-list local-serving">
  {#if gguf.length > 0}
    <LocalFrameworkRow
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

<!-- The library answers "what is on disk"; the serving rows
     above answer "what is running". They were interleaved. -->
<LocalLibraryPanel />

<!-- Two facts told apart: what each surface starts on, and what would
     really answer right now. The fallback sequence that produces the second is edited
     directly beneath, so cause and effect are on one screen. -->
<WorkDefaults {models} />

<!-- REM-MODEL-02 / UX-MODEL-05 — orchestration tuning, one reach down.
     The two controls below decide what happens when the owner's model
     *cannot* serve, and what a local model may consult. Both are real and
     both stay editable; neither is what somebody opens this tab to find
     out. Above them, `WorkDefaults` already answers the ordinary
     questions — what each surface starts on, and what would really answer
     right now — and it keeps naming a fallback that displaced a selection
     **outside** this disclosure, because a substitution that changes
     provider, and therefore where the owner's words go, is never
     something to fold away. What is folded is the tuning, not the
     disclosure. -->
<AdvancedRouting {models} {revision} {onreload} />

<!-- Downloads, conversions and pulls are what the
     runtime is *doing*, so they belong to the runtime rather than beside
     Pricing as a sixth peer tab. -->
<DownloadsPanel />

<style>
  .local-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
</style>
