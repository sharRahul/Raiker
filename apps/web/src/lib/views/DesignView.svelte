<script lang="ts">
  /**
   * Design — describe an image, and it answers with one.
   *
   * This was a form over a gallery: a textarea, two selects, a Generate button,
   * and a grid of results underneath. That shape is wrong for what the page
   * actually is. Asking a model for an image is the same act as asking it for
   * prose or for a patch — you say something, it answers, you look at the answer
   * and say the next thing — so it belongs beside Chat and Build in the
   * navigation and it uses their composer, not a second kind of input.
   *
   * The transcript reads oldest to newest, and a refusal is a turn in it rather
   * than an absence. Generating an image is a hosted model call, so it can be
   * refused by the capability gate, by an empty egress allowlist, or by a
   * missing credential — three states with three different remedies. The runtime
   * records every attempt, so the answer to "I pressed Generate and got nothing"
   * is in the thread, at the point it happened, and not in the audit log.
   */
  import { onMount, tick } from "svelte";
  import Composer from "../components/Composer.svelte";
  import Icon from "../components/Icon.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import { providerName, relativeTime } from "../format";
  import { runtimeBlock } from "../capabilityModel";
  import { imageCandidates, modelName } from "../modelPresentation";
  import type { CapabilityGate, ImageGeneration, ModelsView } from "../apiTypes";

  let view = $state<{ sizes: string[]; generations: ImageGeneration[] } | null>(null);
  let loadError = $state<string | null>(null);
  let gates = $state<CapabilityGate[]>([]);
  let models = $state<ModelsView | null>(null);
  let busy = $state(false);
  let failure = $state<string | null>(null);
  let threadEl = $state<HTMLDivElement | undefined>();

  let prompt = $state("");
  let size = $state("1024x1024");

  /** Said before the press, through the helper every other gated surface uses. */
  const block = $derived(
    runtimeBlock(
      gates.find((gate) => gate.capability === "image_generation"),
      "Image generation",
    ),
  );

  /**
   * Every image model any connected provider declares — one entry per model,
   * not per provider.
   *
   * This is a *model* picker, which is what the surface always needed and did
   * not have: the previous control listed providers, so a provider offering two
   * image models could only ever expose one of them. Which providers are
   * configured for chat has no bearing on it — a profile appears here if and
   * only if it declares a model that draws.
   */
  const imageChoices = $derived(
    (models?.profiles ?? []).flatMap((profile) =>
      imageCandidates(profile.image_models ?? []).map((model) => ({
        key: `${profile.profile_id}::${model}`,
        profileId: profile.profile_id,
        provider: profile.provider,
        model,
      })),
    ),
  );

  /** The pick, as `profile_id::model`. */
  let choiceKey = $state("");
  const choice = $derived(
    imageChoices.find((item) => item.key === choiceKey) ?? imageChoices[0] ?? null,
  );

  /**
   * Oldest first, the way every other transcript in the product reads. The API
   * answers newest-first because it was written for a gallery.
   */
  const turns = $derived([...(view?.generations ?? [])].reverse());

  const REASONS: Record<string, string> = {
    disabled_by_capability_gate:
      "Image generation is turned off. Turn it on in Permissions.",
    "egress_denied:no_allowlist":
      "No provider host is allowlisted, so nothing may leave this machine. Set RAIKER_MODEL_EGRESS_ALLOWLIST.",
    image_provider_credential_missing:
      "No credential is saved for that provider. Connect it on the Models page.",
    image_model_missing: "That provider has no image model named for it.",
    image_refused_by_provider: "The provider refused this prompt under its own policy.",
    image_too_large: "The provider returned an image larger than this workspace stores.",
    prompt_too_long: "That prompt is too long.",
    image_response_missing_data: "The provider answered without an image.",
    image_response_not_base64: "The provider's image could not be decoded.",
    not_authorized_human: "Only you can generate an image.",
  };

  function readable(code: string | null): string {
    if (!code) return "Refused";
    if (REASONS[code]) return REASONS[code];
    if (code.startsWith("egress_denied:"))
      return `${code.slice("egress_denied:".length)} is not on the model egress allowlist.`;
    if (code.startsWith("image_provider_unsupported"))
      return "That provider has no governed image endpoint in this build.";
    if (code.startsWith("unsupported_size:")) return "That size is not offered.";
    if (code.startsWith("http_error:"))
      return `The provider answered with an error (${code.split(":")[1]}).`;
    if (code.startsWith("fetch_failed")) return "The provider could not be reached.";
    return code;
  }

  async function toLatest() {
    await tick();
    if (threadEl) threadEl.scrollTop = threadEl.scrollHeight;
  }

  async function load() {
    try {
      view = await api.images();
      loadError = null;
      if (view.sizes.length && !view.sizes.includes(size)) size = view.sizes[0];
    } catch (error) {
      view = null;
      loadError = error instanceof ApiError ? error.message : "Generations are unavailable.";
    }
    // Neither of these may take the page down: the thread is still readable
    // without them, and a failed gate read must not be reported as a refusal.
    try {
      gates = await api.capabilityGates();
    } catch {
      gates = [];
    }
    try {
      models = await api.models();
      if (!choiceKey && imageChoices.length) choiceKey = imageChoices[0].key;
    } catch {
      models = null;
    }
    await toLatest();
  }

  async function generate() {
    if (!prompt.trim() || choice === null || busy || block.kind !== "none") return;
    busy = true;
    failure = null;
    try {
      await api.generateImage({
        profile_id: choice.profileId,
        prompt: prompt.trim(),
        size,
        model: choice.model,
      });
      prompt = "";
    } catch (error) {
      failure =
        error instanceof ApiError ? readable(error.reasonCode ?? null) : "That request failed.";
    } finally {
      busy = false;
      // Reloaded either way: a refusal is recorded, so the thread is where the
      // owner reads what happened even when this attempt failed.
      await load();
    }
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void generate();
    }
  }

  onMount(load);
