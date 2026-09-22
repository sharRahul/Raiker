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
  import DesignCanvasRegion from "../components/DesignCanvasRegion.svelte";
  // BUG-281 — the research turn already records every page it read; these are
  // what make those records openable here rather than only in the conversation.
  import SourceChips from "../components/SourceChips.svelte";
  import SourceExcerptPanel from "../components/SourceExcerptPanel.svelte";
  import { citedSourceIds, sentenceAround, sourcesForTurn } from "../citations";
  import { designPrimaryAction, MAX_DESIGN_VARIATIONS } from "../designAssets";
  import { routeStateFromHash } from "../routeState";
  import { densityGap, workSurface } from "../workSurface";
  import { api, ApiError } from "../api";
  import { providerName } from "../format";
  import { runtimeBlock } from "../capabilityModel";
  import { composerMenu } from "../composerCapabilities";
  import { readReadiness, refreshReadCapabilities } from "../readCapabilities.svelte";
  import { setWorkProject, workProject } from "../workProject.svelte";
  import { imageCandidates, modelName } from "../modelPresentation";
  import { rememberSurfaceModel, surfaceModel } from "../surfaceModel.svelte";
  import type {
    CapabilityGate,
    ImageGenerationsView,
    ModelsView,
    ProjectsList,
    TurnSourceExcerptView,
    TurnSourceView,
  } from "../apiTypes";


  /** What this mode is about, and how tightly it packs it. */
  const surface = workSurface("design");

  let {
    /** The owner's projects, so the composer can name the one work runs in. */
    projects = null,
  }: { projects?: ProjectsList | null } = $props();

  let view = $state<ImageGenerationsView | null>(null);
  let loadError = $state<string | null>(null);
  let gates = $state<CapabilityGate[]>([]);
  let models = $state<ModelsView | null>(null);
  let busy = $state(false);
  let failure = $state<string | null>(null);
  let threadEl = $state<HTMLDivElement | undefined>();

  const draft = $derived(workDraft(workProject()));
  let size = $state("1024x1024");
  /*
   * The object the next instruction is about, and how many pictures
   * it asks for. Both are BUG-277's doing: until a request could name a prior
   * generation there was no subject to select, and until it could ask for
   * several there was no count to set.
   */
  let selectedId = $state<string | null>(null);
  let variations = $state(1);

  /**
   * Design's research layer.
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
  let research = $state<{ question: string; answer: string; turnId: string } | null>(null);
  let researching = $state(false);
  let researchError = $state<string | null>(null);
  let researchSession = $state<string | null>(null);

  /**
   * BUG-281 — the pages that research turn actually read, openable here.
   *
   * The findings were the model's prose and nothing else. The turn *recorded*
   * its sources all along — every governed read enters the turn-source ledger,
   * which is what Chat's citation chips are drawn from — so the only thing
   * missing was the strip. Without it, opening the page a reference came from
   * meant leaving Design for the conversation the turn happened to run in.
   *
   * Two claims, kept apart exactly as `SourceChips` keeps them elsewhere: the
   * ledger is a fact about what the runtime read, and a citation is the model's
   * own claim about which sentence rests on which page.
   */
  let researchSources = $state<TurnSourceView[]>([]);
  let openSourceId = $state<string | null>(null);
  let openSource = $state<TurnSourceExcerptView | null>(null);
  let openSourceLoading = $state(false);

  function closeSource() {
    openSourceId = null;
    openSource = null;
    openSourceLoading = false;
  }

  async function showSource(source: TurnSourceView, quote = "") {
    if (researchSession === null || !source.openable) return;
    if (openSourceId === source.source_id) {
      closeSource();
      return;
    }
    openSourceId = source.source_id;
    openSource = null;
    openSourceLoading = true;
    try {
      const resolved = await api.turnSourceExcerpt(
        researchSession,
        source.turn_id,
        source.source_id,
        quote,
      );
      if (openSourceId === source.source_id) openSource = resolved;
    } catch {
      // A passage that will not resolve costs the panel, never the findings.
      if (openSourceId === source.source_id) openSource = null;
    } finally {
      if (openSourceId === source.source_id) openSourceLoading = false;
    }
  }
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
   * Design remembers its own model.
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
   * REM-DESIGN-01 — whether the size control decides anything for this choice.
   *
   * Read from the runtime's own list rather than from a provider name kept
   * here, so a provider that gains or loses a sized endpoint changes one tuple
   * in `tier2_image.py` and this follows. A host that predates the field makes
   * no claim, and an absent claim is not read as "no provider takes a size" —
   * that would disable a working control on every older host.
   */
  const sizeIsSent = $derived.by(() => {
    const declared = view?.sized_providers;
    if (declared === undefined || choice === null) return true;
    return declared.includes(choice.provider);
  });

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
   * of those, **edit and variations are implemented** — the governed endpoint
   * takes a source generation and a count (BUG-277), and this composer sends
   * both, so they are controls on the bar rather than menu entries. Outpaint and
   * reference images have no governed path and are therefore absent rather than
   * present and inert, which is the review's own acceptance test: "every exposed
   * composer action reaches an actual backend/runtime path or is omitted".
   *
   * REM-DESIGN-01 — this paragraph used to say the endpoint "takes a prompt, a
   * size and a model and returns one picture", which had been untrue since the
   * lineage work landed. A comment that describes a retired endpoint is read as
   * a statement about the product by the next person to change this file.
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
   * The Work project, named here as it is in Chat and Build.
   *
   * Named, and honestly bounded. Design's research turns run inside this
   * project like any other governed turn; the *image* endpoint takes a prompt,
   * a size and a model and had no project field, so a generated picture did not
   * belong to the project it was made in. BUG-277's lineage work carried
   * `project_id` with it (BUG-282), so a picture generated here is filed
   * against the project the composer names, and the fact below says so without
   * the qualification it used to need.
   */
  const project = $derived(
    (projects?.projects ?? []).find((entry) => entry.project_id === workProject()) ?? null,
  );

  const contextFacts = $derived([
    ...(project !== null
      ? [
          /*
           * UX-BUILD-05 — the link goes to this project, not to the list of
           * them. Naming the project and then opening a page where the owner
           * has to find it again is the weak return path the review names; the
           * id is already here, so the link can carry it.
           */
          {
            label: "Project",
            value: `${project.name} — research and generated images are filed here`,
            short: project.name,
            href: `#/projects?project=${encodeURIComponent(project.project_id)}`,
            action: "Open project work",
          },
        ]
      : []),
    // Size is deliberately *not* a fact here. It has a control of its own two
    // elements to the left, and a line that repeats the value of the control
    // beside it printed "1024x1024" twice in one bar — the duplication
    // COMPOSER-18 exists to prevent. The context line answers for what the turn
    // will use that the bar does not already show. Found live 2026-09-07.
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
      // Chosen here rather than on another page. Sending the owner to
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
      research = {
        question: subject,
        answer: response.message ?? "",
        turnId: response.turn_id ?? "",
      };
      // BUG-281 — read after the answer, and scoped to this turn. A failure
      // here loses the chips and never the findings: provenance for an answer
      // that has already arrived must not be able to take the answer with it.
      closeSource();
      try {
        const ledger = await api.sessionSources(researchSession ?? "");
        researchSources = sourcesForTurn(ledger.sources, response.turn_id);
      } catch {
        researchSources = [];
      }
    } catch (error) {
      research = null;
      researchSources = [];
      closeSource();
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
  /**
   * NEW-PROJ-02 — the project a link arrived with, and the asset it named.
   *
   * A project's image strip had no per-asset action and one generic
   * `#/design` link, so an owner who had just been looking at a picture in a
   * project had to search the whole account's Design history to find it again.
   * Both are coordinates: the gallery behind them is owner-scoped on the
   * server, so an id belonging to somebody else resolves to nothing.
   */
  const arrivedWith = $state(routeStateFromHash(window.location.hash));
  const all = $derived([...(view?.generations ?? [])].reverse());
  /**
   * The project the canvas was scoped to, named. Resolved from the owner's own
   * project list rather than from the gallery, which carries the id and not the
   * name — a filter chip reading `proj_a1b2c3` would be the same defect this
   * change is about, one surface along.
   */
  let scopedProjectName = $state<string | null>(null);
  /** The filter is on whenever a project arrived, named or not. */
  const scoped = $derived(arrivedWith.projectId !== null);
  const turns = $derived(
    arrivedWith.projectId === null
      ? all
      : all.filter((generation) => generation.project_id === arrivedWith.projectId),
  );
  const COUNTS = Array.from({ length: MAX_DESIGN_VARIATIONS }, (_, index) => index + 1);
  const primaryAction = $derived(designPrimaryAction(selectedId, variations));

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
    // From the shared snapshot, so configuring a search provider
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
    // REM-DESIGN-02 — what this request made, so it can be put on the canvas
    // rather than at the top of a list. Declared out here because the reload
    // that finds it happens in `finally`, after a refusal as well as a success.
    let made: string | null = null;
    try {
      const created = await api.generateImage({
        profile_id: choice.profileId,
        prompt: draft.text.trim(),
        size,
        model: choice.model,
        // The subject, when one is on the canvas. Its absence is what makes
        // this a plain generation rather than an edit, which is also what the
        // button has been saying.
        ...(selectedId ? { source_generation_id: selectedId } : {}),
        ...(variations > 1 ? { variations } : {}),
        ...(project ? { project_id: project.project_id } : {}),
      });
      made = created.generation_id;
      if (sentDraft.text === sentText) sentDraft.text = "";
    } catch (error) {
      failure =
        error instanceof ApiError ? readable(error.reasonCode ?? null) : "That request failed.";
    } finally {
      busy = false;
      // Reloaded either way: a refusal is recorded, so the thread is where the
      // owner reads what happened even when this attempt failed.
      await load();
      /*
       * REM-DESIGN-02 — the picture just made is the current work.
       *
       * Every generation went to the top of the history and nothing was
       * selected, so the canvas an owner had been composing on emptied itself
       * at the moment their request succeeded, and the result they asked for
       * arrived as the first row of a list that grows all day. Putting it on
       * the canvas is what keeps "the selected artifact and prompt central"
       * true after the twentieth image as well as the first.
       *
       * Only a picture. A refusal is recorded as a generation too, and a
       * refusal has nothing to put on a canvas — it is read in the history,
       * where its reason is.
       */
      if (made !== null) {
        const generation = (view?.generations ?? []).find(
          (item) => item.generation_id === made,
        );
        if (generation?.has_image) selectedId = generation.generation_id;
      }
    }
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void generate();
    }
  }

  onMount(async () => {
    await load();
    if (arrivedWith.projectId !== null) {
      try {
        const list = await api.projects();
        scopedProjectName =
          list.projects.find((project) => project.project_id === arrivedWith.projectId)?.name ??
          null;
      } catch {
        // Supplementary: the filter still holds and the chip says so without a
        // name, rather than the surface failing over a label.
        scopedProjectName = null;
      }
    }
    // Selected only if it is genuinely in this owner's gallery. An asset that
    // was deleted, failed, or never belonged to them selects nothing and leaves
    // the surface usable, rather than pointing at something that is not there.
    const named = arrivedWith.assetId;
    if (named !== null && (view?.generations ?? []).some((g) => g.generation_id === named)) {
      selectedId = named;
    }
  });
