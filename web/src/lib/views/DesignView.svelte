<script lang="ts">
  import { workDraft } from "../workDraft.svelte";
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
  import ComposerActionMenu from "../components/ComposerActionMenu.svelte";
  import ComposerContext from "../components/ComposerContext.svelte";
  import Icon from "../components/Icon.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import { providerName, relativeTime } from "../format";
  import { runtimeBlock } from "../capabilityModel";
  import { composerMenu } from "../composerCapabilities";
  import { readReadiness, refreshReadCapabilities } from "../readCapabilities.svelte";
  import { setWorkProject, workProject } from "../workProject.svelte";
  import { imageCandidates, modelName } from "../modelPresentation";
  import { rememberSurfaceModel, surfaceModel } from "../surfaceModel.svelte";
  import type {
    CapabilityGate,
    ImageGeneration,
    ModelsView,
    ProjectsList,
  } from "../apiTypes";

  let {
    /** The owner's projects, so the composer can name the one work runs in. */
    projects = null,
  }: { projects?: ProjectsList | null } = $props();

  let view = $state<{ sizes: string[]; generations: ImageGeneration[] } | null>(null);
  let loadError = $state<string | null>(null);
  let gates = $state<CapabilityGate[]>([]);
  let models = $state<ModelsView | null>(null);
  let busy = $state(false);
  let failure = $state<string | null>(null);
  let threadEl = $state<HTMLDivElement | undefined>();

  const draft = $derived(workDraft(workProject()));
  let size = $state("1024x1024");

  /**
   * WEB-06 — Design's research layer.
   *
   * The architecture the plan asks for is `Design composer → planning/research
   * agent → global read capabilities → image model`, and the important word in
   * it is the arrow that *is not there*: nothing goes from the read
   * capabilities straight into image generation. A research turn is an ordinary
   * governed turn on the `design` surface with the ordinary catalogue; the
   * picture is made by a separate endpoint that reaches one image provider and
   * has no idea this exists. So "find me references" cannot become "the image
   * model may browse", because the two never share a path.
   *
   * What comes back is the model's own words about pages it read. It is shown
   * as research, above the composer, for the owner to write a prompt from — not
   * spliced into the prompt on their behalf.
   */
  let research = $state<{ question: string; answer: string } | null>(null);
  let researching = $state(false);
  let researchError = $state<string | null>(null);
  let researchSession = $state<string | null>(null);
  const readiness = $derived(readReadiness());


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

  /**
   * MODEL-02 — Design remembers its own model.
   *
   * Every other Work surface did. Design's picker started on whatever happened
   * to be first in the list of image models on every load, so an owner with two
   * connected image providers re-chose on every visit, and the choice they made
   * last time was not stored anywhere to re-choose *from*. It is a preference
   * like Chat's and Build's: it decides where the picker starts, and the
   * request still names the exact profile and model that readiness judges.
   */
  function remember(key: string) {
    const picked = imageChoices.find((item) => item.key === key);
    if (picked) void rememberSurfaceModel("design", picked.profileId, picked.model);
  }
  const choice = $derived(
    imageChoices.find((item) => item.key === choiceKey) ?? imageChoices[0] ?? null,
  );

  /**
   * COMPOSER-09 — the same composer grammar as Chat and Build.
   *
   * Design's bar carried a model select and a size select permanently: two of
   * the parameters an image request takes, with no route to the rest. The shell
   * is shared now, and what stays at rest is the one visual parameter changed
   * often enough to earn the room.
   *
   * The menus are deliberately short, and short *honestly*. COMPOSER-09
   * describes edit, variations, outpaint, reference images and version compare;
   * Raiker's governed image endpoint takes a prompt, a size and a model and
   * returns one picture. The review's own acceptance test settles what to do
   * about the gap — "every exposed composer action reaches an actual
   * backend/runtime path or is omitted" — so those entries are absent rather
   * than present and inert, and the missing runtime is recorded in
   * docs/plans/TO_BE_FIXED.md instead of implied by a control that does
   * nothing.
   */
  const HANDLED = new Set([
    "set-project",
    // The research reads. They are handled here — not routed away to another
    // page — because this view really runs them, which is the test the composer
    // registry applies to every entry it draws.
    "web-search",
    "web-read",
    "web-extract",
    "weather",
  ]);
  const addItems = $derived(composerMenu("add", "design", gates, HANDLED, readiness));
  const toolItems = $derived(composerMenu("tools", "design", gates, HANDLED, readiness));

  /** COMPOSER-06 — the parameters this press will use, as one inspectable line. */
  /**
   * VIS2-11 — the Work project, named here as it is in Chat and Build.
   *
   * Named, and honestly bounded. Design's research turns run inside this
   * project like any other governed turn; the *image* endpoint takes a prompt,
   * a size and a model and has no project field, so a generated picture does
   * not yet belong to the project it was made in. The fact says which of the
   * two it is rather than implying the stronger one — recorded in
   * docs/plans/TO_BE_FIXED.md as the runtime half that is missing.
   */
  const project = $derived(
    (projects?.projects ?? []).find((entry) => entry.project_id === workProject()) ?? null,
  );

  const contextFacts = $derived([
    ...(project !== null
      ? [
          {
            label: "Project",
            value: `${project.name} — research runs here; images are not filed to it yet`,
            short: project.name,
            href: "#/projects",
            action: "Projects",
          },
        ]
      : []),
    {
      label: "Size",
      value: size,
      short: size,
      href: "#/models?tab=models",
      action: "Models",
    },
    ...(choice !== null
      ? [
          {
            label: "Model",
            value: `${providerName(choice.provider)} · ${modelName(choice.model)}`,
          },
        ]
      : []),
  ]);

  const RESEARCH_ASKS: Record<string, string> = {
    "web-search": "Find public visual references for: ",
    "web-read": "Read this page and describe what it shows: ",
    "web-extract": "Extract the reference details from this page: ",
    weather: "What are the current conditions and light like in: ",
  };

  /** Open state for the project chooser the `+` menu reveals, as in Chat. */
  let projectPickerOpen = $state(false);

  function runComposerAction(id: string) {
    if (id === "set-project") {
      // VIS2-11 — chosen here rather than on another page. Sending the owner to
      // Projects to pick one and back again is the re-choosing this item exists
      // to remove.
      projectPickerOpen = !projectPickerOpen;
      return;
    }
    const ask = RESEARCH_ASKS[id];
    if (ask !== undefined) void runResearch(ask);
  }

  /**
   * Run one research turn on the `design` surface.
   *
   * The composer's text is the subject; an empty composer is not a question, so
   * it asks for one rather than sending a bare verb to a model. The turn keeps
   * its own session so a second question continues the first — research is
   * iterative, and a fresh session each time would throw away what was just
   * established.
   */
  async function runResearch(ask: string) {
    const subject = draft.text.trim();
    if (!subject) {
      researchError = "Describe what to research in the composer first.";
      research = null;
      return;
    }
    if (researching) return;
    researching = true;
    researchError = null;
    try {
      const response = await api.submitPrompt({
        text: ask + subject,
        surface: "design",
        ...(researchSession ? { session_id: researchSession } : {}),
      });
      researchSession = response.session_id ?? researchSession;
      research = { question: subject, answer: response.message ?? "" };
    } catch (error) {
      research = null;
      researchError =
        error instanceof ApiError ? error.message : "That research turn failed.";
    } finally {
      researching = false;
    }
  }

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
    // WEB-07 — from the shared snapshot, so configuring a search provider
    // elsewhere reaches this still-mounted view without a reload.
    await refreshReadCapabilities();
    try {
      models = await api.models();
      if (!choiceKey && imageChoices.length) {
        // The remembered choice first, and only then the head of the list. A
        // model that is no longer connected is not restored: falling back to
        // the first available one is right here, because a Design turn cannot
        // run at all without an image model and there is nothing to explain.
        const remembered = await surfaceModel("design");
        const restored = remembered
          ? imageChoices.find(
              (item) =>
                item.profileId === remembered.profileId && item.model === remembered.model,
            )
          : undefined;
        choiceKey = (restored ?? imageChoices[0]).key;
      }
    } catch {
      models = null;
    }
    await toLatest();
  }

  async function generate() {
    if (!draft.text.trim() || choice === null || busy || block.kind !== "none") return;
    const sentDraft = draft;
    const sentText = sentDraft.text;
    busy = true;
    failure = null;
    try {
      await api.generateImage({
        profile_id: choice.profileId,
        prompt: draft.text.trim(),
        size,
        model: choice.model,
      });
      if (sentDraft.text === sentText) sentDraft.text = "";
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

  {#if researching || research !== null || researchError !== null}
    <section class="research" aria-label="Design research" data-testid="design-research">
      <p class="research-head">
        <Icon name="globe" size="sm" />
        <span
          >Research{#if research !== null}: {research.question}{/if}</span
        >
        {#if research !== null || researchError !== null}
          <button
            type="button"
            class="research-close"
            onclick={() => {
              research = null;
              researchError = null;
            }}>Dismiss</button
          >
        {/if}
      </p>
      {#if researching}
        <p class="research-body">Reading sources…</p>
      {:else if researchError}
        <p class="research-body error" role="alert">{researchError}</p>
      {:else if research !== null}
        <p class="research-body">{research.answer}</p>
        <p class="research-note">
          Gathered by a governed research turn. It read pages; it did not draw
          anything, and image generation gained no network access from it.
        </p>
      {/if}
    </section>
  {/if}

  <Composer
    ariaLabel="Image composer"
    inputId="design-prompt"
    inputLabel="Describe the image"
    bind:value={draft.text}
    inputProps={{
      placeholder: "Describe the image you want…",
      title: "Enter to generate, Shift+Enter for a new line",
      disabled: busy,
      onkeydown: onKeydown,
    }}
    onsubmit={() => void generate()}
  >
    {#snippet left()}
      <!-- COMPOSER-09 — the same two entry points Chat and Build carry, so a
           person moving between the three Work modes finds the composer in the
           same shape each time. -->
      <ComposerActionMenu
        kind="add"
        items={addItems}
        disabled={busy}
        onchoose={runComposerAction}
      />
      <ComposerActionMenu
        kind="tools"
        items={toolItems}
        disabled={busy}
        onchoose={runComposerAction}
      />
      <!-- Size is the one visual parameter changed often enough to stay at
           rest. Everything the review lists beside it — aspect, count, seed,
           quality — belongs in Options, and none of them exist in the governed
           image endpoint yet, so none of them are drawn. -->
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
      <ComposerContext facts={contextFacts} disabled={busy} />
    {/snippet}

    {#snippet above()}
      {#if projectPickerOpen}
        <div class="project-choice" role="group" aria-label="Choose a project">
          <label for="design-project-choice">Project for this work</label>
          <select
            id="design-project-choice"
            class="bar-select"
            value={workProject()}
            onchange={(event) => {
              projectPickerOpen = false;
              setWorkProject((event.currentTarget as HTMLSelectElement).value);
            }}
          >
            <option value="">No project — this work stands alone</option>
            {#each projects?.projects ?? [] as entry (entry.project_id)}
              <option value={entry.project_id}>{entry.name}</option>
            {/each}
          </select>
          <button
            type="button"
            class="btn btn-ghost btn-sm"
            onclick={() => (projectPickerOpen = false)}>Done</button
          >
        </div>
      {/if}
    {/snippet}

    {#snippet right()}
      <!-- COMPOSER-05 — model identity stays visible and model *management*
           does not. Always drawn, whatever is configured: hiding it made "no
           image model is connected" indistinguishable from "this page has no
           model control", and the second reading is the one an owner reached. -->
      <label class="composer-scope model-scope">
        <span class="sr-only">Image model</span>
        <Icon name="models" size="sm" />
        {#if imageChoices.length > 0}
          <select
            class="bar-select"
            bind:value={choiceKey}
            aria-label="Image model"
            disabled={busy}
            onchange={(event) => remember((event.currentTarget as HTMLSelectElement).value)}
          >
            {#each imageChoices as item (item.key)}
              <option value={item.key}>
                {providerName(item.provider)} · {modelName(item.model)}
              </option>
            {/each}
          </select>
        {:else}
          <a
            class="bar-select bar-empty"
            href="#/models"
            title="No image model is connected. Connect one on the Models page."
            >No image model — connect one</a
          >
        {/if}
      </label>
      <button
        type="submit"
        class="btn btn-primary send"
        disabled={busy || !draft.text.trim() || choice === null || block.kind !== "none"}
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
  .research {
    margin: 0 0 var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .research-head {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0 0 0.35rem;
    color: var(--text-2);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .research-close {
    margin-left: auto;
    background: none;
    border: 0;
    padding: 0;
    font: inherit;
    color: var(--accent);
    cursor: pointer;
    text-decoration: underline;
  }
  .research-body { margin: 0; color: var(--text-1); white-space: pre-wrap; }
  .research-body.error { color: var(--danger); }
  .research-note { margin: 0.4rem 0 0; color: var(--text-3); font-size: var(--text-xs); }
  /* The same shape Chat's chooser uses, for the same reason: it opens in flow
     between the prompt and the bar rather than as a popover over the text. */
  .project-choice {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin: 0 0 var(--space-2);
  }
  .project-choice label { color: var(--text-2); font-size: var(--text-sm); }
  .project-choice select { min-width: 12rem; }

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
    /* `inline-block`, not `inline-flex`. Found in the 2026-09-07 round: with no
       image model connected the control drew as an *empty box*. A flex
       container turns its text into an anonymous flex item, which
       `text-overflow: ellipsis` cannot act on — so `overflow: hidden` below
       clipped the whole sentence rather than truncating it, and the one control
       whose entire job is to say "connect a model" said nothing at all. */
    display: inline-block;
    color: var(--text-3);
    text-decoration: none;
    white-space: nowrap;
  }
  .bar-empty:hover {
    color: var(--accent);
    border-color: var(--accent-border);
  }
  /* Found in the live round: with no image model connected this sentence is
     longer than the space beside Generate, and `white-space: nowrap` pushed it
     straight through the button. It truncates and keeps its full text in the
     tooltip, because the sentence is an explanation and the button is the
     thing that must stay reachable. */
  .model-scope {
    min-width: 0;
    max-width: min(16rem, 40vw);
  }
  .model-scope .bar-empty,
  .model-scope .bar-select {
    min-width: 0;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .notice { color: var(--text-2); }
  .notice a { margin-left: 0.35rem; }

  @media (max-width: 63.9rem) {
    .design { height: auto; min-height: var(--content-h); }
    .thread { overflow-y: visible; }
  }
</style>