</script>

<div class="design">
  <div class="thread" bind:this={threadEl}>
    <p class="page-lead">
      Describe an image and a connected image model draws it. The prompt leaves this
      machine; the image is stored here.
      <GuideLink route="design" label="How image generation is governed" />
    </p>

    {#if block.kind !== "none"}
      <p class="notice" role="status">
        {block.reason}
        {#if block.href}<a href={block.href}>{block.linkLabel}</a>{/if}
      </p>
    {/if}

    {#if loadError}
      <PageState state="error" title="Couldn't read your generations" detail={loadError} />
    {:else if view === null}
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
  </div>

  <Composer
    ariaLabel="Image composer"
    inputId="design-prompt"
    inputLabel="Describe the image"
    bind:value={prompt}
    inputProps={{
      placeholder: "Describe the image you want…",
      title: "Enter to generate, Shift+Enter for a new line",
      disabled: busy,
      onkeydown: onKeydown,
    }}
    onsubmit={() => void generate()}
  >
    {#snippet left()}
      <!-- Always here, whatever is configured. Hiding it made "no image model is
           connected" indistinguishable from "this page has no model control",
           and the second reading is the one an owner actually reached. When
           there is nothing to choose it says so in the control itself rather
           than leaving a gap where a control belongs. -->
      <label class="composer-scope">
        <span class="sr-only">Image model</span>
        <Icon name="models" size="sm" />
        {#if imageChoices.length > 0}
          <select class="bar-select" bind:value={choiceKey} aria-label="Image model" disabled={busy}>
            {#each imageChoices as item (item.key)}
              <option value={item.key}>
                {providerName(item.provider)} · {modelName(item.model)}
              </option>
            {/each}
          </select>
        {:else}
          <a class="bar-select bar-empty" href="#/models">No image model — connect one</a>
        {/if}
      </label>
      {#if (view?.sizes ?? []).length > 0}
        <label class="composer-scope">
          <span class="sr-only">Size</span>
          <select class="bar-select" bind:value={size} aria-label="Size" disabled={busy}>
            {#each view!.sizes as option (option)}
              <option value={option}>{option}</option>
            {/each}
          </select>
        </label>
      {/if}
    {/snippet}

    {#snippet right()}
      <button
        type="submit"
        class="btn btn-primary send"
        disabled={busy || !prompt.trim() || choice === null || block.kind !== "none"}
        aria-label={busy ? "Generating" : "Generate"}
      >
        <Icon name={busy ? "clock" : "send"} size="sm" />
        <span class="send-label">{busy ? "Generating…" : "Generate"}</span>
      </button>
    {/snippet}

    {#snippet footer()}
      {#if failure}<p class="error" role="alert">{failure}</p>{/if}
    {/snippet}

    {#snippet hint()}
      Enter generates · Shift+Enter adds a line
    {/snippet}
  </Composer>
</div>

<style>
  /* The same frame Chat uses: the thread takes the room the shell gives it and
     scrolls, the composer stays on the floor of the page. */
  .design {
    display: flex;
    flex-direction: column;
    height: var(--content-h);
    min-height: 0;
  }
  .thread {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
  .turns {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-5);
  }
  .turn {
    display: grid;
    gap: var(--space-2);
    justify-items: start;
  }
  /* The prompt reads as the thing you said, in the same bubble grammar as a
     Chat message, so the pairing is legible without a label on either half. */
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
  .answer {
    display: grid;
    gap: 0.35rem;
    max-width: min(32rem, 100%);
    padding: var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
  }
  .refused {
    border-color: var(--warn-border);
    background: var(--warn-soft);
  }
  .shot {
    display: block;
    border-radius: var(--r-sm);
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
  /* The empty state of the model control: shaped like the select it replaces so
     the bar keeps its rhythm, and a link because the fix is on another page. */
  .bar-empty {
    display: inline-flex;
    align-items: center;
    color: var(--text-3);
    text-decoration: none;
    white-space: nowrap;
  }
  .bar-empty:hover {
    color: var(--accent);
    border-color: var(--accent-border);
  }
  .notice { color: var(--text-2); }
  .notice a { margin-left: 0.35rem; }

  @media (max-width: 63.9rem) {
    .design { height: auto; min-height: var(--content-h); }
    .thread { overflow-y: visible; }
  }
</style>
