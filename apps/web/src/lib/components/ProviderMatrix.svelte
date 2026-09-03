<script lang="ts">
  /**
   * One row per model provider — the whole model-connection question on a single
   * screen.
   *
   * The first-run wizard used to show a flat list of *profiles* and ask the owner
   * to pick one. That list is only ever populated by profiles that already have a
   * concrete model, so on a fresh install it read "No model connection yet" and
   * sent the owner to a different page to do the actual work. The question the
   * screen is asking — "where should Raiker think?" — was never answerable from
   * the screen asking it.
   *
   * A row is therefore the provider, not the profile, and it carries the two
   * things a provider needs:
   *
   *  - **On this machine** (llama.cpp, Ollama, LM Studio): nothing to
   *    authenticate, so the row *detects*. It asks the runtime what it is
   *    serving and puts the answer in a dropdown. A runtime that is not running
   *    says so; it does not offer an invented model name.
   *  - **With an API key** (Anthropic, OpenAI, OpenRouter, Ollama Cloud,
   *    Hugging Face, Gemini): the row takes the key, stores it through the same
   *    governed vault path the Models page uses, and *then* asks the provider
   *    for its catalogue. The dropdown is the provider's own answer — model
   *    names are never guessed, and a wrong key produces a stated failure rather
   *    than an empty box.
   *
   * Nothing here grants anything. Saving a credential and pinning a model are
   * both gate-manager actions enforced server-side, readiness is still measured
   * against the exact model before any work, and a key's value is never read
   * back — the row can only report that one is stored.
   */
  import { onDestroy } from "svelte";
  import { api, ApiError } from "../api";
  import type { ModelProfile, ProviderModelList } from "../apiTypes";
  import { providerName } from "../format";
  import { modelName } from "../modelPresentation";
  import { providerErrorGuidance } from "../providerErrors";
  import Icon from "./Icon.svelte";
  import ProviderLogo from "./ProviderLogo.svelte";

  let {
    profiles,
    onselected,
    onchanged,
  }: {
    /** Every profile the registry publishes, from `GET /api/models`. */
    profiles: ModelProfile[];
    /** A model was pinned to a profile; the caller decides what that means next. */
    onselected?: (profileId: string, model: string) => void;
    /** Something that changes the model view was saved. */
    onchanged?: () => void;
  } = $props();

  /** Where a provider's key is issued. Shown as text, never fetched. */
  const KEY_SOURCE: Record<string, string> = {
    anthropic: "console.anthropic.com → API keys",
    openai: "platform.openai.com/api-keys",
    openrouter: "openrouter.ai/keys",
    "ollama-cloud": "ollama.com → Settings → Keys",
    huggingface: "huggingface.co/settings/tokens",
    gemini: "aistudio.google.com/apikey",
  };

  /** What a local runtime is, in one line, so the row explains itself. */
  const LOCAL_SOURCE: Record<string, string> = {
    "llama.cpp": "GGUF files in the folders you approved, served by llama.cpp on this device.",
    ollama: "Whatever the Ollama service on this device has already pulled.",
    "lm-studio": "Whatever LM Studio has downloaded and is serving locally.",
    "openai-compatible": "Any OpenAI-compatible server you run — vLLM, TGI, a home-lab host.",
  };

  interface Row {
    /** The profile a selection is pinned to. */
    profileId: string;
    provider: string;
    label: string;
    /** How this row finds models. */
    kind: "gguf" | "detect" | "key" | "endpoint" | "subscription";
    source: string;
    /** True once a credential is stored for this profile. */
    connected: boolean;
    /** The model currently pinned to this profile, or "" for none. */
    pinned: string;
  }

  // One row per provider. llama.cpp publishes four identical slot profiles (four
  // models can serve at once); the row is the provider, so it takes the first and
  // says so, rather than showing the same runtime four times.
  const rows = $derived.by<Row[]>(() => {
    const seen = new Set<string>();
    const built: Row[] = [];
    for (const profile of profiles) {
      if (seen.has(profile.provider)) continue;
      seen.add(profile.provider);
      const kind: Row["kind"] =
        profile.provider === "chatgpt-codex"
          ? "subscription"
          : profile.provider === "llama.cpp"
          ? "gguf"
          : profile.provider === "openai-compatible"
            ? "endpoint"
            : profile.local_only
              ? "detect"
              : "key";
      built.push({
        profileId: profile.profile_id,
        provider: profile.provider,
        label: providerName(profile.provider),
        kind,
        source:
          kind === "subscription"
            ? "Uses the ChatGPT subscription already signed in to the local Codex client. Raiker never receives its token."
            : kind === "key"
            ? (KEY_SOURCE[profile.provider] ?? "the provider's own console")
            : (LOCAL_SOURCE[profile.provider] ?? "this device"),
        connected: profile.connection_configured === true,
        // A llama.cpp profile's `model` is the *slot alias* the runtime serves
        // under (`local-gguf`), not a GGUF the owner chose — showing it as
        // "Selected: Local GGUF" claimed a choice nobody had made and no file
        // that existed. Which GGUF is actually serving is a deployment fact this
        // read does not carry, so the row says nothing rather than something
        // untrue.
        pinned:
          kind !== "gguf" && profile.model && profile.model !== "<model>" ? profile.model : "",
      });
    }
    // On this machine first: it needs no account, so it is the cheapest answer to
    // the question the screen is asking.
    const order: Row["kind"][] = ["gguf", "detect", "endpoint", "subscription", "key"];
    return built.sort((left, right) => order.indexOf(left.kind) - order.indexOf(right.kind));
  });

  /** Per-row transient state, keyed by profile id. */
  let catalogue = $state<Record<string, ProviderModelList>>({});
  let choice = $state<Record<string, string>>({});
  let apiKey = $state<Record<string, string>>({});
  let endpoint = $state<Record<string, string>>({});
  let busy = $state<Record<string, "detecting" | "saving" | "pinning" | "deploying">>({});
  let note = $state<Record<string, string>>({});
  let failure = $state<Record<string, string>>({});
  let ggufModels = $state<Array<{ model_id: string; name: string; size_bytes: number }> | null>(null);
  let ggufError = $state<string | null>(null);
  /**
   * Credentials this screen stored or removed since it opened. A successful save
   * is proof a key exists, so the row switches to its model picker immediately
   * rather than waiting for the next `/api/models` snapshot to agree — which is
   * what left a just-connected provider still showing an empty key box.
   */
  let stored = $state<Record<string, boolean>>({});
  /** Which ChatGPT plan Codex reports, so the row can name it rather than
      leaving an owner with several subscriptions guessing which is in use. */
  let subscriptionPlan = $state<string | null>(null);
  const isConnected = (row: Row) => stored[row.profileId] ?? row.connected;
  let loginPolling: ReturnType<typeof setTimeout> | null = null;

  function set<T>(map: Record<string, T>, key: string, value: T): Record<string, T> {
    return { ...map, [key]: value };
  }
  function drop<T>(map: Record<string, T>, key: string): Record<string, T> {
    return Object.fromEntries(Object.entries(map).filter(([id]) => id !== key));
  }

  const gigabytes = (value: number) => `${(value / 1024 ** 3).toFixed(1)} GB`;

  /** What the row calls itself. llama.cpp is named for what the owner has — GGUF
      files — rather than for the server that reads them. */
  const rowTitle = (row: Row) => (row.kind === "gguf" ? "Local GGUF" : row.label);

  /** The provider's own catalogue, or an honest statement of why there is none. */
  async function detect(row: Row) {
    busy = set(busy, row.profileId, "detecting");
    failure = drop(failure, row.profileId);
    note = drop(note, row.profileId);
    try {
      const answer = await api.providerModels(row.profileId);
      // A catalogue is keyed by model id in the dropdown, so a provider that
      // lists the same id twice would crash the render and freeze this row on
      // "Asking…". One id is one model: de-duplicate, keeping the provider's own
      // order. (This is the second half of the OpenRouter finding — the first
      // half was the redaction layer flattening three distinct ids into one.)
      const list = { ...answer, models: [...new Set(answer.models)] };
      catalogue = set(catalogue, row.profileId, list);
      if (list.status === "available" && list.models.length > 0) {
        // Pre-select the pinned model when the provider still serves it, so the
        // dropdown opens on the owner's own choice rather than on the provider's
        // first alphabetical one.
        choice = set(
          choice,
          row.profileId,
          list.models.includes(row.pinned) ? row.pinned : list.models[0],
        );
      }
    } catch (error) {
      failure = set(
        failure,
        row.profileId,
        error instanceof ApiError && error.reasonCode
          ? `${row.label} could not be listed (${error.reasonCode}).`
          : `${row.label} could not be reached from this device.`,
      );
    } finally {
      busy = drop(busy, row.profileId);
    }
  }

  async function loadGguf() {
    ggufError = null;
    try {
      const library = await api.modelLibrary();
      ggufModels = library.models
        .filter((model) => model.complete)
        .map((model) => ({ model_id: model.model_id, name: model.name, size_bytes: model.size_bytes }));
    } catch {
      ggufModels = [];
      ggufError = "The local model library could not be read.";
    }
  }

  async function scanGguf() {
    ggufError = null;
    ggufModels = null;
    try {
      await api.rescanModelLibrary();
    } catch {
      ggufError = "Raiker could not scan the folders you approved.";
    }
    await loadGguf();
  }

  /** Store the key, then ask the provider what it serves. */
  async function saveKey(row: Row) {
    const key = (apiKey[row.profileId] ?? "").trim();
    if (key === "") return;
    busy = set(busy, row.profileId, "saving");
    failure = drop(failure, row.profileId);
    note = drop(note, row.profileId);
    try {
      await api.saveModelConnection(row.profileId, (endpoint[row.profileId] ?? "").trim(), key);
      // The value is gone from this page the moment it is stored; the row can
      // only ever report that a credential exists.
      apiKey = set(apiKey, row.profileId, "");
      stored = set(stored, row.profileId, true);
      note = set(note, row.profileId, `${row.label} credential stored. Reading its catalogue…`);
      onchanged?.();
      await detect(row);
      if (catalogue[row.profileId]?.status === "available") {
        const count = catalogue[row.profileId].models.length;
        note = set(
          note,
          row.profileId,
          `${row.label} answered with ${count} model${count === 1 ? "" : "s"}. Choose one.`,
        );
      } else {
        note = drop(note, row.profileId);
      }
    } catch (error) {
      const guidance = error instanceof ApiError ? providerErrorGuidance(error.reasonCode) : null;
      failure = set(
        failure,
        row.profileId,
        (guidance ? `${guidance.message} ${guidance.fix}` : null) ??
          (error instanceof ApiError && error.reasonCode
            ? `${row.label} refused the credential (${error.reasonCode}).`
            : `${row.label} would not accept that credential.`),
      );
    } finally {
      busy = drop(busy, row.profileId);
    }
  }

  async function readSubscriptionStatus(row: Row, poll = false) {
    try {
      const status = await api.codexSubscriptionStatus();
      const connected = status.connection_status === "connected";
      stored = set(stored, row.profileId, connected);
      subscriptionPlan = status.plan_type;
      if (connected) {
        note = set(note, row.profileId, "Reading available models…");
        await detect(row);
      } else if (status.connection_status === "codex_missing") {
        failure = set(failure, row.profileId, "Codex is not installed on this device.");
      } else if (poll) {
        note = set(note, row.profileId, "Finish sign-in in the browser. Raiker will check again shortly.");
        loginPolling = setTimeout(() => void readSubscriptionStatus(row, true), 2000);
      }
    } catch {
      failure = set(failure, row.profileId, "The local Codex client could not report ChatGPT sign-in status.");
    }
  }

  /** Forget the subscription here; the Codex client keeps its own session. */
  async function disconnectSubscription(row: Row) {
    busy = set(busy, row.profileId, "saving");
    failure = drop(failure, row.profileId);
    note = drop(note, row.profileId);
    try {
      await api.disconnectCodexSubscription();
      stored = set(stored, row.profileId, false);
      subscriptionPlan = null;
      catalogue = drop(catalogue, row.profileId);
      onchanged?.();
    } catch {
      failure = set(failure, row.profileId, "The ChatGPT subscription could not be disconnected.");
    } finally {
      busy = drop(busy, row.profileId);
    }
  }

  async function startSubscriptionLogin(row: Row) {
    busy = set(busy, row.profileId, "saving");
    failure = drop(failure, row.profileId);
    note = drop(note, row.profileId);
    try {
      await api.startCodexSubscriptionLogin();
      note = set(note, row.profileId, "Finish sign-in in the browser. Raiker will check again shortly.");
      if (loginPolling !== null) clearTimeout(loginPolling);
      loginPolling = setTimeout(() => void readSubscriptionStatus(row, true), 2000);
    } catch (error) {
      failure = set(
        failure,
        row.profileId,
        error instanceof ApiError && error.reasonCode
          ? `ChatGPT sign-in could not start (${error.reasonCode}).`
          : "ChatGPT sign-in could not start. Check that Codex is installed on this device.",
      );
    } finally {
      busy = drop(busy, row.profileId);
    }
  }

  /** Point the OpenAI-compatible profile at the owner's own server, then ask it. */
  async function saveEndpoint(row: Row) {
    const url = (endpoint[row.profileId] ?? "").trim();
    if (url === "") return;
    busy = set(busy, row.profileId, "saving");
    failure = drop(failure, row.profileId);
    note = drop(note, row.profileId);
    try {
      await api.saveModelConnection(row.profileId, url, "");
      note = set(note, row.profileId, "Endpoint saved. Asking it what it serves…");
      onchanged?.();
      await detect(row);
      if (catalogue[row.profileId]?.status === "available") note = drop(note, row.profileId);
    } catch (error) {
      const guidance = error instanceof ApiError ? providerErrorGuidance(error.reasonCode) : null;
      failure = set(
        failure,
        row.profileId,
        (guidance ? `${guidance.message} ${guidance.fix}` : null) ??
          (error instanceof ApiError && error.reasonCode
            ? `That endpoint was refused (${error.reasonCode}).`
            : "That endpoint was refused."),
      );
    } finally {
      busy = drop(busy, row.profileId);
    }
  }

  async function forget(row: Row) {
    if (
      !window.confirm(
        `Remove the stored ${row.label} credential from this Raiker instance? Nothing at ${row.label} is changed.`,
      )
    )
      return;
    busy = set(busy, row.profileId, "saving");
    try {
      await api.saveModelConnection(row.profileId, "", "");
      catalogue = drop(catalogue, row.profileId);
      choice = drop(choice, row.profileId);
      stored = set(stored, row.profileId, false);
      note = set(note, row.profileId, `${row.label} credential removed.`);
      onchanged?.();
    } catch {
      failure = set(failure, row.profileId, `The ${row.label} credential could not be removed.`);
    } finally {
      busy = drop(busy, row.profileId);
    }
  }

  /** Pin one concrete model to this profile. Enforced gate-manager-only server-side. */
  async function pin(row: Row) {
    const model = (choice[row.profileId] ?? "").trim();
    if (model === "") return;
    busy = set(busy, row.profileId, "pinning");
    failure = drop(failure, row.profileId);
    try {
      await api.selectModel(row.profileId, model);
      note = set(note, row.profileId, `${modelName(model)} is now this provider's model.`);
      onchanged?.();
      onselected?.(row.profileId, model);
    } catch (error) {
      failure = set(
        failure,
        row.profileId,
        error instanceof ApiError && error.reasonCode
          ? `That model could not be selected (${error.reasonCode}).`
          : "That model could not be selected.",
      );
    } finally {
      busy = drop(busy, row.profileId);
    }
  }

  /** Start serving one local GGUF. The runtime, not this page, picks the slot. */
  async function deploy(row: Row) {
    const modelId = (choice[row.profileId] ?? "").trim();
    if (modelId === "") return;
    busy = set(busy, row.profileId, "deploying");
    failure = drop(failure, row.profileId);
    try {
      await api.deployLocalModel(modelId);
      note = set(
        note,
        row.profileId,
        "Deployment queued. llama.cpp decides which of its four slots serves this model, and that slot becomes the selected profile once it answers — follow it in Activity.",
      );
      onchanged?.();
    } catch {
      failure = set(
        failure,
        row.profileId,
        "That model could not be deployed. It needs `llama-server` on PATH and a complete GGUF.",
      );
    } finally {
      busy = drop(busy, row.profileId);
    }
  }

  /**
   * A catalogue past this many models gets a filter box above it.
   *
   * OpenRouter really does serve 413 models. A native `<select>` of that length is
   * technically honest and practically unusable — the reference products that face
   * the same list all put a search box over it — and the first-run wizard is the
   * worst place to make someone scroll one. Below the threshold a filter is just a
   * control in the way, so it is absent.
   */
  const FILTER_THRESHOLD = 12;
  let filter = $state<Record<string, string>>({});

  /** This row's catalogue, narrowed by whatever the owner typed. */
  function visibleModels(row: Row): string[] {
    const all = catalogue[row.profileId]?.models ?? [];
    const needle = (filter[row.profileId] ?? "").trim().toLowerCase();
    if (needle === "") return all;
    // Matched against both the raw id and the displayed name: an owner reading
    // "Sonnet 4.5" should not have to know it is `claude-sonnet-4-5-20250929`.
    return all.filter(
      (model) =>
        model.toLowerCase().includes(needle) || modelName(model).toLowerCase().includes(needle),
    );
  }

  /** What a listing attempt actually found, in the row's own words. */
  function catalogueNote(row: Row, list: ProviderModelList): string {
    switch (list.status) {
      case "available":
        return list.models.length === 0
          ? `${row.label} answered, and is serving no models yet.`
          : `${list.models.length} model${list.models.length === 1 ? "" : "s"} from ${row.label}.`;
      case "policy_denied":
        return `${row.label} is blocked by provider policy. Enable its gate in Permissions first.`;
      case "unsupported":
        return `${row.label} does not publish a model list. Type the exact model id instead.`;
      default:
        return row.kind === "key"
          ? `${row.label} could not be reached. Check the credential and this device's network access.`
          : `${row.label} is not running on this device.`;
    }
  }

  // Local runtimes are asked once on open: detection is the row's whole content,
  // and a row that waits for a click to say what it found is a row that reads as
  // empty. Hosted providers are asked only when a credential is already stored —
  // there is nothing to ask with otherwise.
  let probed = false;
  $effect(() => {
    if (probed || rows.length === 0) return;
    probed = true;
    void loadGguf();
    for (const row of rows) {
      if (row.kind === "detect" || (row.kind === "key" && isConnected(row))) void detect(row);
      if (row.kind === "subscription") void readSubscriptionStatus(row);
    }
  });

  onDestroy(() => {
    if (loginPolling !== null) clearTimeout(loginPolling);
  });
