<script lang="ts">
  import { onMount } from "svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ProviderLogo from "../components/ProviderLogo.svelte";
  import ModelPricingPanel from "../components/ModelPricingPanel.svelte";
  import TabStrip from "../components/TabStrip.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type {
    CodexSubscriptionStatus,
    ModelCapacitiesView,
    ModelProfile,
    ModelsView as ModelsData,
    ProviderModelList,
  } from "../apiTypes";
  import { capabilityLabel } from "../capabilityModel";
  import { humanize, providerName, relativeTime } from "../format";
  import { formatCost, sourceNote, spendShares } from "../contextPresentation";
  import {
    providerErrorGuidance,
    type ProviderErrorGuidance,
  } from "../providerErrors";
  import { modelName } from "../modelPresentation";
  import { readinessLabel, UNPINNED_MODEL } from "../modelReadinessLabels";
  import { isChoosableModel } from "../modelReadiness.svelte";
  import { installerRuntimeFor, openRuntimeInstaller } from "../runtimeInstall";
  import { setModels } from "../models.svelte";
  import LocalLibraryPanel from "./models/LocalLibraryPanel.svelte";
  import HuggingFacePanel from "./models/HuggingFacePanel.svelte";
  import DownloadsPanel from "./models/DownloadsPanel.svelte";
  import AvailableModels from "./models/AvailableModels.svelte";
  import ProviderUsagePanel from "./models/ProviderUsagePanel.svelte";
  import ProvidersPanel from "./models/ProvidersPanel.svelte";
  import LocalFrameworkRow from "./models/LocalFrameworkRow.svelte";
  import SpeechRuntimePanel from "./models/SpeechRuntimePanel.svelte";

  // The shell owns a models snapshot for the topbar chip; it passes onchanged
  // so a selection here is reflected there without a full page reload. `tab`
  // comes from the hash, so every panel is a shareable location — the context
  // popover's "Configure →" links straight to #/models?tab=pricing.
  let {
    onchanged,
    tab = "local",
  }: { onchanged?: () => void; tab?: string } = $props();

  /**
   * The page is split by *what you came to do*, not by which table the data
   * lives in. Everything on this page used to be one long scroll, which meant
   * an owner looking for a rate scrolled past provider cards, and an owner
   * connecting a provider scrolled past the fallback list.
   *
   * "Providers" then became its own long scroll for the same reason: it held
   * local runtimes, hosted accounts, advanced routers, vendor installers, and
   * the GGUF library at once. Obtaining a model that runs on this machine and
   * signing in to somebody else's are different jobs with different vocabulary,
   * different risks, and almost no shared controls, so they are separate tabs.
   * Local is first because Raiker prefers local backends.
   */
  const TABS = [
    { id: "local", label: "Local" },
    { id: "hosted", label: "Hosted" },
    { id: "huggingface", label: "Hugging Face" },
    { id: "activity", label: "Activity" },
    { id: "routing", label: "Routing" },
    { id: "pricing", label: "Pricing" },
  ];

  // Which provider sections each tab owns. The three groups already existed as
  // headings inside one scroll; the split promotes them to destinations.
  const TAB_SECTIONS: Record<string, readonly ("Local" | "Hosted" | "Advanced")[]> = {
    local: ["Local"],
    hosted: ["Hosted", "Advanced"],
  };
  const visibleSections = $derived(TAB_SECTIONS[tab] ?? []);
  const showsProviderCards = $derived(visibleSections.length > 0);

  function selectTab(next: string) {
    tab = next;
    window.location.hash = `#/models?tab=${encodeURIComponent(next)}`;
  }

  let models = $state<ModelsData | null>(null);
  let loadError = $state<string | null>(null);
  let capacities = $state<ModelCapacitiesView | null>(null);
  let capacityRefreshAttempted = false;
  let catalogueRefreshing = $state(false);
  let catalogueNotice = $state<string | null>(null);
  let codexSubscriptionStatus = $state<CodexSubscriptionStatus["connection_status"]>("signed_out");
  let codexSubscriptionPlan = $state<string | null>(null);
  let codexSubscriptionBusy = $state(false);
  let codexSubscriptionNotice = $state<string | null>(null);

  // "ChatGPT Plus connected" says which subscription is in use in three words;
  // the generic line is the fallback when Codex does not name a plan.
  const codexPlanLabel = $derived(
    codexSubscriptionPlan
      ? `ChatGPT ${codexSubscriptionPlan.charAt(0).toUpperCase()}${codexSubscriptionPlan.slice(1)} connected`
      : "ChatGPT subscription connected",
  );

  const isCodexSubscription = (profile: ModelProfile) => profile.provider === "chatgpt-codex";
  const isConnected = (profile: ModelProfile) =>
    profile.connection_configured ||
    (isCodexSubscription(profile) && codexSubscriptionStatus === "connected");

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
      if (models.profiles.some(isCodexSubscription)) {
        try {
          const subscription = await api.codexSubscriptionStatus();
          codexSubscriptionStatus = subscription.connection_status;
          codexSubscriptionPlan = subscription.plan_type;
        } catch {
          codexSubscriptionStatus = "signed_out";
          codexSubscriptionPlan = null;
        }
      }
      try {
        capacities = await api.modelCapacities();
        if (capacities.refresh_due && !capacityRefreshAttempted) {
          capacityRefreshAttempted = true;
          await api.refreshModelCapacities(false);
          models = await api.models();
          capacities = await api.modelCapacities();
        }
      } catch {
        capacities = null;
      }
      // Mirror the fresh snapshot into the shared store so every mounted
      // composer (Chat, Build) updates its model picker without a reload —
      // connecting a provider, selecting a model, or reordering the fallback
      // all flow through here.
      setModels(models);
      sequence = [...models.fallback_sequence];
      advisorChoice = models.advisor_profile_id ?? "";
    } catch (e) {
      models = null;
      // A 429 is the runtime's own request limiter, not a broken page — and
      // "Unavailable (429)" tells an owner neither what happened nor that it
      // clears by itself. Naming it is the same rule the rest of this page
      // follows: say what is wrong and what fixes it.
      loadError =
        e instanceof ApiError && e.status === 429
          ? "Too many requests in the last minute. Raiker throttled this read; wait a moment and press Refresh."
          : e instanceof ApiError
            ? `Unavailable (${e.status})`
            : "Unavailable";
    }
  }

  async function refreshProviderCatalogues(profileIds?: string[]) {
    if (catalogueRefreshing) return;
    catalogueRefreshing = true;
    catalogueNotice = null;
    try {
      const refreshed = await api.refreshProviderCatalogues(profileIds);
      const unavailable = refreshed.providers.filter((provider) => provider.status !== "available");
      catalogueNotice =
        unavailable.length === 0
          ? "Connected provider catalogues refreshed."
          : `Refreshed ${refreshed.providers.length - unavailable.length} provider${refreshed.providers.length - unavailable.length === 1 ? "" : "s"}; ${unavailable.length} could not be refreshed.`;
      await load();
      onchanged?.();
    } catch {
      catalogueNotice = "Could not refresh connected provider catalogues.";
    } finally {
      catalogueRefreshing = false;
    }
  }

  async function startCodexSubscriptionLogin() {
    if (codexSubscriptionBusy) return;
    codexSubscriptionBusy = true;
    codexSubscriptionNotice = null;
    try {
      const status = await api.startCodexSubscriptionLogin();
      codexSubscriptionStatus = status.connection_status;
      codexSubscriptionNotice = "Finish sign-in in the browser, then refresh this page to list your available models.";
    } catch (error) {
      codexSubscriptionNotice =
        error instanceof ApiError && error.reasonCode
          ? `ChatGPT sign-in could not start (${error.reasonCode}).`
          : "ChatGPT sign-in could not start. Check that Codex is installed on this device.";
    } finally {
      codexSubscriptionBusy = false;
    }
  }

  /** Sign the ChatGPT subscription out of Raiker; Codex keeps its own session. */
  async function disconnectCodexSubscription() {
    if (codexSubscriptionBusy) return;
    codexSubscriptionBusy = true;
    codexSubscriptionNotice = null;
    try {
      await api.disconnectCodexSubscription();
      codexSubscriptionStatus = "signed_out";
      codexSubscriptionPlan = null;
      await load();
    } catch {
      codexSubscriptionNotice = "The ChatGPT subscription could not be disconnected.";
    } finally {
      codexSubscriptionBusy = false;
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
  // Only models this machine could actually run. A profile whose readiness
  // check has failed — a llama.cpp slot with nothing served, an Ollama model
  // that is no longer pulled — is not a default anyone can choose, so listing
  // it only offered a selection that would be refused at the next turn. A
  // profile that has never been checked is not known to be unavailable and
  // stays; so does the current selection, which must never vanish from the
  // control that shows it.
  const globalChoices = $derived(
    (
      models?.chat_profiles ??
      (models?.profiles ?? []).filter((profile) => profile.configured)
    ).filter((profile) => isChoosableModel(profile) || profile.selected),
  );
  /** The provider card whose model dialog is open, or null. */
  const pickerProfile = $derived(
    (models?.profiles ?? []).find((profile) => profile.profile_id === pickerFor) ?? null,
  );

  /** The models this owner keeps offered for one profile, from the snapshot. */
  const availableModelsFor = (profileId: string) =>
    (models?.chat_profiles ?? [])
      .filter((profile) => profile.profile_id === profileId)
      .map((profile) => profile.model);

  const globalGroups = $derived.by(() => {
    const groups = new Map<string, ModelProfile[]>();
    for (const profile of globalChoices) {
      groups.set(profile.provider, [...(groups.get(profile.provider) ?? []), profile]);
    }
    return [...groups].map(([provider, profiles]) => ({ provider, profiles }));
  });
  const globalChoice = $derived.by(() => {
    const selected = globalChoices.find((profile) => profile.selected);
    return selected
      ? JSON.stringify([selected.profile_id, selected.model])
      : "";
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
  let signInAdminApiKey = $state("");
  // BUG-274 — where an identity-linked key acts. Not a credential, so it is a
  // plain text field: an owner has to be able to read back what they typed to
  // check it against the console, and masking it would hide the one thing the
  // "workspace not recognised" answer asks them to compare.
  let signInWorkspaceId = $state("");
  let signInEndpoint = $state("");
  let signInAdvanced = $state(false);
  let signInSaving = $state(false);
  let signInError = $state<string | null>(null);
  let disconnecting = $state<Record<string, true>>({});
  // BUG-47 — one provider being tested must not disable, or answer for, any
  // other. Both the in-flight flag and the result are per profile id.
  let testing = $state<Record<string, true>>({});
  // BUG-47 — a test result belongs to the provider that asked for it. Holding
  // one string for the whole view made *"Ollama responded and exposed 9
  // models"* appear beneath every connected card, which reads as three
  // providers answering when one did. Keyed by profile id, a card renders only
  // its own result and hosted cards keep their independent status.
  let testResults = $state<Record<string, string>>({});
  // BUG-270 — the owner has just installed a runtime and wants the card to stop
  // saying it is missing. One flag for the whole view: detection is a single
  // pass over every runtime, not a per-provider operation.
  let detecting = $state(false);
  // Which provider's installer is being opened, and what to say afterwards.
  let installing = $state<string | null>(null);
  let installNotice = $state<string | null>(null);
  let detailsFor = $state<ModelProfile | null>(null);
  // Governed refusals are policy outcomes, not faults. Hold the reason code so
  // the dialog can render the control that unblocks it instead of a bare code.
  let signInGuidance = $state<ProviderErrorGuidance | null>(null);

  const signInProfile = $derived(
    models?.profiles.find((p) => p.profile_id === signInFor) ?? null,
  );

  function contextCapacity(profile: ModelProfile): string {
    if (!profile.context_window_tokens) {
      return "Not reported by this runtime. Refresh its model catalogue or configure an exact fallback before relying on a percentage.";
    }
    const source =
      profile.context_window_source === "owner"
        ? "Administrator override"
        : profile.context_window_source === "provider"
          ? "Reported by the provider runtime"
          : "Configured in Raiker";
    return `${new Intl.NumberFormat().format(profile.context_window_tokens)} tokens · ${source}`;
  }

  async function configureCapacity(profile: ModelProfile) {
    const raw = window.prompt(
      "Exact context capacity in tokens. Leave blank to clear the administrator override.",
      profile.context_window_tokens?.toString() ?? "",
    );
    if (raw === null) return;
    const tokens = raw.trim() ? Number(raw) : null;
    if (tokens !== null && (!Number.isInteger(tokens) || tokens < 1024)) {
      selectError =
        "Context capacity must be an integer of at least 1,024 tokens.";
      return;
    }
    const reason = window.prompt(
      "Why is this override needed?",
      "Verified against the local runtime configuration",
    );
    if (reason === null) return;
    try {
      await api.setModelCapacity(
        profile.profile_id,
        profile.model,
        tokens,
        reason,
      );
      await load();
    } catch {
      selectError = "Could not update context capacity.";
    }
  }

  function openSignIn(profileId: string, options: { advanced?: boolean } = {}) {
    signInFor = profileId;
    signInApiKey = "";
    signInAdminApiKey = "";
    signInWorkspaceId = "";
    signInEndpoint = "";
    // BUG-274 — a readiness answer that says "add the workspace ID to this
    // connection" has to land on the box, not three clicks away from it.
    signInAdvanced = options.advanced === true;
    signInError = null;
    signInGuidance = null;
  }
  function closeSignIn() {
    signInFor = null;
    signInApiKey = "";
    signInAdminApiKey = "";
    signInWorkspaceId = "";
    signInEndpoint = "";
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
      await api.saveModelConnection(
        profileId,
        signInEndpoint.trim(),
        signInApiKey.trim(),
        signInAdminApiKey.trim(),
        signInWorkspaceId.trim(),
      );
      signInApiKey = "";
      signInAdminApiKey = "";
      signInWorkspaceId = "";
      signInEndpoint = "";
      signInFor = null;
      // Found while proving BUG-274 live. **Reconnect** is reached through
      // Details, and saving left that modal sitting over the card it had just
      // changed — so the owner's next action (Test, Select models…) hit an
      // overlay instead of the control they were aiming at. The live harness
      // had been closing it by hand since FIXED-141, which made it look like a
      // test concern rather than the interface defect it is.
      detailsFor = null;
      await load();
    } catch (e) {
      signInGuidance =
        e instanceof ApiError ? providerErrorGuidance(e.reasonCode) : null;
      // BUG-274 — the remediation names a field, so open the section holding
      // it. An answer that says "add the workspace ID" while the box is folded
      // away is the same dead end the old copy was.
      if (signInGuidance?.code?.startsWith("provider_workspace") === true)
        signInAdvanced = true;
      signInError =
        signInGuidance !== null
          ? null
          : e instanceof ApiError
            ? `Could not connect (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
            : "Could not connect";
    } finally {
      signInSaving = false;
    }
  }

  async function disconnectConnection(profile: ModelProfile) {
    const id = profile.profile_id;
    const name = providerName(profile.provider);
    if (
      !window.confirm(
        `Disconnect ${name}? The encrypted credential and custom endpoint stored for this provider will be removed from this Raiker instance.`,
      )
    )
      return;
    disconnecting = { ...disconnecting, [id]: true };
    testResults = without(testResults, id);
    try {
      await api.saveModelConnection(id, "", "");
      await load();
      testResults = { ...testResults, [id]: `${name} connection removed.` };
      onchanged?.();
    } catch {
      testResults = {
        ...testResults,
        [id]: `Could not disconnect ${name}. The saved credential was left unchanged.`,
      };
    } finally {
      disconnecting = without(disconnecting, id);
    }
  }

  function without<T>(map: Record<string, T>, key: string): Record<string, T> {
    return Object.fromEntries(Object.entries(map).filter(([id]) => id !== key));
  }

  // BUG-47 — every test result names the provider it came from. The picker's
  // note can be anonymous because it renders inside an open picker you just
  // opened; a test result sits among other providers' cards, and an anonymous
  // "Provider unreachable" is exactly what made the misplacement invisible.
  function testNote(profile: ModelProfile, list: ProviderModelList): string {
    const name = providerName(profile.provider);
    switch (list.status) {
      case "available":
        return `${name} responded and exposed ${list.models.length} model${list.models.length === 1 ? "" : "s"}.`;
      case "policy_denied":
        return `${name}'s model list was denied by provider policy — enable its gate first.`;
      case "unsupported":
        return `${name} does not support model listing. Type a model id instead.`;
      default: {
        // BUG-272 — "could not be reached" is the FIXED-355 defect on the
        // catalogue path: the server had already classified *why*, and this
        // discarded it and sent the owner to debug their network. A code with
        // guidance says what to do; only a genuinely unclassified failure falls
        // back to reachability.
        const guidance = providerErrorGuidance(list.reason_code);
        if (guidance !== null) return `${name}: ${guidance.message} ${guidance.fix}`;
        return `${name} could not be reached. Check that it is running and reachable from this device.`;
      }
    }
  }

  // BUG-69 — Test is the obvious control on this page, so it has to answer the
  // question the owner is actually asking: can this model run? A catalogue
  // listing does not answer it. A live run on 2026-08-09 reported "Anthropic
  // responded and exposed 10 models" while readiness stayed unchecked and every
  // work surface stayed blocked. When a concrete model is pinned, Test now runs
  // the exact-model readiness check and reports (and records) that verdict;
  // profiles with no model pinned still get the catalogue reachability note,
  // which is the only honest answer available for them.
  /**
   * BUG-270 — whether this profile may be shown as *naming* a model.
   *
   * The `<model>` placeholder was never the only way a profile could fail to
   * name a real model. A profile whose runtime is not on this machine names a
   * string that resolves to nothing here, and printing it beside "Not installed
   * on this machine" tells the owner two contradictory things at once. Both
   * cases now take the same "no model" treatment, from one predicate.
   */
  function namesAModel(profile: ModelProfile): boolean {
    return profile.model !== UNPINNED_MODEL && profile.configured !== false;
  }

  /**
   * BUG-270 — offer the setup, rather than only reporting its absence.
   *
   * "Not installed on this machine" is a fact and half an answer: the owner
   * then had to find the install panel further up the page and work out which
   * of its cards matched the row that told them. This is the same governed
   * vendor path that panel takes, offered where the absence is stated.
   */
  async function setUpRuntime(provider: string) {
    const runtime = installerRuntimeFor(provider);
    if (runtime === null) return;
    installing = provider;
    try {
      await openRuntimeInstaller(runtime);
      // Deliberately not "installed". Raiker opened a download; whether the
      // owner ran it is theirs to say, and **Look again** is how they say it.
      installNotice = `Opened the official ${providerName(provider)} download. Install it, then choose Look again.`;
    } catch {
      installNotice = `Could not open the ${providerName(provider)} download.`;
    } finally {
      installing = null;
    }
  }

  async function redetectRuntimes() {
    detecting = true;
    try {
      await api.detectLocalRuntimes();
      await load();
      // The instruction the notice carried has been followed, whatever the
      // answer turned out to be.
      installNotice = null;
    } catch {
      // A failed look leaves the last answer standing rather than replacing it
      // with a claim this call did not establish.
    } finally {
      detecting = false;
    }
  }

  async function testConnection(profile: ModelProfile) {
    const id = profile.profile_id;
    testing = { ...testing, [id]: true };
    // Clear this provider's previous answer only. Another card's result is
    // that card's state and is not this test's to discard.
    testResults = without(testResults, id);
    // BUG-274 — a previous answer about the workspace is this test's to replace.
    workspaceRefused = without(workspaceRefused, id);
    let message: string;
    if (profile.model && profile.model !== "<model>") {
      try {
        const readiness = await api.checkModelReadiness(id, profile.model);
        message = readiness.remediation
          ? `${readiness.summary} ${readiness.remediation}`
          : readiness.summary;
        noteWorkspaceRefusal(id, readiness.reason_code);
        await load();
      } catch (e) {
        message = throttled(e)
          ? THROTTLED
          : `Raiker could not check ${providerName(profile.provider)}.`;
      }
    } else {
      try {
        const list = await api.providerModels(id);
        message = testNote(profile, list);
        noteWorkspaceRefusal(id, list.reason_code);
      } catch (e) {
        message = throttled(e)
          ? THROTTLED
          : `Raiker could not reach ${providerName(profile.provider)}.`;
      }
    }
    testing = without(testing, id);
    testResults = { ...testResults, [id]: message };
  }

  /**
   * BUG-274 — this provider refused because of the workspace, not the key.
   *
   * Two sources, because **Test** has two paths and the live run found the
   * second: with a model pinned it runs the readiness check and the verdict is
   * on the profile; with none pinned it reads the catalogue, and that answer
   * exists only in this view. Reading the readiness row alone offered the field
   * on exactly the case an owner has *already* got past — a pinned model — and
   * not on a fresh connection, which is where the refusal actually happens.
   *
   * Both are governed reason codes rather than message text, so the offer
   * appears for those two codes and never because a sentence contained the word.
   */
  let workspaceRefused = $state<Record<string, true>>({});

  function wantsWorkspace(profile: ModelProfile): boolean {
    return (
      workspaceRefused[profile.profile_id] === true ||
      (profile.readiness_reason_code ?? "").startsWith("provider_workspace")
    );
  }

  /** Remember a governed workspace refusal against the card that got it. */
  function noteWorkspaceRefusal(profileId: string, reasonCode: string | null | undefined) {
    if ((reasonCode ?? "").startsWith("provider_workspace"))
      workspaceRefused = { ...workspaceRefused, [profileId]: true };
  }

  // A short chip label for the exact readiness state, so a card says what a
  // check actually found instead of only whether a credential is stored.
  function readinessChip(profile: ModelProfile): string | null {
    const label = readinessLabel(profile.readiness_state);
    if (label === null) return null;
    const state = profile.readiness_state;
    // BUG-83 — a chip that says only "Ready" cannot be told apart from one that
    // said "Ready" an hour ago. Naming when the check was last confirmed is what
    // makes the expiry legible instead of surprising.
    if (state === "ready" && profile.readiness_checked_at) {
      return `${label} · confirmed ${relativeTime(profile.readiness_checked_at)}`;
    }
    return label;
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
      // The same governed code the Test button reads. Opening the picker is how
      // most owners meet this refusal, so it has to offer the field that fixes
      // it too — otherwise the answer depends on which button you pressed.
      noteWorkspaceRefusal(profileId, pickerList?.reason_code);
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

  // FIXED-160 — the runtime's own request limiter is not a broken page, and
  // "could not check" tells an owner neither what happened nor that it clears by
  // itself. Every check on this page says so in the same words.
  const THROTTLED =
    "Too many requests in the last minute. Raiker throttled this check; wait a moment and try again.";
  const throttled = (e: unknown) => e instanceof ApiError && e.status === 429;

  // BUG-82 — the advisor gets the same readiness chip and repair sentence a
  // provider card gets, because it is a second model this runtime really calls.
  let advisorChecking = $state(false);
  let advisorCheckNote = $state<string | null>(null);
  const advisorChip = $derived(
    models?.advisor_profile_id ? readinessLabel(models.advisor_readiness_state) : null,
  );

  async function checkAdvisor() {
    if (models === null || !models.advisor_profile_id || !models.advisor_model) return;
    advisorChecking = true;
    advisorCheckNote = null;
    try {
      const readiness = await api.checkModelReadiness(
        models.advisor_profile_id,
        models.advisor_model,
      );
      advisorCheckNote = readiness.remediation
        ? `${readiness.summary} ${readiness.remediation}`
        : readiness.summary;
      await load();
    } catch (e) {
      advisorCheckNote = throttled(e) ? THROTTLED : "Raiker could not check the advisor model.";
    } finally {
      advisorChecking = false;
    }
  }

  async function saveAdvisor() {
    advisorSaving = true;
    advisorError = null;
    advisorSaved = false;
    advisorCheckNote = null;
    try {
      const result = await api.setModelAdvisor(advisorChoice || null);
      if (models !== null) {
        models = { ...models, advisor_profile_id: result.advisor_profile_id };
      }
      advisorChoice = result.advisor_profile_id ?? "";
      advisorSaved = true;
      // A new choice has its own readiness; re-read so the chip describes the
      // model now selected rather than the one it replaced.
      await load();
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
      default: {
        // The FIXED-355 / FIXED-370 defect, alive in the *other* control on
        // this page. `testNote` has read the server's classification since
        // BUG-272; this one printed "Provider unreachable" for every failure —
        // and it is the one on the path an owner actually walks, because
        // choosing a model is what you do straight after connecting.
        //
        // A live run against an identity-linked key showed it: the provider
        // answered in full, naming the workspace id it wanted, and the picker
        // said the provider could not be reached.
        const guidance = providerErrorGuidance(list.reason_code);
        if (guidance !== null) return `${guidance.message} ${guidance.fix}`;
        return "Provider unreachable — type a model id if you know it.";
      }
    }
  }

  const addable = $derived(
    (models?.profiles ?? []).filter((p) => !sequence.includes(p.profile_id)),
  );

  const dirty = $derived(
    models !== null &&
      JSON.stringify(sequence) !== JSON.stringify(models.fallback_sequence),
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
      if (models !== null)
        models = { ...models, fallback_sequence: result.fallback_sequence };
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
      case "enabled_runtime":
        return "On";
      case "enabled_policy_gated":
        return "On (policy-gated)";
      case "enabled_read_only":
        return "Read-only";
      case "disabled":
        return "Off";
      default:
        return humanize(state);
    }
  }

  /**
   * What this gate does, rather than what its row says.
   *
   * Connecting a provider *is* consent to use it — `provider_runtime_policy_from_gates`
   * treats a saved connection as the third and lowest-authority route to an open
   * gate, which is what removes the "configure a provider, then separately
   * discover you must also flip a switch" trap. So an owner with Anthropic
   * connected has hosted models running while the gate row is still unset, and
   * this panel printed **Off** directly above the connected card that had just
   * answered.
   *
   * It is wrong in the other direction too, and worse. On an instance with
   * nothing connected the row resolves to `enabled_runtime` from the shipped
   * default table while the enforcing path refuses every hosted provider, so the
   * panel read **On** above providers that would answer
   * `hosted_provider_requires_explicit_policy` at the first turn.
   *
   * That is FIXED-322's defect on a second surface, and this is its fix, in the
   * same shape: the stored state is reported unchanged and the enforcing answer
   * decides the word. An explicit revocation still outranks a connection, so a
   * gate the owner turned off reads **Off** whatever is connected — which is the
   * case that must never be softened.
   */
  function gateLabel(state: string, enforced: boolean | undefined): string {
    if (enforced === undefined) return gateStateLabel(state);
    const stored = gateStateLabel(state);
    if (enforced) return stored === "Off" ? "On (by connection)" : stored;
    // The enforcing path refuses, and this is the more dangerous half: an owner
    // reading "On" here connects nothing, sends a turn, and meets
    // `hosted_provider_requires_explicit_policy`. The label names both the
    // answer and the thing that changes it.
    return stored === "Off" ? "Off" : "Off until connected";
  }

  function sectionFor(profile: ModelProfile): "Local" | "Hosted" | "Advanced" {
    if (
      profile.provider === "openrouter" ||
      profile.provider === "huggingface" ||
      profile.provider === "ollama-cloud" ||
      profile.provider === "openai-compatible"
    )
      return "Advanced";
    return profile.requires_network ? "Hosted" : "Local";
  }

  const configuredProfiles = $derived(
    (models?.profiles ?? []).filter(
      (p) => p.connection_configured || p.selected,
    ),
  );
  // A percentage of "all shipped profiles" was a meaningless denominator — a
  // user who connects the one provider they intend to use is finished, not 10%
  // finished. The honest headline is how many providers are actually ready.
  //
  // BUG-69 — and "ready" has to mean ready. Counting saved connections put
  // "1 of 10 providers set up" on this page in the same session where Chat
  // said "No readiness check exists for this exact model" and refused to send.
  // The server already counts proven observations; this reads that number and
  // only falls back to counting `ready` profiles if the field is absent.
  const readyCount = $derived(
    models?.ready_provider_count ??
      (models?.profiles ?? []).filter((p) => p.ready === true).length,
  );
  // Set up and usable, whether or not the last observation is still inside its
  // window. This is what an owner means by "I have models"; `readyCount` is
  // what Raiker has actually proven.
  //
  // BUG-270 — the local half of this is a fact the browser cannot see. Four
  // empty llama.cpp slots carry `local-gguf…` model strings and the Ollama
  // native default names a third-party model, so `model !== "<model>"` counted
  // five models on a machine with none of them installed. The server now answers
  // it from the deployment rows and the cached runtime detection; this reads
  // that number and only falls back to the old client-side shape when an older
  // backend sends no field.
  const usableCount = $derived(
    models?.usable_provider_count ??
      (models?.profiles ?? []).filter(
        (p) =>
          p.configured !== false &&
          p.model !== "<model>" &&
          isChoosableModel(p) &&
          (p.connection_configured || !p.off_machine),
      ).length,
  );

  // Each provider's bar is its share of total spend across every provider, so
  // it needs no configured budget to mean something. Providers with no cost
  // (local runtimes, or ones never used) simply have no bar.
  const spendByProfile = $derived(
    spendShares(
      (models?.profiles ?? []).map((p) => ({
        id: p.profile_id,
        cost: p.total_cost,
      })),
    ),
  );
  const totalSpend = $derived(
    (models?.profiles ?? []).reduce((sum, p) => {
      const value = Number(p.total_cost);
      return Number.isFinite(value) && value > 0 ? sum + value : sum;
    }, 0),
  );
  const spendCurrency = $derived(
    (models?.profiles ?? []).find((p) => p.total_cost && p.cost_currency)
      ?.cost_currency ?? "USD",
  );

  /**
   * The profile's fixed posture as one line (BUG-208 slice E).
   *
   * These were four chips sitting beside the readiness chip, which made a
   * property of the profile look like a measurement of it. None of them changes
   * with the workspace, so none of them is state.
   */
  function posture(profile: ModelProfile): string {
    const parts = [
      profile.requires_network ? "Needs network" : "",
      profile.requires_egress_policy ? "Egress-gated" : "",
      profile.runtime_gate ? capabilityLabel(profile.runtime_gate) : "",
      profile.prompt_cache_ttl ? `Cache ${profile.prompt_cache_ttl}` : "",
    ].filter((part) => part !== "");
    return parts.join(" · ");
  }

  function usageLine(profile: ModelProfile): string {
    if (!profile.billable) return "No API cost — runs on this machine";
    const used = profile.models_used ?? 0;
    if (used === 0) return "Not used yet";
    const turns = profile.turns_used ?? 0;
    return `${used} model${used === 1 ? "" : "s"} used · ${turns} turn${turns === 1 ? "" : "s"}`;
  }
  function profilesFor(section: "Local" | "Hosted" | "Advanced") {
    return (models?.profiles ?? []).filter(
      (profile) => sectionFor(profile) === section,
    );
  }
  function frameworkProfiles(provider: "llama.cpp" | "mlx") {
    return profilesFor("Local").filter((profile) => profile.provider === provider);
  }
  function ordinaryLocalProfiles() {
    return profilesFor("Local").filter(
      (profile) => profile.provider !== "llama.cpp" && profile.provider !== "mlx",
    );
  }
  function providerHelp(profile: ModelProfile): string {
    if (profile.provider === "ollama")
      return "Run Ollama locally, then choose one of its installed models.";
    if (profile.provider === "lm-studio")
      return "Start the LM Studio local server, then choose the loaded model.";
    if (profile.provider === "llama.cpp")
      return "Start llama-server and expose the model name configured by the server.";
    if (profile.provider === "mlx")
      return "Run an MLX model locally with mlx-lm on Apple silicon.";
    if (profile.provider === "openai-compatible")
      return "Use this for a vLLM, home-lab, or other OpenAI-compatible endpoint you control.";
    if (profile.provider === "anthropic")
      return "Sign in with your Anthropic API key, enable hosted access, then choose a model.";
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
        return {
          tint: "#d97757",
          headline: "Connect to Anthropic",
          credentialLabel: "Anthropic API key",
          hint: "Create a key at console.anthropic.com. Anthropic uses API keys only — no email login.",
          authMethods: ["apikey"],
          loginUrl: "https://console.anthropic.com/settings/keys",
          loginLabel: "Get an Anthropic key",
        };
      case "openai":
        // Sign-in here means signing in to the OpenAI *platform* account —
        // Google, Microsoft, and Apple all work — to create an API key, which
        // is then pasted below. It deliberately does not claim to use a ChatGPT
        // subscription: ChatGPT Plus/Pro and the API are separately billed, and
        // no subscription grants a third-party app API access. Saying so here
        // is cheaper than a user discovering it through a 401.
        return {
          tint: "#10a37f",
          headline: "Connect to OpenAI",
          credentialLabel: "OpenAI API key",
          hint: "Sign in to platform.openai.com with Google, Microsoft, Apple, or email, then create an API key and paste it below. API usage is billed separately from a ChatGPT subscription — a Plus or Pro plan does not include API access.",
          authMethods: ["login", "apikey"],
          loginUrl: "https://platform.openai.com/api-keys",
          loginLabel: "Sign in with Google or email",
        };
      case "gemini":
        return {
          tint: "#4285f4",
          headline: "Connect to Google AI",
          credentialLabel: "Gemini API key",
          hint: "Create a key in Google AI Studio. Google also supports sign-in with your Google account via Vertex AI.",
          authMethods: ["login", "apikey"],
          loginUrl: "https://aistudio.google.com/apikey",
          loginLabel: "Sign in with Google",
        };
      case "openrouter":
        return {
          tint: "#6b3fa0",
          headline: "Connect to OpenRouter",
          credentialLabel: "OpenRouter API key",
          hint: "Create a key at openrouter.ai/keys. OpenRouter uses API keys only.",
          authMethods: ["apikey"],
          loginUrl: "https://openrouter.ai/keys",
          loginLabel: "Get an OpenRouter key",
        };
      case "huggingface":
        return {
          tint: "#ff9d00",
          headline: "Connect to Hugging Face",
          credentialLabel: "Hugging Face access token",
          hint: "Create a token at huggingface.co/settings/tokens. You can also sign in with your Hugging Face account.",
          authMethods: ["login", "apikey"],
          loginUrl: "https://huggingface.co/settings/tokens",
          loginLabel: "Sign in to Hugging Face",
        };
      case "ollama-cloud":
        return {
          tint: "#22c55e",
          headline: "Connect to Ollama Cloud",
          credentialLabel: "Ollama Cloud API key",
          hint: "Managed Ollama endpoint key. Create one from your Ollama Cloud account.",
          authMethods: ["apikey"],
        };
      case "openai-compatible":
        return {
          tint: "#0f766e",
          headline: "Connect your endpoint",
          credentialLabel: "API key (optional)",
          hint: "A custom OpenAI-compatible endpoint you control (vLLM, home-lab, etc.).",
          authMethods: ["apikey"],
        };
      default:
        return {
          tint: "#0f766e",
          headline: `Connect to ${providerName(provider)}`,
          credentialLabel: "API key",
          hint: "Your provider key, stored encrypted in this Raiker instance.",
          authMethods: ["apikey"],
        };
    }
  }

  onMount(load);
</script>

<div class="head-row">
  <GuideLink route="models" />
  <button
    type="button"
    class="btn btn-ghost btn-sm"
    onclick={() => void refreshProviderCatalogues()}
    disabled={catalogueRefreshing}
    aria-label="Refresh connected providers"
  >
    <Icon name="refresh" size="sm" />
    {catalogueRefreshing ? "Refreshing…" : "Refresh connected providers"}
  </button>
</div>
{#if catalogueNotice}<p class="catalogue-notice" role="status">{catalogueNotice}</p>{/if}

<!-- Readiness and the global default describe the page, not one panel, so
     they sit above the strip: an owner on Pricing or Routing can still see
     whether anything can run and change what runs by default. -->
{#if models !== null && models.profiles.length > 0}
  <section
    class="setup-overview card"
    aria-labelledby="model-setup-title"
  >
    <div>
      <p class="eyebrow">Model setup</p>
      <h2 id="model-setup-title">Choose where Raiker thinks</h2>
    </div>
    <div class="setup-meter" aria-live="polite">
      <!-- "Ready" still means an observation proved it (BUG-69). When every
           observation has merely aged out that number is honestly zero, which
           read as "nothing works" on an instance where models were set up and
           selected — so the line names what is true instead. -->
      <strong
        >{readyCount > 0
          ? `${readyCount} ${readyCount === 1 ? "model" : "models"} ready`
          : usableCount > 0
            ? `${usableCount} ${usableCount === 1 ? "model" : "models"} set up`
            : "No model ready"}</strong
      >
      <span class="of"
        >{configuredProfiles.length} of {models.profiles.length} connected</span
      >
      {#if totalSpend > 0}
        <p class="total-spend">
          {formatCost(String(totalSpend), spendCurrency)} total API cost
        </p>
      {/if}
    </div>
  </section>

  <section
    class="global-model-card card"
    aria-labelledby="global-model-title"
  >
    <div class="global-model-copy">
      <p class="eyebrow">Default</p>
      <h2 id="global-model-title">Global model</h2>
    </div>
    <label class="global-model-field">
      <!-- The card heading beside this already says "Global model", and the
           select carries the same name for assistive technology, so printing it
           a third time only made the card longer. -->
      <small>Choose any configured provider and exact model.</small>
      <select
        aria-label="Global model"
        value={globalChoice}
        onchange={(event) => void selectGlobal(event.currentTarget.value)}
        disabled={selecting}
      >
        <option value="" disabled>Choose a global model</option>
        <!-- Grouped by provider, so a provider names itself once as the
             group it is rather than in front of every one of its models. -->
        {#each globalGroups as group (group.provider)}
          <optgroup label={providerName(group.provider)}>
            {#each group.profiles as profile (`${profile.profile_id}\u0000${profile.model}`)}
              <option value={JSON.stringify([profile.profile_id, profile.model])}
                >{modelName(profile.model)}</option
              >
            {/each}
          </optgroup>
        {/each}
      </select>
    </label>
  </section>
{/if}

<TabStrip
  tabs={TABS}
  selected={tab}
  onselect={selectTab}
  label="Model settings"
/>

{#if loadError}
  <PageState state="error" title="Couldn't load models" detail={loadError} />
{:else if models === null}
  <PageState state="loading" title="Loading models…" />
{:else}
  {#if tab === "huggingface"}<div
      class="panel"
      role="tabpanel"
      id="panel-huggingface"
      aria-labelledby="tab-huggingface"
    >
      <HuggingFacePanel />
    </div>{/if}
  {#if tab === "activity"}<div
      class="panel"
      role="tabpanel"
      id="panel-activity"
      aria-labelledby="tab-activity"
    >
      <ProviderUsagePanel />
      <DownloadsPanel />
    </div>{/if}
  {#if showsProviderCards}
    <div
      class="panel"
      role="tabpanel"
      id={`panel-${tab}`}
      aria-labelledby={`tab-${tab}`}
    >
      <p class="tab-lead">
        {#if tab === "local"}
          Models that run on this machine. Install or start a runtime, pull a
          model, or index GGUF files you already have — nothing here leaves
          this device.
        {:else}
          Accounts you hold with a model provider, and custom endpoints or
          routers you run yourself. You can also choose per prompt in Chat, or
          in the terminal client (<code>/model use …</code>).
        {/if}
      </p>
      <!--
        The four off-machine facts, on the tab they are about. They were their
        own top-level tab — seven words of state and a paragraph, one click away
        from the cards they explain. Read here, they answer the question the
        Hosted tab actually raises: why did this provider refuse. The paragraph
        that sat under them is the guide's *Off-machine provider posture*.
      -->
      {#if tab === "hosted"}
        <dl class="gates" aria-label="Off-machine provider posture">
          <div>
            <dt>Hosted model gate</dt>
            <dd>{gateLabel(models.hosted_model_gate_state, models.hosted_model_gate_enforced)}</dd>
          </div>
          <div>
            <dt>Private-network gate</dt>
            <dd>
              {gateLabel(
                models.private_network_model_gate_state,
                models.private_network_model_gate_enforced,
              )}
            </dd>
          </div>
          <div>
            <dt>Egress allowlist</dt>
            <dd><code>{models.model_egress_allowlist_configured ? "configured" : "not configured"}</code></dd>
          </div>
          <div>
            <dt>Off-machine profiles</dt>
            <dd><code>{models.remote_profile_count}</code></dd>
          </div>
        </dl>
      {/if}
      {#if tab === "local"}<ProvidersPanel onCatalogueChanged={refreshProviderCatalogues} />{/if}
      {#if models.profiles.length === 0}
        <div class="card">
          <!-- VIS-12/FIXED-436 — this said "Add profiles in
               config/model-profiles.json", which named a file Raiker no longer
               reads from the working directory and told the owner to edit
               something they do not have. The shipped registry is never empty,
               so reaching this state means an override replaced it; the page
               that names which registry loaded is the one that can answer. -->
          <EmptyState
            icon="models"
            title="No model profiles are loaded"
            body="Raiker ships with a registry of profiles, so an empty list means an override replaced it."
          >
            {#snippet action()}
              <a class="btn btn-primary" href="#/observe?tab=overview">See which registry loaded</a>
            {/snippet}
          </EmptyState>
        </div>
      {:else}

        {#each visibleSections as section}
          {@const sectionProfiles = profilesFor(section)}
          {#if sectionProfiles.length}
            <section
              class="provider-section"
              aria-labelledby={`section-${section}`}
            >
              <div class="section-heading">
                <div>
                  <p class="eyebrow">{section}</p>
                  <h2 id={`section-${section}`}>
                    {section === "Local"
                      ? "On this device"
                      : section === "Hosted"
                        ? "Your hosted providers"
                        : "Advanced connections"}
                  </h2>
                </div>
                <p>
                  {section === "Local"
                    ? "Private by default; nothing leaves this device."
                    : section === "Hosted"
                      ? "Sign in with your own account and opt in to network access."
                      : "Custom endpoints and provider routers for power users."}
                </p>
              </div>

              {#if section === "Local"}
                <div class="local-list">
                  {#each ordinaryLocalProfiles() as p (p.profile_id)}
                    <div
                      class="local-row"
                      class:selected={p.selected}
                      class:picker-open={pickerFor === p.profile_id}
                    >
                      <span class="row-logo"
                        ><ProviderLogo provider={p.provider} size={28} /></span
                      >
                      <div class="row-main">
                        <!-- No "selected" badge here. A provider row is highlighted when
                       it is the one serving turns, but labelling it "selected"
                       read as "only this provider is available", which is false —
                       every configured provider stays usable. -->
                        <div class="row-title">
                          <h3>{providerName(p.provider)}</h3>
                        </div>
                        <!-- The model line states a fact when there is one and
                             says nothing when there is not. It used to print
                             "model chosen at selection" on every row that had
                             not named one — a placeholder that told an owner
                             about Raiker's pinning vocabulary rather than about
                             their provider, on a page where "Select models…"
                             already offers the choice. -->
                        {#if namesAModel(p)}
                          <p class="row-model"><code>{modelName(p.model)}</code></p>
                        {/if}
                        <p class="row-help">{providerHelp(p)}</p>
                        <!-- BUG-270 — "On this device" is a section whose whole
                             claim is about this device, so the one fact it can
                             state without measuring anything belongs here:
                             whether the runtime is installed at all. Rendered
                             only when detection has an answer — `undefined`
                             means nothing has looked, and silence is honest
                             then. -->
                        {#if p.provider_detected === false}
                          <p class="posture-line runtime-missing">
                            <Icon name="warning" size="sm" />
                            Not installed on this machine
                            {#if installerRuntimeFor(p.provider)}
                              <!-- The offer, not just the finding. Raiker opens
                                   the vendor's own download and accepts nothing
                                   on the owner's behalf. -->
                              <button
                                type="button"
                                class="btn btn-sm"
                                onclick={() => void setUpRuntime(p.provider)}
                                disabled={installing !== null}
                                >{installing === p.provider
                                  ? "Opening…"
                                  : `Set up ${providerName(p.provider)}`}</button
                              >
                            {/if}
                            <button
                              type="button"
                              class="link-button"
                              onclick={() => void redetectRuntimes()}
                              disabled={detecting}
                              >{detecting ? "Looking…" : "Look again"}</button
                            >
                          </p>
                          {#if installNotice && installing === null}
                            <p class="posture-line install-notice" role="status">
                              {installNotice}
                            </p>
                          {/if}
                        {/if}
                        <div class="chips">
                          <span class="chip"
                            >{endpointLabel(p.endpoint_kind)}</span
                          >
                          {#if p.local_only}<span class="chip chip-ok"
                              >Local-only</span
                            >{/if}
                          {#if p.connection_configured}<span
                              class="chip chip-ok">Connection saved</span
                            >{/if}
                          {#if readinessChip(p)}<span
                              class="chip"
                              class:chip-ok={p.ready === true}
                              class:chip-warn={!isChoosableModel(p)}
                              title={p.readiness_summary ?? undefined}
                              >{readinessChip(p)}</span
                            >{/if}
                          {#if p.prompt_cache_ttl}<span
                              class="chip chip-ok"
                              title="Prompt caching cuts cost and latency by reusing the stable prompt prefix"
                              >Cache {p.prompt_cache_ttl}</span
                            >{/if}
                        </div>
                      </div>
                      <div class="row-usage"><span>{usageLine(p)}</span></div>
                      <div class="row-actions">
                        <button
                          type="button"
                          class="btn btn-ghost btn-sm"
                          onclick={() => void testConnection(p)}
                          disabled={testing[p.profile_id] === true}
                          >{testing[p.profile_id] === true
                            ? "Testing…"
                            : "Test"}</button
                        >
                        <button
                          type="button"
                          class="btn btn-ghost btn-sm"
                          onclick={() => (detailsFor = p)}>Details</button
                        >
                        <button
                          type="button"
                          class="btn btn-ghost btn-sm"
                          onclick={() => void openPicker(p.profile_id)}
                          aria-expanded={pickerFor === p.profile_id}
                          >Select models…</button
                        >
                        {#if !p.selected && p.model !== "<model>"}
                          <button
                            type="button"
                            class="btn btn-sm"
                            onclick={() => void select(p.profile_id)}
                            disabled={selecting}>Select</button
                          >
                        {/if}
                      </div>
                      <!-- BUG-47 — the local row that ran the test is where its
                     answer belongs. Without this the result had nowhere to go
                     here and surfaced under the hosted cards instead. -->
                      {#if testResults[p.profile_id]}
                        <p
                          class="test-result row-test-result"
                          role="status"
                          data-test-result={p.profile_id}
                        >
                          {testResults[p.profile_id]}
                        </p>
                      {/if}
                    </div>
                  {/each}
                  {#if frameworkProfiles("llama.cpp").length > 0}
                    <LocalFrameworkRow
                      provider="llama.cpp"
                      title="GGUF"
                      format="gguf"
                      profiles={frameworkProfiles("llama.cpp")}
                      description="Up to four detected GGUF models, each served in its own slot by the llama.cpp server Raiker runs for you."
                      onchanged={() => void load()}
                      ontest={(profile) => void testConnection(profile)}
                      ondetails={(profile) => (detailsFor = profile)}
                      onselect={(profile) => void select(profile.profile_id)}
                      testing={testing[frameworkProfiles("llama.cpp")[0].profile_id] === true}
                      {selecting}
                      testResult={testResults[frameworkProfiles("llama.cpp")[0].profile_id] ?? null}
                    />
                  {/if}
                  {#if frameworkProfiles("mlx").length > 0}
                    <LocalFrameworkRow
                      provider="mlx"
                      title="MLX"
                      format="mlx"
                      profiles={frameworkProfiles("mlx")}
                      description="Choose up to four detected MLX models optimized for Apple silicon."
                      onchanged={() => void load()}
                      ontest={(profile) => void testConnection(profile)}
                      ondetails={(profile) => (detailsFor = profile)}
                      onselect={(profile) => void select(profile.profile_id)}
                      testing={testing[frameworkProfiles("mlx")[0].profile_id] === true}
                      {selecting}
                      testResult={testResults[frameworkProfiles("mlx")[0].profile_id] ?? null}
                    />
                  {/if}
                  <!-- BUG-256 — dictation's runtime is a local runtime, and it
                       belongs beside the others rather than in a category of
                       its own. Nothing here is contacted until Save and test. -->
                  <SpeechRuntimePanel />
                </div>
              {:else}
                <div class="provider-grid">
                  {#each sectionProfiles as p (p.profile_id)}
                    {@const b = brand(p.provider)}
                    <article
                      class="provider-card"
                      class:selected={p.selected}
                      class:connected={isConnected(p)}
                    >
                      <div class="pc-head">
                        <span class="pc-logo"
                          ><ProviderLogo
                            provider={p.provider}
                            size={34}
                          /></span
                        >
                        <div class="pc-title">
                          <h3>{providerName(p.provider)}</h3>
                        </div>
                      </div>
                      <!-- Same rule as the local rows: name the model when one
                           is named, and print nothing when none is. Eight cards
                           reading "no model pinned" was the largest single block
                           of text on this page and the least of it about the
                           owner's providers — "Not connected" below and
                           "Select models…" beneath that already carry it. -->
                      {#if namesAModel(p)}
                        <p class="pc-model"><code>{modelName(p.model)}</code></p>
                      {/if}
                      <p class="pc-status">
                        <!-- BUG-198 — this line reports whether a connection is
                             *saved*, which is not whether the provider answers:
                             a card could read "Connected" directly above
                             "Provider unreachable". Reachability is the
                             readiness chip below, and only it may claim it. -->
                        {#if isCodexSubscription(p) && isConnected(p)}
                          <span class="status-dot ok" aria-hidden="true"></span>
                          {codexPlanLabel}
                        {:else if isCodexSubscription(p) && codexSubscriptionStatus === "codex_missing"}
                          <span class="status-dot" aria-hidden="true"></span> Codex
                          not installed
                        {:else if isConnected(p)}
                          <span class="status-dot ok" aria-hidden="true"></span>
                          Connection saved
                        {:else}
                          <span class="status-dot" aria-hidden="true"></span> Not
                          connected
                        {/if}
                      </p>
                      <div class="chips">
                        {#if readinessChip(p)}<span
                            class="chip"
                            class:chip-ok={p.ready === true}
                            class:chip-warn={!isChoosableModel(p)}
                            title={p.readiness_summary ?? undefined}
                            >{readinessChip(p)}</span
                          >{/if}
                      </div>
                      <!-- BUG-208 slice E — these four were chips beside the
                           readiness chip, which made a fixed property of the
                           profile look like something that had just been
                           measured. Readiness is the only state on this card;
                           the posture is one quiet line. -->
                      {#if posture(p) !== ""}
                        <p class="posture-line">{posture(p)}</p>
                      {/if}
                      <!-- BUG-270 — a local runtime that is not on this machine
                           is the one thing the card can say without measuring
                           anything, and it is exactly what an owner needs to
                           read before wondering why a model they never
                           installed is not answering. Only rendered when
                           detection has an answer: `provider_detected` is null
                           when nothing has looked, and silence is the honest
                           output then. -->
                      {#if p.provider_detected === false}
                        <p class="posture-line runtime-missing">
                          <Icon name="warning" size="sm" />
                          Not installed on this machine
                          {#if installerRuntimeFor(p.provider)}
                            <button
                              type="button"
                              class="btn btn-sm"
                              onclick={() => void setUpRuntime(p.provider)}
                              disabled={installing !== null}
                              >{installing === p.provider
                                ? "Opening…"
                                : `Set up ${providerName(p.provider)}`}</button
                            >
                          {/if}
                          <button
                            type="button"
                            class="link-button"
                            onclick={() => void redetectRuntimes()}
                            disabled={detecting}
                            >{detecting ? "Looking…" : "Look again"}</button
                          >
                        </p>
                        {#if installNotice && installing === null}
                          <p class="posture-line install-notice" role="status">
                            {installNotice}
                          </p>
                        {/if}
                      {/if}
                      <!-- Shown only where there is something to report: a
                           local runtime that cannot bill and a provider with no
                           turns yet were both rendering a line and an em dash. -->
                      {#if p.billable && (p.turns_used ?? 0) > 0}
                      <div class="usage-strip">
                        <div class="usage-line">
                          <span>{usageLine(p)}</span>
                          {#if p.billable}
                            <strong
                              >{formatCost(p.total_cost, p.cost_currency) ??
                                "—"}</strong
                            >
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
                            <span
                              class="bar-fill"
                              data-value={spendByProfile[p.profile_id]}
                            ></span>
                          </div>
                          <p class="usage-note">
                            {spendByProfile[p.profile_id]}% of your total API
                            spend{#if sourceNote(p.price_source, p.price_as_of)}&nbsp;·
                              {sourceNote(p.price_source, p.price_as_of)}{/if}
                          </p>
                        {:else if p.billable && (p.turns_used ?? 0) > 0}
                          <p class="usage-note">
                            No price configured for the models used, so cost is
                            unknown.
                          </p>
                        {/if}
                      </div>
                      {/if}

                      <div class="pc-actions">
                        {#if isCodexSubscription(p) && isConnected(p)}
                          <!-- The readiness check is what lets a pinned model be
                               used, so the subscription card offers it for the
                               same reason every other connected provider does. -->
                          <button
                            type="button"
                            class="btn btn-ghost btn-sm"
                            onclick={() => void testConnection(p)}
                            disabled={testing[p.profile_id] === true}
                            >{testing[p.profile_id] === true ? "Testing…" : "Test"}</button
                          >
                          <!-- Signing in stays reachable while connected: an
                               owner with more than one ChatGPT plan has no other
                               way to move Raiker to the one they want. -->
                          <button
                            type="button"
                            class="btn btn-ghost btn-sm"
                            onclick={() => void startCodexSubscriptionLogin()}
                            disabled={codexSubscriptionBusy}
                            >{codexSubscriptionBusy ? "Opening sign-in…" : "Switch account"}</button
                          >
                          <button
                            type="button"
                            class="btn btn-ghost btn-sm"
                            onclick={() => void disconnectCodexSubscription()}
                            disabled={codexSubscriptionBusy}
                            >Sign out</button
                          >
                        {:else if isCodexSubscription(p)}
                          <button
                            type="button"
                            class="btn btn-primary btn-sm pc-connect"
                            onclick={() => void startCodexSubscriptionLogin()}
                            disabled={codexSubscriptionBusy}
                            style={`--brand:${b.tint}`}
                            >{codexSubscriptionBusy
                              ? "Opening sign-in…"
                              : "Sign in with ChatGPT"}</button
                          >
                        {:else if !p.connection_configured}
                          <button
                            type="button"
                            class="btn btn-primary btn-sm pc-connect"
                            onclick={() => openSignIn(p.profile_id)}
                            style={`--brand:${b.tint}`}>Connect</button
                          >
                        {:else}
                          <!-- BUG-208 slice E — Reconnect and Disconnect are
                               credential management, not the thing an owner came
                               to this card to do. They live in Details, which is
                               one click away and already open on this profile. -->
                          <button
                            type="button"
                            class="btn btn-ghost btn-sm"
                            onclick={() => void testConnection(p)}
                            disabled={testing[p.profile_id] === true}
                            >{testing[p.profile_id] === true
                              ? "Testing…"
                              : "Test"}</button
                          >
                        {/if}
                        <button
                          type="button"
                          class="btn btn-ghost btn-sm"
                          onclick={() => void openPicker(p.profile_id)}
                          aria-expanded={pickerFor === p.profile_id}
                          >Select models…</button
                        >
                        {#if p.connection_configured && !p.selected && p.model !== "<model>"}
                          <button
                            type="button"
                            class="btn btn-sm"
                            onclick={() => void select(p.profile_id)}
                            disabled={selecting}>Select</button
                          >
                        {/if}
                        <button
                          type="button"
                          class="btn btn-ghost btn-sm"
                          onclick={() => (detailsFor = p)}>Details</button
                        >
                      </div>
                      {#if testResults[p.profile_id]}
                        <p
                          class="test-result"
                          role="status"
                          data-test-result={p.profile_id}
                        >
                          {testResults[p.profile_id]}
                          <!-- BUG-274 — the readiness answer names the field;
                               this is the field. Without it the owner reads
                               "add the workspace ID to this connection" and
                               then has to find it under Details → Reconnect →
                               Advanced, which is a remediation pointing at
                               nothing they can see. -->
                          {#if wantsWorkspace(p)}
                            <button
                              type="button"
                              class="link-button"
                              onclick={() =>
                                openSignIn(p.profile_id, { advanced: true })}
                              >Add workspace ID</button
                            >
                          {/if}
                        </p>
                      {/if}
                      {#if isCodexSubscription(p) && codexSubscriptionNotice}
                        <p class="test-result" role="status">{codexSubscriptionNotice}</p>
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
      <!-- Building a local model finishes here: a runtime above, and the GGUF
           files this machine already holds below. Splitting them across two
           tabs made the owner navigate mid-task. -->
      {#if tab === "local"}<LocalLibraryPanel />{/if}
    </div>
  {/if}

  {#if tab === "routing"}
    <div
      class="panel"
      role="tabpanel"
      id="panel-routing"
      aria-labelledby="tab-routing"
    >
      <section class="card fallback" aria-labelledby="fallback-h">
        <h2 id="fallback-h">Model fallback sequence</h2>

        {#if sequence.length === 0}
          <p class="fallback-empty">
            No fallback configured. The turn fails closed if the selected
            provider is unavailable.
          </p>
        {:else}
          <ol class="fallback-list">
            {#each sequence as id, i (id)}
              <li class="fallback-item">
                <span class="rank">{i + 1}</span>
                <span class="fallback-name">
                  {profileLabel(id)}
                </span>
                <span class="fallback-actions">
                  <button
                    type="button"
                    class="btn btn-ghost btn-sm"
                    onclick={() => move(i, -1)}
                    disabled={i === 0}
                    aria-label="Move up">↑</button
                  >
                  <button
                    type="button"
                    class="btn btn-ghost btn-sm"
                    onclick={() => move(i, 1)}
                    disabled={i === sequence.length - 1}
                    aria-label="Move down">↓</button
                  >
                  <button
                    type="button"
                    class="btn btn-ghost btn-sm"
                    onclick={() => remove(i)}
                    aria-label="Remove">Remove</button
                  >
                </span>
              </li>
            {/each}
          </ol>
        {/if}

        <div class="fallback-add">
          <select bind:value={addChoice} aria-label="Add a fallback backend">
            <option value="">Add a backend…</option>
            {#each addable as p (p.profile_id)}
              <option value={p.profile_id}
                >{providerName(p.provider)}{namesAModel(p)
                  ? ` (${modelName(p.model)})`
                  : " (no model)"}</option
              >
            {/each}
          </select>
          <button
            type="button"
            class="btn btn-sm"
            onclick={add}
            disabled={addChoice === ""}>Add</button
          >
        </div>

        <div class="fallback-save">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            onclick={save}
            disabled={!dirty || saving}
          >
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
          A local model can consult one advisor through the governed
          <code>consult_advisor</code> tool. Picking one grants nothing: every
          consult is still gated at call time.
          <GuideLink section="connecting-a-model" label="How an advisor is governed" />
        </p>
        <div class="advisor-row">
          <select bind:value={advisorChoice} aria-label="Advisor model profile">
            <option value="">No advisor</option>
            {#each advisorCandidates as p (p.profile_id)}
              <option value={p.profile_id}
                >{providerName(p.provider)} — {modelName(p.model)}</option
              >
            {/each}
          </select>
          <button
            type="button"
            class="btn btn-primary btn-sm"
            onclick={saveAdvisor}
            disabled={!advisorDirty || advisorSaving}
          >
            {advisorSaving ? "Saving…" : "Save advisor"}
          </button>
          {#if advisorError}
            <span class="error" role="alert">{advisorError}</span>
          {:else if advisorSaved && !advisorDirty}
            <span class="ok-note">Saved.</span>
          {/if}
        </div>
        <!-- BUG-82 — what the last check of the *exact* advisor model found, and
             the one control that repairs it. Without this an owner could pin an
             advisor with no credential, no credit or no running runtime and see
             nothing wrong until a consult failed mid-turn. -->
        {#if models?.advisor_profile_id}
          <div class="advisor-readiness">
            {#if advisorChip}
              <span
                class="chip"
                class:chip-ok={models.advisor_readiness_state === "ready"}
                class:chip-warn={models.advisor_readiness_state !== "ready"}
                data-testid="advisor-readiness-chip"
                title={models.advisor_readiness_summary ?? undefined}>{advisorChip}</span
              >
            {/if}
            <span class="advisor-model-name">{modelName(models.advisor_model ?? "")}</span>
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              onclick={checkAdvisor}
              disabled={advisorChecking || !models.advisor_model}
            >
              {advisorChecking ? "Checking…" : "Check advisor"}
            </button>
          </div>
          {#if advisorCheckNote}
            <p class="sub" role="status">{advisorCheckNote}</p>
          {:else if models.advisor_readiness_state !== "ready" && models.advisor_readiness_remediation}
            <p class="sub" role="status">
              {models.advisor_readiness_summary} {models.advisor_readiness_remediation}
            </p>
          {/if}
        {/if}
      </section>
    </div>
  {/if}

  {#if tab === "pricing"}
    <div
      class="panel"
      role="tabpanel"
      id="panel-pricing"
      aria-labelledby="tab-pricing"
    >
      <!-- BUG-21 — the price registry. Its own destination, because looking up
         what a model costs is its own errand, not a footnote to connecting one. -->
      <ModelPricingPanel />
    </div>
  {/if}

{/if}


{#if detailsFor}
  {@const capacityEntry = capacities?.entries.find(
    (entry) =>
      entry.profile_id === detailsFor!.profile_id &&
      entry.model === detailsFor!.model,
  )}
  <div
    class="details-overlay"
    role="presentation"
    onclick={(event) =>
      event.target === event.currentTarget && (detailsFor = null)}
  >
    <div
      class="details-dialog card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="model-details-title"
      tabindex="-1"
    >
      <button
        class="close"
        aria-label="Close model details"
        onclick={() => (detailsFor = null)}>×</button
      >
      <p class="eyebrow">Model details</p>
      <div class="details-heading">
        <ProviderLogo provider={detailsFor.provider} size={28} />
        <h2 id="model-details-title">{providerName(detailsFor.provider)}</h2>
      </div>
      <dl class="details-grid">
        <div>
          <dt>Selected model</dt>
          <dd>
            <code
              >{detailsFor.selected
                ? modelName(detailsFor.model)
                : "Not selected"}</code
            >
          </dd>
        </div>
        <div>
          <dt>Connection</dt>
          <dd>
            {detailsFor.connection_configured
              ? "Encrypted instance connection saved"
              : "Not configured"}
            <!-- BUG-274 — that a workspace is named, never which one. Here
                 rather than on the card: the card carries readiness and nothing
                 else by design (BUG-208 slice E), and this is credential
                 management, which is what Details already holds. -->
            {#if detailsFor.workspace_configured}
              · workspace named
            {/if}
          </dd>
        </div>
        <div>
          <dt>Context capacity</dt>
          <dd>{contextCapacity(detailsFor)}</dd>
        </div>
        <div>
          <dt>Local refresh</dt>
          <dd>
            {capacities?.sync.find(
              (state) => state.profile_id === detailsFor?.profile_id,
            )?.next_refresh_at
              ? `Next check ${capacities.sync.find((state) => state.profile_id === detailsFor?.profile_id)?.next_refresh_at}`
              : "Scheduled when this local runtime is available"}
          </dd>
        </div>
        <div>
          <dt>Current context usage</dt>
          <dd>
            No provider context telemetry has been received for this model yet.
          </dd>
        </div>
        <div>
          <dt>Subscription / rate limits</dt>
          <dd>
            Not available through this connection. Raiker only displays daily or
            weekly limits when an authorized provider API exposes them.
          </dd>
        </div>
      </dl>
      {#if detailsFor.connection_configured}
        <div class="details-actions">
          <button
            type="button"
            class="btn btn-ghost btn-sm"
            onclick={() => openSignIn(detailsFor!.profile_id)}>Reconnect</button
          >
          <button
            type="button"
            class="btn btn-ghost btn-sm"
            aria-label={`Disconnect ${providerName(detailsFor.provider)}`}
            onclick={() => void disconnectConnection(detailsFor!)}
            disabled={disconnecting[detailsFor.profile_id] === true}
            >{disconnecting[detailsFor.profile_id] === true
              ? "Disconnecting…"
              : "Disconnect"}</button
          >
        </div>
      {/if}
      {#if capacities?.can_override}<button
          class="btn btn-ghost btn-sm"
          onclick={() => void configureCapacity(detailsFor!)}
          >Configure exact capacity</button
        >{/if}
      {#if capacityEntry?.history.length}<details>
          <summary>Administrator override history</summary>
          <ol>
            {#each capacityEntry.history as event}<li>
                {event.action} · {event.context_window_tokens?.toLocaleString() ??
                  "cleared"} · {event.recorded_at}{#if event.reason}
                  — {event.reason}{/if}
              </li>{/each}
          </ol>
        </details>{/if}
    </div>
  </div>
{/if}

<!-- Choosing a model is a decision with a catalogue behind it, so it gets a
     dialog rather than an accordion inside a card. Inline, it pushed every
     other provider down the page and turned a six-model list into a scroll
     inside a scroll. -->
{#if pickerFor !== null && pickerProfile !== null}
  <div
    class="signin-overlay"
    role="presentation"
    onclick={(event) => event.target === event.currentTarget && closePicker()}
  >
    <div
      class="signin-dialog picker-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="picker-title"
      tabindex="-1"
    >
      <button class="close" aria-label="Close model picker" onclick={closePicker}>×</button>
      <div class="signin-logo">
        <ProviderLogo provider={pickerProfile.provider} size={40} />
      </div>
      <h2 id="picker-title">{providerName(pickerProfile.provider)} models</h2>
      {#if pickerLoading}
        <p class="picker-note" role="status">
          Loading models from {providerName(pickerProfile.provider)}…
        </p>
      {:else if pickerList !== null && pickerList.status === "available" && pickerList.models.length > 0}
        <!-- Each switch is the whole decision: on means this model is offered
             everywhere, off means it is not. There is no second "Use model"
             step, because there was never a second question. -->
        <AvailableModels
          profileId={pickerProfile.profile_id}
          catalogue={pickerList.models}
          chosen={availableModelsFor(pickerProfile.profile_id)}
          onsaved={() => void load()}
        />
        <div class="picker-actions">
          <button type="button" class="btn btn-ghost btn-sm" onclick={closePicker}>Done</button>
        </div>
      {:else}
        <p class="picker-note">
          {pickerList !== null
            ? pickerNote(pickerList)
            : "Model list unavailable — enter a custom model name."}
        </p>
        <input
          class="picker-input"
          type="text"
          placeholder="Custom model name"
          bind:value={pickerChoice}
          aria-label="Custom model name"
        />
        <div class="picker-actions">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            onclick={() => pickerFor && void select(pickerFor, pickerChoice)}
            disabled={selecting || pickerChoice.trim() === ""}
            >{selecting ? "Selecting…" : "Use model"}</button
          >
          <button type="button" class="btn btn-ghost btn-sm" onclick={closePicker}>Cancel</button>
        </div>
        {#if selectError}<p class="error picker-error" role="alert">{selectError}</p>{/if}
      {/if}
    </div>
  </div>
{/if}

{#if signInFor !== null && signInProfile !== null}
  {@const b = brand(signInProfile.provider)}
  {@const showLogin = b.authMethods.includes("login")}
  {@const showApiKey = b.authMethods.includes("apikey")}
  <div
    class="signin-overlay"
    role="presentation"
    onclick={(event) => event.target === event.currentTarget && closeSignIn()}
  >
    <div
      class="signin-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="signin-title"
      tabindex="-1"
      style={`--brand:${b.tint}`}
    >
      <button class="close" aria-label="Close" onclick={closeSignIn}>×</button>
      <div class="signin-logo">
        <ProviderLogo provider={signInProfile.provider} size={44} />
      </div>
      <h2 id="signin-title">{b.headline}</h2>
      <p class="signin-hint">{b.hint}</p>

      {#if showLogin && b.loginUrl}
        <a
          class="sso-btn"
          href={b.loginUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={`--brand:${b.tint}`}
        >
          {b.loginLabel} →
        </a>
        {#if showApiKey}
          <div class="signin-divider"><span>or paste a key</span></div>
        {/if}
      {/if}

      {#if showApiKey}
        <label class="field">
          <span class="field-label">{b.credentialLabel}</span>
          <input
            class="input"
            type="password"
            placeholder={b.credentialLabel.toLowerCase().includes("optional")
              ? "(optional)"
              : "sk-…"}
            bind:value={signInApiKey}
            autocomplete="new-password"
          />
        </label>
      {/if}

      {#if signInProfile.provider === "openai" || signInProfile.provider === "anthropic"}
        <label class="field admin-usage-field">
          <span class="field-label"
            >Organization usage admin key <small>(optional)</small></span
          >
          <input
            class="input"
            type="password"
            placeholder="Admin key for usage reports"
            bind:value={signInAdminApiKey}
            autocomplete="new-password"
          />
          <small>
            Used only to read genuine organization usage. Raiker never uses this
            key for model calls.
          </small>
        </label>
      {/if}

      <button
        type="button"
        class="sso-toggle"
        onclick={() => (signInAdvanced = !signInAdvanced)}
        aria-expanded={signInAdvanced}
      >
        {signInAdvanced ? "Hide advanced" : "Advanced"}
      </button>
      {#if signInAdvanced}
        <label class="field">
          <span class="field-label"
            >Custom endpoint <small>(leave blank for provider default)</small
            ></span
          >
          <input
            class="input"
            type="url"
            placeholder="https://…"
            bind:value={signInEndpoint}
          />
        </label>
        <!-- BUG-274 — an identity-linked key acts inside one workspace and the
             provider refuses it without the id. Behind Advanced because most
             keys need nothing here; the refusal opens this section itself. -->
        {#if signInProfile.provider === "anthropic"}
          <label class="field">
            <span class="field-label"
              >Workspace ID <small>(identity-linked keys only)</small></span
            >
            <input
              class="input"
              type="text"
              placeholder="wrkspc_…"
              spellcheck="false"
              autocapitalize="off"
              autocomplete="off"
              bind:value={signInWorkspaceId}
            />
          </label>
        {/if}
      {/if}

      <div class="signin-actions">
        <button
          type="button"
          class="btn btn-primary signin-connect"
          onclick={() => void saveConnection(signInProfile.profile_id)}
          disabled={signInSaving ||
            (signInEndpoint.trim() === "" &&
              signInApiKey.trim() === "" &&
              signInWorkspaceId.trim() === "" &&
              !signInAdvanced)}
        >
          {signInSaving ? "Connecting…" : "Connect"}
        </button>
        <button type="button" class="btn btn-ghost" onclick={closeSignIn}
          >Cancel</button
        >
      </div>
      {#if signInError}<p class="error" role="alert">{signInError}</p>{/if}
      {#if signInGuidance}
        <div class="signin-guidance" role="alert">
          <p class="sg-message">{signInGuidance.message}</p>
          <p class="sg-fix">{signInGuidance.fix}</p>
          {#if signInGuidance.href}
            <a class="sg-link" href={signInGuidance.href} onclick={closeSignIn}
              >{signInGuidance.linkLabel} →</a
            >
          {/if}
          <p class="sg-code">Reason code: <code>{signInGuidance.code}</code></p>
        </div>
      {/if}
      <p class="signin-foot">
        Your key is encrypted in this instance’s vault and never leaves this
        device.
      </p>
    </div>
  </div>
{/if}

<style>
  /* Each panel keeps the vertical rhythm the page had as one scroll, so moving
     a section into a tab changed where it lives, not how it reads. */
  /* A grid column left at `auto` is sized by the widest thing inside it, so one
     unwrappable descendant made every sibling — including plain paragraphs —
     416px wide inside a 366px page, and a phone got clipped body text. The
     column is bound to the container instead; anything genuinely wide now
     overflows on its own and can be given its own scroll. */
  .panel {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-4);
  }
  .panel > :global(*) {
    min-width: 0;
  }
  .tab-lead {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
    line-height: 1.5;
    max-width: 72ch;
  }
  .setup-overview,
  .global-model-card,
  .section-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .setup-overview {
    margin: var(--space-4) 0;
  }
  .global-model-card {
    margin: var(--space-4) 0;
  }
  .global-model-copy {
    max-width: 40rem;
  }
  .global-model-field {
    display: grid;
    gap: 0.3rem;
    min-width: min(100%, 22rem);
    font-weight: 650;
  }
  .global-model-field small {
    color: var(--text-2);
    font-weight: 400;
  }
  .global-model-field select {
    width: 100%;
    font: inherit;
  }
  .global-model-field select:focus-visible {
    outline: 3px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .provider-section {
    margin-top: var(--space-5);
  }
  .section-heading {
    align-items: end;
    margin-bottom: var(--space-3);
  }
  .section-heading h2,
  .setup-overview h2 {
    margin: 0;
    font-size: var(--text-base);
  }
  .section-heading > p {
    max-width: 28rem;
    color: var(--text-3);
    font-size: var(--text-sm);
    margin: 0;
  }
  .eyebrow {
    color: var(--accent);
    font-size: var(--text-2xs);
    font-weight: 750;
    letter-spacing: 0.08em;
    margin: 0 0 0.25rem;
    text-transform: uppercase;
  }
  .setup-meter {
    min-width: 9rem;
    text-align: right;
  }
  .setup-meter strong {
    display: block;
    font-size: var(--text-xl);
  }
  .setup-meter span {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .setup-meter .total-spend {
    color: var(--text-2);
    font-size: var(--text-sm);
    margin: 0.35rem 0 0;
  }
  .posture-line {
    margin: 0.1rem 0 0;
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  /* BUG-270 — the one line on a provider card that is about this machine
     rather than about a provider. It carries the warning tone because it is
     the reason nothing on the card will answer, and it wraps rather than
     truncating so the "Look again" action survives a narrow window. */
  .runtime-missing {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.3rem;
    color: var(--warn, var(--text-2));
  }
  .runtime-missing .link-button {
    background: none;
    border: 0;
    padding: 0;
    color: inherit;
    font: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
  .runtime-missing .link-button:disabled {
    cursor: default;
    opacity: 0.6;
  }
  .install-notice {
    color: var(--text-2);
  }
  .details-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .usage-strip {
    border-top: 1px solid var(--border);
    margin-top: 0.7rem;
    padding-top: 0.6rem;
  }
  .usage-line {
    align-items: baseline;
    color: var(--text-2);
    display: flex;
    font-size: var(--text-sm);
    gap: 0.75rem;
    justify-content: space-between;
  }
  .usage-line strong {
    color: var(--text-1);
  }
  .usage-note {
    color: var(--text-3);
    font-size: var(--text-xs);
    margin: 0.35rem 0 0;
  }
  .row-usage {
    color: var(--text-3);
    font-size: var(--text-sm);
    grid-column: 1 / -1;
  }
  /* Geometry lives in the shared `.bar` primitive; this only places it. */
  .spend-bar {
    margin-top: 0.35rem;
  }

  /* ── Local: clean list rows ── */
  .local-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .local-row {
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
    padding: 0.75rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    flex-wrap: wrap;
  }
  .local-row.selected {
    border-color: var(--accent-border);
    box-shadow: 0 0 0 1px var(--accent-border);
  }
  .local-row.picker-open {
    border-color: var(--accent-border);
  }
  .row-logo {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .row-main {
    flex: 1;
    min-width: 0;
  }
  .row-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .row-title h3 {
    margin: 0;
    font-size: var(--text-base);
  }
  .row-model {
    margin: 0.15rem 0 0.4rem;
    color: var(--text-2);
    font-size: var(--text-sm);
    overflow-wrap: anywhere;
  }
  .row-help {
    color: var(--text-3);
    font-size: var(--text-sm);
    line-height: 1.35;
    margin: 0 0 0.5rem;
  }
  .row-actions {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
    align-items: center;
  }

  /* ── Hosted/Advanced: provider cards ── */
  .provider-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr));
    gap: var(--space-4);
  }
  .provider-card {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 1rem 1.05rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-1);
  }
  .provider-card.selected {
    border-color: var(--accent-border);
    box-shadow:
      0 0 0 1px var(--accent-border),
      var(--shadow-1);
  }
  .provider-card.connected {
    border-color: var(--ok-border);
  }
  .pc-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .pc-logo {
    min-width: 2.4rem;
    height: 2.4rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .pc-title {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
  }
  .pc-title h3 {
    margin: 0;
    font-size: var(--text-base);
  }
  .pc-model {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
    overflow-wrap: anywhere;
  }
  .pc-status {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .status-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: var(--text-3);
  }
  .status-dot.ok {
    background: var(--ok);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 22%, transparent);
  }
  .pc-actions {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
    margin-top: 0.2rem;
  }
  .pc-connect {
    background: var(--brand);
    border-color: var(--brand);
    color: var(--brand-black);
  }
  .pc-connect:hover:not(:disabled) {
    background: color-mix(in srgb, var(--brand) 88%, var(--brand-black));
    border-color: color-mix(in srgb, var(--brand) 88%, var(--brand-black));
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .chip {
    font-size: var(--text-xs);
    font-weight: 600;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    padding: 0.08rem 0.55rem;
  }
  .chip-ok {
    border-color: var(--ok-border);
    background: var(--ok-soft);
    color: var(--ok);
  }
  .chip-warn {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }

  .picker-dialog {
    display: grid;
    gap: 0.7rem;
    text-align: left;
  }
  .picker-dialog h2 {
    margin: 0;
  }
  .picker-input {
    padding: 0.35rem 0.5rem;
    border-radius: var(--r-md);
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--text-1);
    max-width: 100%;
    font: inherit;
    font-size: var(--text-md);
  }
  .picker-note {
    font-size: var(--text-xs);
    color: var(--text-3);
    margin: 0;
  }
  .picker-actions {
    display: flex;
    gap: 0.4rem;
  }
  .picker-error {
    font-size: var(--text-sm);
    margin: 0;
  }
  .test-result {
    color: var(--text-2);
    font-size: var(--text-xs);
    margin: 0.3rem 0 0;
  }
  /* The local rows are a wrapping flex row; a result needs the full width to
     sit under the row that produced it rather than beside its actions. */
  .row-test-result {
    width: 100%;
  }

  /* ── Sign-in modal ── */
  .signin-overlay {
    align-items: center;
    background: var(--overlay);
    display: flex;
    inset: 0;
    justify-content: center;
    padding: var(--space-4);
    position: fixed;
    z-index: 40;
  }
  .signin-dialog {
    position: relative;
    width: min(100%, 26rem);
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-top: 4px solid var(--brand);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-2);
    padding: 1.6rem 1.5rem 1.3rem;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }
  .signin-dialog .close {
    position: absolute;
    top: 0.6rem;
    right: 0.7rem;
    background: transparent;
    border: 0;
    color: var(--text-2);
    cursor: pointer;
    font-size: var(--text-2xl);
    line-height: 1;
  }
  .signin-logo {
    min-height: 3rem;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 0.1rem;
  }
  .signin-dialog h2 {
    margin: 0;
    text-align: center;
    font-size: var(--text-xl);
  }
  .signin-hint {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-sm);
    line-height: 1.4;
    text-align: center;
  }
  .sso-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    padding: 0.55rem 1rem;
    border-radius: var(--r-sm);
    background: var(--brand);
    color: var(--brand-black);
    font-weight: 600;
    font-size: var(--text-sm);
    text-decoration: none;
    border: 1px solid var(--brand);
    transition: opacity 120ms var(--ease);
    margin: 0.3rem 0 0.1rem;
  }
  .sso-btn:hover {
    text-decoration: none;
    opacity: 0.9;
  }
  .signin-divider {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.4rem 0;
  }
  .signin-divider::before,
  .signin-divider::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--border);
  }
  .signin-divider span {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .field-label {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-2);
  }
  .field-label small {
    color: var(--text-3);
    font-weight: 400;
  }
  .admin-usage-field > small {
    color: var(--text-3);
    font-size: var(--text-2xs);
    line-height: 1.35;
  }
  .sso-toggle {
    align-self: flex-start;
    background: transparent;
    border: 0;
    color: var(--accent);
    cursor: pointer;
    font-size: var(--text-sm);
    padding: 0.1rem 0;
  }
  .signin-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.3rem;
  }
  .signin-connect {
    flex: 1;
    background: var(--brand);
    border-color: var(--brand);
    color: var(--brand-black);
  }
  .signin-connect:hover:not(:disabled) {
    background: color-mix(in srgb, var(--brand) 88%, var(--brand-black));
    border-color: color-mix(in srgb, var(--brand) 88%, var(--brand-black));
  }
  .signin-foot {
    margin: 0.4rem 0 0;
    text-align: center;
    color: var(--text-3);
    font-size: var(--text-2xs);
  }
  .signin-guidance {
    background: var(--warn-soft);
    border: 1px solid var(--warn-border);
    border-radius: var(--r-sm);
    display: grid;
    gap: 0.35rem;
    padding: 0.7rem 0.8rem;
  }
  .signin-guidance p {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.45;
    overflow-wrap: anywhere;
  }
  .signin-guidance code {
    overflow-wrap: anywhere;
  }
  .sg-message {
    color: var(--text-1);
    font-weight: 600;
  }
  .sg-fix {
    color: var(--text-2);
  }
  .sg-link {
    color: var(--accent);
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .sg-code {
    color: var(--text-3);
    font-size: var(--text-xs);
  }

  /* ── Details modal ── */
  .details-overlay {
    align-items: center;
    background: var(--overlay);
    display: flex;
    inset: 0;
    justify-content: center;
    padding: var(--space-4);
    position: fixed;
    z-index: 30;
  }
  .details-dialog {
    max-width: 42rem;
    position: relative;
    width: min(100%, 42rem);
  }
  .details-heading {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    margin-bottom: 0.9rem;
  }
  .details-dialog h2 {
    margin: 0;
  }
  .close {
    background: transparent;
    border: 0;
    color: var(--text-2);
    cursor: pointer;
    font-size: var(--text-2xl);
    line-height: 1;
    position: absolute;
    right: 0.75rem;
    top: 0.65rem;
  }
  .details-grid {
    display: grid;
    gap: 0.85rem;
    margin: var(--space-4) 0 0;
  }
  .details-grid div {
    border-top: 1px solid var(--border);
    padding-top: 0.65rem;
  }
  .details-grid dt {
    color: var(--text-3);
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
  }
  .details-grid dd {
    color: var(--text-2);
    line-height: 1.45;
    margin: 0.2rem 0 0;
  }

  /* ── Fallback / advisor / gates ── */
  .fallback {
    margin-top: var(--space-4);
  }
  .fallback-empty {
    color: var(--text-3);
    font-size: var(--text-sm);
    margin: 0.5rem 0;
  }
  .fallback-list {
    list-style: none;
    margin: var(--space-3) 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .fallback-item {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--neutral-soft);
    padding: 0.4rem 0.6rem;
  }
  .rank {
    font-weight: 700;
    color: var(--text-3);
    min-width: 1.2rem;
    text-align: center;
  }
  .fallback-name {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .fallback-actions {
    display: flex;
    gap: 0.25rem;
  }
  .fallback-add,
  .fallback-save {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-top: var(--space-3);
    flex-wrap: wrap;
  }
  .fallback-add select {
    max-width: 22rem;
    font-size: var(--text-sm);
  }
  .ok-note {
    color: var(--ok);
    font-size: var(--text-sm);
  }
  .advisor {
    margin-top: var(--space-4);
  }
  .advisor .sub {
    margin-bottom: var(--space-3);
  }
  .advisor-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  /* BUG-82 — the advisor's readiness sits directly under its selector, in the
     same chip vocabulary a provider card uses, so the two models this runtime
     runs are reported the same way. */
  .advisor-readiness {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 0.6rem;
  }
  .advisor-model-name {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .advisor-row select {
    max-width: 22rem;
    font-size: var(--text-sm);
  }
  /* The four off-machine facts, read as a strip above the Hosted cards rather
     than as a card of their own on a tab of their own. */
  .gates {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: 0.5rem 1rem;
    margin: 0 0 var(--space-4);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
  }
  .gates dt {
    font-size: var(--text-xs);
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
  }
  .gates dd {
    margin: 0.1rem 0 0;
  }
  .sub {
    color: var(--text-3);
    font-size: var(--text-sm);
    margin: 0;
  }
  @media (max-width: 44rem) {
    .setup-overview,
    .global-model-card,
    .section-heading {
      align-items: flex-start;
      flex-direction: column;
    }
    .setup-meter {
      text-align: left;
      width: 100%;
    }
    .local-row {
      flex-direction: column;
    }
    /* These two cards sit above the tab strip so every panel can see readiness
       and change the default. Stacked on a phone that pushed the tabs below the
       fold, so the explanatory copy — which the headline and the labelled
       select already carry — is dropped rather than the controls. */
    .global-model-field small {
      display: none;
    }
    .setup-overview,
    .global-model-card {
      gap: 8px;
    }
  }
</style>