</script>

<!-- The Work contract. Design shares its terms with Chat and Build
     and differs in its object: an asset is looked at, so it takes the middle
     density rather than the transcript's air or the workbench's pack. -->
<div
  class="design"
  data-work-surface={surface.mode}
  data-primary-object={surface.primaryObject}
  data-density={surface.density}
  style={`--surface-gap:${densityGap(surface.density)}`}
>
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

    <!-- NEW-PROJ-02 — when a project sent the owner here, the canvas says so
         and offers the way out. A filter nobody can see is a canvas that looks
         like it has lost work. -->
    {#if scoped}
      <p class="scope-chip" role="status">
        <Icon name="folder" size="sm" />
        <span
          >Showing images from {scopedProjectName ?? "one project"} · {turns.length}
          {turns.length === 1 ? "image" : "images"}</span
        >
        <a href="#/design">Show all images</a>
      </p>
    {/if}

    <!-- The region that holds this surface's object, as its own
         component. What Design shows *is* the asset, so how an asset is
         presented lives in one file rather than in the middle of the view. -->
    <DesignCanvasRegion
      turns={turns}
      loading={view === null}
      {loadError}
      {readable}
      sizedProviders={view?.sized_providers}
      bind:selectedId
    />
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
              researchSources = [];
              closeSource();
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
        <!-- BUG-281 — what the turn read, openable at the passage it used,
             without leaving Design for the conversation it ran in. -->
        {#if researchSources.length > 0}
          <SourceChips
            sources={researchSources}
            citedIds={citedSourceIds(research.answer, researchSources)}
            {openSourceId}
            onopen={(source) =>
              void showSource(
                source,
                sentenceAround(research?.answer ?? "", source.source_id),
              )}
          />
          {#if openSourceId !== null}
            <SourceExcerptPanel
              source={openSource}
              loading={openSourceLoading}
              onclose={closeSource}
            />
          {/if}
        {/if}
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
           rest. Of the rest the review lists — aspect, seed, quality — none has
           a governed path, so none is drawn; count does, and is next to it.

           REM-DESIGN-01 — and it is offered only where it decides anything. The
           select was drawn for every provider and the chosen value recorded on
           the row, including for one whose governed request carries no size at
           all: the owner picked a shape, Raiker filed it, and the provider never
           heard it. Which providers take one is read from the runtime
           (`sized_providers`), not kept as a second copy here. -->
      {#if (view?.sizes ?? []).length > 0}
        <label class="composer-scope">
          <span class="sr-only">Size</span>
          <select
            class="bar-select"
            bind:value={size}
            aria-label="Size"
            disabled={busy || !sizeIsSent}
            title={sizeIsSent
              ? "The size Raiker asks the provider for"
              : `${choice?.provider ?? "This provider"} chooses the size itself — Raiker does not send one.`}
          >
            {#each view!.sizes as option (option)}
              <option value={option}>{option}</option>
            {/each}
          </select>
        </label>
      {/if}
      <!-- A count, beside the size, for the same reason the size is there: it is
           a visual parameter changed often enough to stay at rest, and unlike
           aspect, seed and quality it now reaches a real runtime path. -->
      <label class="composer-scope">
        <span class="sr-only">How many</span>
        <select
          class="bar-select"
          bind:value={variations}
          aria-label="How many"
          disabled={busy || selectedId !== null}
          title={selectedId !== null
            ? "An edit produces one new version of the selected image."
            : "How many images to generate"}
        >
          {#each COUNTS as option (option)}
            <option value={option}>{option === 1 ? "1 image" : `${option} images`}</option>
          {/each}
        </select>
      </label>
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
        aria-label={busy ? "Working" : primaryAction}
      >
        <Icon name={busy ? "clock" : "send"} size="sm" />
        <!-- COMPOSER-15 — the word names the act the press performs. Design has
             three now because it has three requests, and the word follows the
             state: Edit only while an asset is on the canvas. -->
        <span class="send-label">{busy ? "Working…" : primaryAction}</span>
      </button>
    {/snippet}

    {#snippet footer()}
      {#if failure}<p class="error" role="alert">{failure}</p>{/if}
    {/snippet}

    {#snippet hint()}
      <!-- The hint names the same act the button does. "Enter generates" beside
           a button reading **Edit** is the mismatch COMPOSER-15 is about, one
           line further down. -->
      Enter {selectedId ? "edits" : "generates"} · Shift+Enter adds a line
    {/snippet}
  </Composer>
</div>

<style>
  /* NEW-PROJ-02 — the canvas saying which project it is scoped to. */
  .scope-chip {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0 0 var(--space-3);
    padding: 6px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-2);
    font-size: var(--text-xs);
  }
  .scope-chip a { margin-left: auto; color: var(--accent); }
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
  /* The prompt reads as the thing you said, in the same bubble grammar as a
     Chat message, so the pairing is legible without a label on either half. */
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
