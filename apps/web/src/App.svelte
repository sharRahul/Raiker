<script lang="ts">
  import { onMount } from "svelte";
  import Nav from "./lib/Nav.svelte";
  import RuntimeStatusBanner from "./lib/RuntimeStatusBanner.svelte";
  import StopSwitch from "./lib/StopSwitch.svelte";
  import { DEFAULT_ROUTE, NAV_ITEMS, routeFromHash } from "./lib/nav";
  import { runtimeStatusFixture } from "./fixtures/runtimeStatus";
  import Home from "./routes/Home.svelte";
  import Placeholder from "./routes/Placeholder.svelte";

  let current = $state(typeof window === "undefined" ? DEFAULT_ROUTE : routeFromHash(window.location.hash));
  const activeItem = $derived(NAV_ITEMS.find((item) => item.id === current) ?? NAV_ITEMS[0]);

  onMount(() => {
    const handler = () => {
      current = routeFromHash(window.location.hash);
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  });
</script>

<a class="skip-link" href="#main">Skip to content</a>

<div class="app-shell">
  <header class="topbar">
    <RuntimeStatusBanner status={runtimeStatusFixture} />
    <StopSwitch />
  </header>
  <div class="app-body">
    <Nav items={NAV_ITEMS} {current} />
    <main id="main" class="content" tabindex="-1">
      {#if current === "home"}
        <Home />
      {:else}
        <Placeholder title={activeItem.label} />
      {/if}
    </main>
  </div>
</div>

<style>
  .app-shell {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }
  .topbar {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.6rem 1rem;
    border-bottom: 1px solid #2a2a2e;
    background: #0a0a0d;
  }
  .app-body {
    display: flex;
    flex: 1;
    min-height: 0;
  }
  .content {
    flex: 1;
    padding: 1.25rem 1.5rem;
    overflow: auto;
  }
  .content:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: -2px;
  }
  .skip-link {
    position: absolute;
    left: -999px;
    top: 0;
    background: #1c2a3a;
    color: #cfe5ff;
    padding: 0.5rem 0.75rem;
    z-index: 100;
  }
  .skip-link:focus {
    left: 0.5rem;
    top: 0.5rem;
  }
</style>
