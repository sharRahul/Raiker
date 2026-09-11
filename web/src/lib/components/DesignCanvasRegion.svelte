<script lang="ts">
  /*
   * VIS2-20 — Design's canvas region, as its own component.
   *
   * The review names six regions Design should converge on. Five of them —
   * asset rail, variation grid, crop/selection inspector, version history,
   * export dialog — describe a canvas runtime Raiker does not have: the
   * governed image endpoint takes a prompt, a size and a model and returns one
   * picture (recorded in docs/plans/TO_BE_FIXED.md as BUG-277). Extracting
   * empty shells for them would be the projection-without-substance this
   * product refuses everywhere else.
   *
   * This is the region that exists: what has been generated, in order, with the
   * prompt that asked for it. It is extracted so the surface's *object* has a
   * component of its own — the thing VIS2-20 is actually for — and so a change
   * to how an asset is presented happens in one file rather than inside a
   * 700-line view.
   */
  import Icon from "./Icon.svelte";
  import PageState from "./PageState.svelte";
  import { api } from "../api";
  import type { ImageGeneration } from "../apiTypes";
  import { relativeTime } from "../format";

  let {
    turns,
    loading = false,
    loadError = null,
    readable,
  }: {
    turns: ImageGeneration[];
    loading?: boolean;
    loadError?: string | null;
    /** The view's own plain-English reading of a refusal's reason code. */
    readable: (code: string | null) => string;
  } = $props();
</script>

{#if loadError}
  <PageState state="error" title="Couldn't read your generations" detail={loadError} />
{:else if loading}
  <PageState state="loading" title="Reading your generations…" />
{:else if turns.length === 0}
  <PageState
    state="empty"
    title="Nothing generated yet"
    detail="Describe an image below. What you generate is stored in this workspace."
  />
{:else}
  <ol class="turns">
    {#each turns as item (item.generation_id)}
      <li class="turn">
        <p class="asked">{item.prompt}</p>
        <div class="answer" class:refused={item.status !== "ok"}>
          {#if item.has_image}
            <a
              class="shot"
              href={api.imageBytesUrl(item.generation_id)}
              target="_blank"
              rel="noopener"
            >
              <img src={api.imageBytesUrl(item.generation_id)} alt={item.prompt} loading="lazy" />
            </a>
          {:else}
            <p class="refusal">
              <Icon name="warning" size="sm" />
              {readable(item.reason_code)}
            </p>
          {/if}
          <p class="sub">{item.model} · {item.size} · {relativeTime(item.created_at)}</p>
        </div>
      </li>
    {/each}
  </ol>
{/if}

<style>
  .turns {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    /* VIS2-21 — density, from the Work contract. An asset is looked at, so it
       takes the middle: room around the object without a transcript's air. */
    gap: var(--surface-gap, var(--space-5));
  }
  .turn {
    display: grid;
    gap: var(--space-2);
  }
  .asked {
    margin: 0;
    justify-self: end;
    max-width: min(42rem, 85%);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--r-lg);
    background: var(--accent-soft);
    color: var(--text-1);
    font-size: var(--text-sm);
    overflow-wrap: anywhere;
  }
  /* VIS2-14 — the asset is the object, so it is not put in a card. A returned
     picture sits on the page with its own hairline boundary; only a *refusal*
     draws a box, because a refusal is a message rather than an image and needs
     somewhere to be said. */
  .answer {
    display: grid;
    gap: 0.35rem;
    max-width: min(32rem, 100%);
  }
  .refused {
    padding: var(--space-2);
    border: 1px solid var(--warn-border);
    border-radius: var(--r-lg);
    background: var(--warn-soft);
  }
  /* The boundary has to be obvious in both themes without being chrome: on a
     light ground a hairline plus the first shadow tier; on a dark one a lighter
     hairline and no shadow, because a shadow on near-black carries nothing.
     `--canvas-edge` and `--canvas-lift` hold that difference. */
  .shot {
    display: block;
    border: 1px solid var(--canvas-edge);
    border-radius: var(--r-sm);
    box-shadow: var(--canvas-lift);
    overflow: hidden;
  }
  .shot img {
    display: block;
    width: 100%;
    height: auto;
  }
  .refusal {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--warn);
    font-size: var(--text-sm);
  }
  .sub {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-xs);
  }
</style>
