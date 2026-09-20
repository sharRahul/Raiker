<script lang="ts">
  /*
   * Design's canvas, now that there is something to compose.
   *
   * This component used to be one region and said so: "five of them describe a
   * canvas runtime Raiker does not have", because the governed image endpoint
   * took a prompt and returned one picture. BUG-277 built that runtime — a
   * request can name a prior generation as its subject, ask for several
   * pictures, and the store records what each was made from — so the regions the
   * review asks for now have real relationships to draw and are no longer empty
   * shells.
   *
   * Three regions, and the review's rule about which dominates:
   *
   *   Assets  │  Canvas / selected asset  │  Inspector
   *           │                           │   versions, variations, detail
   *
   * The canvas is the largest intentional region whenever an asset exists. With
   * nothing selected it is the history — what has been generated, in order, with
   * the prompt that asked for it — because a canvas with no object on it is not
   * a canvas, and an empty three-pane frame would be chrome pretending to be a
   * workspace.
   *
   * What is still absent, and deliberately: selection within an image, masking,
   * outpainting. Those need provider capabilities behind the governed endpoint
   * that this build does not have, and the composer redesign's acceptance test
   * 19 settles what to do about that — every exposed action reaches a real
   * runtime path or is omitted. A crop tool that cannot crop is worse than no
   * crop tool, because it looks like a promise.
   */
  import Icon from "./Icon.svelte";
  import PageState from "./PageState.svelte";
  import { api } from "../api";
  import type { ImageGeneration } from "../apiTypes";
  import { relativeTime } from "../format";
  import {
    designAssets,
    KIND_LABEL,
    refusalsFor,
    variationSet,
    versionChain,
  } from "../designAssets";

  let {
    turns,
    loading = false,
    loadError = null,
    readable,
    sizedProviders = undefined,
    selectedId = $bindable(null),
  }: {
    turns: ImageGeneration[];
    loading?: boolean;
    loadError?: string | null;
    /**
     * REM-DESIGN-01 — the providers whose governed request carries the size.
     * `undefined` on a host older than the field, which makes no claim either
     * way; the detail then prints the recorded value as it always did.
     */
    sizedProviders?: string[];
    /** The view's own plain-English reading of a refusal's reason code. */
    readable: (code: string | null) => string;
    /**
     * The asset the next instruction is about. Bindable because the composer
     * above needs it too: it is what turns **Generate** into **Edit**, and a
     * selection the button cannot see would be a selection that means nothing.
     */
    selectedId?: string | null;
  } = $props();

  const assets = $derived(designAssets(turns));

  /** Whether this generation's size is a request Raiker actually made. */
  function sizeWasSent(generation: ImageGeneration): boolean {
    if (sizedProviders === undefined) return true;
    return sizedProviders.includes(generation.provider);
  }
  const selected = $derived(
    selectedId === null
      ? null
      : (assets.find((asset) => asset.generation.generation_id === selectedId) ?? null),
  );
  const versions = $derived(selectedId ? versionChain(turns, selectedId) : []);
  const variations = $derived(selectedId ? variationSet(turns, selectedId) : []);
  const refusals = $derived(selectedId ? refusalsFor(turns, selectedId) : []);

  // A selection that no longer exists is not a selection. Clearing it here
  // rather than rendering an empty canvas keeps the button's word honest.
  $effect(() => {
    if (selectedId !== null && selected === null) selectedId = null;
  });

  const shot = (generation: ImageGeneration) => api.imageBytesUrl(generation.generation_id);
</script>

