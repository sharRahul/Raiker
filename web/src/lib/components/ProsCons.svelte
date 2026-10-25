<script lang="ts">
  /**
   * QUI-A07 — two short lists per option.
   *
   * Pros and cons are headed in words and marked "+" and "−" as well as by
   * colour, so the two lists are told apart without either.
   */
  import type { ProsConsOption } from "../answerBlocks";

  let { caption = "", options }: { caption?: string; options: ProsConsOption[] } = $props();
</script>

<figure class="pros-cons">
  {#if caption}<figcaption>{caption}</figcaption>{/if}
  <div class="options" style={`--count: ${options.length}`}>
    {#each options as option, index (index)}
      <section class="option" aria-label={option.name}>
        <h4>{option.name}</h4>
        {#if option.pros.length > 0}
          <p class="list-head">Pros</p>
          <ul class="pros">
            {#each option.pros as entry, i (i)}<li><span class="mark" aria-hidden="true">+</span>{entry}</li>{/each}
          </ul>
        {/if}
        {#if option.cons.length > 0}
          <p class="list-head">Cons</p>
          <ul class="cons">
            {#each option.cons as entry, i (i)}<li><span class="mark" aria-hidden="true">−</span>{entry}</li>{/each}
          </ul>
        {/if}
      </section>
    {/each}
  </div>
</figure>

<style>
  .pros-cons { margin: 0; }
  figcaption { font-weight: 650; color: var(--text-1); margin-bottom: var(--space-2); }
  .options { display: grid; grid-template-columns: repeat(var(--count), minmax(0, 1fr)); gap: var(--space-3); }
  .option { min-width: 0; }
  h4 { margin: 0 0 var(--space-1); font-size: var(--text-md); color: var(--text-1); }
  .list-head { margin: var(--space-2) 0 var(--space-1); font-size: var(--text-xs); font-weight: 650; color: var(--text-2); }
  ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.25rem; }
  li { display: flex; gap: 0.4rem; color: var(--text-1); font-size: var(--text-sm); }
  .mark { font-weight: 700; width: 0.8rem; flex: none; }
  .pros .mark { color: var(--ok); }
  .cons .mark { color: var(--danger); }
</style>
