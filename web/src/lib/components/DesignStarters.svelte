<script lang="ts">
  export interface Starter { name: string; prompt: string; needsImage?: boolean }
  let { onchoose, editAvailable = false }: { onchoose: (starter: Starter) => void; editAvailable?: boolean } = $props();
  const starters: Starter[] = [
    { name: "Create an image", prompt: "Create an image of " },
    { name: "Edit an image", prompt: "Edit this image: ", needsImage: true },
    { name: "Product mockup", prompt: "Create a premium product mockup with realistic lighting and a clean background: " },
    { name: "Social media graphic", prompt: "Create a social media graphic with a clear focal point for " },
    { name: "Poster", prompt: "Create a modern, professional poster for [event or subject], using a clear visual hierarchy and compelling typography." },
    { name: "Logo concept", prompt: "Explore a distinctive logo concept for " },
    { name: "Cinematic portrait", prompt: "Create a cinematic portrait featuring dramatic lighting, natural detail and professional composition." },
    { name: "Remove background", prompt: "Remove the background from this image while preserving the main subject and fine details.", needsImage: true },
  ];
</script>
<section class="starters" aria-labelledby="starters-heading">
  <h2 id="starters-heading">What would you like to create?</h2>
  <div class="grid">
    {#each starters as starter, index (starter.name)}
      <button type="button" class="starter" disabled={!!starter.needsImage && !editAvailable} title={starter.needsImage && !editAvailable ? "Choose a model that supports image editing" : undefined} onclick={() => onchoose(starter)}>
        <span class="preview preview-{index}" aria-hidden="true"></span>
        <span class="name">{starter.name}</span>
        {#if starter.needsImage}<span class="detail">{editAvailable ? "Requires an image" : "Requires an editing model"}</span>{/if}
      </button>
    {/each}
  </div>
</section>
<style>
  .starters { width: min(100%, 50rem); margin: auto; padding: var(--space-4) 0; }
  h2 { text-align: center; color: var(--text-1); font-size: var(--text-xl); margin: 0 0 var(--space-4); }
  .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); }
  .starter { display: flex; flex-direction: column; align-items: stretch; justify-content: flex-start; min-width: 0; padding: 0; border: 0; text-align: left; background: transparent; color: var(--text-1); font: inherit; cursor: pointer; }
  .starter:disabled { opacity: .6; cursor: not-allowed; }
  .starter:focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; border-radius: var(--r-sm); }
  .preview { display: block; aspect-ratio: 4 / 3; border-radius: var(--r-md); background-image: url("/design-starters.png"); background-size: 400% auto; border: 1px solid var(--border); }
  .preview-0 { background-position: 0% 16.667%; }
  .preview-1 { background-position: 33.333% 16.667%; }
  .preview-2 { background-position: 66.667% 16.667%; }
  .preview-3 { background-position: 100% 16.667%; }
  .preview-4 { background-position: 0% 83.333%; }
  .preview-5 { background-position: 33.333% 83.333%; }
  .preview-6 { background-position: 66.667% 83.333%; }
  .preview-7 { background-position: 100% 83.333%; }
  .name, .detail { display: block; margin-top: var(--space-1); }
  .name { font-weight: 600; font-size: var(--text-sm); }
  .detail { color: var(--text-3); font-size: var(--text-xs); }
  @media (max-width: 50rem) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
