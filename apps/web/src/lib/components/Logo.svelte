<script lang="ts">
  // The Raiker mark: the governed-core sphere with the Γ_ prompt eye (rendered
  // PNG). Light theme uses the floating-orb mark; dark theme uses the
  // light-tiled mark so it reads on a dark surface.
  let { size = 28 }: { size?: number } = $props();
</script>

<span class="logo" role="img" aria-label="Raiker" style="--sz:{size}px"></span>

<style>
  .logo {
    display: block;
    width: var(--sz);
    height: var(--sz);
    background: center / contain no-repeat url("/raiker-mark.png?v=20260714");
  }
  :global(:root[data-theme="dark"]) .logo {
    background-image: url("/raiker-mark-dark.png?v=20260714");
  }
  :global(:root[data-theme="light"]) .logo {
    background-image: url("/raiker-mark.png?v=20260714");
  }
  @media (prefers-color-scheme: dark) {
    :global(:root:not([data-theme])) .logo {
      background-image: url("/raiker-mark-dark.png?v=20260714");
    }
  }
</style>
