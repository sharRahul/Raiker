<script lang="ts">
  /**
   * C6 — what an answer was drawn from, under the answer.
   *
   * Two different claims live here and the strip keeps them apart, because
   * conflating them would be the dishonest version of provenance:
   *
   * * **The ledger is a fact.** Every chip is a source the runtime really
   *   recorded — a governed tool call that returned material, or a file the
   *   owner attached. It exists whether or not the model mentioned it.
   * * **A citation is a claim.** A chip the model actually cited (`[s1]` in its
   *   answer) is marked as cited. That is the model saying "this sentence rests
   *   on that"; it is not something Raiker can verify, so it is shown as what
   *   it is rather than promoted to a fact.
   *
   * Clicking a chip opens the source at the passage the turn used. Nothing is
   * fetched until one is clicked.
   */
  import Icon from "./Icon.svelte";
  import type { IconName } from "../icons";
  import type { TurnSourceView } from "../apiTypes";

  let {
    sources,
    citedIds = new Set<string>(),
    openSourceId = null,
    onopen,
  }: {
    sources: TurnSourceView[];
    /** Source ids the model actually cited in this answer. */
    citedIds?: ReadonlySet<string>;
    /** The source currently open in the inspector, for `aria-expanded`. */
    openSourceId?: string | null;
    onopen: (source: TurnSourceView) => void;
  } = $props();

  const KIND_ICONS: Record<string, IconName> = {
    file: "file",
    attachment: "file",
    repository: "branch",
    email: "send",
    calendar: "clock",
    chat_tool: "chat",
    connector: "connections",
    web: "search",
    memory: "spark",
    skill: "code",
    subagent: "eye",
  };

  const KIND_LABELS: Record<string, string> = {
    file: "Workspace file",
    attachment: "Attached file",
    repository: "Repository",
    email: "Email",
    calendar: "Calendar",
    chat_tool: "Chat tool",
    connector: "Connector",
    web: "Web",
    memory: "Memory",
    skill: "Skill",
    subagent: "Subagent",
  };

  function icon(kind: string): IconName {
    return KIND_ICONS[kind] ?? "file";
  }

  function hint(source: TurnSourceView): string {
    const parts = [KIND_LABELS[source.kind] ?? source.kind, source.locator, source.detail];
    return parts.filter((part) => part !== "" && part !== undefined).join(" · ");
  }
</script>

{#if sources.length > 0}
  <section class="sources" aria-label="Sources this answer used">
    <h4>Sources</h4>
    <ul>
      {#each sources as source (source.source_id)}
        <li>
          <button
            type="button"
            class="source-chip"
            class:cited={citedIds.has(source.source_id)}
            class:inert={!source.openable}
            disabled={!source.openable}
            aria-expanded={openSourceId === source.source_id}
            title={hint(source)}
            onclick={() => onopen(source)}
          >
            <span class="marker" aria-hidden="true">{source.source_id.slice(1)}</span>
            <Icon name={icon(source.kind)} size="sm" />
            <span class="label">{source.title}</span>
            {#if citedIds.has(source.source_id)}
              <span class="sr-only">— cited in this answer</span>
            {/if}
          </button>
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .sources {
    margin: 0.5rem 0 0;
  }
  h4 {
    margin: 0 0 0.3rem;
    font-size: var(--text-2xs);
    font-weight: 600;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    color: var(--text-3);
  }
  ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .source-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    max-width: 22rem;
    padding: 0.2rem 0.5rem 0.2rem 0.25rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    color: var(--text-2);
    font-size: var(--text-xs);
    cursor: pointer;
  }
  .source-chip:hover:not(:disabled),
  .source-chip:focus-visible:not(:disabled) {
    border-color: var(--accent-border);
    color: var(--text-1);
  }
  /* A chip the model cited carries the accent; one it did not is still shown,
     because the ledger is the fact and the citation is only the claim. */
  .source-chip.cited {
    border-color: var(--accent-border);
    background: var(--accent-soft);
    color: var(--accent-strong);
  }
  .source-chip.inert {
    cursor: default;
    opacity: 0.72;
  }
  .marker {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.15rem;
    height: 1.15rem;
    border-radius: var(--r-pill);
    background: var(--sunken);
    font-size: var(--text-2xs);
    font-weight: 700;
    line-height: 1;
  }
  .cited .marker {
    background: var(--accent);
    color: var(--text-inverse);
  }
  .label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