{#if loadError}
  <PageState state="error" title="Couldn't read your generations" detail={loadError} />
{:else if loading}
  <PageState state="loading" title="Reading your generations…" />
{:else if assets.length === 0 && turns.length === 0}
  <PageState
    state="empty"
    title="Nothing generated yet"
    detail="Describe an image below. What you generate is stored in this workspace."
  />
{:else if selected === null}
  <!-- No object, so no three-pane frame: the history *is* the page. Selecting
       an asset is what turns this surface into a canvas. -->
  <ol class="turns">
    {#each turns as item (item.generation_id)}
      <li class="turn">
        <p class="asked">{item.prompt}</p>
        <div class="answer" class:refused={item.status !== "ok"}>
          {#if item.has_image}
            <button
              type="button"
              class="shot"
              onclick={() => (selectedId = item.generation_id)}
              aria-label={`Open ${item.prompt} on the canvas`}
            >
              <img src={shot(item)} alt={item.prompt} loading="lazy" />
            </button>
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
{:else}
  <div class="workspace">
    <!-- Assets. Every picture this owner has, newest first, so the one being
         worked on can be swapped without leaving the canvas. -->
    <aside class="rail" aria-label="Assets">
      <!-- REM-DESIGN-02 — the strip says how many it is showing. Unnamed, a
           column of thumbnails reads as "some recent ones"; named and counted,
           it reads as the library it is, and an owner can tell at a glance
           whether the picture they are looking for is in it. -->
      <p class="rail-head">Assets <span>{assets.length}</span></p>
      <ol>
        {#each assets as asset (asset.generation.generation_id)}
          <li>
            <button
              type="button"
              class="thumb"
              class:current={asset.generation.generation_id === selectedId}
              aria-current={asset.generation.generation_id === selectedId ? "true" : undefined}
              onclick={() => (selectedId = asset.generation.generation_id)}
              title={asset.generation.prompt}
            >
              <img src={shot(asset.generation)} alt={asset.generation.prompt} loading="lazy" />
            </button>
          </li>
        {/each}
      </ol>
    </aside>

    <!-- The canvas. The largest region whenever an asset exists, which is the
         one composition rule the Design canvas states outright. -->
    <section class="canvas" aria-label="Canvas">
      <!-- Above the object, not below it. The canvas takes the room the shell
           gives it, so a control placed under the picture is one the owner has
           to scroll past the picture to find — and the way back out of a
           workspace should never be the thing you go looking for. -->
      <button type="button" class="clear" onclick={() => (selectedId = null)}>
        <Icon name="x" size="sm" />
        Back to everything
      </button>
      <img src={shot(selected.generation)} alt={selected.generation.prompt} />
      <p class="prompt">{selected.generation.prompt}</p>
    </section>

    <aside class="inspector" aria-label="Inspector">
      {#if versions.length > 1}
        <!-- The version strip. A chain of single parents, oldest first, showing
             only the line this asset is on — two edits of one picture are two
             branches, and putting both here would say one came after the other
             when neither came from the other. -->
        <section class="panel" aria-label="Versions">
          <h3>Versions</h3>
          <ol class="strip">
            {#each versions as version, index (version.generation_id)}
              <li>
                <button
                  type="button"
                  class="thumb small"
                  class:current={version.generation_id === selectedId}
                  onclick={() => (selectedId = version.generation_id)}
                  aria-label={`Version ${index + 1}: ${version.prompt}`}
                >
                  <img src={shot(version)} alt="" loading="lazy" />
                  <span class="ordinal">{index + 1}</span>
                </button>
              </li>
            {/each}
          </ol>
        </section>
      {/if}

      {#if variations.length > 1}
        <!-- The compare grid: the pictures one request returned together. -->
        <section class="panel" aria-label="Variations">
          <h3>From the same request</h3>
          <div class="grid">
            {#each variations as sibling (sibling.generation_id)}
              <button
                type="button"
                class="thumb"
                class:current={sibling.generation_id === selectedId}
                onclick={() => (selectedId = sibling.generation_id)}
                aria-label={`Variation: ${sibling.prompt}`}
              >
                <img src={shot(sibling)} alt="" loading="lazy" />
              </button>
            {/each}
          </div>
        </section>
      {/if}

      <section class="panel" aria-label="Detail">
        <h3>Detail</h3>
        <dl class="facts">
          <div>
            <dt>Made</dt>
            <dd>
              {KIND_LABEL[selected.generation.kind ?? "create"] ?? "Generated"}
              {#if selected.parent}
                <button
                  type="button"
                  class="link"
                  onclick={() => (selectedId = selected!.parent!.generation_id)}
                >{selected.parent.prompt}</button>
              {:else if selected.generation.source_generation_id}
                <!-- The source is gone. An origin, not a broken row: a source
                     can be forgotten while the images made from it remain. -->
                <span class="muted">an image no longer stored</span>
              {/if}
            </dd>
          </div>
          <div><dt>Model</dt><dd>{selected.generation.model}</dd></div>
          <!-- REM-DESIGN-01 — the recorded size is what was *asked for*, and
               for a provider Raiker sends no size to it was never asked. It
               printed here beside the picture as though it described it. -->
          <div>
            <dt>Size</dt>
            <dd>
              {#if sizeWasSent(selected.generation)}
                {selected.generation.size}
              {:else}
                <span class="muted">chosen by {selected.generation.provider}</span>
              {/if}
            </dd>
          </div>
          <div><dt>When</dt><dd>{relativeTime(selected.generation.created_at)}</dd></div>
        </dl>
        <a class="download" href={shot(selected.generation)} target="_blank" rel="noopener">
          Open full size
        </a>
      </section>

      {#if refusals.length > 0}
        <!-- Why the executor records lineage on refusals too: an edit that was
             denied is still something the owner asked of this picture. -->
        <section class="panel" aria-label="Refused attempts">
          <h3>Refused</h3>
          <ul class="refusals">
            {#each refusals as item (item.generation_id)}
              <li>{readable(item.reason_code)} <span class="muted">· {relativeTime(item.created_at)}</span></li>
            {/each}
          </ul>
        </section>
      {/if}
    </aside>
  </div>
{/if}

<style>
  .turns {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    /* Density, from the Work contract. An asset is looked at, so it
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
  /* The asset is the object, so it is not put in a card. A returned
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
    padding: 0;
    border: 1px solid var(--canvas-edge);
    border-radius: var(--r-sm);
    box-shadow: var(--canvas-lift);
    background: none;
    overflow: hidden;
    cursor: pointer;
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

  /* ── The canvas workspace ── */

  /* "the canvas must dominate whenever an asset exists", which is a
     statement about column widths: the rail and the inspector are sized to
     their content and the canvas takes what is left. On a spatial
     page the room a large display adds goes here, to the space. */
  .workspace {
    display: grid;
    grid-template-columns: 6rem minmax(0, 1fr) minmax(0, 17rem);
    gap: var(--space-4);
    align-items: start;
    min-height: 0;
  }
  /* REM-DESIGN-02 — the strip says what it is and how much of it there is. */
  .rail-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
    margin: 0 0 var(--space-2);
    color: var(--text-3);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 650;
  }
  .rail-head span { color: var(--text-2); }
  .rail ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
    max-height: 34rem;
    overflow-y: auto;
  }
  .thumb {
    display: block;
    width: 100%;
    padding: 0;
    border: 1px solid var(--canvas-edge);
    border-radius: var(--r-sm);
    background: var(--sunken);
    overflow: hidden;
    cursor: pointer;
    position: relative;
  }
  .thumb img {
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 1;
    object-fit: cover;
  }
  /* Which asset is on the canvas, said by more than colour: the accent ring is
     doubled by `aria-current` for assistive tech and by the ordinal in a
     version strip. */
  .thumb.current {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }
  .thumb:focus-visible {
    outline: 3px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .canvas {
    display: grid;
    gap: var(--space-2);
    justify-items: start;
    min-width: 0;
  }
  .canvas img {
    display: block;
    width: 100%;
    /* The object takes the room the shell gives it: a work surface is already
       full width, so on a large display this grows with the viewport rather
       than stopping at a laptop's height. */
    max-height: min(70vh, 48rem);
    object-fit: contain;
    border: 1px solid var(--canvas-edge);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .canvas .prompt {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
    max-width: var(--prose-measure);
  }
  .clear {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0;
    border: 0;
    background: none;
    color: var(--text-3);
    font: inherit;
    font-size: var(--text-xs);
    cursor: pointer;
  }
  .clear:hover { color: var(--accent); }
  .inspector {
    display: grid;
    gap: var(--space-4);
    align-content: start;
    min-width: 0;
  }
  .panel { display: grid; gap: var(--space-2); }
  .panel h3 {
    margin: 0;
    font-size: var(--text-2xs);
    font-weight: 750;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .strip {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: var(--space-2);
    overflow-x: auto;
  }
  .strip .thumb { width: 3.2rem; flex: none; }
  .ordinal {
    position: absolute;
    right: 2px;
    bottom: 2px;
    padding: 0 0.25rem;
    border-radius: var(--r-sm);
    background: var(--overlay);
    color: var(--brand-white);
    font-size: var(--text-2xs);
    font-variant-numeric: tabular-nums;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
  }
  .facts { display: grid; gap: 0.4rem; margin: 0; }
  .facts div { display: grid; grid-template-columns: 4.2rem minmax(0, 1fr); gap: var(--space-2); }
  .facts dt { color: var(--text-3); font-size: var(--text-xs); }
  .facts dd {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-xs);
    overflow-wrap: anywhere;
  }
  .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: var(--text-xs);
    text-align: left;
    cursor: pointer;
  }
  .muted { color: var(--text-3); }
  .download { font-size: var(--text-xs); }
  .refusals {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.3rem;
    color: var(--warn);
    font-size: var(--text-xs);
  }

  /* the Design canvas's mobile rule: do not squeeze three desktop panes onto a small
     screen. The canvas stays the object; the rail becomes a horizontal strip
     above it and the inspector follows underneath. */
  @media (max-width: 60rem) {
    .workspace { grid-template-columns: minmax(0, 1fr); }
    .rail ol {
      grid-auto-flow: column;
      grid-auto-columns: 4rem;
      max-height: none;
      overflow-x: auto;
    }
  }
</style>
