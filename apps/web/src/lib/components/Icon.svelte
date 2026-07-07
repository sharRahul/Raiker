<script lang="ts">
  import { ICON_PATHS, type IconName } from "../icons";

  let {
    name,
    size = 18,
    label = null,
  }: { name: IconName; size?: number; label?: string | null } = $props();

  const paths = $derived(ICON_PATHS[name]);
</script>

<svg
  width={size}
  height={size}
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
    <path {d} />
  {/each}
</svg>
