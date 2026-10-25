<script lang="ts">
  // QUI-V04 — the Raiker mark: a rounded ring with one deliberate gap at about
  // half past one, so it reads as one bounded workspace with a single opening
  // and never as a "C" or a power icon. Drawn, not rendered: it takes the
  // accent of whichever theme is on. Never rotated or animated — a turning ring
  // would read as a spinner. An empty label marks it decorative, beside a
  // visible name.
  let { size = 28, label = "Raiker" }: { size?: number; label?: string } = $props();
</script>

<svg
  class="logo"
  width={size}
  height={size}
  viewBox="0 0 32 32"
  role={label ? "img" : undefined}
  aria-label={label || undefined}
  aria-hidden={label ? undefined : "true"}
  focusable="false"
>
  <path d="M26.72 13.53A11 11 0 1 1 18.47 5.28" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" />
</svg>

<style>
  .logo {
    display: block;
    flex: none;
    color: var(--accent);
  }
</style>
