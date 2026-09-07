<script lang="ts">
  // BUG-37 — two additions to what was a single-weight stroke renderer.
  //
  // `size` now accepts a name from the optical scale (`sm`/`md`/`lg`/`xl`) as
  // well as a number, so a call site chooses a role rather than a pixel count.
  // Numbers still work, unchanged, because a handful of places genuinely need
  // an off-scale size to sit correctly inside a bespoke control.
  //
  // `filled` is the selected half of the filled/outline pair. These are stroke
  // icons, so filling the geometry itself would misread badly on the open ones
  // (a chevron, a pulse line); instead the same paths gain a soft wash behind
  // them. It reads as "this one is selected" at a glance, it cannot drift from
  // the outline because it *is* the outline, and it inherits `currentColor`, so
  // a selected nav row in either theme needs no second colour decision.
  import { ICON_PATHS, ICON_SIZE, type IconName, type IconSize } from "../icons";

  let {
    name,
    size = "md",
    label = null,
    filled = false,
  }: {
    name: IconName;
    size?: number | IconSize;
    label?: string | null;
    filled?: boolean;
  } = $props();

  const paths = $derived(ICON_PATHS[name]);
  const px = $derived(typeof size === "number" ? size : ICON_SIZE[size]);
</script>

<svg
  width={px}
  height={px}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.7"
  stroke-linecap="round"
  stroke-linejoin="round"
  role={label ? "img" : "presentation"}
  aria-label={label ?? undefined}
  aria-hidden={label ? undefined : "true"}
>
  {#each paths as d (d)}
    {#if filled}
      <path {d} fill="currentColor" fill-opacity="0.16" stroke="none" />
    {/if}
    <path {d} />
  {/each}
</svg>
