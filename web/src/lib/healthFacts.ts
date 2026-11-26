/**
 * RU-08 — the readiness facts first run sets up, each with the page that fixes
 * it: the model, disk and memory, command sandbox, backups, embedding model,
 * voice, updates and the always-on host. Every fact is read from an endpoint its own settings page
 * already uses; this only turns each answer into one line. A fact that could
 * not be read is `unknown`, never a pass.
 */
import type {
  BackupsView,
  CommandSandboxView,
  HostView,
  MemorySettingsView,
  ModelsView,
  SetupSystemReadiness,
  UpdateStatusView,
  VoiceStatus,
} from "./generated/apiContract";

export type HealthFactState = "ok" | "warn" | "fail" | "info" | "unknown";

export type HealthFact = {
  id: string;
  label: string;
  state: HealthFactState;
  detail: string;
  href: string;
  linkLabel: string;
};

export type HealthSources = {
  /** Optional: callers that have not read them get no model or machine fact. */
  models?: ModelsView | null;
  system?: SetupSystemReadiness | null;
  sandbox: CommandSandboxView | null;
  backups: BackupsView | null;
  memory: MemorySettingsView | null;
  voice: VoiceStatus | null;
  update: UpdateStatusView | null;
  host: HostView | null;
};

const DAY_MS = 24 * 60 * 60 * 1000;
/** A backup older than this is stale enough to say so. */
export const BACKUP_STALE_DAYS = 7;

const UNREAD = "Could not be read.";

function sandboxFact(view: CommandSandboxView | null): HealthFact {
  const base = { id: "sandbox", label: "Command sandbox", href: "#/settings?tab=advanced&kind=runtime", linkLabel: "Command sandbox" };
  if (view === null || typeof view.applies !== "boolean") return { ...base, state: "unknown", detail: UNREAD };
  if (!view.applies) {
    if (view.native_ready === false) {
      return {
        ...base,
        state: "fail",
        detail: view.native_install_command
          ? `Bubblewrap is not installed. Run: ${view.native_install_command}`
          : "Bubblewrap is not installed; install the bubblewrap package.",
      };
    }
    if (view.native_ready === null) return { ...base, state: "info", detail: "This system's own sandbox runs commands." };
    return { ...base, state: "ok", detail: "Bubblewrap runs commands." };
  }
  if (view.windows_backend === "wsl") {
    return view.wsl_configured
      ? { ...base, state: "ok", detail: "Commands run in Raiker's WSL2 distribution." }
      : {
          ...base,
          state: "fail",
          detail: `WSL2 is chosen but not set up${view.wsl_missing.length ? ` (missing: ${view.wsl_missing.join(", ")})` : ""}.`,
        };
  }
  return {
    ...base,
    state: "fail",
    detail: view.wsl_configured
      ? "The restricted account is chosen and is refused; choose WSL2."
      : "No command sandbox is set up, so commands are refused. Set up WSL2.",
  };
}

function backupFact(view: BackupsView | null, now: number): HealthFact {
  const base = { id: "backups", label: "Backups", href: "#/settings?tab=backups", linkLabel: "Backups" };
  if (view === null || !Array.isArray(view.backups)) return { ...base, state: "unknown", detail: UNREAD };
  const latest = [...view.backups].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  if (!latest) return { ...base, state: "warn", detail: "No backup has been made." };
  const age = Math.floor((now - Date.parse(latest.created_at)) / DAY_MS);
  const when = age <= 0 ? "today" : age === 1 ? "yesterday" : `${age} days ago`;
  if (!latest.verified_at) return { ...base, state: "warn", detail: `Last backup ${when} was not verified.` };
  if (age > BACKUP_STALE_DAYS) return { ...base, state: "warn", detail: `Last verified backup was ${when}.` };
  return { ...base, state: "ok", detail: `Last verified backup ${when}.` };
}

function embeddingFact(view: MemorySettingsView | null): HealthFact {
  // The same rule Memory's Recall backend card uses: meaning only when the
  // backend in use is semantic and a question can be embedded into it.
  const base = { id: "embedding", label: "Search by meaning", href: "#/memory?tab=controls", linkLabel: "Memory controls" };
  if (view === null || !Array.isArray(view.embedding_providers)) return { ...base, state: "unknown", detail: UNREAD };
  const retrieval = view.retrieval;
  if (retrieval === null || !retrieval.semantic) {
    const offer = view.embedding_providers[0]?.model;
    return {
      ...base,
      state: "warn",
      detail: offer
        ? `Recall matches words only. ${offer} is available to build a meaning-based index.`
        : "Recall matches words only; no embedding model is available.",
    };
  }
  if (retrieval.query_embeddable === false) {
    return { ...base, state: "warn", detail: `Stored in ${retrieval.model}, but questions are not embedded yet, so recall still matches words.` };
  }
  const waiting = view.unindexed_memories + view.unindexed_file_chunks;
  return waiting > 0
    ? { ...base, state: "info", detail: `${retrieval.model} · ${waiting} waiting to be indexed.` }
    : { ...base, state: "ok", detail: `${retrieval.model} · everything indexed.` };
}

