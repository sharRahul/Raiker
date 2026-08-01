<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ProviderLogo from "../components/ProviderLogo.svelte";
  import ModelPricingPanel from "../components/ModelPricingPanel.svelte";
  import TabStrip from "../components/TabStrip.svelte";
  import { api, ApiError } from "../api";
  import type { ModelCapacitiesView, ModelProfile, ModelsView as ModelsData, ProviderModelList } from "../apiTypes";
  import { capabilityLabel } from "../capabilityModel";
  import { humanize, providerName } from "../format";
  import { formatCost, sourceNote, spendShares } from "../contextPresentation";
  import { providerErrorGuidance, type ProviderErrorGuidance } from "../providerErrors";
  import { modelName } from "../modelPresentation";
  import { setModels } from "../models.svelte";

  // The shell owns a models snapshot for the topbar chip; it passes onchanged
  // so a selection here is reflected there without a full page reload. `tab`
  // comes from the hash, so every panel is a shareable location — the context
  // popover's "Configure →" links straight to #/models?tab=pricing.
  let { onchanged, tab = "providers" }: { onchanged?: () => void; tab?: string } = $props();

  /**
   * The page is split by *what you came to do*, not by which table the data
   * lives in. Everything on this page used to be one long scroll, which meant
   * an owner looking for a rate scrolled past provider cards, and an owner
   * connecting a provider scrolled past the fallback list.
   */
  const TABS = [
    { id: "providers", label: "Providers" },
    { id: "routing", label: "Routing" },
    { id: "pricing", label: "Pricing" },
    { id: "posture", label: "Posture" },
  ];

  function selectTab(next: string) {
    window.location.hash = `#/models?tab=${encodeURIComponent(next)}`;
  }

  let models = $state<ModelsData | null>(null);
  let loadError = $state<string | null>(null);
  let capacities = $state<ModelCapacitiesView | null>(null);
  let capacityRefreshAttempted = false;

  // Editable copy of the user-owned fallback sequence (ordered profile ids).
  let sequence = $state<string[]>([]);
  let saving = $state(false);
  let saveError = $state<string | null>(null);
  let saved = $state(false);
  let addChoice = $state("");

  async function load() {
    loadError = null;
    try {
      models = await api.models();
      try {
        capacities = await api.modelCapacities();
        if (capacities.refresh_due && !capacityRefreshAttempted) {
          capacityRefreshAttempted = true;
          await api.refreshModelCapacities(false);
          models = await api.models();
          capacities = await api.modelCapacities();
        }
      } catch { capacities = null; }
      // Mirror the fresh snapshot into the shared store so every mounted
      // composer (Chat, Build) updates its model picker without a reload —
      // connecting a provider, selecting a model, or reordering the fallback
      // all flow through here.
      setModels(models);
      sequence = [...models.fallback_sequence];
      advisorChoice = models.advisor_profile_id ?? "";
    } catch (e) {
      models = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  // ── Model selection (per provider) ──────────────────────────────────
  // One picker open at a time. The model list comes from the provider itself,
  // on demand; when the catalogue is unavailable the user can type a model id.
  let pickerFor = $state<string | null>(null);
  let pickerList = $state<ProviderModelList | null>(null);
  let pickerLoading = $state(false);
  let pickerChoice = $state("");
  let selecting = $state(false);
  let selectError = $state<string | null>(null);
  const globalChoices = $derived(
    models?.chat_profiles ?? (models?.profiles ?? []).filter((profile) => profile.configured),
  );
  const globalChoice = $derived.by(() => {
    const selected = globalChoices.find((profile) => profile.selected);
    return selected ? JSON.stringify([selected.profile_id, selected.model]) : "";
  });

  async function selectGlobal(value: string) {
    if (!value) return;
    const [profileId, model] = JSON.parse(value) as [string, string];
    await select(profileId, model);
  }

  function normalizePickerList(list: ProviderModelList): ProviderModelList {
    if (list.status !== "available") return list;
    return { ...list, models: [...new Set(list.models)] };
  }

  // ── Sign-in / connection modal ─────────────────────────────────────
  // Hosted and Advanced providers present their connection as a focused
  // sign-in dialog instead of an inline form: a provider-branded card with an
  // email + API key (the real credential the backend stores) and an advanced
  // custom-endpoint toggle. The credential is saved once into the encrypted,
  // per-instance vault and never returned to this view.
  let signInFor = $state<string | null>(null);
  let signInApiKey = $state("");
  let signInEndpoint = $state("");
  let signInAdvanced = $state(false);
  let signInSaving = $state(false);
  let signInError = $state<string | null>(null);
  let testFor = $state<string | null>(null);
  let testResult = $state<string | null>(null);
  let detailsFor = $state<ModelProfile | null>(null);
  // Governed refusals are policy outcomes, not faults. Hold the reason code so
  // the dialog can render the control that unblocks it instead of a bare code.
  let signInGuidance = $state<ProviderErrorGuidance | null>(null);

  const signInProfile = $derived(models?.profiles.find((p) => p.profile_id === signInFor) ?? null);

  function contextCapacity(profile: ModelProfile): string {
    if (!profile.context_window_tokens) {
      return "Not reported by this runtime. Refresh its model catalogue or configure an exact fallback before relying on a percentage.";
    }
    const source = profile.context_window_source === "owner"
      ? "Administrator override"
      : profile.context_window_source === "provider"
        ? "Reported by the provider runtime"
        : "Configured in Raiker";
    return `${new Intl.NumberFormat().format(profile.context_window_tokens)} tokens · ${source}`;
  }

  async function configureCapacity(profile: ModelProfile) {
    const raw = window.prompt("Exact context capacity in tokens. Leave blank to clear the administrator override.", profile.context_window_tokens?.toString() ?? "");
    if (raw === null) return;
    const tokens = raw.trim() ? Number(raw) : null;
    if (tokens !== null && (!Number.isInteger(tokens) || tokens < 1024)) { selectError = "Context capacity must be an integer of at least 1,024 tokens."; return; }
    const reason = window.prompt("Why is this override needed?", "Verified against the local runtime configuration");
    if (reason === null) return;
    try { await api.setModelCapacity(profile.profile_id, profile.model, tokens, reason); await load(); }
    catch { selectError = "Could not update context capacity."; }
  }

  function openSignIn(profileId: string) {
    signInFor = profileId;
    signInApiKey = "";
    signInEndpoint = "";
    signInAdvanced = false;
    signInError = null;
    signInGuidance = null;
  }
  function closeSignIn() {
    signInFor = null;
    signInError = null;
    signInGuidance = null;
  }

  async function saveConnection(profileId: string) {
    signInSaving = true;
    signInError = null;
    signInGuidance = null;
    try {
      // Email is captured for a friendlier sign-in feel but only the API key
      // and optional endpoint are stored server-side (the backend vault has no
      // email field). Keeping it in the UI only avoids sending unused PII.
      await api.saveModelConnection(profileId, signInEndpoint.trim(), signInApiKey.trim());
      signInApiKey = "";
      signInEndpoint = "";
      signInFor = null;
      await load();
    } catch (e) {
      signInGuidance = e instanceof ApiError ? providerErrorGuidance(e.reasonCode) : null;
      signInError = signInGuidance !== null
        ? null
        : e instanceof ApiError
          ? `Could not connect (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not connect";
    } finally {
      signInSaving = false;
    }
  }

  async function testConnection(profile: ModelProfile) {
    testFor = profile.profile_id;
    testResult = null;
    try {
      const result = await api.providerModels(profile.profile_id);
      testResult = result.status === "available"
        ? `${providerName(profile.provider)} responded and exposed ${result.models.length} model${result.models.length === 1 ? "" : "s"}.`
        : pickerNote(result);
    } catch {
      testResult = "Raiker could not reach this provider.";
    } finally {
      testFor = null;
    }
  }

  async function openPicker(profileId: string) {
    if (pickerFor === profileId) {
      closePicker();
      return;
    }
    pickerFor = profileId;
    pickerList = null;
    pickerChoice = "";
    selectError = null;
    pickerLoading = true;
    try {
      pickerList = normalizePickerList(await api.providerModels(profileId));
    } catch {
      pickerList = null; // manual entry still works
    } finally {
      pickerLoading = false;
    }
  }

  function closePicker() {
    pickerFor = null;
    pickerList = null;
    pickerChoice = "";
    selectError = null;
  }

  async function select(profileId: string, model = "") {
    selecting = true;
    selectError = null;
    try {
      await api.selectModel(profileId, model.trim() || undefined);
      closePicker();
      await load();
      onchanged?.();
    } catch (e) {
      selectError =
        e instanceof ApiError
          ? `Could not select (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not select";
    } finally {
      selecting = false;
    }
  }

  // ── Advisor model ──────────────────────────────────────────────────
  let advisorChoice = $state("");
  let advisorSaving = $state(false);
  let advisorError = $state<string | null>(null);
  let advisorSaved = $state(false);

  const advisorCandidates = $derived(
    (models?.profiles ?? []).filter((p) => p.model !== "<model>"),
  );
  const advisorDirty = $derived(
    models !== null && advisorChoice !== (models.advisor_profile_id ?? ""),
  );

  async function saveAdvisor() {
    advisorSaving = true;
    advisorError = null;
    advisorSaved = false;
    try {
      const result = await api.setModelAdvisor(advisorChoice || null);
      if (models !== null) {
        models = { ...models, advisor_profile_id: result.advisor_profile_id };
      }
      advisorChoice = result.advisor_profile_id ?? "";
      advisorSaved = true;
    } catch (e) {
      advisorError =
        e instanceof ApiError
          ? `Could not save (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not save";
    } finally {
      advisorSaving = false;
    }
  }

  function pickerNote(list: ProviderModelList): string {
    switch (list.status) {
      case "policy_denied":
        return "Model list denied by provider policy — enable the provider's gate first. You can still type a model id.";
      case "unsupported":
        return "This provider does not support model listing — type a model id.";
      default:
        return "Provider unreachable — type a model id if you know it.";
    }
  }

  const addable = $derived(
    (models?.profiles ?? []).filter((p) => !sequence.includes(p.profile_id)),
  );

  const dirty = $derived(
    models !== null && JSON.stringify(sequence) !== JSON.stringify(models.fallback_sequence),
  );

  function profileLabel(id: string): string {
    const p = models?.profiles.find((x) => x.profile_id === id);
    return p ? providerName(p.provider) : id;
  }

  function move(index: number, delta: number) {
    const next = index + delta;
    if (next < 0 || next >= sequence.length) return;
    const copy = [...sequence];
    [copy[index], copy[next]] = [copy[next], copy[index]];
    sequence = copy;
    saved = false;
  }

  function remove(index: number) {
    sequence = sequence.filter((_, i) => i !== index);
    saved = false;
  }

  function add() {
    if (addChoice === "" || sequence.includes(addChoice)) return;
    sequence = [...sequence, addChoice];
    addChoice = "";
    saved = false;
  }

  async function save() {
    saving = true;
    saveError = null;
    saved = false;
    try {
      const result = await api.setModelFallback(sequence);
      sequence = [...result.fallback_sequence];
      if (models !== null) models = { ...models, fallback_sequence: result.fallback_sequence };
      saved = true;
    } catch (e) {
      saveError =
        e instanceof ApiError
          ? `Could not save (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not save";
    } finally {
      saving = false;
    }
  }

  function endpointLabel(kind: string): string {
    switch (kind) {
      case "local_process":
      case "local":
        return "Local";
      case "private_network":
        return "Home-lab";
      case "remote_hosted":
        return "Hosted";
      default:
        return humanize(kind);
    }
  }

  // Plain-English labels for the backend's gate-state identifiers. These are
  // the values the backend stores as enabled_runtime / enabled_policy_gated /
  // etc. — showing them raw (even via humanize()) reads as jargon.
  function gateStateLabel(state: string): string {
    switch (state) {
      case "enabled_runtime": return "On";
      case "enabled_policy_gated": return "On (policy-gated)";
      case "enabled_read_only": return "Read-only";
      case "disabled": return "Off";
      default: return humanize(state);
    }
  }

  function sectionFor(profile: ModelProfile): "Local" | "Hosted" | "Advanced" {
    if (profile.provider === "openrouter" || profile.provider === "huggingface" || profile.provider === "ollama-cloud" || profile.provider === "openai-compatible") return "Advanced";
    return profile.requires_network ? "Hosted" : "Local";
  }

  const sections = ["Local", "Hosted", "Advanced"] as const;
  const configuredProfiles = $derived((models?.profiles ?? []).filter((p) => p.connection_configured || p.selected));
  // A percentage of "all shipped profiles" was a meaningless denominator — a
  // user who connects the one provider they intend to use is finished, not 10%
  // finished. The honest headline is how many providers are actually ready.
  const readyCount = $derived(configuredProfiles.length);

  // Each provider's bar is its share of total spend across every provider, so
  // it needs no configured budget to mean something. Providers with no cost
  // (local runtimes, or ones never used) simply have no bar.
  const spendByProfile = $derived(
    spendShares(
      (models?.profiles ?? []).map((p) => ({ id: p.profile_id, cost: p.total_cost })),
    ),
  );
  const totalSpend = $derived(
    (models?.profiles ?? []).reduce((sum, p) => {
      const value = Number(p.total_cost);
      return Number.isFinite(value) && value > 0 ? sum + value : sum;
    }, 0),
  );
  const spendCurrency = $derived(
    (models?.profiles ?? []).find((p) => p.total_cost && p.cost_currency)?.cost_currency ?? "USD",
  );

  function usageLine(profile: ModelProfile): string {
    if (!profile.billable) return "No API cost — runs on this machine";
    const used = profile.models_used ?? 0;
    if (used === 0) return "Not used yet";
    const turns = profile.turns_used ?? 0;
    return `${used} model${used === 1 ? "" : "s"} used · ${turns} turn${turns === 1 ? "" : "s"}`;
  }
  function profilesFor(section: "Local" | "Hosted" | "Advanced") {
    return (models?.profiles ?? []).filter((profile) => sectionFor(profile) === section);
  }
  function providerHelp(profile: ModelProfile): string {
    if (profile.provider === "ollama") return "Run Ollama locally, then choose one of its installed models.";
    if (profile.provider === "lm-studio") return "Start the LM Studio local server, then choose the loaded model.";
    if (profile.provider === "llama.cpp") return "Start llama-server and expose the model name configured by the server.";
    if (profile.provider === "openai-compatible") return "Use this for a vLLM, home-lab, or other OpenAI-compatible endpoint you control.";
    if (profile.provider === "anthropic") return "Sign in with your Anthropic API key, enable hosted access, then choose a model.";
    return "Sign in with your provider key, enable the required policy gate, then choose a model.";
  }

  // Provider brand metadata for the sign-in screen. Each provider is researched
  // and matches its real auth surface:
  //   - Anthropic: API key only (docs.anthropic.com — x-api-key, no OAuth)
  //   - OpenAI: API key (platform.openai.com — Bearer; account login is for the
  //     dashboard, not the API itself)
  //   - Gemini: API key (AI Studio) AND Google login (Vertex AI / ADC)
  //   - OpenRouter: API key only (openrouter.ai — Bearer)
  //   - Hugging Face: access token AND login (HF tokens "used in place of
  //     password"; huggingface.co/docs)
  //   - Ollama local: no auth; Ollama Cloud: API key
  // Raiker stores the credential in its encrypted vault — it does not perform a
  // real OAuth redirect (that needs backend client-id/redirect support). The
  // "Sign in" button links to the provider's key/token page so the user can
  // grab one, then paste it here.
  type AuthMethod = "login" | "apikey";
  interface Brand {
    tint: string;
    headline: string;
    credentialLabel: string;
    hint: string;
    authMethods: AuthMethod[];
    loginUrl?: string;
    loginLabel?: string;
  }
  function brand(provider: string): Brand {
    switch (provider) {
      case "anthropic":
        return { tint: "#d97757", headline: "Connect to Anthropic", credentialLabel: "Anthropic API key", hint: "Create a key at console.anthropic.com. Anthropic uses API keys only — no email login.", authMethods: ["apikey"], loginUrl: "https://console.anthropic.com/settings/keys", loginLabel: "Get an Anthropic key" };
      case "openai":
        // Sign-in here means signing in to the OpenAI *platform* account —
        // Google, Microsoft, and Apple all work — to create an API key, which
        // is then pasted below. It deliberately does not claim to use a ChatGPT
        // subscription: ChatGPT Plus/Pro and the API are separately billed, and
        // no subscription grants a third-party app API access. Saying so here
        // is cheaper than a user discovering it through a 401.
        return { tint: "#10a37f", headline: "Connect to OpenAI", credentialLabel: "OpenAI API key", hint: "Sign in to platform.openai.com with Google, Microsoft, Apple, or email, then create an API key and paste it below. API usage is billed separately from a ChatGPT subscription — a Plus or Pro plan does not include API access.", authMethods: ["login", "apikey"], loginUrl: "https://platform.openai.com/api-keys", loginLabel: "Sign in with Google or email" };
      case "gemini":
        return { tint: "#4285f4", headline: "Connect to Google AI", credentialLabel: "Gemini API key", hint: "Create a key in Google AI Studio. Google also supports sign-in with your Google account via Vertex AI.", authMethods: ["login", "apikey"], loginUrl: "https://aistudio.google.com/apikey", loginLabel: "Sign in with Google" };
      case "openrouter":
        return { tint: "#6b3fa0", headline: "Connect to OpenRouter", credentialLabel: "OpenRouter API key", hint: "Create a key at openrouter.ai/keys. OpenRouter uses API keys only.", authMethods: ["apikey"], loginUrl: "https://openrouter.ai/keys", loginLabel: "Get an OpenRouter key" };
      case "huggingface":
        return { tint: "#ff9d00", headline: "Connect to Hugging Face", credentialLabel: "Hugging Face access token", hint: "Create a token at huggingface.co/settings/tokens. You can also sign in with your Hugging Face account.", authMethods: ["login", "apikey"], loginUrl: "https://huggingface.co/settings/tokens", loginLabel: "Sign in to Hugging Face" };
      case "ollama-cloud":
        return { tint: "#22c55e", headline: "Connect to Ollama Cloud", credentialLabel: "Ollama Cloud API key", hint: "Managed Ollama endpoint key. Create one from your Ollama Cloud account.", authMethods: ["apikey"] };
      case "openai-compatible":
        return { tint: "#0f766e", headline: "Connect your endpoint", credentialLabel: "API key (optional)", hint: "A custom OpenAI-compatible endpoint you control (vLLM, home-lab, etc.).", authMethods: ["apikey"] };
      default:
        return { tint: "#0f766e", headline: `Connect to ${providerName(provider)}`, credentialLabel: "API key", hint: "Your provider key, stored encrypted in this Raiker instance.", authMethods: ["apikey"] };
    }
  }

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    The model profiles Raiker can talk to. The choice of backend belongs to you — local, home-lab,
    or hosted — and there is never a silent fallback between them.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh models">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

<TabStrip tabs={TABS} selected={tab} onselect={selectTab} label="Model settings" />

{#if loadError}
  <PageState state="error" title="Couldn't load models" detail={loadError} />
{:else if models === null}
  <PageState state="loading" title="Loading models…" />
{:else}
  {#if tab === "providers"}
  <div class="panel" role="tabpanel" id="panel-providers" aria-labelledby="tab-providers">
  <p class="tab-lead">
    Connect a provider and choose the exact model that serves your work. You can also choose per
    prompt in Chat, or in the terminal client (<code>/model use …</code>).
  </p>
  {#if models.profiles.length === 0}
    <div class="card">
      <EmptyState icon="models" title="No model profiles configured" body="Add profiles in config/model-profiles.json." />
    </div>
  {:else}
    <section class="setup-overview card" aria-labelledby="model-setup-title">
      <div>
        <p class="eyebrow">Model setup</p>
        <h2 id="model-setup-title">Choose where Raiker thinks</h2>
        <p class="sub">Each connection belongs only to this Raiker instance. One ready provider is enough to work.</p>
      </div>
      <div class="setup-meter" aria-label={`${readyCount} of ${models.profiles.length} providers set up`}>
        <strong>{readyCount} <span class="of">of {models.profiles.length}</span></strong>
        <span>providers set up</span>
        {#if totalSpend > 0}
          <p class="total-spend">{formatCost(String(totalSpend), spendCurrency)} total API cost</p>
        {/if}
      </div>
    </section>

    <section class="global-model-card card" aria-labelledby="global-model-title">
      <div class="global-model-copy">
        <p class="eyebrow">Default</p>
        <h2 id="global-model-title">Global model</h2>
        <p class="sub">Used whenever a surface does not choose its own model, including each scheduled run when it begins.</p>
      </div>
      <label class="global-model-field">
        <span>Global model</span>
        <small>Choose any configured provider and exact model.</small>
        <select aria-label="Global model" value={globalChoice} onchange={(event) => void selectGlobal(event.currentTarget.value)} disabled={selecting}>
          <option value="" disabled>Choose a global model</option>
          {#each globalChoices as profile (`${profile.profile_id}\u0000${profile.model}`)}
            <option value={JSON.stringify([profile.profile_id, profile.model])}>{providerName(profile.provider)} — {modelName(profile.model)}</option>
          {/each}
        </select>
      </label>
    </section>

    {#each sections as section}
      {@const sectionProfiles = profilesFor(section)}
      {#if sectionProfiles.length}
      <section class="provider-section" aria-labelledby={`section-${section}`}>
        <div class="section-heading">
          <div><p class="eyebrow">{section}</p><h2 id={`section-${section}`}>{section === "Local" ? "On this device" : section === "Hosted" ? "Your hosted providers" : "Advanced connections"}</h2></div>
          <p>{section === "Local" ? "Private by default; nothing leaves this device." : section === "Hosted" ? "Sign in with your own account and opt in to network access." : "Custom endpoints and provider routers for power users."}</p>
        </div>

        {#if section === "Local"}
          <div class="local-list">
            {#each sectionProfiles as p (p.profile_id)}
              <div class="local-row" class:selected={p.selected} class:picker-open={pickerFor === p.profile_id}>
                <span class="row-logo"><ProviderLogo provider={p.provider} size={28} /></span>
                <div class="row-main">
                  <div class="row-title">
                    <h3>{providerName(p.provider)}</h3>
                    {#if p.selected}<Badge variant="active" label="selected" />{/if}
                  </div>
                  <p class="row-model">
                    {#if p.model === "<model>"}<span class="model-unpinned">model chosen at selection</span>{:else}<code>{modelName(p.model)}</code>{/if}
                  </p>
                  <p class="row-help">{providerHelp(p)}</p>
                  <div class="chips">
                    <span class="chip">{endpointLabel(p.endpoint_kind)}</span>
                    {#if p.local_only}<span class="chip chip-ok">Local-only</span>{/if}
                    {#if p.connection_configured}<span class="chip chip-ok">Connection saved</span>{/if}
                    {#if p.prompt_cache_ttl}<span class="chip chip-ok" title="Prompt caching cuts cost and latency by reusing the stable prompt prefix">Cache {p.prompt_cache_ttl}</span>{/if}
                  </div>
                </div>
                <div class="row-usage"><span>{usageLine(p)}</span></div>
                <div class="row-actions">
                  <button type="button" class="btn btn-ghost btn-sm" onclick={() => void testConnection(p)} disabled={testFor === p.profile_id}>{testFor === p.profile_id ? "Testing…" : "Test"}</button>
                  <button type="button" class="btn btn-ghost btn-sm" onclick={() => detailsFor = p}>Details</button>
                  <button type="button" class="btn btn-ghost btn-sm" onclick={() => void openPicker(p.profile_id)} aria-expanded={pickerFor === p.profile_id}>{p.model === "<model>" ? "Choose model…" : "Change model…"}</button>
                  {#if !p.selected && p.model !== "<model>"}
                    <button type="button" class="btn btn-sm" onclick={() => void select(p.profile_id)} disabled={selecting}>Select</button>
                  {/if}
                </div>
                {#if pickerFor === p.profile_id}
                  <div class="picker local-picker-inline">
                    {#if pickerLoading}
                      <p class="picker-note" role="status">Loading models from {providerName(p.provider)}…</p>
                    {:else}
                      {#if pickerList !== null && pickerList.status === "available" && pickerList.models.length > 0}
                        <select class="picker-select" bind:value={pickerChoice} aria-label="Available models">
                          <option value="">Pick a model…</option>
                          {#each pickerList.models as m (m)}
                            <option value={m}>{modelName(m)}</option>
                          {/each}
                        </select>
                      {:else}
                        {#if pickerList !== null}
                          <p class="picker-note">{pickerNote(pickerList)}</p>
                        {:else}
                          <p class="picker-note">Model list unavailable — enter a custom model name.</p>
                        {/if}
                        <input class="picker-input" type="text" placeholder="Custom model name" bind:value={pickerChoice} aria-label="Custom model name" />
                      {/if}
                      <div class="picker-actions">
                        <button type="button" class="btn btn-primary btn-sm" onclick={() => void select(p.profile_id, pickerChoice)} disabled={selecting || pickerChoice.trim() === ""}>{selecting ? "Selecting…" : "Use model"}</button>
                        <button type="button" class="btn btn-ghost btn-sm" onclick={closePicker}>Cancel</button>
                      </div>
                      {#if selectError}<p class="error picker-error" role="alert">{selectError}</p>{/if}
                    {/if}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <div class="provider-grid">
            {#each sectionProfiles as p (p.profile_id)}
              {@const b = brand(p.provider)}
              <article class="provider-card" class:selected={p.selected} class:connected={p.connection_configured}>
                <div class="pc-head">
                  <span class="pc-logo"><ProviderLogo provider={p.provider} size={34} /></span>
                  <div class="pc-title"><h3>{providerName(p.provider)}</h3>
                    {#if p.selected}<Badge variant="active" label="selected" />{/if}
                  </div>
                </div>
                <p class="pc-model">
                  {#if p.model === "<model>"}<span class="model-unpinned">no model pinned</span>{:else}<code>{modelName(p.model)}</code>{/if}
                </p>
                <p class="pc-status">
                  {#if p.connection_configured}
                    <span class="status-dot ok" aria-hidden="true"></span> Connected
                  {:else}
                    <span class="status-dot" aria-hidden="true"></span> Not connected
                  {/if}
                </p>
                <div class="chips">
                  {#if p.requires_network}<span class="chip chip-warn">Needs network</span>{/if}
                  {#if p.requires_egress_policy}<span class="chip chip-warn">Egress-gated</span>{/if}
                  {#if p.runtime_gate}<span class="chip" title="Runtime gate that must be enabled">{capabilityLabel(p.runtime_gate)}</span>{/if}
                  {#if p.prompt_cache_ttl}<span class="chip chip-ok" title="Prompt caching cuts cost and latency">Cache {p.prompt_cache_ttl}</span>{/if}
                </div>
                <div class="usage-strip">
                  <div class="usage-line">
                    <span>{usageLine(p)}</span>
                    {#if p.billable}
                      <strong>{formatCost(p.total_cost, p.cost_currency) ?? "—"}</strong>
                    {/if}
                  </div>
                  {#if spendByProfile[p.profile_id] !== undefined}
                    <!-- BUG-37 — a bar, not a meter: this is one provider's
                         share of a comparison, so it carries no capacity tone.
                         Same geometry as the context meter, different meaning,
                         and both now come from one place. -->
                    <div
                      class="bar spend-bar"
                      style={`--meter-value: ${spendByProfile[p.profile_id]}`}
                      role="progressbar"
                      aria-label={`${providerName(p.provider)} share of total API spend`}
                      aria-valuemin="0"
                      aria-valuemax="100"
                      aria-valuenow={spendByProfile[p.profile_id]}
                    >
                      <span class="bar-fill" data-value={spendByProfile[p.profile_id]}></span>
                    </div>
                    <p class="usage-note">{spendByProfile[p.profile_id]}% of your total API spend{#if sourceNote(p.price_source, p.price_as_of)}&nbsp;· {sourceNote(p.price_source, p.price_as_of)}{/if}</p>
                  {:else if p.billable && (p.turns_used ?? 0) > 0}
                    <p class="usage-note">No price configured for the models used, so cost is unknown.</p>
                  {/if}
                </div>

                <div class="pc-actions">
                  {#if !p.connection_configured}
                    <button type="button" class="btn btn-primary btn-sm pc-connect" onclick={() => openSignIn(p.profile_id)} style={`--brand:${b.tint}`}>Connect</button>
                  {:else}
                    <button type="button" class="btn btn-ghost btn-sm" onclick={() => openSignIn(p.profile_id)}>Reconnect</button>
                    <button type="button" class="btn btn-ghost btn-sm" onclick={() => void testConnection(p)} disabled={testFor === p.profile_id}>{testFor === p.profile_id ? "Testing…" : "Test"}</button>
                  {/if}
                  <button type="button" class="btn btn-ghost btn-sm" onclick={() => void openPicker(p.profile_id)} aria-expanded={pickerFor === p.profile_id}>{p.model === "<model>" ? "Choose model…" : "Change model…"}</button>
                  {#if p.connection_configured && !p.selected && p.model !== "<model>"}
                    <button type="button" class="btn btn-sm" onclick={() => void select(p.profile_id)} disabled={selecting}>Select</button>
                  {/if}
                  <button type="button" class="btn btn-ghost btn-sm" onclick={() => detailsFor = p}>Details</button>
                </div>
                {#if testResult && testFor === null && p.connection_configured}
                  <p class="test-result" role="status">{testResult}</p>
                {/if}

                {#if pickerFor === p.profile_id}
                  <div class="picker">
                    {#if pickerLoading}
                      <p class="picker-note" role="status">Loading models from {providerName(p.provider)}…</p>
                    {:else}
                      {#if pickerList !== null && pickerList.status === "available" && pickerList.models.length > 0}
                        <select class="picker-select" bind:value={pickerChoice} aria-label="Available models">
                          <option value="">Pick a model…</option>
                          {#each pickerList.models as m (m)}
                            <option value={m}>{modelName(m)}</option>
                          {/each}
                        </select>
                      {:else}
                        {#if pickerList !== null}
                          <p class="picker-note">{pickerNote(pickerList)}</p>
                        {:else}
                          <p class="picker-note">Model list unavailable — enter a custom model name.</p>
                        {/if}
                        <input class="picker-input" type="text" placeholder="Custom model name" bind:value={pickerChoice} aria-label="Custom model name" />
                      {/if}
                      <div class="picker-actions">
                        <button type="button" class="btn btn-primary btn-sm" onclick={() => void select(p.profile_id, pickerChoice)} disabled={selecting || pickerChoice.trim() === ""}>{selecting ? "Selecting…" : "Use model"}</button>
                        <button type="button" class="btn btn-ghost btn-sm" onclick={closePicker}>Cancel</button>
                      </div>
                      {#if selectError}<p class="error picker-error" role="alert">{selectError}</p>{/if}
                    {/if}
                  </div>
                {/if}
              </article>
            {/each}
          </div>
        {/if}
      </section>
      {/if}
    {/each}

    {#if selectError && pickerFor === null}
      <p class="error" role="alert">{selectError}</p>
    {/if}
  {/if}
  </div>
  {/if}

  {#if tab === "routing"}
  <div class="panel" role="tabpanel" id="panel-routing" aria-labelledby="tab-routing">
  <p class="tab-lead">
    What serves a turn when your first choice cannot, and which model a local model may consult.
    Nothing here grants access: every candidate is still gated by provider policy at call time.
  </p>
  <section class="card fallback" aria-labelledby="fallback-h">
    <h2 id="fallback-h">Model fallback sequence</h2>
    <p class="sub">
      If the selected provider is unavailable — no network, a timeout, a non-responsive host, or a
      policy denial — Raiker tries these backends in order, top to bottom. Point it at your local
      runtimes (llama.cpp, Ollama, LM Studio, vLLM) so a turn never dead-ends when a hosted API is
      down. Each candidate is still gated by provider policy: listing a hosted provider here never
      grants access on its own.
    </p>

    {#if sequence.length === 0}
      <p class="fallback-empty">No fallback configured. The turn fails closed if the selected provider is unavailable.</p>
    {:else}
      <ol class="fallback-list">
        {#each sequence as id, i (id)}
          <li class="fallback-item">
            <span class="rank">{i + 1}</span>
            <span class="fallback-name">
              {profileLabel(id)}
            </span>
            <span class="fallback-actions">
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">↑</button>
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => move(i, 1)} disabled={i === sequence.length - 1} aria-label="Move down">↓</button>
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => remove(i)} aria-label="Remove">Remove</button>
            </span>
          </li>
        {/each}
      </ol>
    {/if}

    <div class="fallback-add">
      <select bind:value={addChoice} aria-label="Add a fallback backend">
        <option value="">Add a backend…</option>
        {#each addable as p (p.profile_id)}
          <option value={p.profile_id}>{providerName(p.provider)}{p.model !== "<model>" ? ` (${modelName(p.model)})` : " (no model)"}</option>
        {/each}
      </select>
      <button type="button" class="btn btn-sm" onclick={add} disabled={addChoice === ""}>Add</button>
    </div>

    <div class="fallback-save">
      <button type="button" class="btn btn-primary btn-sm" onclick={save} disabled={!dirty || saving}>
        {saving ? "Saving…" : "Save sequence"}
      </button>
      {#if saveError}
        <span class="error" role="alert">{saveError}</span>
      {:else if saved && !dirty}
        <span class="ok-note">Saved.</span>
      {/if}
    </div>
  </section>

  <section class="card advisor" aria-labelledby="advisor-h">
    <h2 id="advisor-h">Advisor model</h2>
    <p class="sub">
      When you run a local model, it can consult one advisor — typically a hosted model — through
      the governed <code>consult_advisor</code> tool. Picking an advisor grants nothing on its own:
      the consult is gated by the <code>advisor_model_runtime</code> capability, its decision mode
      (default <strong>ask</strong>, which withholds the consult), and the provider's own policy
      (hosted gate, egress allowlist, API key) at call time. The advisor's answer is always treated
      as untrusted data, and the question/answer never enter the audit log — only lengths do.
    </p>
    <div class="advisor-row">
      <select bind:value={advisorChoice} aria-label="Advisor model profile">
        <option value="">No advisor</option>
        {#each advisorCandidates as p (p.profile_id)}
          <option value={p.profile_id}>{providerName(p.provider)} — {modelName(p.model)}</option>
        {/each}
      </select>
      <button type="button" class="btn btn-primary btn-sm" onclick={saveAdvisor} disabled={!advisorDirty || advisorSaving}>
        {advisorSaving ? "Saving…" : "Save advisor"}
      </button>
      {#if advisorError}
        <span class="error" role="alert">{advisorError}</span>
      {:else if advisorSaved && !advisorDirty}
        <span class="ok-note">Saved.</span>
      {/if}
    </div>
  </section>

  </div>
  {/if}

  {#if tab === "pricing"}
  <div class="panel" role="tabpanel" id="panel-pricing" aria-labelledby="tab-pricing">
    <!-- BUG-21 — the price registry. Its own destination, because looking up
         what a model costs is its own errand, not a footnote to connecting one. -->
    <ModelPricingPanel />
  </div>
  {/if}

  {#if tab === "posture"}
  <div class="panel" role="tabpanel" id="panel-posture" aria-labelledby="tab-posture">
  <section class="card gate-status" aria-labelledby="model-gates-h">
    <h2 id="model-gates-h">Off-machine provider posture</h2>
    <dl class="gates">
      <div><dt>Hosted model gate</dt><dd>{gateStateLabel(models.hosted_model_gate_state)}</dd></div>
      <div><dt>Private-network gate</dt><dd>{gateStateLabel(models.private_network_model_gate_state)}</dd></div>
      <div><dt>Egress allowlist</dt><dd><code>{models.model_egress_allowlist_configured ? "configured" : "not configured"}</code></dd></div>
      <div><dt>Off-machine profiles</dt><dd><code>{models.remote_profile_count}</code></dd></div>
    </dl>
    <p class="sub">
      Read-only status. Allowlist values and API keys are never displayed. Hosted providers fail
      closed unless the runtime gate, threat-model acknowledgement, confirmation token, egress
      allowlist, and provider key are all present{models.no_silent_hosted_fallback ? " — and there is no silent fallback to hosted models" : ""}.
    </p>
  </section>
  </div>
  {/if}
{/if}

{#if detailsFor}
  {@const capacityEntry = capacities?.entries.find((entry) => entry.profile_id === detailsFor!.profile_id && entry.model === detailsFor!.model)}
  <div class="details-overlay" role="presentation" onclick={(event) => event.target === event.currentTarget && (detailsFor = null)}>
    <div class="details-dialog card" role="dialog" aria-modal="true" aria-labelledby="model-details-title" tabindex="-1">
      <button class="close" aria-label="Close model details" onclick={() => detailsFor = null}>×</button>
      <p class="eyebrow">Model details</p>
      <div class="details-heading"><ProviderLogo provider={detailsFor.provider} size={28} /><h2 id="model-details-title">{providerName(detailsFor.provider)}</h2></div>
      <dl class="details-grid">
        <div><dt>Selected model</dt><dd><code>{detailsFor.selected ? modelName(detailsFor.model) : "Not selected"}</code></dd></div>
        <div><dt>Connection</dt><dd>{detailsFor.connection_configured ? "Encrypted instance connection saved" : "Not configured"}</dd></div>
        <div><dt>Context capacity</dt><dd>{contextCapacity(detailsFor)}</dd></div>
        <div><dt>Local refresh</dt><dd>{capacities?.sync.find((state) => state.profile_id === detailsFor?.profile_id)?.next_refresh_at ? `Next check ${capacities.sync.find((state) => state.profile_id === detailsFor?.profile_id)?.next_refresh_at}` : "Scheduled when this local runtime is available"}</dd></div>
        <div><dt>Current context usage</dt><dd>No provider context telemetry has been received for this model yet.</dd></div>
        <div><dt>Subscription / rate limits</dt><dd>Not available through this connection. Raiker only displays daily or weekly limits when an authorized provider API exposes them.</dd></div>
      </dl>
      {#if capacities?.can_override}<button class="btn btn-ghost btn-sm" onclick={() => void configureCapacity(detailsFor!)}>Configure exact capacity</button>{/if}
      {#if capacityEntry?.history.length}<details><summary>Administrator override history</summary><ol>{#each capacityEntry.history as event}<li>{event.action} · {event.context_window_tokens?.toLocaleString() ?? "cleared"} · {event.recorded_at}{#if event.reason} — {event.reason}{/if}</li>{/each}</ol></details>{/if}
    </div>
  </div>
{/if}

{#if signInFor !== null && signInProfile !== null}
  {@const b = brand(signInProfile.provider)}
  {@const showLogin = b.authMethods.includes("login")}
  {@const showApiKey = b.authMethods.includes("apikey")}
  <div class="signin-overlay" role="presentation" onclick={(event) => event.target === event.currentTarget && closeSignIn()}>
    <div class="signin-dialog" role="dialog" aria-modal="true" aria-labelledby="signin-title" tabindex="-1" style={`--brand:${b.tint}`}>
      <button class="close" aria-label="Close" onclick={closeSignIn}>×</button>
      <div class="signin-logo"><ProviderLogo provider={signInProfile.provider} size={44} /></div>
      <h2 id="signin-title">{b.headline}</h2>
      <p class="signin-hint">{b.hint}</p>

      {#if showLogin && b.loginUrl}
        <a class="sso-btn" href={b.loginUrl} target="_blank" rel="noopener noreferrer" style={`--brand:${b.tint}`}>
          {b.loginLabel} →
        </a>
        {#if showApiKey}
          <div class="signin-divider"><span>or paste a key</span></div>
        {/if}
      {/if}

      {#if showApiKey}
        <label class="field">
          <span class="field-label">{b.credentialLabel}</span>
          <input class="input" type="password" placeholder={b.credentialLabel.toLowerCase().includes("optional") ? "(optional)" : "sk-…"} bind:value={signInApiKey} autocomplete="off" />
        </label>
      {/if}

      <button type="button" class="sso-toggle" onclick={() => (signInAdvanced = !signInAdvanced)} aria-expanded={signInAdvanced}>
        {signInAdvanced ? "Hide advanced" : "Advanced: custom endpoint"}
      </button>
      {#if signInAdvanced}
        <label class="field">
          <span class="field-label">Custom endpoint <small>(leave blank for provider default)</small></span>
          <input class="input" type="url" placeholder="https://…" bind:value={signInEndpoint} />
        </label>
      {/if}

      <div class="signin-actions">
        <button type="button" class="btn btn-primary signin-connect" onclick={() => void saveConnection(signInProfile.profile_id)} disabled={signInSaving || (signInEndpoint.trim() === "" && signInApiKey.trim() === "" && !signInAdvanced)}>
          {signInSaving ? "Connecting…" : "Connect"}
        </button>
        <button type="button" class="btn btn-ghost" onclick={closeSignIn}>Cancel</button>
      </div>
      {#if signInError}<p class="error" role="alert">{signInError}</p>{/if}
      {#if signInGuidance}
        <div class="signin-guidance" role="alert">
          <p class="sg-message">{signInGuidance.message}</p>
          <p class="sg-fix">{signInGuidance.fix}</p>
          {#if signInGuidance.href}
            <a class="sg-link" href={signInGuidance.href} onclick={closeSignIn}>{signInGuidance.linkLabel} →</a>
          {/if}
          <p class="sg-code">Reason code: <code>{signInGuidance.code}</code></p>
        </div>
      {/if}
      <p class="signin-foot">Your key is encrypted in this instance’s vault and never leaves this device.</p>
    </div>
  </div>
{/if}

<style>
  /* Each panel keeps the vertical rhythm the page had as one scroll, so moving
     a section into a tab changed where it lives, not how it reads. */
  .panel { display: grid; gap: var(--space-4); }
  .tab-lead {
    margin: 0;
    color: var(--text-2);
    font-size: 0.86rem;
    line-height: 1.5;
    max-width: 72ch;
  }
  .head-row { display:flex; align-items:flex-start; justify-content:space-between; gap:var(--space-4); }
  .setup-overview, .global-model-card, .section-heading { display:flex; align-items:center; justify-content:space-between; gap:var(--space-4); }
  .setup-overview { margin:var(--space-4) 0; }
  .global-model-card { margin:var(--space-4) 0; }
  .global-model-copy { max-width:40rem; }
  .global-model-field { display:grid; gap:.3rem; min-width:min(100%, 22rem); font-weight:650; }
  .global-model-field small { color:var(--text-2); font-weight:400; }
  .global-model-field select { width:100%; min-height:44px; padding:0 .8rem; border:1px solid var(--border-strong); border-radius:var(--r-md); background:var(--surface); color:var(--text-1); font:inherit; }
  .global-model-field select:focus-visible { outline:3px solid var(--focus-ring); outline-offset:2px; }
  .provider-section { margin-top:var(--space-5); }
  .section-heading { align-items:end; margin-bottom:var(--space-3); }
  .section-heading h2, .setup-overview h2 { margin:0; font-size:1.1rem; }
  .section-heading > p { max-width:28rem; color:var(--text-3); font-size:0.82rem; margin:0; }
  .eyebrow { color:var(--accent); font-size:0.7rem; font-weight:750; letter-spacing:0.08em; margin:0 0 0.25rem; text-transform:uppercase; }
  .setup-meter { min-width:9rem; text-align:right; }
  .setup-meter strong { display:block; font-size:1.35rem; }
  .setup-meter strong .of { color:var(--text-3); font-size:0.9rem; font-weight:500; }
  .setup-meter span { color:var(--text-3); font-size:0.75rem; }
  .setup-meter .total-spend { color:var(--text-2); font-size:0.78rem; margin:0.35rem 0 0; }
  .usage-strip { border-top:1px solid var(--border); margin-top:0.7rem; padding-top:0.6rem; }
  .usage-line { align-items:baseline; color:var(--text-2); display:flex; font-size:0.8rem; gap:0.75rem; justify-content:space-between; }
  .usage-line strong { color:var(--text-1); }
  .usage-note { color:var(--text-3); font-size:0.72rem; margin:0.35rem 0 0; }
  .row-usage { color:var(--text-3); font-size:0.78rem; grid-column:1 / -1; }
  /* Geometry lives in the shared `.bar` primitive; this only places it. */
  .spend-bar { margin-top:0.35rem; }

  /* ── Local: clean list rows ── */
  .local-list { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:0.5rem; }
  .local-row { display:flex; gap:0.85rem; align-items:flex-start; padding:0.75rem 0.9rem; border:1px solid var(--border); border-radius:var(--r-md); background:var(--surface); flex-wrap:wrap; }
  .local-row.selected { border-color:var(--accent-border); box-shadow:0 0 0 1px var(--accent-border); }
  .local-row.picker-open { border-color:var(--accent-border); }
  .row-logo { flex:0 0 auto; display:inline-flex; align-items:center; justify-content:center; }
  .row-main { flex:1; min-width:0; }
  .row-title { display:flex; align-items:center; gap:0.5rem; }
  .row-title h3 { margin:0; font-size:0.98rem; }
  .row-model { margin:0.15rem 0 0.4rem; color:var(--text-2); font-size:0.84rem; overflow-wrap:anywhere; }
  .row-help { color:var(--text-3); font-size:0.78rem; line-height:1.35; margin:0 0 0.5rem; }
  .row-actions { display:flex; gap:0.4rem; flex-wrap:wrap; align-items:center; }

  /* ── Hosted/Advanced: provider cards ── */
  .provider-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(19rem, 1fr)); gap:var(--space-4); }
  .provider-card { display:flex; flex-direction:column; gap:0.5rem; padding:1rem 1.05rem; border:1px solid var(--border); border-radius:var(--r-md); background:var(--surface); box-shadow:var(--shadow-1); }
  .provider-card.selected { border-color:var(--accent-border); box-shadow:0 0 0 1px var(--accent-border), var(--shadow-1); }
  .provider-card.connected { border-color:var(--ok-border); }
  .pc-head { display:flex; align-items:center; gap:0.6rem; }
  .pc-logo { min-width:2.4rem; height:2.4rem; display:inline-flex; align-items:center; justify-content:center; }
  .pc-title { display:flex; align-items:center; gap:0.45rem; flex-wrap:wrap; }
  .pc-title h3 { margin:0; font-size:1rem; }
  .pc-model { margin:0; color:var(--text-2); font-size:0.84rem; overflow-wrap:anywhere; }
  .pc-status { margin:0; display:flex; align-items:center; gap:0.4rem; font-size:0.8rem; color:var(--text-2); }
  .status-dot { width:0.5rem; height:0.5rem; border-radius:50%; background:var(--text-3); }
  .status-dot.ok { background:var(--ok); box-shadow:0 0 0 3px color-mix(in srgb, var(--ok) 22%, transparent); }
  .pc-actions { display:flex; gap:0.4rem; flex-wrap:wrap; margin-top:0.2rem; }
  .pc-connect { background:var(--brand); border-color:var(--brand); color:#fff; }
  .pc-connect:hover:not(:disabled) { background:color-mix(in srgb, var(--brand) 88%, #000); border-color:color-mix(in srgb, var(--brand) 88%, #000); }

  .chips { display:flex; flex-wrap:wrap; gap:0.35rem; }
  .chip { font-size:0.72rem; font-weight:600; border-radius:var(--r-pill); border:1px solid var(--neutral-border); background:var(--neutral-soft); color:var(--text-2); padding:0.08rem 0.55rem; }
  .chip-ok { border-color:var(--ok-border); background:var(--ok-soft); color:var(--ok); }
  .chip-warn { border-color:var(--warn-border); background:var(--warn-soft); color:var(--warn); }
  .model-unpinned { color:var(--text-3); font-style:italic; }

  .picker { margin-top:0.55rem; border-top:1px dashed var(--border); padding-top:0.55rem; display:flex; flex-direction:column; gap:0.45rem; }
  .local-picker-inline { width:100%; margin-top:0.2rem; padding-top:0.55rem; border-top:1px dashed var(--border); }
  .picker-select, .picker-input { padding:0.35rem 0.5rem; border-radius:var(--r-md); border:1px solid var(--border-strong); background:var(--surface); color:var(--text-1); max-width:100%; font:inherit; font-size:0.88rem; }
  .picker-note { font-size:0.76rem; color:var(--text-3); margin:0; }
  .picker-actions { display:flex; gap:0.4rem; }
  .picker-error { font-size:0.78rem; margin:0; }
  .test-result { color:var(--text-2); font-size:0.76rem; margin:0.3rem 0 0; }

  /* ── Sign-in modal ── */
  .signin-overlay { align-items:center; background:color-mix(in srgb, #000 55%, transparent); display:flex; inset:0; justify-content:center; padding:var(--space-4); position:fixed; z-index:40; }
  .signin-dialog { position:relative; width:min(100%, 26rem); background:var(--surface); border:1px solid var(--border-strong); border-top:4px solid var(--brand); border-radius:var(--r-lg); box-shadow:var(--shadow-2); padding:1.6rem 1.5rem 1.3rem; display:flex; flex-direction:column; gap:0.65rem; }
  .signin-dialog .close { position:absolute; top:0.6rem; right:0.7rem; background:transparent; border:0; color:var(--text-2); cursor:pointer; font-size:1.6rem; line-height:1; }
  .signin-logo { min-height:3rem; display:flex; align-items:center; justify-content:center; margin:0 auto 0.1rem; }
  .signin-dialog h2 { margin:0; text-align:center; font-size:1.15rem; }
  .signin-hint { margin:0; color:var(--text-3); font-size:0.8rem; line-height:1.4; text-align:center; }
  .sso-btn { display:flex; align-items:center; justify-content:center; gap:0.4rem; padding:0.55rem 1rem; border-radius:var(--r-sm); background:var(--brand); color:#fff; font-weight:600; font-size:0.86rem; text-decoration:none; border:1px solid var(--brand); transition:opacity 120ms var(--ease); margin:0.3rem 0 0.1rem; }
  .sso-btn:hover { text-decoration:none; opacity:0.9; }
  .signin-divider { display:flex; align-items:center; gap:0.5rem; margin:0.4rem 0; }
  .signin-divider::before, .signin-divider::after { content:""; flex:1; height:1px; background:var(--border); }
  .signin-divider span { color:var(--text-3); font-size:0.72rem; }
  .field { display:flex; flex-direction:column; gap:0.25rem; }
  .field-label { font-size:0.76rem; font-weight:600; color:var(--text-2); }
  .field-label small { color:var(--text-3); font-weight:400; }
  .sso-toggle { align-self:flex-start; background:transparent; border:0; color:var(--accent); cursor:pointer; font-size:0.78rem; padding:0.1rem 0; }
  .signin-actions { display:flex; gap:0.5rem; margin-top:0.3rem; }
  .signin-connect { flex:1; background:var(--brand); border-color:var(--brand); color:#fff; }
  .signin-connect:hover:not(:disabled) { background:color-mix(in srgb, var(--brand) 88%, #000); border-color:color-mix(in srgb, var(--brand) 88%, #000); }
  .signin-foot { margin:0.4rem 0 0; text-align:center; color:var(--text-3); font-size:0.7rem; }
  .signin-guidance { background:var(--warn-soft); border:1px solid var(--warn-border); border-radius:var(--r-sm); display:grid; gap:0.35rem; padding:0.7rem 0.8rem; }
  .signin-guidance p { margin:0; font-size:0.8rem; line-height:1.45; overflow-wrap:anywhere; }
  .signin-guidance code { overflow-wrap:anywhere; }
  .sg-message { color:var(--text-1); font-weight:600; }
  .sg-fix { color:var(--text-2); }
  .sg-link { color:var(--accent); font-size:0.8rem; font-weight:600; }
  .sg-code { color:var(--text-3); font-size:0.72rem; }

  /* ── Details modal ── */
  .details-overlay { align-items:center; background:color-mix(in srgb, #000 45%, transparent); display:flex; inset:0; justify-content:center; padding:var(--space-4); position:fixed; z-index:30; }
  .details-dialog { max-width:42rem; position:relative; width:min(100%, 42rem); }
  .details-heading { display:flex; align-items:center; gap:0.65rem; margin-bottom:0.9rem; }
  .details-dialog h2 { margin:0; }
  .close { background:transparent; border:0; color:var(--text-2); cursor:pointer; font-size:1.6rem; line-height:1; position:absolute; right:0.75rem; top:0.65rem; }
  .details-grid { display:grid; gap:0.85rem; margin:var(--space-4) 0 0; }
  .details-grid div { border-top:1px solid var(--border); padding-top:0.65rem; }
  .details-grid dt { color:var(--text-3); font-size:0.73rem; font-weight:700; text-transform:uppercase; }
  .details-grid dd { color:var(--text-2); line-height:1.45; margin:0.2rem 0 0; }

  /* ── Fallback / advisor / gates ── */
  .fallback { margin-top:var(--space-4); }
  .fallback-empty { color:var(--text-3); font-size:0.84rem; margin:0.5rem 0; }
  .fallback-list { list-style:none; margin:var(--space-3) 0; padding:0; display:flex; flex-direction:column; gap:0.4rem; }
  .fallback-item { display:flex; align-items:center; gap:0.6rem; border:1px solid var(--neutral-border); border-radius:var(--r-md); background:var(--neutral-soft); padding:0.4rem 0.6rem; }
  .rank { font-weight:700; color:var(--text-3); min-width:1.2rem; text-align:center; }
  .fallback-name { flex:1; display:flex; align-items:baseline; gap:0.5rem; flex-wrap:wrap; font-weight:600; overflow-wrap:anywhere; }
  .fallback-actions { display:flex; gap:0.25rem; }
  .fallback-add, .fallback-save { display:flex; align-items:center; gap:0.6rem; margin-top:var(--space-3); flex-wrap:wrap; }
  .fallback-add select { padding:0.35rem 0.5rem; border-radius:var(--r-md); border:1px solid var(--border-strong); background:var(--surface); color:var(--text-1); max-width:22rem; font:inherit; font-size:0.86rem; }
  .ok-note { color:var(--ok); font-size:0.82rem; }
  .advisor { margin-top:var(--space-4); }
  .advisor .sub { margin-bottom:var(--space-3); }
  .advisor-row { display:flex; align-items:center; gap:0.6rem; flex-wrap:wrap; }
  .advisor-row select { padding:0.35rem 0.5rem; border-radius:var(--r-md); border:1px solid var(--border-strong); background:var(--surface); color:var(--text-1); max-width:22rem; font:inherit; font-size:0.86rem; }
  .gate-status { margin-top:var(--space-4); }
  .gates { display:grid; grid-template-columns:repeat(auto-fit, minmax(12rem, 1fr)); gap:0.5rem 1rem; margin:0 0 var(--space-3); }
  .gates dt { font-size:0.72rem; font-weight:650; text-transform:uppercase; letter-spacing:0.05em; color:var(--text-3); }
  .gates dd { margin:0.1rem 0 0; }
  .sub { color:var(--text-3); font-size:0.8rem; margin:0; }
  .error { color:var(--danger); }
  @media (max-width: 44rem) {
    .head-row, .setup-overview, .global-model-card, .section-heading { align-items:flex-start; flex-direction:column; }
    .setup-meter { text-align:left; width:100%; }
    .local-row { flex-direction:column; }
  }
</style>
