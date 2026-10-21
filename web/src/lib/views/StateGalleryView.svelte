<script lang="ts">
  /**
   * QUI-G03 — the state gallery. Development builds only (`#/state-gallery`;
   * `routeFromHash` refuses it in a production build).
   *
   * Every shared piece in each state it can be in — empty, loading, working,
   * needs permission, error and done — on one page, so a change to a token or
   * a component can be checked in every state, in light and in dark, without
   * arranging a workspace that happens to be in each. Nothing here talks to
   * the API: TurnControl is given no session, so its Stop cannot be sent.
   */
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import StatTile from "../components/StatTile.svelte";
  import TurnControl from "../components/TurnControl.svelte";
  import ChatContextPanel from "../components/ChatContextPanel.svelte";
  import { applyTheme } from "../theme";

  // The owner's own theme choice comes back when the gallery is left.
  const ownTheme = document.documentElement.dataset.theme;
  let theme = $state<"light" | "dark">(ownTheme === "dark" ? "dark" : "light");
  $effect(() => applyTheme(theme));
  $effect(() => () => {
    if (ownTheme === undefined) delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = ownTheme;
  });

  const STATES = ["empty", "loading", "working", "needs-permission", "error", "done"] as const;
  const TITLES: Record<(typeof STATES)[number], string> = {
    empty: "Empty",
    loading: "Loading",
    working: "Working",
    "needs-permission": "Needs permission",
    error: "Error",
    done: "Done",
  };
</script>

<section class="gallery" aria-labelledby="gallery-title">
  <header class="gallery-head">
    <h2 id="gallery-title">State gallery</h2>
    <div class="theme-switch" role="radiogroup" aria-label="Theme">
      {#each ["light", "dark"] as const as choice (choice)}
        <label><input type="radio" name="gallery-theme" value={choice} bind:group={theme} /> {choice === "light" ? "Light" : "Dark"}</label>
      {/each}
    </div>
  </header>

  {#each STATES as state (state)}
    <section class="state-row" aria-labelledby={`state-${state}`} data-state={state}>
      <h3 id={`state-${state}`}>{TITLES[state]}</h3>
      <div class="specimens">
        {#if state === "empty"}
          <EmptyState icon="tasks" title="No tasks yet" body="Tasks you start or schedule appear here." />
          <PageState state="empty" title="Nothing here yet" />
          <ChatContextPanel files={[]} plan={null} sources={[]} activity={[]} onclose={() => {}} />
        {:else if state === "loading"}
          <PageState state="loading" title="Loading tasks…" />
          <PageState state="loading" title="Loading tasks…" lines={3} />
        {:else if state === "working"}
          <TurnControl sessionId={null} activity="Reading 2 emails from Anna" />
          <Badge variant="active" />
          <StatTile label="In progress" value={2} detail="Two runs are working." tone="accent" />
        {:else if state === "needs-permission"}
          <div class="decision" data-testid="gallery-decision">
            <strong>Review send email</strong>
            <span>Sends on your behalf · waiting 2 min</span>
          </div>
          <Badge variant="blocked" label="Waiting for you" />
          <StatTile label="Decisions" value={1} detail="One decision is waiting." tone="warn" href="#/approvals" linkLabel="Decide" />
        {:else if state === "error"}
          <PageState state="error" title="Couldn't read your tasks" detail="Refresh to try again. Nothing was started or changed." />
          <StatTile label="Health check" value="—" detail="Not read yet." tone="danger" />
        {:else}
          <Badge variant="done" />
          <StatTile label="This week" value="3" detail="Three outcomes finished." tone="ok" />
          <p class="outcome">Completed · 2 steps</p>
        {/if}
      </div>
    </section>
  {/each}
</section>

<style>
  .gallery { display: grid; gap: var(--space-5); max-width: 61.25rem; }
  .gallery-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
  .gallery-head h2 { margin: 0; }
  .theme-switch { display: flex; gap: var(--space-3); font-size: var(--text-sm); }
  .state-row { display: grid; gap: var(--space-2); padding-top: var(--space-3); border-top: 1px solid var(--border); }
  .state-row h3 { margin: 0; font-size: var(--text-md); }
  .specimens { display: grid; grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr)); gap: var(--space-3); align-items: start; }
  .decision {
    display: grid; gap: 0.15rem; padding: var(--space-3);
    border: 1px solid var(--warn-border); border-radius: var(--r-md); background: var(--surface);
  }
  .decision span, .outcome { font-size: var(--text-sm); color: var(--text-2); }
  .outcome { margin: 0; }
</style>