</script>

<div class="provider-matrix">
  <div class="group-head">
    <h3>On this machine</h3>
    <p>No account and no network. Raiker asks each runtime what it is serving.</p>
  </div>

  {#each rows.filter((row) => row.kind === "gguf" || row.kind === "detect" || row.kind === "endpoint") as row (row.profileId)}
    <article class="row" role="group" aria-label={rowTitle(row)} data-provider={row.provider}>
      <div class="identity">
        <ProviderLogo provider={row.provider} />
        <div>
          <strong>{rowTitle(row)}</strong>
          <small>{row.source}</small>
        </div>
      </div>

      <div class="controls">
        {#if row.kind === "gguf"}
          <label class="field">
            <span class="sr-only">GGUF model to serve</span>
            <select
              class="select"
              aria-label="GGUF model to serve"
              bind:value={choice[row.profileId]}
              disabled={ggufModels === null || ggufModels.length === 0}
            >
              {#if ggufModels === null}
                <option value="">Reading your approved folders…</option>
              {:else if ggufModels.length === 0}
                <option value="">No complete GGUF found</option>
              {:else}
                {#each ggufModels as model (model.model_id)}
                  <option value={model.model_id}>{model.name} · {gigabytes(model.size_bytes)}</option>
                {/each}
              {/if}
            </select>
          </label>
          <button class="btn btn-ghost btn-sm" type="button" onclick={() => void scanGguf()}>
            <Icon name="refresh" size={14} /> Scan
          </button>
          <button
            class="btn btn-sm btn-primary"
            type="button"
            disabled={busy[row.profileId] !== undefined || !(choice[row.profileId] ?? "")}
            onclick={() => void deploy(row)}
          >
            {busy[row.profileId] === "deploying" ? "Starting…" : "Serve this model"}
          </button>
        {:else}
          {#if row.kind === "endpoint"}
            <!-- An OpenAI-compatible server is the one local row whose *address*
                 the owner owns. Without this the row said "any server you run" and
                 could only ever reach the profile's default port, which is a
                 promise it could not keep. Saving the endpoint goes through the
                 same governed connection path a key does, so the endpoint policy
                 (loopback vs private network vs remote) is classified server-side
                 exactly as it is everywhere else. -->
            <label class="field key-field">
              <span class="sr-only">{row.label} endpoint</span>
              <!-- The browser will otherwise offer the credential the owner
                   just typed into Raiker's own sign-in form, and drop their
                   username into a provider address. -->
              <input
                class="input"
                type="url"
                spellcheck="false"
                autocomplete="off"
                placeholder="http://127.0.0.1:8000/v1"
                aria-label={`${row.label} endpoint`}
                bind:value={endpoint[row.profileId]}
              />
            </label>
            <button
              class="btn btn-ghost btn-sm"
              type="button"
              disabled={busy[row.profileId] !== undefined || !(endpoint[row.profileId] ?? "").trim()}
              onclick={() => void saveEndpoint(row)}
            >
              {busy[row.profileId] === "saving" ? "Saving…" : "Save endpoint"}
            </button>
          {/if}
          {#if (catalogue[row.profileId]?.models.length ?? 0) > FILTER_THRESHOLD}
            <label class="field filter-field">
              <span class="sr-only">Filter {row.label} models</span>
              <input
                class="input"
                type="search"
                placeholder={`Filter ${catalogue[row.profileId].models.length} models`}
                aria-label={`Filter ${row.label} models`}
                bind:value={filter[row.profileId]}
              />
            </label>
          {/if}
          <label class="field">
            <span class="sr-only">{row.label} model</span>
            <select
              class="select"
              aria-label={`${row.label} model`}
              bind:value={choice[row.profileId]}
              disabled={visibleModels(row).length === 0}
            >
              {#if busy[row.profileId] === "detecting"}
                <option value="">Asking {row.label}…</option>
              {:else if (catalogue[row.profileId]?.models.length ?? 0) === 0}
                <option value="">No model detected</option>
              {:else if visibleModels(row).length === 0}
                <option value="">No model matches that filter</option>
              {:else}
                {#each visibleModels(row) as model (model)}
                  <option value={model}>{modelName(model)}</option>
                {/each}
              {/if}
            </select>
          </label>
          <button
            class="btn btn-ghost btn-sm"
            type="button"
            disabled={busy[row.profileId] !== undefined}
            onclick={() => void detect(row)}
          >
            <Icon name="refresh" size={14} /> Detect
          </button>
          <button
            class="btn btn-sm btn-primary"
            type="button"
            disabled={busy[row.profileId] !== undefined || !(choice[row.profileId] ?? "")}
            onclick={() => void pin(row)}
          >
            {busy[row.profileId] === "pinning" ? "Selecting…" : "Use this model"}
          </button>
        {/if}
      </div>

      <p class="state">
        {#if row.pinned}<span class="pinned">Selected: {modelName(row.pinned)}</span>{/if}
        {#if failure[row.profileId]}<span class="failed" role="alert">{failure[row.profileId]}</span>
        {:else if note[row.profileId]}<span role="status">{note[row.profileId]}</span>
        {:else if row.kind === "gguf" && ggufError}<span class="failed" role="alert">{ggufError}</span>
        {:else if catalogue[row.profileId]}<span>{catalogueNote(row, catalogue[row.profileId])}</span>{/if}
      </p>
    </article>
  {/each}

  <div class="group-head">
    <h3>With your ChatGPT subscription</h3>
    <p>Sign in through the local Codex client. Raiker never asks for or stores your ChatGPT token.</p>
  </div>

  {#each rows.filter((row) => row.kind === "subscription") as row (row.profileId)}
    <article class="row" role="group" aria-label={rowTitle(row)} data-provider={row.provider}>
      <div class="identity">
        <ProviderLogo provider={row.provider} />
        <div><strong>{rowTitle(row)}</strong><small>{row.source}</small></div>
      </div>
      <div class="controls">
        {#if isConnected(row)}
          <span class="stored">
            <Icon name="lock" size={13} />
            {subscriptionPlan
              ? `${subscriptionPlan.charAt(0).toUpperCase()}${subscriptionPlan.slice(1)} connected`
              : "Connected"}
          </span>
          <label class="field">
            <span class="sr-only">{row.label} model</span>
            <select class="select" aria-label={`${row.label} model`} bind:value={choice[row.profileId]} disabled={visibleModels(row).length === 0}>
              {#if busy[row.profileId] === "detecting"}<option value="">Asking {row.label}…</option>
              {:else if (catalogue[row.profileId]?.models.length ?? 0) === 0}<option value="">No model listed</option>
              {:else}{#each visibleModels(row) as model (model)}<option value={model}>{modelName(model)}</option>{/each}{/if}
            </select>
          </label>
          <button class="btn btn-ghost btn-sm" type="button" disabled={busy[row.profileId] !== undefined} onclick={() => void detect(row)}><Icon name="refresh" size={14} /> Refresh</button>
          <button class="btn btn-sm btn-primary" type="button" disabled={busy[row.profileId] !== undefined || !(choice[row.profileId] ?? "")} onclick={() => void pin(row)}>{busy[row.profileId] === "pinning" ? "Selecting…" : "Use this model"}</button>
          <!-- Reachable while connected: an owner holding more than one ChatGPT
               plan has no other way to move Raiker between them. -->
          <button class="btn btn-ghost btn-sm" type="button" disabled={busy[row.profileId] !== undefined} onclick={() => void startSubscriptionLogin(row)}>Switch account</button>
          <button class="btn btn-ghost btn-sm" type="button" disabled={busy[row.profileId] !== undefined} onclick={() => void disconnectSubscription(row)}>Sign out</button>
        {:else}
          <button class="btn btn-sm btn-primary" type="button" disabled={busy[row.profileId] !== undefined} onclick={() => void startSubscriptionLogin(row)}>{busy[row.profileId] === "saving" ? "Opening sign-in…" : "Sign in with ChatGPT"}</button>
        {/if}
      </div>
      <p class="state">
        {#if row.pinned}<span class="pinned">Selected: {modelName(row.pinned)}</span>{/if}
        {#if failure[row.profileId]}<span class="failed" role="alert">{failure[row.profileId]}</span>
        {:else if note[row.profileId]}<span role="status">{note[row.profileId]}</span>
        {:else if catalogue[row.profileId]}<span>{catalogueNote(row, catalogue[row.profileId])}</span>
        {:else if !isConnected(row)}<span>Sign in with the ChatGPT subscription on this device.</span>{/if}
      </p>
    </article>
  {/each}

  <div class="group-head">
    <h3>With an API key</h3>
    <p>
      Paste a key and Raiker asks that provider for its own catalogue. The key is
      encrypted at rest and never shown again — this page can only report that one
      is stored.
    </p>
  </div>

  {#each rows.filter((row) => row.kind === "key") as row (row.profileId)}
    <article class="row" role="group" aria-label={rowTitle(row)} data-provider={row.provider}>
      <div class="identity">
        <ProviderLogo provider={row.provider} />
        <div>
          <strong>{rowTitle(row)}</strong>
          <small>{row.source}</small>
        </div>
      </div>

      <div class="controls">
        {#if isConnected(row)}
          <span class="stored"><Icon name="lock" size={13} /> Key stored</span>
          {#if (catalogue[row.profileId]?.models.length ?? 0) > FILTER_THRESHOLD}
            <label class="field filter-field">
              <span class="sr-only">Filter {row.label} models</span>
              <input
                class="input"
                type="search"
                placeholder={`Filter ${catalogue[row.profileId].models.length} models`}
                aria-label={`Filter ${row.label} models`}
                bind:value={filter[row.profileId]}
              />
            </label>
          {/if}
          <label class="field">
            <span class="sr-only">{row.label} model</span>
            <select
              class="select"
              aria-label={`${row.label} model`}
              bind:value={choice[row.profileId]}
              disabled={visibleModels(row).length === 0}
            >
              {#if busy[row.profileId] === "detecting"}
                <option value="">Asking {row.label}…</option>
              {:else if (catalogue[row.profileId]?.models.length ?? 0) === 0}
                <option value="">No model listed</option>
              {:else if visibleModels(row).length === 0}
                <option value="">No model matches that filter</option>
              {:else}
                {#each visibleModels(row) as model (model)}
                  <option value={model}>{modelName(model)}</option>
                {/each}
              {/if}
            </select>
          </label>
          <button
            class="btn btn-sm btn-primary"
            type="button"
            disabled={busy[row.profileId] !== undefined || !(choice[row.profileId] ?? "")}
            onclick={() => void pin(row)}
          >
            {busy[row.profileId] === "pinning" ? "Selecting…" : "Use this model"}
          </button>
          <button
            class="btn btn-ghost btn-sm"
            type="button"
            disabled={busy[row.profileId] !== undefined}
            onclick={() => void forget(row)}
          >
            Forget key
          </button>
        {:else}
          <label class="field key-field">
            <span class="sr-only">{row.label} API key</span>
            <input
              class="input"
              type="password"
              autocomplete="new-password"
              spellcheck="false"
              placeholder={`${row.label} API key`}
              aria-label={`${row.label} API key`}
              bind:value={apiKey[row.profileId]}
              onkeydown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void saveKey(row);
                }
              }}
            />
          </label>
          <button
            class="btn btn-sm btn-primary"
            type="button"
            disabled={busy[row.profileId] !== undefined || !(apiKey[row.profileId] ?? "").trim()}
            onclick={() => void saveKey(row)}
          >
            {busy[row.profileId] === "saving" ? "Saving…" : "Save and list models"}
          </button>
        {/if}
      </div>

      <p class="state">
        {#if row.pinned}<span class="pinned">Selected: {modelName(row.pinned)}</span>{/if}
        {#if failure[row.profileId]}<span class="failed" role="alert">{failure[row.profileId]}</span>
        {:else if note[row.profileId]}<span role="status">{note[row.profileId]}</span>
        {:else if catalogue[row.profileId]}<span>{catalogueNote(row, catalogue[row.profileId])}</span>
        {:else if !isConnected(row)}<span>Key from {row.source}.</span>{/if}
      </p>
    </article>
  {/each}
</div>

<style>
  .provider-matrix {
    display: grid;
    gap: var(--space-2);
    min-width: 0;
  }
  .group-head {
    margin-top: var(--space-2);
  }
  .group-head:first-child {
    margin-top: 0;
  }
  .group-head h3 {
    margin: 0;
  }
  .group-head p {
    margin: 0.15rem 0 0;
    max-width: 62ch;
    color: var(--text-2);
    font-size: var(--text-sm);
    line-height: 1.45;
  }
  /* One row is one provider: who it is, how to reach it, and what it found. The
     three parts keep their own column on a wide screen and stack in order on a
     narrow one, so the row never becomes a grid the eye has to reassemble. */
  .row {
    display: grid;
    grid-template-columns: minmax(11rem, 15rem) minmax(0, 1fr);
    align-items: center;
    gap: var(--space-2) var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  .identity {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
  }
  .identity strong {
    display: block;
    color: var(--text-1);
    font-size: var(--text-md);
  }
  .identity small {
    display: block;
    color: var(--text-3);
    font-size: var(--text-2xs);
    line-height: 1.35;
  }
  .controls {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    justify-content: flex-end;
    min-width: 0;
  }
  .field {
    display: block;
    min-width: 0;
    flex: 1 1 11rem;
  }
  .field .select,
  .field .input {
    width: 100%;
  }
  .key-field {
    flex: 1 1 15rem;
  }
  /* Narrower than the picker it filters: the list is the answer, the filter is
     how you reach it. */
  .filter-field {
    flex: 0 1 9rem;
  }
  .stored {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.15rem 0.5rem;
    border: 1px solid var(--ok-border);
    border-radius: var(--r-pill);
    background: var(--ok-soft);
    color: var(--ok);
    font-size: var(--text-2xs);
    font-weight: 700;
    white-space: nowrap;
  }
  .state {
    grid-column: 1 / -1;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem var(--space-2);
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-xs);
    line-height: 1.4;
  }
  .pinned {
    color: var(--accent);
    font-weight: 700;
  }
  .failed {
    color: var(--danger);
  }
  @media (max-width: 52rem) {
    .row {
      grid-template-columns: minmax(0, 1fr);
    }
    .controls {
      justify-content: flex-start;
    }
  }
</style>
