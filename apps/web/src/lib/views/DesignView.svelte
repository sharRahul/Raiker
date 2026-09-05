<script lang="ts">
  /**
   * Design — generate an image, and see what you have generated.
   *
   * The page is deliberately small: a prompt, a provider, a size, and a
   * gallery. What it does *not* do is hide the governed path underneath it.
   * Generating an image is a hosted model call, so it can be refused by the
   * capability gate, by an empty egress allowlist, or by a missing credential —
   * three different states with three different remedies, and a page that
   * collapsed them into "couldn't generate" would send the owner hunting.
   *
   * A refusal is a *record*, not an absence. The runtime writes one for every
   * attempt, so the gallery shows what was refused and why beside what worked.
   * An owner who pressed Generate and got nothing should find the answer here
   * rather than in the audit log.
   */
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import { relativeTime } from "../format";
  import { runtimeBlock } from "../capabilityModel";
  import { modelName } from "../modelPresentation";
  import type { CapabilityGate, ImageGeneration, ModelsView } from "../apiTypes";

  let view = $state<{ sizes: string[]; generations: ImageGeneration[] } | null>(null);
  let loadError = $state<string | null>(null);
  let gates = $state<CapabilityGate[]>([]);
  let models = $state<ModelsView | null>(null);
  let busy = $state(false);
  let failure = $state<string | null>(null);

  let prompt = $state("");
  let profileId = $state("");
  let size = $state("1024x1024");

  /** Said before the press, through the helper every other gated surface uses. */
  const block = $derived(
    runtimeBlock(
      gates.find((gate) => gate.capability === "image_generation"),
      "Image generation",
    ),
  );

  /**
   * Providers that can actually answer. A profile without an `image_model` has
   * no image endpoint in this build, and offering it would be an invitation to
   * a refusal.
   */
  const imageProfiles = $derived(
    (models?.profiles ?? []).filter((profile) => Boolean(profile.image_model)),
  );

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

  async function load() {
    try {
      view = await api.images();
      loadError = null;
      if (view.sizes.length && !view.sizes.includes(size)) size = view.sizes[0];
    } catch (error) {
      view = null;
      loadError = error instanceof ApiError ? error.message : "Generations are unavailable.";
    }
    // Neither of these may take the page down: the gallery is still readable
    // without them, and a failed gate read must not be reported as a refusal.
    try {
      gates = await api.capabilityGates();
    } catch {
      gates = [];
    }
    try {
      models = await api.models();
      if (!profileId && imageProfiles.length) profileId = imageProfiles[0].profile_id;
    } catch {
      models = null;
    }
  }

  async function generate(event: SubmitEvent) {
    event.preventDefault();
    if (!prompt.trim() || !profileId) return;
    busy = true;
    failure = null;
    try {
      await api.generateImage({ profile_id: profileId, prompt: prompt.trim(), size });
      prompt = "";
    } catch (error) {
      failure =
        error instanceof ApiError ? readable(error.reasonCode ?? null) : "That request failed.";
    } finally {
      busy = false;
      // Reloaded either way: a refusal is recorded, so the gallery is where the
      // owner reads what happened even when this attempt failed.
      await load();
    }
  }

  onMount(load);
</script>

<p class="page-lead">
  Generate images with a hosted image model you have connected. The prompt leaves this
  machine; the image is stored here.
  <GuideLink route="design" label="How image generation is governed" />
</p>

{#if block.kind !== "none"}
  <p class="notice" role="status">
    {block.reason}
    {#if block.href}<a href={block.href}>{block.linkLabel}</a>{/if}
  </p>
{/if}

<form class="composer card" onsubmit={generate}>
  <label class="prompt">
    <span class="sr-only">Prompt</span>
    <textarea
      bind:value={prompt}
      rows="3"
      placeholder="Describe the image you want"
      aria-label="Prompt"
      disabled={busy}
    ></textarea>
  </label>
  <div class="controls">
    <label>
      <span>Provider</span>
      <select bind:value={profileId} disabled={busy || imageProfiles.length === 0}>
        {#each imageProfiles as profile (profile.profile_id)}
          <option value={profile.profile_id}>
            {profile.provider} · {modelName(profile.image_model ?? "")}
          </option>
        {/each}
      </select>
    </label>
    <label>
      <span>Size</span>
      <select bind:value={size} disabled={busy}>
        {#each view?.sizes ?? [] as option (option)}
          <option value={option}>{option}</option>
        {/each}
      </select>
    </label>
    <button
      type="submit"
      class="btn btn-primary"
      disabled={busy || !prompt.trim() || !profileId || block.kind !== "none"}
    >
      {busy ? "Generating…" : "Generate"}
    </button>
  </div>
  {#if imageProfiles.length === 0 && models !== null}
    <p class="sub">
      No connected provider offers an image model. Connect OpenAI or Gemini on the Models
      page.
    </p>
  {/if}
  {#if failure}<p class="error" role="alert">{failure}</p>{/if}
</form>

{#if loadError}
  <PageState state="error" title="Couldn't read your generations" detail={loadError} />
{:else if view === null}
  <PageState state="loading" title="Reading your generations…" />
{:else if view!.generations.length === 0}
  <PageState
    state="empty"
    title="Nothing generated yet"
    detail="What you generate is stored in this workspace and listed here."
  />
{:else}
  <ul class="gallery">
    {#each view!.generations as item (item.generation_id)}
      <li class="card" class:refused={item.status !== "ok"}>
        {#if item.has_image}
          <a class="shot" href={api.imageBytesUrl(item.generation_id)} target="_blank" rel="noopener">
            <img src={api.imageBytesUrl(item.generation_id)} alt={item.prompt} loading="lazy" />
          </a>
        {:else}
          <p class="refusal"><Icon name="warning" size="sm" /> {readable(item.reason_code)}</p>
        {/if}
        <p class="prompt-text">{item.prompt}</p>
        <p class="sub">
          {item.model} · {item.size} · {relativeTime(item.created_at)}
        </p>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .composer { display: grid; gap: var(--space-3); margin-bottom: var(--space-4); }
  .prompt textarea {
    width: 100%;
    resize: vertical;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-1);
    font: inherit;
  }
  .controls { display: flex; flex-wrap: wrap; align-items: end; gap: var(--space-3); }
  .controls label { display: grid; gap: 0.25rem; font-size: var(--text-sm); color: var(--text-2); }
  .controls select { min-width: 0; }
  .controls .btn { margin-left: auto; }
  .gallery {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(16rem, 100%), 1fr));
    gap: var(--space-4);
  }
  .gallery li { display: grid; gap: 0.35rem; align-content: start; }
  .refused { border-color: var(--warn-border); background: var(--warn-soft); }
  .shot { display: block; border-radius: var(--r-sm); overflow: hidden; }
  .shot img { display: block; width: 100%; height: auto; }
  .refusal { margin: 0; display: flex; align-items: center; gap: 0.4rem; color: var(--warn); font-size: var(--text-sm); }
  .prompt-text { margin: 0; font-size: var(--text-sm); overflow-wrap: anywhere; }
  .sub { margin: 0; color: var(--text-3); font-size: var(--text-xs); }
  .error { margin: 0; color: var(--danger); font-size: var(--text-sm); }
  .notice { color: var(--text-2); }
  .notice a { margin-left: 0.35rem; }
</style>
