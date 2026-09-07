<script lang="ts">
  /**
   * Mounts one code-split route (BUG-74).
   *
   * A route already in the module cache renders on the same tick, so navigating
   * back and forth never flashes. Only the very first visit to a route whose
   * chunk has not been prefetched yet can await, and that window is deliberately
   * silent rather than filled with a spinner: a skeleton that appears for 30 ms
   * is more disruptive than nothing appearing for 30 ms.
   */
  import {
    loadRoute,
    peekRoute,
    type LazyRouteId,
    type RouteComponent,
  } from "../routeComponents";

  let {
    route,
    props = {},
  }: { route: LazyRouteId; props?: Record<string, unknown> } = $props();

  let loaded = $state<RouteComponent | null>(null);
  let failed = $state(false);

  $effect(() => {
    const requested = route;
    const cached = peekRoute(requested);
    if (cached !== null) {
      loaded = cached;
      failed = false;
      return;
    }
    loaded = null;
    failed = false;
    let current = true;
    void loadRoute(requested)
      .then((component) => {
        // A route the owner has already navigated away from must not replace
        // whatever they are looking at now.
        if (current && route === requested) loaded = component;
      })
      .catch(() => {
        if (current && route === requested) failed = true;
      });
    return () => {
      current = false;
    };
  });

  const Loaded = $derived(loaded);
</script>

{#if Loaded !== null}
  <Loaded {...props} />
{:else if failed}
  <section class="route-error" role="alert">
    <h2>This page could not be loaded</h2>
    <p>
      Part of the workspace failed to download. Reload the page; if it keeps happening, the
      local server may have been restarted mid-session.
    </p>
  </section>
{/if}

<style>
  .route-error {
    padding: var(--space-5);
    border: 1px solid var(--warn-border);
    border-radius: var(--r-md);
    background: var(--warn-soft);
  }
  .route-error h2 {
    margin: 0 0 var(--space-2);
  }
  .route-error p {
    margin: 0;
    color: var(--text-2);
  }
</style>