function voiceFact(view: VoiceStatus | null): HealthFact {
  const base = { id: "voice", label: "Voice", href: "#/settings?tab=voice", linkLabel: "Voice" };
  if (view === null || !view.listening) return { ...base, state: "unknown", detail: UNREAD };
  const listening = view.listening.state;
  if (listening === "off") return { ...base, state: "info", detail: "Off. Optional." };
  if (listening === "not_installed") return { ...base, state: "info", detail: "Not installed. Optional." };
  if (listening === "unavailable") return { ...base, state: "warn", detail: "Turned on but not available on this machine." };
  return { ...base, state: "ok", detail: listening === "ready" ? "Ready." : "Installed; starts when used." };
}

function updateFact(view: UpdateStatusView | null): HealthFact {
  const base = { id: "updates", label: "Updates", href: "#/settings?tab=updates", linkLabel: "Updates" };
  if (view === null || typeof view.state !== "string") return { ...base, state: "unknown", detail: UNREAD };
  const state: HealthFactState =
    view.state === "up_to_date" ? "ok"
    : view.state === "available" || view.state === "unreachable" ? "warn"
    : "info";
  return { ...base, state, detail: view.message };
}

function hostFact(view: HostView | null): HealthFact {
  const base = { id: "always-on", label: "Always-on host", href: "#/settings?tab=updates", linkLabel: "Settings" };
  if (view === null || !view.service) return { ...base, state: "unknown", detail: UNREAD };
  if (!view.service.supported) return { ...base, state: "info", detail: "Starting with this computer is not supported here." };
  if (view.paused) return { ...base, state: "warn", detail: "Paused; scheduled work waits." };
  return view.service.registered
    ? { ...base, state: "ok", detail: `Starts with this computer (${view.service.label}).` }
    : { ...base, state: "info", detail: "Runs only while Raiker is open. Optional." };
}

function modelFact(view: ModelsView | null): HealthFact {
  const base = { id: "model", label: "Model", href: "#/models", linkLabel: "Models" };
  if (view === null || !Array.isArray(view.profiles)) return { ...base, state: "unknown", detail: UNREAD };
  if (!view.current_model) {
    return {
      ...base,
      state: "fail",
      detail: view.profiles.length
        ? "No model is chosen, so Chat cannot answer. Choose one."
        : "No provider is connected, so Chat cannot answer. Add one.",
    };
  }
  return { ...base, state: "ok", detail: `${view.current_model} answers.` };
}

function machineFact(view: SetupSystemReadiness | null): HealthFact {
  // Memory and free storage, as first run measured them on this host.
  const base = { id: "disk-memory", label: "Disk and memory", href: "#/observe?tab=overview&repair=machine", linkLabel: "This machine" };
  if (view === null || !Array.isArray(view.checks)) return { ...base, state: "unknown", detail: UNREAD };
  const rows = view.checks.filter((c) => c.id === "memory" || c.id === "storage");
  if (!rows.length) return { ...base, state: "unknown", detail: UNREAD };
  const worst = rows.some((c) => c.state === "fail") ? "fail" : rows.some((c) => c.state === "warn") ? "warn" : "ok";
  const detail = rows
    .map((c) => (c.state === "fail" || c.state === "warn") && c.remedy ? `${c.label}: ${c.detail}. ${c.remedy}` : `${c.label}: ${c.detail}`)
    .join(" · ");
  return { ...base, state: worst, detail };
}

/** The facts, in the order first run sets them up. */
export function healthFacts(sources: HealthSources, now: number = Date.now()): HealthFact[] {
  const lead: HealthFact[] = [];
  if (sources.models !== undefined) lead.push(modelFact(sources.models));
  if (sources.system !== undefined) lead.push(machineFact(sources.system));
  return [
    ...lead,
    sandboxFact(sources.sandbox),
    backupFact(sources.backups, now),
    embeddingFact(sources.memory),
    voiceFact(sources.voice),
    updateFact(sources.update),
    hostFact(sources.host),
  ];
}
