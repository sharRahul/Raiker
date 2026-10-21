<script lang="ts">
  /**
   * Side-task models: a separate model for each side task, with
   * its own fallback. Summarising (conversation compaction) tries this chain,
   * then the turn's own model. Vision describes an attached image when the
   * turn's model cannot see; only models that accept images may be in it, and
   * with no chain the image is withheld as before.
   */
  import { api, ApiError } from "../../api";
  import type { ModelsView as ModelsData } from "../../apiTypes";
  import { profileLabel } from "../../format";
  import { modelName } from "../../modelPresentation";

  let { models, onreload }: { models: ModelsData; onreload: () => Promise<void> } = $props();

  type Task = "summarise" | "vision";
  const TASKS: { task: Task; title: string; help: string }[] = [
    {
      task: "summarise",
      title: "Summarising",
      help: "Compacts a long conversation. Tried in order; the turn's own model is the last resort.",
    },
    {
      task: "vision",
      title: "Vision",
      help: "Describes an attached image when the turn's model cannot see. Only models that accept images.",
    },
  ];

  /** Every concrete model the owner has set up, once each. */
  const options = $derived(
    (models.chat_profiles ?? []).filter((p) => p.model && !p.model.includes("<")),
  );
  type Entry = { profile_id: string; model: string };
  const chainOf = (task: Task): Entry[] =>
    ((models.side_tasks?.[task] ?? []) as Record<string, string>[]).map((entry) => ({
      profile_id: entry.profile_id ?? "",
      model: entry.model ?? "",
    }));
  const labelOf = (entry: { profile_id: string; model: string }) => {
    const profile = models.profiles.find((p) => p.profile_id === entry.profile_id);
    return `${profile ? profileLabel(profile) : entry.profile_id} · ${modelName(entry.model)}`;
  };

  let choice = $state<Record<Task, string>>({ summarise: "", vision: "" });
  let busy = $state<Task | null>(null);
  let note = $state<Record<Task, string>>({ summarise: "", vision: "" });

  const REFUSALS: Record<string, string> = {
    side_task_model_lacks_vision: "That model does not accept images, so it cannot describe one.",
    side_task_chain_too_long: "A side task holds at most three models.",
    side_task_model_required: "Choose a concrete model.",
  };

  async function save(task: Task, chain: { profile_id: string; model: string }[]) {
    busy = task;
    note = { ...note, [task]: "" };
    try {
      await api.setSideTaskModels(task, chain);
      await onreload();
      note = { ...note, [task]: chain.length ? "Saved." : "Cleared — the turn's own model is used." };
    } catch (e) {
      const code = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      note = { ...note, [task]: REFUSALS[code] ?? `Could not save${code ? ` (${code})` : ""}.` };
    } finally {
      busy = null;
    }
  }

  function add(task: Task) {
    if (!choice[task]) return;
    const [profile_id, model] = JSON.parse(choice[task]) as [string, string];
    const chain = chainOf(task);
    if (chain.some((entry) => entry.profile_id === profile_id && entry.model === model)) return;
    choice = { ...choice, [task]: "" };
    void save(task, [...chain, { profile_id, model }]);
  }
</script>

<section class="side-tasks" aria-labelledby="side-tasks-title">
  <h3 id="side-tasks-title">Side-task models</h3>
  <p class="lead">A separate model for work a turn needs done on the side, each with its own fallback.</p>
  {#each TASKS as row (row.task)}
    {@const chain = chainOf(row.task)}
    <div class="task" role="group" aria-label={`${row.title} models`}>
      <div class="task-head">
        <strong>{row.title}</strong>
        <span>{row.help}</span>
      </div>
      {#if chain.length}
        <ol class="chain">
          {#each chain as entry, index (`${entry.profile_id}\u0000${entry.model}`)}
            <li>
              <span>{labelOf(entry)}</span>
              <button
                type="button"
                class="btn btn-ghost btn-sm"
                aria-label={`Remove ${labelOf(entry)} from ${row.title}`}
                disabled={busy !== null}
                onclick={() => void save(row.task, chain.filter((_, i) => i !== index))}>Remove</button
              >
            </li>
          {/each}
        </ol>
      {:else}
        <p class="empty">
          {row.task === "summarise" ? "Uses the turn's own model." : "None — images go unseen by a model that cannot see."}
        </p>
      {/if}
      {#if chain.length < 3}
        <div class="add">
          <select aria-label={`Add a ${row.title} model`} bind:value={choice[row.task]} disabled={busy !== null}>
            <option value="">Add a model…</option>
            {#each options as p (`${p.profile_id}\u0000${p.model}`)}
              <option value={JSON.stringify([p.profile_id, p.model])}>{profileLabel(p)} · {modelName(p.model)}</option>
            {/each}
          </select>
          <button type="button" class="btn btn-sm" disabled={!choice[row.task] || busy !== null} onclick={() => add(row.task)}
            >Add</button
          >
        </div>
      {/if}
      {#if note[row.task]}<p class="note" role="status">{note[row.task]}</p>{/if}
    </div>
  {/each}
</section>

<style>
  .side-tasks { display: grid; gap: .8rem; margin-top: 1.2rem; }
  .side-tasks h3 { margin: 0; }
  .lead, .empty, .note { margin: 0; color: var(--text-3); font-size: var(--text-sm); }
  .task { border: 1px solid var(--border); border-radius: var(--r-md); padding: .7rem .8rem; display: grid; gap: .5rem; }
  .task-head { display: grid; gap: .15rem; }
  .task-head span { color: var(--text-3); font-size: var(--text-sm); }
  .chain { margin: 0; padding-left: 1.2rem; display: grid; gap: .3rem; }
  .chain li span { margin-right: .5rem; }
  .add { display: flex; gap: .5rem; align-items: center; }
  .add select { flex: 1; min-width: 0; }
</style>
