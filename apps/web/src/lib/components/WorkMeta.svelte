<script lang="ts">
  /**
   * VIS-14 — one object vocabulary for a piece of work.
   *
   * Threads, Tasks and Projects are three views of the same thing: work the
   * owner has going. They described it three different ways. A thread said
   * "3 turns · 2h ago" with the project as a bare tag; a task said
   * "Runs hourly · updated 2h ago" with its state as a `Badge`; a project said
   * "4 sessions". Same facts, three orders, three spellings, three styles — so
   * a task thread read as though it belonged to another application from the
   * chat thread beside it on Home.
   *
   * The vocabulary the review asks for, in this order:
   *
   *     project · state · last activity · what it runs on
   *
   * Each part is optional, because not every object has all of them, and the
   * ones an object does have appear in the same place with the same weight
   * wherever it is drawn. `state` stays a `Badge` — it is the one part that was
   * already consistent, and the badge is how every other surface says a state.
   */
  import Badge from "./Badge.svelte";
  import { relativeTime } from "../format";

  let {
    project = null,
    state = null,
    stateVariant = "metadata-only",
    activityAt = null,
    /** What "last activity" means for this object: "updated", "started", … */
    activityVerb = "updated",
    detail = null,
  }: {
    project?: string | null;
    state?: string | null;
    stateVariant?: string;
    activityAt?: string | null;
    activityVerb?: string;
    /** One extra fact this object has and the others do not — turns, sessions. */
    detail?: string | null;
  } = $props();
</script>

<p class="work-meta">
  {#if project}<span class="tag">{project}</span>{/if}
  {#if state}<Badge variant={stateVariant} label={state} />{/if}
  {#if detail}<span class="detail">{detail}</span>{/if}
  {#if activityAt}
    <span class="when" title={activityAt}>{activityVerb} {relativeTime(activityAt)}</span>
  {/if}
</p>

<style>
  .work-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  /* VIS-15 — a project is a neutral fact about where work lives, not a status,
     so it is a quiet chip rather than another coloured one. */
  .tag {
    padding: 0.05rem 0.4rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    color: var(--text-2);
  }
  .detail {
    color: var(--text-3);
  }
  .when {
    color: var(--text-3);
  }
</style>
