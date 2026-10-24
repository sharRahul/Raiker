<script lang="ts">
  import { askConfirm } from "../confirm.svelte";
  import { onDestroy, onMount } from "svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ProviderLogo from "../components/ProviderLogo.svelte";
  import RowOverflow from "../components/RowOverflow.svelte";
  import AddDialog from "../components/AddDialog.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type {
    CodexSubscriptionStatus,
    ModelCapacitiesView,
    ModelDecision,
    ModelNextAction,
    ModelProfile,
    ModelsView as ModelsData,
    ProviderModelList,
  } from "../apiTypes";
  import { capabilityLabel } from "../capabilityModel";
  import { humanize, providerName, relativeTime, profileLabel } from "../format";
  import { formatCost, sourceNote, spendShares } from "../contextPresentation";
  import {
    providerErrorGuidance,
    unreachableProviderNote,
    type ProviderErrorGuidance,
  } from "../providerErrors";
  import { inferenceLocation } from "../inferenceLocation";
  import { modelName } from "../modelPresentation";
  import { readinessLabel, UNPINNED_MODEL } from "../modelReadinessLabels";
  import { isChoosableModel } from "../modelReadiness.svelte";
  import { installerRuntimeFor, openRuntimeInstaller } from "../runtimeInstall";
  import { detectionNotice, onReturnToApp } from "../returnAndDetect";
  import { setModels } from "../models.svelte";
  import {
    connectionRefusal,
    listCatalogue,
    refusedForWorkspace,
    removeConnection,
    saveConnection as storeConnection,
    type ConnectionRefusal,
  } from "../providerConnections";
  import { modelDecisions } from "../surfaceModel.svelte";
  import HuggingFacePanel from "./models/HuggingFacePanel.svelte";
  import ProvidersPanel from "./models/ProvidersPanel.svelte";
  import MyModels from "./models/MyModels.svelte";
  import ModelComparison from "./models/ModelComparison.svelte";
  import { brand } from "./models/providerBrands";
  import ModelDetailsDialog from "./models/ModelDetailsDialog.svelte";
  import RuntimeTab from "./models/RuntimeTab.svelte";
  import ModelPickerDialog from "./models/ModelPickerDialog.svelte";
  import ReadinessSteps from "./models/ReadinessSteps.svelte";

  // The shell owns a models snapshot for the topbar chip; it passes onchanged
  // so a selection here is reflected there without a full page reload.
  let {
    onchanged,
    tab = null,
    source = null,
    view = "page",
  }: {
    onchanged?: () => void;
    /** An old tab address; `add` opens Add model. */
    tab?: string | null;
    /** With `tab: "add"`, the source Add model opens on (`?source=`). */
    source?: string | null;
    /** `routing` draws only what is serving, for Settings › Advanced. */
    view?: "page" | "routing";
  } = $props();

  /*
   * QUI-L08 — one page, no tabs: the execution profile card, then My models.
   * Adding a model is a three-step dialog whose second step shows only the
   * source chosen in the first.
   */
  const ADD_SOURCES = [
    {
      id: "local",
      name: "On this computer",
      category: "Source",
      description: "A model this machine runs itself. Nothing you send leaves it.",
    },
    {
      id: "account",
      name: "An account I have",
      category: "Source",
      description: "Anthropic, OpenAI, Gemini or another provider, with your own key.",
    },
    {
      id: "huggingface",
      name: "Hugging Face",
      category: "Source",
      description: "Download an open model and run it on this computer.",
    },
    {
      id: "custom",
      name: "Custom endpoint",
      category: "Source",
      description: "A router such as OpenRouter, or a vLLM or home-lab server you control.",
    },
  ];
  const SOURCE_SECTIONS: Record<string, readonly ("Local" | "Hosted" | "Advanced")[]> = {
    local: ["Local"],
    account: ["Hosted"],
    custom: ["Advanced"],
  };
  let adding = $state(false);
  let addSource = $state<string | null>(null);
  let changing = $state(false);
  const visibleSections = $derived(addSource === null ? [] : (SOURCE_SECTIONS[addSource] ?? []));

  function openAdd(source: string | null) {
    addSource = source;
    adding = true;
  }
  function closeAdd() {
    adding = false;
    addSource = null;
    if (typeof window !== "undefined" && /[?&]tab=/.test(window.location.hash)) {
      history.replaceState(history.state, "", "#/models");
    }
    void load();
  }

  let models = $state<ModelsData | null>(null);
  // An old address that named the Add tab, or the Hugging Face one, opens the
  // dialog on that step.
  const SERVING_TABS = ["runtime", "routing", "library", "downloads", "activity"];
  const USAGE_TABS = ["usage", "pricing"];
  function applyRequestedTab(requested: string | null) {
    if (requested === null) return;
    // What serves models and what they cost moved to Settings › Advanced.
    if (SERVING_TABS.includes(requested)) {
      window.location.replace("#/settings?tab=advanced&kind=models");
    } else if (USAGE_TABS.includes(requested)) {
      window.location.replace("#/settings?tab=advanced&kind=usage");
    } else if (requested === "add" || requested === "posture") openAdd(requestedSource());
    else if (requested === "huggingface" || requested === "discover") openAdd("huggingface");
  }
  /** `?source=` on an Add model link, when it names one of the four. */
  function requestedSource(): string | null {
    const named =
      source ??
      (typeof window === "undefined"
        ? null
        : new URLSearchParams(window.location.hash.split("?", 2)[1] ?? "").get("source"));
    return ADD_SOURCES.some((item) => item.id === named) ? named : null;
  }
  function tabInHash(): string | null {
    if (typeof window === "undefined" || !/^#\/models(?:[?/]|$)/.test(window.location.hash)) return null;
    return new URLSearchParams(window.location.hash.split("?", 2)[1] ?? "").get("tab");
  }
  $effect(() => {
    if (view !== "page") return;
    applyRequestedTab(tab ?? tabInHash());
    const onHash = () => applyRequestedTab(tabInHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  });
  /**
   * Every surface's decision, read once for the whole page.
   *
   * The inventory needs it to say which rows are a Work default and whether a
   * local one is serving. Assembling that from the profile list would be the
   * page computing its own answer again, which is the thing the contract
   * exists to stop.
   */
  let decisions = $state<Record<string, ModelDecision> | null>(null);
  /**
   * UX-MODEL-02 — Chat's model decision, said as four steps and one next action
   * on the profile card while any step is not done. "Check it now" runs the
   * exact-pair check here; every other action opens what owns the fix.
   */
  const chatDecision = $derived(decisions?.chat ?? null);
  const showReadiness = $derived(
    chatDecision !== null &&
      (chatDecision.steps ?? []).length > 0 &&
      (!chatDecision.ready || chatDecision.next_action !== null),
  );
  let checkingReadiness = $state(false);
  let readinessNotice = $state<string | null>(null);
  async function takeReadinessAction(action: ModelNextAction) {
    if (action.target === "permissions") {
      window.location.hash = "#/capabilities";
      return;
    }
    if (action.target === "runtime") {
      window.location.hash = "#/settings?tab=advanced&kind=models";
      return;
    }
    if (action.target !== "check") {
      openAdd(null);
      return;
    }
    if (chatDecision === null || !chatDecision.selected.profile_id) return;
    checkingReadiness = true;
    readinessNotice = null;
    try {
      await api.checkModelReadiness(chatDecision.selected.profile_id, chatDecision.selected.model);
    } catch {
      readinessNotice = "The check could not be started. Nothing was changed.";
    } finally {
      decisions = await modelDecisions();
      checkingReadiness = false;
    }
  }

  let loadError = $state<string | null>(null);
  let capacities = $state<ModelCapacitiesView | null>(null);
  let capacityRefreshAttempted = false;
  let catalogueRefreshing = $state(false);
  let catalogueNotice = $state<string | null>(null);
  let codexSubscriptionStatus = $state<
    CodexSubscriptionStatus["connection_status"] | "login_pending"
  >("signed_out");
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

  /** Counts full reads, so a panel holding an edit can tell a reload from a re-read. */
  let loadRevision = $state(0);

  async function load() {
    loadError = null;
    // Never fatal: the page is readable without the per-surface decisions, and
    // a status read that fails must not take the model list down with it.
    void modelDecisions().then((answer) => (decisions = answer));
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
      // A full read resets what Advanced routing is editing; the quiet
      // re-read below does not, so a half-made sequence survives it.
      loadRevision += 1;
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
  /** Named endpoints: the owner's own name for a custom endpoint. */
  let signInLabel = $state("");
  /** Credential pools: backup keys tried when the primary is throttled or spent. */
  let signInBackupKeys = $state<string[]>(["", "", ""]);
  let signInRemoveBackups = $state(false);
  // Connect with the key already in this provider's environment variable. The
  // server reports only the variable's name; the value never reaches the page.
  let signInUseEnvironment = $state(false);
  // BUG-349 (D3) — dial a link-local answer for this custom endpoint. Off by
  // default and prefilled from the saved connection, so re-saving keeps it.
  let signInAllowLinkLocal = $state(false);
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
  /** UX-MODEL-04 — My models as the inventory list or as a comparison. */
  let modelsLayout = $state<"list" | "compare">("list");
  let detailsFor = $state<ModelProfile | null>(null);
  // Governed refusals are policy outcomes, not faults. Hold the reason code so
  // the dialog can render the control that unblocks it instead of a bare code.
  let signInGuidance = $state<ProviderErrorGuidance | null>(null);

  const signInProfile = $derived(
    models?.profiles.find((p) => p.profile_id === signInFor) ?? null,
  );

  function openSignIn(profileId: string, options: { advanced?: boolean } = {}) {
    signInFor = profileId;
    signInApiKey = "";
    signInAdminApiKey = "";
    signInWorkspaceId = "";
    signInEndpoint = "";
    signInLabel = models?.profiles.find((p) => p.profile_id === profileId)?.connection_label ?? "";
    signInBackupKeys = ["", "", ""];
    signInRemoveBackups = false;
    signInUseEnvironment = false;
    signInAllowLinkLocal =
      models?.profiles.find((p) => p.profile_id === profileId)?.allows_link_local === true;
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
      const outcome = await storeConnection(profileId, {
        endpoint: signInEndpoint,
        apiKey: signInApiKey,
        adminApiKey: signInAdminApiKey,
        workspaceId: signInWorkspaceId,
        label: signInLabel,
        useEnvironmentCredential: signInUseEnvironment,
        allowLinkLocal: signInAllowLinkLocal,
        backupApiKeys: signInRemoveBackups
          ? []
          : signInBackupKeys.some((key) => key.trim())
            ? signInBackupKeys.filter((key) => key.trim())
            : null,
      });
      if (!outcome.ok) throw outcome;
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
      // BUG-319 — the refusal is read the way setup reads it.
      const refusal = isConnectionRefusal(e) ? e : connectionRefusal(e);
      signInGuidance = refusal.guidance;
      // BUG-274 — the remediation names a field, so open the section holding
      // it. An answer that says "add the workspace ID" while the box is folded
      // away is the same dead end the old copy was.
      if (refusal.workspaceRefused) signInAdvanced = true;
      signInError =
        signInGuidance !== null
          ? null
          : refusal.status !== null
            ? `Could not connect (${refusal.status}${refusal.reasonCode ? `: ${refusal.reasonCode}` : ""})`
            : "Could not connect";
    } finally {
      signInSaving = false;
    }
  }

  async function disconnectConnection(profile: ModelProfile) {
    const id = profile.profile_id;
    const name = providerName(profile.provider);
    if (
      !(await askConfirm({
        title: `Disconnect ${name}?`,
        body: "The encrypted credential and custom endpoint stored for this provider will be removed from this Raiker instance.",
        confirmLabel: "Disconnect",
        danger: true,
      }))
    )
      return;
    disconnecting = { ...disconnecting, [id]: true };
    testResults = without(testResults, id);
    try {
      if (!(await removeConnection(id)).ok) {
        testResults = {
          ...testResults,
          [id]: `Could not disconnect ${name}. The saved credential was left unchanged.`,
        };
        return;
      }
      await load();
      testResults = { ...testResults, [id]: `${name} connection removed.` };
      onchanged?.();
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
      case "policy_denied": {
        // BUG-349 — a denial is not always the gate. A refused address or a
        // connection bound to another origin has its own repair, and "enable
        // its gate" sent the owner to a control that was already on.
        const denied = providerErrorGuidance(list.reason_code);
        if (denied !== null) return `${name}: ${denied.message} ${denied.fix}`;
        return `${name}'s model list was denied by provider policy — enable its gate first.`;
      }
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
        // BUG-289 — the remedy depends on the kind of destination: a hosted
        // provider this host cannot reach is not a runtime to start.
        return unreachableProviderNote(name, profile.off_machine);
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
      // owner ran it is theirs to say — and the rule here is that Raiker should ask
      // itself rather than asking them to press Look again.
      installNotice = `Opened the official ${providerName(provider)} download. Install it and come back — Raiker will look again.`;
      armReturnDetect(providerName(provider));
    } catch {
      installNotice = `Could not open the ${providerName(provider)} download.`;
    } finally {
      installing = null;
    }
  }

  /**
   * Re-run detection the moment the owner comes back.
   *
   * One shot, cancelled on unmount, and honest about the outcome: it reports
   * what detection *found*, so a tab regaining focus can never be mistaken for
   * an install that happened.
   */
  let cancelReturnDetect: (() => void) | null = null;

  function armReturnDetect(vendor: string) {
    cancelReturnDetect?.();
    cancelReturnDetect = onReturnToApp(() => {
      cancelReturnDetect = null;
      void (async () => {
        detecting = true;
        try {
          const result = await api.detectLocalRuntimes();
          await load();
          installNotice = detectionNotice({
            vendor,
            detected: result.runtimes.some((row) => row.present),
          });
        } catch {
          // A failed look leaves the last answer standing rather than replacing
          // it with a claim this call did not establish.
        } finally {
          detecting = false;
        }
      })();
    });
  }

  onDestroy(() => cancelReturnDetect?.());

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
      const outcome = await listCatalogue(id);
      if (outcome.ok) {
        message = testNote(profile, outcome.list);
        noteWorkspaceRefusal(id, outcome.list.reason_code);
      } else {
        message =
          outcome.status === 429
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
    if (refusedForWorkspace(reasonCode))
      workspaceRefused = { ...workspaceRefused, [profileId]: true };
  }

  function isConnectionRefusal(value: unknown): value is ConnectionRefusal {
    return typeof value === "object" && value !== null && (value as { ok?: unknown }).ok === false;
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
      const outcome = await listCatalogue(profileId);
      pickerList = outcome.ok ? normalizePickerList(outcome.list) : null; // manual entry still works
      // The same governed code the Test button reads. Opening the picker is how
      // most owners meet this refusal, so it has to offer the field that fixes
      // it too — otherwise the answer depends on which button you pressed.
      noteWorkspaceRefusal(profileId, outcome.ok ? pickerList?.reason_code : outcome.reasonCode);
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

  type RoutingSort = "" | "price" | "throughput" | "latency";
  let routingBusy = $state(false);
  let routingNote = $state("");
  /** Save OpenRouter routing preferences; they apply from the next request. */
  async function saveRouting(profile: ModelProfile, dataCollection: "" | "deny", sort: RoutingSort) {
    routingBusy = true;
    routingNote = "";
    try {
      await api.setModelRouting(profile.profile_id, dataCollection, sort);
      routingNote =
        dataCollection === "deny"
          ? "Saved. Requests go only to providers that do not store prompts; some free models may then have none."
          : "Saved. It applies from the next request.";
      await load();
    } catch (e) {
      routingNote =
        e instanceof ApiError
          ? `Could not save routing (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not save routing";
    } finally {
      routingBusy = false;
    }
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

  // FIXED-160 — the runtime's own request limiter is not a broken page, and
  // "could not check" tells an owner neither what happened nor that it clears by
  // itself. Every check on this page says so in the same words.
  const THROTTLED =
    "Too many requests in the last minute. Raiker throttled this check; wait a moment and try again.";
  const throttled = (e: unknown) => e instanceof ApiError && e.status === 429;

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
  /** The model the global default names, for the profile card. */
  const inForce = $derived(globalChoices.find((profile) => profile.selected) ?? null);
  /**
   * What the owner has: a connected account, the model in force, or a model
   * this machine can run. The rest of the registry is what *could* be added,
   * which is the Add model dialog's job.
   */
  const ownedProfiles = $derived(
    (models?.profiles ?? []).filter(
      (p) =>
        p.selected ||
        p.connection_configured ||
        (!p.off_machine && p.model !== UNPINNED_MODEL && isChoosableModel(p)),
    ),
  );
  /**
   * Step 3 of Add model: what the chosen source now has set up — each model
   * the owner keeps offered there (`chat_profiles`), or the connection itself
   * while no model is chosen yet.
   */
  const reviewProfiles = $derived.by(() => {
    if (addSource === null || addSource === "huggingface") return [];
    const inSource = (p: ModelProfile) => visibleSections.includes(sectionFor(p));
    const offered = (models?.chat_profiles ?? []).filter(inSource);
    const connected = configuredProfiles.filter(
      (p) => inSource(p) && !offered.some((pair) => pair.profile_id === p.profile_id),
    );
    return [...offered, ...connected];
  });

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
      profile.requires_egress_policy ? "Needs your connection" : "",
      profile.runtime_gate ? capabilityLabel(profile.runtime_gate) : "",
      profile.prompt_cache_ttl ? `Cache ${profile.prompt_cache_ttl}` : "",
      // BUG-349 (D4) — which route an off-machine request takes. A proxy is the
      // owner's own environment; a home-lab endpoint is always dialled directly.
      profile.off_machine
        ? profile.proxy_route
          ? `Through your proxy (${profile.proxy_route})`
          : "Direct connection"
        : "",
    ].filter((part) => part !== "");
    return parts.join(" · ");
  }

  /** BUG-349 (D4) — "No", or which proxy carries how many off-machine profiles. */
  const proxyPosture = $derived.by(() => {
    const proxied = (models?.profiles ?? []).filter((p) => p.off_machine && p.proxy_route);
    if (proxied.length === 0) return "No — off-machine requests are dialled directly";
    const routes = [...new Set(proxied.map((p) => p.proxy_route))].join(", ");
    return `Yes — ${proxied.length} hosted profile${proxied.length === 1 ? "" : "s"} via ${routes}`;
  });

  function usesCloudInference(profile: ModelProfile): boolean {
    // BUG-340 — the running service's own answer (`remote_host`), with the
    // model's Cloud name as the fallback; one rule for every surface.
    return profile.local_only && inferenceLocation(profile, profile.model).kind === "remote";
  }

  function usageLine(profile: ModelProfile): string {
    if (usesCloudInference(profile)) return "Provider pricing may apply";
    if (!profile.billable) return "No API cost — runs on this machine";
    const used = profile.models_used ?? 0;
    if (used === 0) return "Not used yet";
    const turns = profile.turns_used ?? 0;
    return `${used} model${used === 1 ? "" : "s"} used · ${turns} turn${turns === 1 ? "" : "s"}`;
  }
  /**
   * Named custom endpoints. Raiker ships four OpenAI-compatible
   * slots; the first is always offered, the rest only once set up or asked for,
   * so four identical empty cards never stand in for one choice.
   */
  let revealedEndpoints = $state<string[]>([]);
  const customEndpoints = $derived(
    (models?.profiles ?? []).filter((profile) => profile.provider === "openai-compatible"),
  );
  function endpointShown(profile: ModelProfile): boolean {
    if (profile.provider !== "openai-compatible") return true;
    return (
      customEndpoints[0]?.profile_id === profile.profile_id ||
      profile.connection_configured ||
      profile.selected ||
      revealedEndpoints.includes(profile.profile_id)
    );
  }
  const nextEndpoint = $derived(customEndpoints.find((profile) => !endpointShown(profile)) ?? null);
  function addEndpoint() {
    if (nextEndpoint === null) return;
    // Read once: revealing this slot recomputes `nextEndpoint` to the one after.
    const profileId = nextEndpoint.profile_id;
    revealedEndpoints = [...revealedEndpoints, profileId];
    openSignIn(profileId);
  }
  function profilesFor(section: "Local" | "Hosted" | "Advanced") {
    return (models?.profiles ?? []).filter(
      (profile) => sectionFor(profile) === section && endpointShown(profile),
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

  /**
   * Escape closes whichever of this page's three modals is open, as it does
   * every other dialog in the product. Innermost first, so Escape
   * unwinds one layer at a time rather than clearing the stack: the picker can
   * be opened from the details panel, and closing both at once would lose the
   * owner's place.
   */
  $effect(() => {
    if (pickerFor === null && signInFor === null && detailsFor === null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      if (pickerFor !== null) closePicker();
      else if (signInFor !== null) closeSignIn();
      else detailsFor = null;
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  onMount(load);

  /**
   * Owner decision, 2026-10-04 — Raiker re-checks a model chosen on a local
   * service it can ask (Ollama) on every host tick. An open page reads that
   * answer again so *Ready* never outlives the service it describes.
   *
   * Quiet on purpose: no loading state and no reset of anything being edited.
   * It skips a hidden tab, an open picker or details dialog and a selection in
   * flight, and only runs while some profile is a watched one — a page with no
   * local service to follow has nothing to re-read. Two reads every fifteen
   * seconds stay far inside the host's per-minute request budget.
   */
  const WATCH_INTERVAL_MS = 15_000;
  async function rereadQuietly() {
    if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
    if (pickerFor !== null || detailsFor !== null || selecting) return;
    if (!models?.profiles.some((profile) => typeof profile.provider_running === "boolean")) return;
    try {
      const fresh = await api.models();
      models = fresh;
      setModels(fresh);
      void modelDecisions().then((answer) => (decisions = answer));
    } catch {
      // The last answer stands; the next tick asks again.
    }
  }
  onMount(() => {
    const timer = window.setInterval(() => void rereadQuietly(), WATCH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  });
</script>

{#if view === "routing"}
  <!-- QUI-L08 — what is serving and what a turn falls back to, now in
       Settings › Advanced. The same component, with this page's data. -->
  {#if loadError}
    <PageState state="error" title="Couldn't load models" detail={loadError} />
  {:else if models === null}
    <PageState state="loading" title="Loading models…" />
  {:else}
    <RuntimeTab
      {models}
      revision={loadRevision}
      onreload={load}
      gguf={frameworkProfiles("llama.cpp")}
      mlx={frameworkProfiles("mlx")}
      {testing}
      {testResults}
      {selecting}
      ontest={(profile) => void testConnection(profile)}
      ondetails={(profile) => (detailsFor = profile)}
      onselect={(profile) => void select(profile.profile_id, profile.model)}
    />
  {/if}
{:else}
<div class="head-row">
  <GuideLink route="models" />
  <div class="head-actions">
    <button
      type="button"
      class="btn btn-ghost btn-sm"
      onclick={() => void refreshProviderCatalogues()}
      disabled={catalogueRefreshing}
      aria-label="Refresh connected providers"
    >
      <Icon name="refresh" size="sm" />
      {catalogueRefreshing ? "Refreshing…" : "Refresh"}
    </button>
    <button type="button" class="btn btn-primary btn-sm" onclick={() => openAdd(null)}>
      <Icon name="plus" size="sm" /> Add model
    </button>
  </div>
</div>
{#if catalogueNotice}<p class="catalogue-notice" role="status">{catalogueNotice}</p>{/if}

{#if loadError}
  <PageState state="error" title="Couldn't load models" detail={loadError} />
{:else if models === null}
  <PageState state="loading" title="Loading models…" />
{:else}
  <!-- While Add model is open the page behind it is out of reach, for a
       screen reader as much as for a pointer. -->
  <div class="models-page" inert={adding} aria-hidden={adding ? "true" : undefined}>
  <!-- QUI-L08 — the execution profile in one card: the model in force, whether
       it is ready, where it runs and what that means for privacy and cost, and
       Change. It replaces the Model setup and Global model cards that stood
       above every tab. -->
  <section class="profile-card card" aria-labelledby="profile-card-title">
    <div class="profile-main">
      {#if inForce !== null}
        <ProviderLogo provider={inForce.provider} size={36} />
        <div class="profile-copy">
          <p class="eyebrow">Model in use</p>
          <h2 id="profile-card-title">{modelName(inForce.model)}</h2>
          <p class="profile-facts">
            <span>{providerName(inForce.provider)}</span>
            <span>{isChoosableModel(inForce) ? (readinessLabel(inForce.readiness_state) ?? "Set up") : "Not ready"}</span>
            <span>{inForce.off_machine ? `Sent to ${providerName(inForce.provider)}` : "Stays on this computer"}</span>
          </p>
          <p class="profile-tradeoff">
            {inForce.off_machine
              ? `What you send leaves this computer and ${providerName(inForce.provider)} bills each request to your account.`
              : "Nothing you send leaves this computer, and there is no API cost."}
            {#if totalSpend > 0}
              {formatCost(String(totalSpend), spendCurrency)} spent so far.
            {/if}
          </p>
          {#if showReadiness && chatDecision !== null}
            <div class="profile-readiness">
              <ReadinessSteps
                steps={chatDecision.steps}
                action={chatDecision.next_action}
                busy={checkingReadiness}
                label="Chat readiness"
                onaction={(action) => void takeReadinessAction(action)}
              />
              {#if readinessNotice}<p class="error" role="alert">{readinessNotice}</p>{/if}
            </div>
          {/if}
        </div>
      {:else}
        <div class="profile-copy">
          <p class="eyebrow">Model in use</p>
          <h2 id="profile-card-title">No default model is chosen</h2>
          <p class="profile-tradeoff">
            Chat and Build need a model before they can answer. Add one that runs on this computer
            or connect an account you have.
          </p>
          {#if showReadiness && chatDecision !== null}
            <div class="profile-readiness">
              <ReadinessSteps
                steps={chatDecision.steps}
                action={chatDecision.next_action}
                busy={checkingReadiness}
                label="Chat readiness"
                onaction={(action) => void takeReadinessAction(action)}
              />
              {#if readinessNotice}<p class="error" role="alert">{readinessNotice}</p>{/if}
            </div>
          {/if}
        </div>
      {/if}
    </div>
    <div class="profile-actions">
      {#if changing}
        <label class="global-model-field">
          <span class="sr-only">Global model</span>
          <select
            aria-label="Global model"
            value={globalChoice}
            onchange={(event) => {
              changing = false;
              void selectGlobal(event.currentTarget.value);
            }}
            disabled={selecting}
          >
            <option value="" disabled>Choose a model</option>
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
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => (changing = false)}>Cancel</button>
      {:else if globalChoices.length > 0}
        <button type="button" class="btn btn-sm" onclick={() => (changing = true)}>Change</button>
      {:else if !showReadiness}
        <button type="button" class="btn btn-primary btn-sm" onclick={() => openAdd(null)}>Add model</button>
      {/if}
    </div>
  </section>
  {#if selectError && pickerFor === null}
    <p class="error" role="alert">{selectError}</p>
  {/if}

  <section class="my-models" aria-labelledby="my-models-title">
    <div class="lead-row">
      <h2 id="my-models-title">My models</h2>
      <!-- UX-MODEL-04 — the same models as a comparison. -->
      <div class="segmented" role="group" aria-label="Show models as">
        <button type="button" class="segment" aria-pressed={modelsLayout === "list"} onclick={() => (modelsLayout = "list")}>List</button>
        <button type="button" class="segment" aria-pressed={modelsLayout === "compare"} onclick={() => (modelsLayout = "compare")}>Compare</button>
      </div>
    </div>
    {#if modelsLayout === "compare"}
      <ModelComparison profiles={models.profiles} />
    {:else}
      <MyModels
        profiles={ownedProfiles}
        {decisions}
        busy={selecting}
        onuse={(profile) => void select(profile.profile_id, profile.model)}
        onstart={() => (window.location.hash = "#/settings?tab=advanced&kind=models")}
        ondetails={(profile) => (detailsFor = profile)}
        onadd={() => openAdd(null)}
        onchanged={() => void load()}
      />
    {/if}
  </section>
  </div>
{/if}

{#if adding && models !== null}
  <!-- QUI-L04 / QUI-L08 — Add model, in three steps: choose the source; then
       only that source; then review where data goes, what it costs, whether
       it is ready and whether it becomes the default. -->
  <AddDialog
    title="Add model"
    options={ADD_SOURCES}
    bind:chosen={addSource}
    searchLabel="Search ways to add a model"
    onclose={closeAdd}
  >
    {#snippet steps(option)}
      <p class="step-line" aria-label="Steps">
        <span>1 · Source</span><span aria-current="step">2 · {option.name}</span><span>3 · Review</span>
      </p>
      {#if option.id === "huggingface"}
        <HuggingFacePanel />
      {:else if models !== null}
        {#if option.id !== "local"}
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
            <dt>Connected off-machine providers</dt>
            <dd>
              <code
                >{models.profiles.filter((p) => p.off_machine && p.connection_configured).length}</code
              >
            </dd>
          </div>
          <div>
            <dt>Off-machine profiles</dt>
            <dd><code>{models.remote_profile_count}</code></dd>
          </div>
          <div>
            <!-- BUG-349 (D4) — whether hosted requests go through the owner's
                 proxy. Home-lab and local endpoints never do. -->
            <dt>Through your proxy</dt>
            <dd data-testid="proxy-posture">{proxyPosture}</dd>
          </div>
        </dl>
        {/if}
        {#if option.id === "local"}<ProvidersPanel onCatalogueChanged={refreshProviderCatalogues} />{/if}
      {#if models.profiles.length === 0}
        <div class="card">
          <!-- the empty-state rule/FIXED-436 — this said "Add profiles in
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
                    ? "Local endpoints. Cloud-tagged Ollama models may run off-device."
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
                          <h3>{profileLabel(p)}</h3>
                        </div>
                        <!-- The model line states a fact when there is one and
                             says nothing when there is not; "Select models…"
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
                        <!-- Owner decision, 2026-10-04 — a service Raiker can
                             ask over loopback (Ollama) says whether it is
                             running now, not only whether it is installed. A
                             running service with no model chosen is the one
                             state that needs the owner, and the row's primary
                             action below says so. -->
                        {#if p.provider_running === true}
                          <p class="posture-line runtime-running" data-testid="runtime-running">
                            <Icon name="check" size="sm" />
                            {namesAModel(p)
                              ? "Running on this device. Raiker checks it and this model on its own."
                              : "Running on this device. Choose one of its models."}
                          </p>
                        {:else if p.provider_running === false && (p.provider_detected === true || namesAModel(p))}
                          <!-- A model already chosen here is the owner's evidence
                               that the service exists, whatever the PATH says
                               (the Ollama desktop app is not on it): stopped,
                               not missing. -->
                          <p class="posture-line runtime-missing" data-testid="runtime-stopped">
                            <Icon name="warning" size="sm" />
                            {p.provider_detected === true ? "Installed, but not running." : "Not running on this device."}
                            Start {providerName(p.provider)} and Raiker will notice.
                          </p>
                        {/if}
                        {#if p.provider_detected === false && !(p.provider_running === false && namesAModel(p))}
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
                            >{usesCloudInference(p) ? "Local endpoint" : endpointLabel(p.endpoint_kind)}</span
                          >
                          {#if usesCloudInference(p)}<span class="chip chip-warn">Cloud inference</span>{/if}
                          {#if p.local_only && !usesCloudInference(p)}<span class="chip chip-ok"
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
                      <!-- One visible action, and it is whichever
                           one this row's state actually calls for: name a model
                           when none is named, put it in force when one is, and
                           nothing at all when it already is. Test and Details
                           are troubleshooting, which is what an overflow is
                           for. -->
                      <div class="row-actions">
                        {#if p.model === "<model>"}
                          <button
                            type="button"
                            class="btn btn-sm"
                            class:btn-primary={p.provider_running === true}
                            onclick={() => void openPicker(p.profile_id)}
                            aria-expanded={pickerFor === p.profile_id}
                            >{p.provider_running === true ? "Choose a model" : "Select models…"}</button
                          >
                        {:else if !p.selected}
                          <button
                            type="button"
                            class="btn btn-sm"
                            onclick={() => void select(p.profile_id, p.model)}
                            disabled={selecting}>Select</button
                          >
                        {/if}
                        <RowOverflow
                          label={profileLabel(p)}
                          items={[
                            ...(p.model === "<model>"
                              ? []
                              : [{ label: "Select models…", run: () => void openPicker(p.profile_id) }]),
                            {
                              label: testing[p.profile_id] === true ? "Testing…" : "Test connection",
                              run: () => void testConnection(p),
                              disabled: testing[p.profile_id] === true,
                            },
                            { label: "Details", run: () => (detailsFor = p) },
                          ]}
                        />
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
                          <h3>{profileLabel(p)}</h3>
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
                        {:else if p.model === "<model>"}
                          <!-- Connected, no model named yet: naming one is the
                               only thing left to do here. -->
                          <button
                            type="button"
                            class="btn btn-sm"
                            onclick={() => void openPicker(p.profile_id)}
                            aria-expanded={pickerFor === p.profile_id}
                            >Select models…</button
                          >
                        {:else if !p.selected}
                          <button
                            type="button"
                            class="btn btn-sm"
                            onclick={() => void select(p.profile_id, p.model)}
                            disabled={selecting}>Select</button
                          >
                        {/if}
                        <!-- A connected provider used to
                             carry Test, Select models, Select and Details at
                             once, permanently, on every card. Test is
                             troubleshooting: it belongs where you go when
                             something is wrong, not as a standing invitation to
                             re-prove a connection that is working. BUG-208
                             slice E already moved Reconnect and Disconnect into
                             Details for the same reason. -->
                        <RowOverflow
                          label={profileLabel(p)}
                          items={[
                            // Everywhere it is not already the visible primary.
                            // Browsing what a provider serves is how an owner
                            // decides whether to keep the connection at all, so
                            // it must not depend on having one.
                            ...(p.connection_configured && p.model === "<model>"
                              ? []
                              : [{ label: "Select models…", run: () => void openPicker(p.profile_id) }]),
                            ...(p.connection_configured
                              ? [
                                  {
                                    label:
                                      testing[p.profile_id] === true
                                        ? "Testing…"
                                        : "Test connection",
                                    run: () => void testConnection(p),
                                    disabled: testing[p.profile_id] === true,
                                  },
                                ]
                              : []),
                            { label: "Details", run: () => (detailsFor = p) },
                          ]}
                        />
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
                      {#if (p.backup_key_count ?? 0) > 0}
                        <p class="pool-line" role="status">
                          {p.key_pool_status ||
                            `${p.backup_key_count} backup key${p.backup_key_count === 1 ? "" : "s"} ready for rate limits and empty quota.`}
                        </p>
                      {/if}
                      {#if p.provider === "openrouter" && p.connection_configured}
                        <!-- OpenRouter routing, as two owner choices.
                             Nothing is denied by default: denying data collection
                             leaves some free models with no provider at all. -->
                        <fieldset class="pc-routing" aria-label="OpenRouter routing">
                          <label class="pc-routing-check">
                            <input
                              type="checkbox"
                              checked={p.routing_data_collection === "deny"}
                              disabled={routingBusy}
                              onchange={(e) =>
                                void saveRouting(p, e.currentTarget.checked ? "deny" : "", p.routing_sort as RoutingSort)}
                            />
                            Only providers that do not store prompts
                          </label>
                          <label class="pc-routing-sort">
                            <span>Prefer</span>
                            <select
                              value={p.routing_sort}
                              disabled={routingBusy}
                              onchange={(e) =>
                                void saveRouting(
                                  p,
                                  p.routing_data_collection === "deny" ? "deny" : "",
                                  e.currentTarget.value as RoutingSort,
                                )}
                            >
                              <option value="">OpenRouter's default</option>
                              <option value="price">Lowest price</option>
                              <option value="throughput">Highest throughput</option>
                              <option value="latency">Lowest latency</option>
                            </select>
                          </label>
                          {#if routingNote}<p class="pc-routing-note" role="status">{routingNote}</p>{/if}
                        </fieldset>
                      {/if}
                      {#if isCodexSubscription(p) && codexSubscriptionNotice}
                        <p class="test-result" role="status">{codexSubscriptionNotice}</p>
                      {/if}

                    </article>
                  {/each}
                </div>
                {#if section === "Advanced" && nextEndpoint !== null}
                  <!-- Named endpoints: one more server of your own
                       (vLLM, SGLang, a home-lab host), with its own name and key. -->
                  <button type="button" class="btn btn-ghost btn-sm add-endpoint" onclick={addEndpoint}
                    >+ Add another endpoint</button
                  >
                {/if}
              {/if}
            </section>
          {/if}
        {/each}

        {#if selectError && pickerFor === null}
          <p class="error" role="alert">{selectError}</p>
        {/if}
      {/if}
      {/if}
      {#if reviewProfiles.length > 0}
        <section class="add-review" aria-labelledby="add-review-title">
          <h3 id="add-review-title">3 · Review</h3>
          <ul>
            {#each reviewProfiles as profile (`${profile.profile_id}\u0000${profile.model}`)}
              <li>
                <span class="review-name">{profile.model && profile.model !== UNPINNED_MODEL ? modelName(profile.model) : providerName(profile.provider)}</span>
                <span>{profile.off_machine ? `Sent to ${providerName(profile.provider)}` : "Stays on this computer"}</span>
                <span>{profile.off_machine ? `Billed by ${providerName(profile.provider)}` : "No API cost"}</span>
                <span>{isChoosableModel(profile) ? (readinessLabel(profile.readiness_state) ?? "Set up") : "Not ready yet"}</span>
                {#if profile.selected}
                  <span class="review-default">Default</span>
                {:else if isChoosableModel(profile) && profile.model && profile.model !== UNPINNED_MODEL}
                  <button type="button" class="btn btn-sm" disabled={selecting} onclick={() => void select(profile.profile_id, profile.model)}>Make default</button>
                {/if}
              </li>
            {/each}
          </ul>
          {#if selectError}<p class="error" role="alert">{selectError}</p>{/if}
          <div class="review-actions">
            <button type="button" class="btn btn-primary" onclick={closeAdd}>Done</button>
          </div>
        </section>
      {/if}
    {/snippet}
  </AddDialog>
{/if}
{/if}

{#if detailsFor}
  <!-- The profile as last read, not as it was when Details opened: a saved
       override must show in the dialog that saved it. -->
  <ModelDetailsDialog
    profile={models?.profiles.find((p) => p.profile_id === detailsFor?.profile_id) ?? detailsFor}
    {capacities}
    disconnecting={disconnecting[detailsFor.profile_id] === true}
    onclose={() => (detailsFor = null)}
    onreconnect={(profile) => openSignIn(profile.profile_id)}
    ondisconnect={(profile) => void disconnectConnection(profile)}
    onchanged={load}
  />
{/if}

<!-- Choosing a model is a decision with a catalogue behind it, so it gets a
     dialog rather than an accordion inside a card. Inline, it pushed every
     other provider down the page and turned a six-model list into a scroll
     inside a scroll. -->
{#if pickerFor !== null && pickerProfile !== null}
  <ModelPickerDialog
    profile={pickerProfile}
    list={pickerList}
    loading={pickerLoading}
    chosen={availableModelsFor(pickerProfile.profile_id)}
    {selecting}
    {selectError}
    bind:choice={pickerChoice}
    onclose={closePicker}
    onuse={(model) => pickerFor && void select(pickerFor, model)}
    onsaved={() => void load()}
  />
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

      {#if signInProfile.provider === "openai-compatible"}
        <!-- A custom endpoint is its address first: name it, say where it is,
             then a key if the server wants one. -->
        <label class="field">
          <span class="field-label">Name <small>(optional — e.g. Home GPU)</small></span>
          <input class="input" type="text" maxlength="40" placeholder="OpenAI-compatible" bind:value={signInLabel} />
        </label>
        <label class="field">
          <span class="field-label">Endpoint</span>
          <input class="input" type="url" placeholder="http://127.0.0.1:8000/v1" bind:value={signInEndpoint} />
        </label>
        <!-- BUG-349 (D3) — a link-local address (169.254.x.x, fe80::) is refused
             unless the owner says this server is theirs, on a direct cable. A
             cloud metadata address is refused whatever this says. -->
        <label class="field env-credential">
          <input type="checkbox" bind:checked={signInAllowLinkLocal} data-testid="allow-link-local" />
          <span>
            Allow a link-local address
            <small>(169.254.x.x or fe80:: — only for a server you own on a direct cable)</small>
          </span>
        </label>
      {/if}

      {#if showApiKey && signInProfile.environment_credential_env}
        <label class="field env-credential">
          <input type="checkbox" bind:checked={signInUseEnvironment} />
          <span>
            Use the key from <code>{signInProfile.environment_credential_env}</code>
            <small>(already set where Raiker runs — it stays there)</small>
          </span>
        </label>
      {/if}

      {#if showApiKey && !signInUseEnvironment}
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
      {#if signInAdvanced && signInProfile.provider !== "openai-compatible"}
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
        {#if showApiKey}
          <!-- Credential pools: when the key above is rate
               limited or out of quota, the request moves to the next key. -->
          <fieldset class="field backup-keys">
            <legend class="field-label">Backup keys <small>(optional — tried in order when a key is rate limited or out of quota)</small></legend>
            {#each [0, 1, 2] as slot (slot)}
              <input
                class="input"
                type="password"
                autocomplete="new-password"
                aria-label={`Backup key ${slot + 1}`}
                placeholder={`Backup key ${slot + 1}`}
                bind:value={signInBackupKeys[slot]}
              />
            {/each}
            {#if (signInProfile.backup_key_count ?? 0) > 0}
              <label class="backup-remove">
                <input type="checkbox" bind:checked={signInRemoveBackups} />
                Remove the {signInProfile.backup_key_count} saved backup key{signInProfile.backup_key_count === 1 ? "" : "s"}
              </label>
            {/if}
          </fieldset>
        {/if}
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
              signInLabel.trim() === "" &&
              !signInBackupKeys.some((key) => key.trim()) &&
              !signInRemoveBackups &&
              !signInUseEnvironment &&
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
      <!-- The key is stored only here, and it is *sent* — to this provider,
           with each request. "Never leaves this device" was not true. -->
      <p class="signin-foot">
        Your key is encrypted in this instance’s vault and is sent only to
        {signInProfile ? providerName(signInProfile.provider) : "this provider"}, with each request.
      </p>
    </div>
  </div>
{/if}

<style>
  .head-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  /* QUI-L08 — the execution profile card. */
  .profile-card {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
  }
  .profile-main {
    display: flex;
    gap: var(--space-3);
    min-width: 0;
  }
  .profile-copy h2 {
    margin: 0.1rem 0 0;
    font-size: var(--text-xl);
    overflow-wrap: anywhere;
  }
  .profile-facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0 var(--space-3);
    margin: var(--space-1) 0 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .profile-tradeoff {
    margin: var(--space-2) 0 0;
    color: var(--text-2);
    font-size: var(--text-sm);
    max-width: 44rem;
  }
  .profile-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
  }
  .my-models h2 {
    margin: 0;
    font-size: var(--text-md);
  }
  .step-line {
    display: flex;
    gap: var(--space-3);
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .step-line [aria-current="step"] {
    color: var(--text-1);
  }
  .add-review {
    display: grid;
    gap: var(--space-2);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
  }
  .add-review h3 {
    margin: 0;
    font-size: var(--text-sm);
  }
  .add-review ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  .add-review li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-1) var(--space-3);
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .review-name {
    color: var(--text-1);
    font-weight: 650;
  }
  .review-default {
    font-weight: 650;
  }
  .review-actions {
    display: flex;
    justify-content: flex-end;
  }
  

  .lead-row {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-2) var(--space-4);
  }

  
  .section-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
  }

  .global-model-field {
    display: grid;
    gap: 0.3rem;
    min-width: min(100%, 22rem);
    font-weight: 650;
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
  .section-heading h2{
    margin: 0;
    font-size: var(--text-base);
  }
  .section-heading > p {
    max-width: 28rem;
    color: var(--text-3);
    font-size: var(--text-sm);
    margin: 0;
  }

  .profile-readiness {
    margin-top: var(--space-3);
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
  .runtime-running {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    color: var(--ok, var(--text-2));
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
    z-index: var(--z-scrim);
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

  /* The picker's and the sign-in dialog's close control. */
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
  @media (max-width: 44rem) {
    
    .section-heading {
      align-items: flex-start;
      flex-direction: column;
    }

    .local-row {
      flex-direction: column;
    }

  }
  .pc-routing { border: 1px solid var(--border); border-radius: var(--r-md); padding: .55rem .7rem; margin: .5rem 0 0; display: grid; gap: .45rem; font-size: var(--text-sm); }
  .pc-routing-check { display: flex; align-items: center; gap: .45rem; }
  .pc-routing-sort { display: flex; align-items: center; gap: .5rem; }
  .pc-routing-sort select { flex: 1; min-width: 0; }
  .pc-routing-note { margin: 0; color: var(--text-3); font-size: var(--text-xs); }
  .add-endpoint { margin-top: .6rem; }
  .backup-keys { border: 0; padding: 0; margin: 0; display: grid; gap: .4rem; }
  .backup-remove { display: flex; align-items: center; gap: .4rem; font-size: var(--text-sm); }
  .env-credential { flex-direction: row; align-items: flex-start; gap: .5rem; font-size: var(--text-sm); color: var(--text-2); }
  .env-credential input { margin-top: .2rem; }
  .env-credential small { display: block; color: var(--text-3); font-size: var(--text-2xs); }
  .pool-line { margin: .4rem 0 0; color: var(--text-3); font-size: var(--text-xs); }
</style>
