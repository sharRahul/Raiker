import type {
  ConversionQuantization,
  ApprovalDetailView,
  HuggingFaceVariant,
  InterruptRequestBody,
  KnowledgeSourceKind,
  ManagedFileScope,
  ManagedFileUpload,
  MemoryControlView,
  ModelOperation,
  ModelSetupState,
  ProjectContext,
  PromptRequestBody,
  SetupState,
  SpeechRuntimeChange,
} from "./apiTypes";
import type { ApprovalMode } from "./approvalMode";
import { restoreSession } from "./api/auth";
import { request, requestBlob } from "./api/core";
// OPT-02 — every ordinary JSON operation's wrapper is generated
// (scripts/api_contract.py); streams, downloads and the few calls that shape a
// body stay written here.
import { contract } from "./generated/apiContract";
import type {
  CreateStandingGrantRequest,
  SettingsView,
  CreateTelemetryDestinationRequest,
  GenerateImageRequest,
  ModelPriceRequest,
  TaskCreateRequest,
} from "./generated/apiContract";

// The endpoint catalogue. Transport, sign-in and streaming live under ./api/;
// what they export is re-exported here, so a caller imports from one place.
export { ApiError, getToken, hasToken, setCsrfToken, setToken } from "./api/core";
export { connect, health, createInstance, restoreSession, auth } from "./api/auth";
export type { HealthView, LoginResult } from "./api/auth";
export { streamPrompt, streamResumeAfterApproval } from "./api/streaming";

export type { SettingsView };

/** One generated setter per decision mode; the route names the mode, not the body. */
const SET_DECISION_MODE = {
  ask: contract.askForCapability,
  allow: contract.allowCapability,
  auto: contract.autoCapability,
  deny: contract.denyCapability,
} as const;

