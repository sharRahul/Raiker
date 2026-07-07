<script lang="ts">
  // The Raiker mark: an "R" monogram inside a soft shield — governed and secure by design.
  let { size = 28 }: { size?: number } = $props();
</script>

<svg width={size} height={size} viewBox="0 0 32 32" fill="none" role="img" aria-label="Raiker">
  <path
    d="M16 2.5 27 7v8.2c0 6.6-4.6 11.5-11 14.3C9.6 26.7 5 21.8 5 15.2V7l11-4.5Z"
    fill="var(--accent-soft)"
    stroke="var(--accent)"
    stroke-width="1.8"
    stroke-linejoin="round"
  />
  <path
    d="M12.2 22V10h4.6a3.6 3.6 0 0 1 1.3 7l3 5h-3.2l-2.6-4.6h-.5V22h-2.6Zm2.6-7h1.9a1.4 1.4 0 0 0 0-2.8h-1.9V15Z"
    fill="var(--accent)"
  />
</svg>