export const api = {
  restoreSession,
  // ── The user guide, served from the install rather than a repository ──
  guide: () => contract.guideIndex(),
  guideSection: (slug: string) => contract.guideSection(slug),
  // ── Local-account settings, vault key, MFA status ──
  settings: () => contract.getSettings(),
  composerApprovalMode: () => contract.getComposerApprovalMode(),
  setComposerApprovalMode: (mode: ApprovalMode) =>
    contract.putComposerApprovalMode({ approval_mode: mode }),
  putSettings: (settings: Record<string, unknown>) => contract.putSettings({ settings }),
  // ── Dictation's runtime (BUG-256) ──
  // Reading contacts nothing. Probing contacts only the address the owner
  // typed. Transcribing sends one clip and gets one transcript back; the audio
  // is never written anywhere on either side of the call.
  speechRuntime: () => contract.readSpeechRuntime(),
  saveSpeechRuntime: (change: SpeechRuntimeChange) => contract.writeSpeechRuntime(change),
  probeSpeechRuntime: (change: SpeechRuntimeChange = {}) => contract.probeSpeechRuntime(change),
  transcribeSpeech: (clip: Blob, language?: string) =>
    request<{ text: string }>(
      language && language !== "auto"
        ? `/api/speech/transcribe?language=${encodeURIComponent(language)}`
        : "/api/speech/transcribe",
      {
        method: "POST",
        headers: { "Content-Type": clip.type || "audio/wav" },
        body: clip,
      },
    ),

  vaultStatus: () => contract.getVaultStatus(),
  setVaultKey: (key: string, mfaCode?: string) =>
    contract.setVaultKey({ key, mfa_code: mfaCode }),
  clearVaultKey: (mfaCode?: string) => contract.deleteVaultKey(mfaCode || undefined),

  // ── Read-only governed views ──
  sessionContextUsage: (sessionId: string) => contract.getSessionContextUsage(sessionId),
  // B6 — the agent's standing plan for one conversation, so a reload or a
  // second tab picks the checklist back up instead of starting blank.
  sessionPlan: (sessionId: string) => contract.getSessionPlan(sessionId),
  capabilityGates: () => contract.listCapabilityGates(),
  // One read for the whole contract: the catalogue, its
  // per-surface parity, and typed readiness. Every composer answers from this
  // rather than deriving a list of its own, which is the drift the contract
  // exists to remove.
  readCapabilities: () => contract.listReadCapabilities(),
  // The same bundle a model turn is given. Read rather than
  // recomputed, so a page and a turn cannot disagree about what time it is.
  environment: () => contract.getEnvironment(),
  capabilityGate: (capability: string) => contract.getCapabilityGate(capability),
  runtimeMode: () => contract.getRuntimeMode(),
  // ── Host lifecycle (BUG-40) ──
  // The menu-bar control's contract: what state the host is in, what background
  // work is in flight, and the four actions the distribution design requires.
  // Quit and Restart report waiting work first and only stop once confirmed.
  host: () => contract.getHost(),
  // BUG-251 — the host lists directory *names* so a field can offer Browse…
  // instead of asking the owner to spell an absolute path. Names only; nothing
  // here reads a file, and every approval path still governs what happens next.
  hostPaths: (path: string, files = false) =>
    contract.browseHostPaths(files ? { path, files } : { path }),
  pauseHost: (reason?: string) => contract.pauseHost({ reason: reason ?? null }),
  resumeHost: () => contract.resumeHost(),
  quitHost: (confirm = false) => contract.quitHost({ confirm }),
  restartHost: (confirm = false) => contract.restartHost({ confirm }),
  // ── Install provenance and the signed update channel (BUG-44) ──
  // The read is local only: opening the panel must never be a way to cause an
  // outbound request. The check is the one that asks, and only when the owner
  // has pinned a channel.
  hostUpdate: () => contract.getUpdateStatus(),
  checkHostUpdate: () => contract.checkUpdate(),
  applyHostUpdate: (confirm = false) => contract.applyUpdate({ confirm }),
  runtimeReadiness: () => contract.getRuntimeReadiness(),
  diagnostics: () => contract.getDiagnostics(),
  // MEM-09 — the memory integrity report, and its one stated repair. The scan
  // is read-only and starts when the owner asks for it; the rebuild is a
  // separate, named action over a projection that can lose nothing.
  memoryIntegrity: () => contract.memoryIntegrity(),
  rebuildConversationIndex: () => contract.rebuildConversationIndex(),
  // DEC-24 step 6 — every text index at once: the repair for one SQLite reports
  // as damaged, where a drifted count only needed the conversation rebuild.
  rebuildTextIndexes: () => contract.rebuildTextIndexes(),
  removeDamagedVectors: () => contract.removeDamagedVectors(),
  models: () => contract.getModels(),
  weeklyModelUsage: (refreshNative = false) =>
    contract.getWeeklyModelUsage(refreshNative ? { refresh_native: true } : {}),
  setWeeklyModelBudget: (profileId: string, tokenBudget: number | null) =>
    contract.setWeeklyModelBudget(profileId, { token_budget: tokenBudget }),
  modelReadiness: () => contract.listModelReadiness(),
  checkModelReadiness: (profile_id: string, model: string) =>
    contract.checkModelReadiness({ profile_id, model }),
  // BUG-270 — which local model runtimes are installed on this machine.
  // Detection is a PATH lookup cached in a row, so the read is free and this
  // POST is the owner saying "I just installed one, look again".
  detectLocalRuntimes: () => contract.detectLocalRuntimes(),
  // Where each work surface's model picker starts. A preference only: the turn
  // still names its exact profile and model, and readiness judges that pair.
  surfaceModels: () => contract.getSurfaceModels(),
  setSurfaceModel: (surface: string, profile_id: string, model: string) =>
    contract.setSurfaceModel({ surface, profile_id, model }),
  /**
   * Which model is selected here, and which one will actually run.
   *
   * Read by every surface that names a model. Before this, the Models page, the
   * composer picker, Chat, Build and Design each assembled their own answer
   * from the selection store, the surface defaults, readiness and the fallback
   * sequence — five correct facts that could not be made to agree.
   */
  modelDecision: (surface: string, projectId?: string) =>
    contract.getModelDecision({ surface, ...(projectId ? { project_id: projectId } : {}) }),
  /**
   * Every surface's decision in one read. The Models Overview answers "what
   * powers Chat, Build and Design" as its first fact; asking per surface would
   * be five separately-timed answers and a page that can show one row from
   * before a change beside one from after it.
   */
  modelDecisions: () => contract.getModelDecisions(),
  modelSetup: () => contract.getModelSetup(),
  updateModelSetup: (
    body: Omit<
      ModelSetupState,
      "owner_principal_id" | "created_at" | "updated_at"
    >,
  ) => contract.updateModelSetup(body),
  setup: () => contract.getSetup(),
  updateSetup: (
    body: Omit<SetupState, "owner_principal_id" | "privacy_acknowledged_at" | "backup_verified_at" | "created_at" | "updated_at">,
  ) => contract.updateSetup(body),
  createSetupBackup: (target: string) => contract.createSetupBackup({ target }),
  modelLibrary: () => contract.getModelLibrary(),
  addModelLibraryRoot: (path: string) => contract.addModelLibraryRoot({ path }),
  removeModelLibraryRoot: (path: string) => contract.removeModelLibraryRoot({ path }),
  rescanModelLibrary: () => contract.rescanModelLibrary(),
  deployLocalModel: (modelId: string, profileId?: string) =>
    contract.deployLocalModel(modelId, profileId ? { profile_id: profileId } : {}),
  deployMlxModel: (modelId: string, profileId?: string) =>
    contract.deployMlxModel(modelId, profileId ? { profile_id: profileId } : {}),
  modelOperations: () => contract.listModelOperations(),
  previewModelOperation: (kind: ModelOperation["kind"], target: string) =>
    contract.previewModelOperation({ kind, target, confirmed: false }),
  pullOllamaModel: (model: string) => contract.pullOllamaModel({ model, confirmed: true }),
  cancelModelOperation: (operationId: string) => contract.cancelModelOperation(operationId),
  retryModelOperation: (operationId: string) => contract.retryModelOperation(operationId),
  partialFiles: (operationId: string) => contract.previewPartialFiles(operationId),
  deletePartialFiles: (operationId: string) =>
    contract.deletePartialFiles(operationId, { confirmed: true }),
  cleanupModelOperation: (operationId: string) => contract.cleanupModelOperation(operationId),
  saveHuggingFaceCredential: (token: string) => contract.saveHuggingFaceCredential({ token }),
  // BUG-296 — this probe answers 200 even when the Hub is unreachable, and
  // names the reason in the body. A 503 here was an uncaught console error on
  // every Models visit for a host with no route to huggingface.co, which is the
  // budget that exists to catch real ones.
  trendingHuggingFace: () => contract.trendingHuggingFace(),
  searchHuggingFace: (query: string) => contract.searchHuggingFace({ query }),
  huggingFaceVariants: (repoId: string) => {
    const [owner, repository] = repoId.split("/", 2);
    return contract.listHuggingFaceVariants(owner, repository);
  },
  previewHuggingFaceDownload: (
    variant: HuggingFaceVariant,
    destination?: string,
  ) =>
    contract.previewHuggingFaceDownload({
      repo_id: variant.repo_id,
      revision: variant.revision,
      files: variant.files,
      destination: destination || null,
      confirmed: false,
    }),
  downloadHuggingFaceModel: (
    variant: HuggingFaceVariant,
    destination: string,
  ) =>
    contract.downloadHuggingFaceModel({
      repo_id: variant.repo_id,
      revision: variant.revision,
      files: variant.files,
      destination,
      confirmed: true,
    }),
  previewModelConversion: (
    source: string,
    output: string,
    revision: string,
    quantization: ConversionQuantization,
  ) =>
    contract.previewModelConversion({
      source,
      output,
      revision,
      quantization,
      confirmed: false,
    }),
  startModelConversion: (
    source: string,
    output: string,
    revision: string,
    quantization: ConversionQuantization,
  ) =>
    contract.startModelConversion({
      source,
      output,
      revision,
      quantization,
      confirmed: true,
    }),
  modelCapacities: () => contract.getModelCapacities(),
  refreshModelCapacities: (force = false) =>
    contract.refreshModelCapacities(force ? { force: true } : {}),
  setModelCapacity: (
    profileId: string,
    model: string,
    tokens: number | null,
    reason: string,
  ) => contract.setModelCapacity(profileId, { model, tokens, reason }),
  // Read-only status of governed service connectors (never reaches the network;
  // never exposes a credential value). Enabling one is done via the capability
  // gate + decision-mode control plane, not here.
  connections: () => contract.getConnections(),
  // ── Local MCP servers (Control Deck task 4b) ────────────────────────────
  // Owner-scoped. Create and test-connect run through the governed capability
  // (a disabled gate returns 403 disabled_by_capability_gate); rename and
  // delete are human-only owner-scoped operations.
  // ── Channels (BUG-225) ──────────────────────────────────────────────────
  // Read-only listing plus the owner's pairing controls. A test delivery goes
  // through the governed `external_channel_runtime` capability, so a closed gate
  // refuses it exactly as it would refuse a real one.
  channels: () => contract.listChannels(),
  pairChannel: (connector_id: string, display_name: string, senders: string[]) =>
    contract.pairChannel({ connector_id, display_name, senders }),
  setChannelEnabled: (pairingId: string, enabled: boolean) =>
    contract.setChannelEnabled(pairingId, { enabled }),
  setChannelSenders: (pairingId: string, senders: string[]) =>
    contract.setChannelSenders(pairingId, { senders }),
  unpairChannel: (pairingId: string) => contract.unpairChannel(pairingId),
  // UX-MSG-04 — a test names no destination; it goes where the channel delivers.
  deliverChannelTest: (connector_id: string, text: string) =>
    contract.deliverChannelTest({ connector_id, text }),
  setChannelDestination: (pairingId: string, delivery_url: string | null) =>
    contract.setChannelDestination(pairingId, { delivery_url }),
  mcpServers: () => contract.listMcpServers(),
  // BUG-221 — servers installed plugins *offer*. An offer is a description, not
  // a connection: adding one posts to the ordinary create routes above, so the
  // capability gate and the audit event apply exactly as they would by hand.
  mcpOffers: () => contract.listMcpOffers(),
  // Whether a connected server's tools can actually be called in a turn. The
  // handshake and the agent's reach are separate facts, so the page states both.
  mcpAgentAccess: () => contract.getMcpAgentAccess(),
  createMcpServer: (name: string, template: string) => contract.createMcpServer({ name, template }),
  connectMcpServer: (serverId: string) => contract.connectMcpServer(serverId),
  renameMcpServer: (serverId: string, name: string) => contract.renameMcpServer(serverId, { name }),
  deleteMcpServer: (serverId: string) => contract.deleteMcpServer(serverId),
  createRemoteMcpServer: (
    name: string,
    endpoint_url: string,
    auth_ref: string | null,
  ) => contract.createRemoteMcpServer({ name, endpoint_url, auth_ref }),
  mcpSessions: (serverId: string) => contract.listMcpSessions(serverId),
  mcpFindings: (serverId: string) => contract.listMcpFindings(serverId),
  pauseMcpServer: (serverId: string) => contract.pauseMcpServer(serverId),
  resumeMcpServer: (serverId: string) => contract.resumeMcpServer(serverId),
  approveMcpTools: (serverId: string, tools: string[]) =>
    contract.approveMcpTools(serverId, { tools }),
  notifications: () => contract.listNotifications(),
  markNotificationRead: (id: string) => contract.markNotificationRead(id),
  notificationDelivery: () => contract.notificationDelivery(),
  acknowledgeHeldNotifications: (notificationIds: string[]) =>
    contract.acknowledgeHeldNotifications({ notification_ids: notificationIds }),
  sendTestNotice: () => contract.sendTestNotice(),
  standingGrants: (includeInactive = true) =>
    contract.listStandingGrants({ include_inactive: includeInactive }),
  createStandingGrant: (body: CreateStandingGrantRequest) => contract.createStandingGrant(body),
  revokeStandingGrant: (grantId: string) => contract.revokeStandingGrant(grantId),
  securityCredentials: () => contract.listSecurityCredentials(),
  securityFindings: () => contract.listSecurityFindings(),
  securityHealth: () => contract.listSecurityHealth(),
  capabilityContainment: () => contract.listCapabilityContainment(),
  setCapabilityContainment: (
    capability: string,
    subjectId: string,
    action: "pause" | "kill" | "resume",
  ) => contract.setCapabilityContainment(capability, subjectId, action),
  plugins: () => contract.listPlugins(),
  // Read-only. The hook config files are the owner's own text on disk; this
  // reports what the runtime loaded from them, including one it could not read.
  hooks: () => contract.listHooks(),
  verifySecurityCredential: (provider: string) => contract.verifySecurityCredential(provider),
  scanSecurity: () => contract.scanSecurity(),
  checkSecurityHealth: () => contract.checkSecurityHealth(),
  checkPasswordBreach: (password: string, enabled: boolean) =>
    contract.checkPasswordBreach({ password, enabled }),
  connectorStore: () => contract.connectorStore(),
  installConnector: (connectorId: string) => contract.installConnector(connectorId),
  uninstallConnector: (connectorId: string) => contract.uninstallConnector(connectorId),
  setConnectorCredentials: (
    connectorId: string,
    values: Record<string, string>,
    expiresAt?: string,
  ) => contract.setConnectorCredentials(connectorId, { values, expires_at: expiresAt || null }),
  setConnectorEnabled: (connectorId: string, enabled: boolean) =>
    contract.setConnectorEnabled(connectorId, { enabled }),
  registerConnectorManifest: (
    connectorId: string,
    manifest: Record<string, unknown>,
  ) => contract.registerConnectorManifest(connectorId, { manifest }),
  checkLanguage: (text: string) => contract.checkLanguage({ text, language: "en-US" }),
  // On-demand listing of the models a provider serves (user-initiated; provider
  // policy is enforced server-side before any network contact).
  providerModels: (profileId: string) => contract.listProviderModels(profileId),
  refreshProviderCatalogues: (profile_ids?: string[]) =>
    contract.refreshConnectedProviderCatalogues(profile_ids ? { profile_ids } : {}),
  codexSubscriptionStatus: () => contract.getChatgptCodexStatus(),
  startCodexSubscriptionLogin: () => contract.startChatgptCodexLogin(),
  // BUG-259 — adopting the subscription is its own act. Reading the status no
  // longer connects anything, so this is the only way a ChatGPT account becomes
  // one of this owner's providers.
  connectCodexSubscription: () => contract.connectChatgptCodex(),
  disconnectCodexSubscription: () => contract.disconnectChatgptCodex(),
  // Persist (or clear, with null) the user-owned advisor model profile — the
  // model a local model may consult through the governed consult_advisor tool.
  // Gate-manager only, enforced server-side; selecting an advisor grants nothing.
  setModelAdvisor: (profile_id: string | null) => contract.setModelAdvisor({ profile_id }),
  // Persist the operator's model selection (human gate-manager only, enforced
  // server-side; placeholder profiles require a concrete model).
  selectModel: (profile_id: string, model?: string) =>
    contract.setModelSelection({ profile_id, model: model || null }),
  // `workspaceId` names where an identity-linked key acts (BUG-274). It is not
  // a credential and is sent as an ordinary field; the server refuses a value
  // that could not safely become a header before it stores anything.
  saveModelConnection: (
    profileId: string,
    endpoint: string,
    apiKey: string,
    adminApiKey = "",
    workspaceId = "",
  ) =>
    contract.setModelConnection(profileId, {
      endpoint: endpoint || null,
      api_key: apiKey || null,
      admin_api_key: adminApiKey || null,
      workspace_id: workspaceId || null,
    }),
  // Persist the user-owned ordered model fallback sequence (human gate-manager only,
  // enforced server-side). Returns the cleaned/de-duplicated sequence.
  setModelFallback: (profile_ids: string[]) => contract.setModelFallback({ profile_ids }),
  // Upload one image (base64) into the governed attachment store. Validation
  // is fail-closed server-side (media-type allowlist, 5 MB cap, magic-byte
  // sniff); the response is metadata only.
  uploadAttachment: (body: {
    filename: string;
    media_type: string;
    data_base64: string;
  }) => contract.uploadAttachment(body),
  // ── File inspector (view-only, session-scoped) ──
  // The preview is authorized by the session that carried the attachment, so
  // these paths 404 for a file this conversation never had. Nothing here
  // uploads, mutates, or downloads.
  // ── BUG-22: conversation transcript export ──
  // The manifest is read first so the owner reviews exactly what will leave the
  // machine — which messages, which files, and the redaction policy — before a
  // format is chosen. The export itself returns the document; scope comes from
  // the authenticated session and the session id, never from the request body.
  sessionExportManifest: (sessionId: string) => contract.getSessionExportManifest(sessionId),
  exportSession: async (
    sessionId: string,
    format: "html" | "markdown" | "pdf",
    filename: string,
  ): Promise<void> => {
    const blob = await requestBlob(
      `/api/sessions/${encodeURIComponent(sessionId)}/export`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format }),
      },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url));
  },
  // ── BUG-231: the audit log, taken out of the product ──
  // Asking for an export is a governed action: it passes the `audit_export`
  // gate, the policy review and the posture check, and appears in the log it
  // exported. Scope is the signed-in account, resolved server-side; the browser
  // names nothing. `downloadAuditExport` fetches with the session credential —
  // a bare <a download> cannot send one — and hands over a blob URL.
  auditExports: () => contract.listAuditExports(),
  createAuditExport: (sessionId?: string) =>
    contract.createAuditExport(sessionId ? { session_id: sessionId } : {}),
  downloadAuditExport: async (exportId: string): Promise<void> => {
    const blob = await requestBlob(
      `/api/audit/exports/${encodeURIComponent(exportId)}/download`,
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${exportId}.jsonl`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url));
  },
  // ── Backlog #18: governed events over OTLP ──
  // The record Raiker keeps, on a wire to somewhere the owner already looks.
  // A destination holds an endpoint and the *name* of the environment variable
  // an auth header lives in — never a credential.
  telemetryDestinations: () => contract.listTelemetryDestinations(),
  createTelemetryDestination: (body: CreateTelemetryDestinationRequest) =>
    contract.createTelemetryDestination(body),
  deleteTelemetryDestination: (destinationId: string) =>
    contract.deleteTelemetryDestination(destinationId),
  runTelemetryExport: (destinationId: string) => contract.runTelemetryExport(destinationId),
  // BUG-276 — put a destination on a cadence the host runs, or take it off one.
  setTelemetryCadence: (destinationId: string, cadence: string) =>
    contract.setTelemetryCadence(destinationId, { cadence }),
  // ── The Design surface ──
  // The list is metadata only; the bytes are a separate, owner-scoped request
  // that names one generation, so a gallery cannot accidentally ship megabytes.
  images: () => contract.listImages(),
  generateImage: (body: GenerateImageRequest) => contract.generateImage(body),
  imageBytesUrl: (generationId: string) =>
    `/api/images/${encodeURIComponent(generationId)}/bytes`,
  // UX-DESIGN-01 — the same owner-scoped bytes, as a named file to save.
  imageDownloadUrl: (generationId: string) =>
    `/api/images/${encodeURIComponent(generationId)}/bytes?download=1`,
  deleteImage: (generationId: string) => contract.deleteImage(generationId),
  restoreImage: (generationId: string) => contract.restoreImage(generationId),
  purgeImage: (generationId: string) => contract.purgeImage(generationId),
  // DEC-07 step 4 — an earlier version back as a new version on top of `head`.
  revertImage: (headId: string, to: string) => contract.revertImage(headId, { to }),
  // ── BUG-21: the normalised price registry ──
  modelPricing: () => contract.getModelPricing(),
  refreshModelPricing: () => contract.refreshModelPricing(),
  setModelPrice: (profileId: string, body: ModelPriceRequest) =>
    contract.setModelPrice(profileId, body),
  sessionAttachments: (sessionId: string) => contract.listSessionAttachments(sessionId),
  attachmentPreview: (sessionId: string, attachmentId: string) =>
    contract.getAttachmentPreview(sessionId, attachmentId),
  // PDFs and images are displayed by the browser itself. Their bytes are
  // fetched with the in-memory bearer token (an <object> or <img> tag cannot
  // send one) and handed over as a same-origin blob URL; the caller revokes it
  // when the pane closes.
  attachmentPreviewObjectUrl: async (bytesPath: string): Promise<string> => {
    const blob = await requestBlob(bytesPath);
    return URL.createObjectURL(blob);
  },
  // BUG-28 — the bytes of one authorised file, for saving rather than reading.
  // Fetched with the bearer token for the same reason previews are: a bare
  // <a download> cannot send one. The server always answers
  // application/octet-stream, so nothing downloaded is ever handed to the
  // browser as something it will run.
  attachmentDownload: (
    sessionId: string,
    attachmentId: string,
  ): Promise<Blob> =>
    requestBlob(
      `/api/sessions/${encodeURIComponent(sessionId)}/attachments/${encodeURIComponent(attachmentId)}/download`,
    ),
  // BUG-27 — which exchange produced a generated file, resolved the same way
  // memory provenance is, so both surfaces give the same honest answers.
  attachmentProvenance: (sessionId: string, attachmentId: string) =>
    contract.getAttachmentProvenance(sessionId, attachmentId),
  // C6 — what the turns in this conversation actually read. Labels and
  // locators only; the material behind a chip is fetched when it is opened.
  sessionSources: (sessionId: string) => contract.listSessionSources(sessionId),
  // C17 — which approved memories this conversation's turns were given.
  // Read live, so a memory corrected or forgotten since the turn ran reads as
  // it is now rather than as a stale copy.
  sessionRecall: (sessionId: string) => contract.listSessionRecall(sessionId),
  // C4 — one cited source, opened at the passage the turn used. Resolution is
  // re-run now, so a changed or unreadable source says so instead of showing a
  // passage that is no longer there.
  // `quote` is the answer sentence an inline marker terminated, when there is
  // one: it locates the run inside a source the turn read whole.
  turnSourceExcerpt: (sessionId: string, turnId: string, sourceId: string, quote = "") =>
    contract.getTurnSourceExcerpt(sessionId, turnId, sourceId, quote === "" ? {} : { quote }),
  // BUG-27 — the passage a memory was drawn from. Every non-resolvable case
  // comes back as a named status rather than an error.
  memorySource: (memoryId: string) => contract.getMemorySource(memoryId),
  events: (
    params: { session_id?: string; turn_id?: string; event_type?: string; limit?: number } = {},
  ) => contract.listEvents(params),
  brain: () => contract.getBrain(),
  /**
   * BUG-305 — everything Raiker may read, both kinds, from one route. The two
   * controllers stay two; the owner's question has one answer.
   */
  knowledgeSources: () => contract.listKnowledgeSources(),
  revokeKnowledgeSource: (kind: KnowledgeSourceKind, sourceId: string) =>
    contract.revokeKnowledgeSource({ kind, source_id: sourceId }),
  addBrainSource: (path: string) => contract.addBrainSource({ path }),
  /** An empty path answers with the roots themselves, not with a listing. */
  browseBrainSources: (path = "") => contract.browseBrainSources({ path }),
  brainSourceRoots: () => contract.listBrainSourceRoots(),
  /** Grant one folder on this computer. Read where it is; nothing is copied. */
  grantBrainSourceFolder: (path: string) => contract.grantBrainSourceFolder({ path }),
  revokeBrainSourceFolder: (rootId: string) => contract.revokeBrainSourceFolder({ root_id: rootId }),
  /**
   * Copy one file from the computer into the workspace. `storeCopy` is the
   * owner's permission for the duplication and has no default on the server:
   * choosing a file is not consent to store it.
   */
  uploadBrainSourceFile: (filename: string, contentBase64: string, storeCopy: boolean) =>
    contract.uploadBrainSourceFile({
      filename,
      content_base64: contentBase64,
      store_copy: storeCopy,
    }),
  reviewBrainSource: (path: string) => contract.reviewBrainSource({ path }),
  brainPreferences: () => contract.getBrainPreferences(),
  saveBrainPreferences: (settings: Record<string, unknown>) =>
    contract.saveBrainPreferences({ settings }),
  removeBrainSource: (path: string) => contract.removeBrainSource({ path }),
  executionEnvironments: () => contract.getExecutionEnvironments(),
  configureExecutionEnvironment: (body: {
    profile_id?: string;
    kind: "ssh" | "daytona" | "container";
    name: string;
    config: Record<string, unknown>;
    enabled: boolean;
  }) => contract.configureExecutionEnvironment(body),
  probeExecutionEnvironment: (profile_id: string) => contract.probeExecutionEnvironment(profile_id),
  // BUG-194 — a boundary that persists needs a way back to a known state, or
  // it is worse than one that never persisted. Refused by name on a profile
  // that rebuilds itself around every command.
  resetExecutionEnvironment: (
    profile_id: string,
    session_id: string,
    recreate: boolean,
  ) => contract.resetExecutionEnvironment(profile_id, { session_id, recreate }),
  selectExecutionEnvironment: (profile_id: string) =>
    contract.selectExecutionEnvironment({ profile_id }),
  commandRuns: (sessionId?: string) =>
    contract.listCommands(sessionId ? { session_id: sessionId } : {}),
  commandRun: (runId: string) => contract.getCommand(runId),
  commandOutput: (runId: string, after = 0) => contract.getCommandOutput(runId, { after }),
  commandReceipt: (runId: string) => contract.getCommandReceipt(runId),
  stopCommand: (runId: string) => contract.stopCommand(runId),
  credentialDeltas: (profileId: string) =>
    contract.listCredentialDeltas({ environment_profile_id: profileId }),
  discardCredentialDelta: (runId: string, decisionId: string) =>
    contract.discardCredentialDelta(runId, { decision_id: decisionId }),
  checkpoints: (sessionId?: string, projectId?: string) =>
    contract.listCheckpoints({ session_id: sessionId, project_id: projectId }),
  checkpoint: (id: string) => contract.getCheckpoint(id),
  // Preflight only. Reading a plan performs no restore; executing one still
  // goes through the governed approval path.
  checkpointRestorePlan: (id: string) => contract.getCheckpointRestorePlan(id),
  // BUG-230 — the rewind. This asks for it; it never performs one. The server
  // recomputes the preflight, records the proposal and returns an approval id,
  // and the workspace changes only when a human approves it in Approvals.
  requestCheckpointRestore: (id: string) => contract.requestCheckpointRestore(id),
  // ── Branch from here (GAP-CHAT C14) ──────────────────────────────────
  // A branch is a *second* conversation seeded from a checkpoint's state summary
  // and memory candidates. It rewrites nothing: the original conversation keeps
  // every turn it had, which is why — unlike a restore — it writes no workspace
  // file and needs no approval. `branchOrigin` answers "is this a branch, and of
  // what", and reports a root conversation as such rather than as an error.
  conversationBranchPlan: (checkpointId: string) => contract.getConversationBranchPlan(checkpointId),
  branchConversation: (checkpointId: string, title = "") =>
    contract.branchConversation(checkpointId, { title }),
  answerOwnerQuestion: (
    approvalId: string,
    body: { answers?: Record<string, string | string[]>; response?: string },
  ) => contract.answerOwnerQuestion(approvalId, body),
  compactConversation: (sessionId: string, throughTurnId: string) =>
    contract.compactConversation(sessionId, { through_turn_id: throughTurnId }),
  conversationBranchOrigin: (sessionId: string) => contract.getConversationBranchOrigin(sessionId),
  // ── Installed skills (Extensions → Skills) ───────────────────────────
  // A skill is instruction text the owner installs; it grants no capability and
  // runs nothing. `verifySkillUrl` reads a linked document and reports what it
  // is without storing it, so Chat and Build can offer an informed import.
  skills: () => contract.listSkills().then((body) => body.skills),
  uploadSkill: (filename: string, data_base64: string) =>
    contract.uploadSkill({ filename, data_base64 }),
  verifySkillUrl: (url: string) => contract.verifySkillUrl({ url }),
  importSkillUrl: (url: string) => contract.importSkillUrl({ url }),
  buildSkill: (name: string, description: string, body: string, command_trigger?: string) =>
    contract.buildSkill({ name, description, body, command_trigger: command_trigger || null }),
  renameSkill: (id: string, name: string) => contract.renameSkill(id, { name }),
  setSkillActive: (id: string, active: boolean) => contract.setSkillActive(id, { active }),
  setChannelRouting: (
    pairingId: string,
    settings: {
      routing_mode: "record_only" | "new_turn" | "side_question" | "interrupt";
      target_session_id: string | null;
      owner_sender_id: string | null;
      approval_relay_enabled: boolean;
    },
  ) => contract.setChannelRouting(pairingId, settings),
  setSkillCommand: (id: string, command_trigger: string | null) =>
    contract.setSkillCommand(id, { command_trigger }),
  downloadSkill: (id: string) =>
    requestBlob(`/api/skills/${encodeURIComponent(id)}/download`),
  deleteSkill: (id: string) => contract.deleteSkill(id),
  extensions: () => contract.getExtensions(),
  projectFiles: (id: string) => contract.getProjectFiles(id),
  diagnosticsExport: () => contract.getDiagnosticsExport(),
  // `origin: "chat"` narrows the list to conversations the owner typed. Task
  // runs live in a server-owned session that is still listed in Sessions; it is
  // only "recent chats" that must mean chats (BUG-10).
  sessions: (projectId?: string, includeArchived = false, origin?: string) =>
    contract.listSessions({
      project_id: projectId,
      include_archived: includeArchived ? true : undefined,
      origin,
    }),
  // C18 — what the owner is working on, across chats, projects and routines.
  // Chat search answers "where did I say that"; this answers the other question.
  workThreads: (limit = 100) => contract.listWorkThreads({ limit }),
  // NEW-THREAD-01 — the index behind Threads. Filters and paging happen on the
  // server, because facets computed over one page can only ever offer what is
  // already on screen.
  workThreadPage: (options: {
    projectId?: string | null;
    kind?: string | null;
    query?: string;
    cursor?: string | null;
    limit?: number;
    // BUG-303 — a scope, not a filter: the two sets do not overlap and every
    // other filter applies within whichever one is read.
    archived?: boolean;
  } = {}) =>
    contract.workThreadPage({
      project_id: options.projectId ?? undefined,
      kind: options.kind ?? undefined,
      query: options.query || undefined,
      cursor: options.cursor ?? undefined,
      limit: options.limit ?? undefined,
      archived: options.archived ? true : undefined,
    }),
  searchChats: (q: string) => contract.searchChatHistory({ q }),

  // ── Web access (RAIKER-2021) ─────────────────────────────────────────
  // What web reads may not reach. The address guard that refuses private and
  // loopback destinations is not represented here because it is not editable —
  // the read below reports it so the page can say so.
  webBlocklist: () => contract.getBlocklist(),
  addWebBlocklistRule: (rule: string, note = "") => contract.addBlocklistRule({ rule, note }),
  deleteWebBlocklistRule: (ruleId: string) => contract.deleteBlocklistRule(ruleId),
  testWebBlocklist: (host: string) => contract.testBlocklist({ host }),
  // ── Git credential (RAIKER-2022) ─────────────────────────────────────
  // The token is write-only across this boundary: it goes up, and no read ever
  // returns it.
  gitCredential: (sessionId?: string) =>
    contract.getGitCredential(sessionId ? { session_id: sessionId } : {}),
  putGitCredential: (token: string) => contract.putGitCredential({ token }),
  deleteGitCredential: () => contract.deleteGitCredential(),
  grantGitCredential: (scope: string, sessionId?: string) =>
    contract.grantGitCredential({ scope, session_id: sessionId ?? null }),
  revokeGitCredential: () => contract.revokeGitCredential(),
  // ── Reliable memory controls (backlog item 3) ────────────────────────
  // User-facing surface over the existing governed memory store. List carries
  // provenance/scope/sensitivity/confidence/retention + pin; forget reuses
  // the governed forget path (human-only); incognito withholds approved
  // project memory from the turn context.
  // UX-MEM-02/03 — the Memory page lists archived and expired records too, so
  // it can offer Restore and say what is about to lapse. Recall never reads
  // this listing; it changes what is shown, not what a turn is given.
  memories: (scope?: string, includeInactive = false) =>
    contract.listMemories(includeInactive ? { scope, include_inactive: true } : { scope }),
  memoryProposals: () => contract.listMemoryProposals(),
  memoryRelationshipProposals: () => contract.getMemoryRelationshipProposals(),
  scanMemoryRelationships: () => contract.postMemoryRelationshipProposalsScan(),
  decideMemoryRelationshipProposal: (
    id: string,
    decision: "approved" | "denied",
    expectedDecision = "needs_user_review",
  ) =>
    contract.postMemoryRelationshipProposalsCandidateIdDecision(id, {
      decision,
      expected_decision: expectedDecision,
    }),
  rejectMemoryRelationship: (id: string, reason: string) =>
    contract.rejectMemoryRelationship(id, { reason, expected_active: true }),
  decideMemoryProposal: (
    id: string,
    body: {
      decision: "approved" | "rejected";
      edited_text?: string;
      reason?: string;
      expected_decision: string;
    },
  ) => contract.decideMemoryProposal(id, body),
  memoryHistory: (id: string) => contract.getMemoryHistory(id),
  changeMemoryScope: (
    id: string,
    scope: string,
    expectedUpdatedAt: string | null,
    reason: string,
  ) =>
    contract.changeMemoryScope(id, { scope, expected_updated_at: expectedUpdatedAt, reason }),
  previewMemoryPurge: (id: string) => contract.previewMemoryPurge(id),
  purgeMemory: (id: string) => contract.purgeMemory(id, id),
  setMemoryPinned: (id: string, pinned: boolean) => contract.setMemoryPinned(id, { pinned }),
  editMemory: (id: string, text: string) => contract.editMemory(id, { text }),
  setMemorySearchEnabled: (id: string, enabled: boolean) =>
    contract.setMemorySearchEnabled(id, { enabled }),
  setMemoryExpiry: (id: string, expiresAt: string | null) =>
    contract.setMemoryExpiry(id, { expires_at: expiresAt }),
  exportMemories: () => contract.exportMemories(),
  // BUG-244 — what an import would actually change, before it changes anything.
  previewMemoryImport: (memories: Array<Partial<MemoryControlView> & { text: string }>) =>
    contract.previewMemoryImport({ memories }),
  // UX-MEM-08 — the owner's per-record skips travel as indices, and the server
  // honours them, so the receipt counts what the owner decided.
  importMemories: (
    memories: Array<Partial<MemoryControlView> & { text: string }>,
    skipDuplicates = true,
    options: { excludeIndices?: number[]; fileName?: string } = {},
  ) =>
    contract.importMemories({
      memories,
      skip_duplicates: skipDuplicates,
      exclude_indices: options.excludeIndices ?? [],
      file_name: options.fileName ?? "",
    }),
  memoryImportBatches: () => contract.listMemoryImportBatches(),
  undoMemoryImport: (batchId: string) => contract.undoMemoryImport(batchId),
  setMemoryArchived: (id: string, archived: boolean) =>
    contract.setMemoryArchived(id, { archived }),
  forgetMemory: (id: string) => contract.forgetMemory(id),
  memorySettings: () => contract.getMemorySettings(),
  setMemoryIncognito: (incognito: boolean) => contract.setMemoryIncognito({ incognito }),
  // MEM-03 — "auto" resolves to the best space that actually holds vectors;
  // any other value must name one, or the server refuses rather than silently
  // searching a different corpus.
  setMemoryEmbeddingBackend: (backend: string) =>
    contract.setMemoryEmbeddingBackend({ embedding_backend: backend }),
  // MEM-10 — build the space rather than only choose between the ones that
  // happen to exist. The call names the provider and the embedding model and
  // never the memories: which rows are eligible is resolved server-side from
  // the acting principal.
  buildMemoryEmbeddingIndex: (provider: string, model: string) =>
    contract.buildMemoryEmbeddingIndex({ provider, model }),
  // MEM-04 — what the runtime captured while it worked. The counts come back
  // with the list because a page that can only count what it received cannot
  // tell an owner whether an empty list means nothing ran or everything was
  // refused on sensitivity.
  observations: () => contract.listObservations(),
  deleteObservations: (ids: string[]) => contract.deleteObservations({ observation_ids: ids }),
  // MEM-07 — the confirmed retention sweep. The server re-derives what is due
  // and refuses anything the preview did not list, so this is a confirmation
  // rather than an instruction.
  cleanupExpiredObservations: (ids: string[]) =>
    contract.cleanupExpiredObservations({ observation_ids: ids }),
  discardGist: (id: string) => contract.discardGist(id),
  // ── Build workspace repositories ────────────────────────────────────────
  // References only. A local folder must resolve inside the workspace (fail
  // closed server-side); a GitHub repository records an `owner/repo` coordinate
  // and performs no network call — its content still reaches a turn through the
  // brokered `github_read` tool under the connector_github_runtime gate.
  codeRepos: () => contract.listCodeRepos(),
  // DEC-06 step 1 — where a Build turn would run, resolved by the server from
  // the same selections a turn reads. The project is the one proposal sent.
  buildBoundary: (projectId: string | null) =>
    contract.getBuildBoundary(projectId ? { project_id: projectId } : {}),
  // B13 — the connected repository, one directory at a time and one bounded
  // file at a time. Both are reads through the same path authority a turn
  // writes through, so the explorer can never reach further than the agent can.
  browseCodeRepo: (repoId: string, path = "") =>
    contract.browseCodeRepo(repoId, path === "" ? {} : { path }),
  readCodeRepoFile: (repoId: string, path: string) => contract.readCodeRepoFile(repoId, { path }),
  // What has changed in the working tree and not yet been committed.
  // The `Changes` tab of Build's artifact pane reads this; it is the same change
  // set a commit would record, because it comes from the same two helpers.
  readCodeRepoChanges: (repoId: string) => contract.readCodeRepoChanges(repoId),
  // B10 — what a parser sees in the file the owner just opened.
  readCodeRepoDiagnostics: (repoId: string, path: string) =>
    contract.readCodeRepoDiagnostics(repoId, { path }),
  connectLocalRepo: (path: string) => contract.connectCodeRepo({ kind: "local", path }),
  connectGithubRepo: (owner: string, repo: string, branch?: string) =>
    contract.connectCodeRepo({ kind: "github", owner, repo, branch: branch || null }),
  selectCodeRepo: (repo_id: string | null) => contract.selectCodeRepo({ repo_id }),
  disconnectCodeRepo: (repoId: string) => contract.disconnectCodeRepo(repoId),
  // B9 — the code map over the selected repository. Reading its state is
  // metadata only; rebuilding fails closed with a reason when the owner has the
  // `code_map_indexing` capability turned off.
  codeMap: () => contract.getCodeMapStatus(),
  // B19 — completion behind an `@`-mention in the composer. Paths and languages
  // only, out of the index the owner built, behind the same capability gate.
  codeMapPaths: (fragment: string, limit = 12) => contract.getCodeMapPaths({ q: fragment, limit }),
  rebuildCodeMap: () => contract.rebuildCodeMap(),
  // ── Projects (organizing scopes; creating/selecting one grants nothing) ──
  projects: () => contract.listProjects(),
  project: (id: string) => contract.getProject(id),
  exportProject: async (id: string): Promise<void> => {
    const path = `/api/projects/${encodeURIComponent(id)}/export`;
    const blob = await requestBlob(path, { method: "POST" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `project-${id}.jsonl`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url));
  },
  // ── Managed knowledge files ───────────────────────────────────────────────
  // Memory and Projects share one contract, differing only in which managed
  // root the file lands in. Every file type is accepted; whether its text can
  // be indexed is reported back per file, never assumed by the client.
  deleteManagedFile: (fileId: string) => contract.deleteManagedFile(fileId),
  retryManagedFile: (fileId: string) => contract.retryManagedFile(fileId),
  managedFiles: (scope: ManagedFileScope, projectId: string | null) =>
    scope === "memory"
      ? contract.listMemoryFiles()
      : contract.listProjectFiles(projectId ?? ""),
  importManagedFiles: (
    scope: ManagedFileScope,
    projectId: string | null,
    files: ManagedFileUpload[],
  ) =>
    scope === "memory"
      ? contract.importMemoryFiles({ files })
      : contract.importProjectFiles(projectId ?? "", { files }),
  // Create a named project for the authenticated local human.
  // The root subpath is derived and contained server-side — no path is sent.
  // `attachPath` is the exception and the only path the client ever sends: the
  // owner is naming a folder they already have, which the server validates and
  // records as a grant before it becomes a root.
  createProject: (name: string, attachPath: string | null = null, attachWritable = true) =>
    contract.createProject(
      attachPath === null
        ? { name }
        : { name, attach_path: attachPath, attach_writable: attachWritable },
    ),
  // ── Project roots ──────────────────────────────────────────────────────
  // One directory at a time, never the whole tree: a folder the owner attached
  // can be arbitrarily large, and walking it eagerly would stall the page on a
  // repository the owner only wanted to glance at.
  browseProject: (projectId: string, path = "") =>
    contract.browseProject(projectId, path === "" ? {} : { path }),
  projectRootStatus: (projectId: string) => contract.projectRootStatus(projectId),
  indexProjectRoot: (projectId: string) => contract.indexProjectRoot(projectId),
  attachProjectFolder: (projectId: string, path: string, writable: boolean) =>
    contract.attachProjectRoot(projectId, { path, writable }),
  detachProjectFolder: (projectId: string) => contract.detachProjectRoot(projectId),
  // Set (or clear, with null) the active project; new sessions are stamped with it.
  selectProject: (project_id: string | null) => contract.selectProject({ project_id }),
  deleteProject: (id: string, confirmed = false) =>
    contract.deleteProject(id, confirmed ? id : undefined),
  saveProjectContext: (id: string, context: ProjectContext) =>
    contract.saveProjectContext(id, context),
  // Nested projects/folders: tree, move, archive
  projectTree: () => contract.listProjectTree(),
  moveProject: (id: string, parent_id: string | null) => contract.moveProject(id, { parent_id }),
  archiveProject: (id: string) => contract.archiveProject(id),
  // UX-PROJ-05 — undo an archive: the project and what was archived with it.
  restoreProject: (id: string) => contract.restoreProject(id),
  // UX-PROJ-07 — what a delete would remove, counted before it is asked for.
  projectDeletionPreview: (id: string) => contract.projectDeletionPreview(id),
  session: (id: string) => contract.getSession(id),
  renameSession: (id: string, title: string) => contract.renameSession(id, { title }),
  archiveSession: (id: string) => contract.archiveSession(id),
  unarchiveSession: (id: string) => contract.unarchiveSession(id),
  // Pin (or unpin) a session. Organizing label only — grants nothing.
  setSessionPinned: (id: string, pinned: boolean) => contract.setSessionPinned(id, { pinned }),
  // Permanently delete one session and its cascaded rows. Requires the explicit
  // confirmation header (mirrors project deletion). Human-only; an account
  // cannot delete another account's session.
  deleteSession: (id: string) => contract.deleteSession(id, id),
  deleteSessions: (session_ids: string[]) => contract.deleteSessions({ session_ids }),
  // Replace the tag set for one session. Tags are organizing labels only —
  // they grant nothing. The server normalizes (trim, lowercase, dedupe,
  // length/count caps). Human-only; an account cannot retag another account's
  // session.
  setSessionTags: (id: string, tags: string[]) => contract.setSessionTags(id, { tags }),
  // Move one chat into a project, or out of every project with a null
  // project_id. A project is an organizing scope — the move grants nothing and
  // only changes the bounded context the chat receives on its next turn.
  // Human-only; an account cannot move another account's chat.
  setSessionProject: (id: string, project_id: string | null) =>
    contract.setSessionProject(id, { project_id }),
  turn: (id: string) => contract.getTurn(id),
  // `project_id` scopes the list to one project's schedules (project-scoped
  // schedules); omitting it lists every task visible to the account.
  tasks: (params: { session_id?: string; task_status?: string; project_id?: string } = {}) =>
    contract.listTasks(params),
  // BUG-299 — one task at its own address, with the attempts behind its status.
  // Home's deduplicated rows, Build's task panel and the Stop control's honest
  // "refresh to see the run's current state" all point here.
  taskDetail: (taskId: string) => contract.getTaskDetail(taskId),
  taskDoctor: (taskId: string) => contract.taskDoctor(taskId),
  setTaskRunLimit: (taskId: string, maxRunMinutes: number | null) =>
    contract.setTaskRunLimit(taskId, { max_run_minutes: maxRunMinutes }),
  createTask: (body: TaskCreateRequest) => contract.createTask(body),
  // BUG-64 — creation alone does not execute model-proposed work. This is the
  // owner's separate, explicit intent to make one parked task due now.
  runTask: (taskId: string) => contract.runTask(taskId),
  // BUG-25 — ask the host to continue one parked scheduled run now. The
  // scheduler does this on its own tick; this is the owner's retry for when
  // automatic continuation could not proceed, and it runs the same path.
  resumeTask: (taskId: string) => contract.resumeTask(taskId),
  // ── Prompts / interrupts ──
  // Non-streaming prompt submit; returns the final governed AgentResponse.
  submitPrompt: (body: PromptRequestBody) => contract.submitPrompt(body),
  // Issue a governed safe-boundary interrupt for one task or all active tasks in a session.
  interrupt: (body: InterruptRequestBody) => contract.interrupts(body),
  // GEP-02 — what the stop switch would reach beyond the task list: the turns
  // writing an answer right now and the commands still running.
  workInFlight: () => contract.workInFlight(),
  stopAll: () => contract.stopAll(),
  // ── Approvals (resolution is metadata-only: records a decision, never executes) ──
  approvals: (statusFilter = "pending") =>
    contract.listApprovals({ status_filter: statusFilter }),
  // Which of a provider's models stay offered in every picker. The default
  // model is a different decision, made by `setModelSelection`.
  setAvailableModels: (profileId: string, models: string[]) =>
    contract.setAvailableModels(profileId, { models }),
  approval: (id: string): Promise<ApprovalDetailView> => contract.getApproval(id),
  // B14 — `accepted_hunks` carries the reviewer's own narrowing: hunk positions
  // in the approved diff, validated server-side against that same diff. Omitted
  // means the whole change set, which is what a decision has always meant.
  resolveApproval: (
    id: string,
    body: { approve: boolean; reason: string; accepted_hunks?: string[] },
  ) => contract.resolveApproval(id, body),
  // BUG-271 — the reviewer corrected a line rather than narrowing the change.
  // An edit is a *different action*, so this is not a field on the decision: it
  // denies the proposal in front of the owner and raises theirs in its place,
  // with its own preview, its own hash and its own approval. Nothing executes.
  replaceApproval: (id: string, body: { patch: string; reason?: string }) =>
    contract.replaceApprovalWithEdit(id, body),
  // B2 — non-streaming continuation of a turn that was parked for this approval.
  resumeAfterApproval: (id: string) => contract.resumeAfterApproval(id),
  // BUG-24 — parked turns this account may continue right now, whoever resolved
  // the approval and wherever they resolved it. Ids only; polling changes
  // nothing, and the server still enforces exactly-once resumption.
  resumableTurns: (sessionId?: string) =>
    contract.listResumableTurns(sessionId ? { session_id: sessionId } : {}),
  resolveCriticalApproval: (
    id: string,
    body: { approve: boolean; reason: string },
  ) => contract.resolveCriticalApproval(id, body),

  // ── Runtime mutations. These reuse the existing governed control routes; the UI adds no
  // authority. Every call is enforced server-side by RuntimeAuthority. ──
  activateRuntimeMode: (mode_name: string, reason: string) =>
    contract.activateRuntimeMode({ mode_name, reason }),
  disableRuntimeMode: (reason: string) => contract.disableRuntimeMode({ reason }),
  setCapabilityState: (
    capability: string,
    body: { target_state: string; reason: string; confirmation_token?: string },
  ) => contract.setCapabilityState(capability, body),
  disableCapability: (capability: string, reason: string) =>
    contract.disableCapability(capability, { reason }),
  // Record a human threat-model acknowledgement (owner/gate-manager only). This
  // is the in-app equivalent of the operator/CLI ack step and only satisfies the
  // acknowledgement precondition — the capability transition still runs after it.
  recordThreatModelAck: (capability: string, reason: string) =>
    contract.recordThreatModelAck(capability, { reason }),

  // ── Per-capability decision modes (ask | allow | auto | deny) ──
  capabilityDecisionMode: (capability: string) => contract.getCapabilityDecisionMode(capability),
  setCapabilityDecisionMode: (
    capability: string,
    mode: "ask" | "allow" | "auto" | "deny",
    reason: string,
  ) => SET_DECISION_MODE[mode](capability, { reason }),
};
