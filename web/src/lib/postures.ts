/**
 * RU-07 — three postures, each a documented bundle of decision modes.
 *
 * A posture changes only *whether Raiker asks*, never *what is turned on*: it
 * sets the decision mode of permissions that are already available, through
 * the same per-capability route a row's own mode control uses, so audit and
 * enforcement are unchanged. Turning a permission on stays its own decision.
 *
 * - **Ask first** — every available permission asks. Today's baseline.
 * - **Work in the sandbox** — changing files in the disposable copy and running
 *   commands in the command sandbox go ahead without a prompt. Anything that
 *   leaves the copy or the machine, writes durable memory, sends a message,
 *   pushes or spends money still asks. Offered only while the command sandbox
 *   is fully enforced; otherwise the owner stays on Ask first.
 * - **Read-only** — everything that changes files, memory, git, runs a
 *   program, sends a message or installs something is set to Never; reading
 *   still asks.
 */
import type { CapabilityGate, CommandSandboxView } from "./apiTypes";

export type PostureId = "ask" | "sandbox" | "read_only";
export type PostureMode = "ask" | "allow" | "deny";

/** Changes that stay inside the disposable copy or the command sandbox. */
export const SANDBOX_ALLOWED: readonly string[] = [
  "file_write_execution",
  "patch_apply_execution",
  "checkpoint_restore_execution",
  "shell_execution",
  "process_execution",
];

/** Everything Read-only refuses: a change to something, or an act on someone's behalf. */
export const READ_ONLY_DENIED: readonly string[] = [
  "file_write_execution",
  "patch_apply_execution",
  "checkpoint_restore_execution",
  "memory_write_execution",
  "memory_forget_execution",
  "semantic_memory_writes",
  "git_write_execution",
  "git_push_execution",
  "shell_execution",
  "process_execution",
  "host_network_code_execution",
  "remote_execution_cap",
  "cloud_execution_cap",
  "scheduled_routines",
  "external_channel_runtime",
  "email_runtime",
  "calendar_runtime",
  "plugin_install",
  "plugin_execution_cap",
  "image_generation",
  "telemetry_export",
];

export const POSTURES: readonly { id: PostureId; label: string; summary: string }[] = [
  {
    id: "ask",
    label: "Ask first",
    summary: "Raiker asks before using any permission.",
  },
  {
    id: "sandbox",
    label: "Work in the sandbox",
    summary:
      "File changes in the disposable copy and commands in the sandbox go ahead; pushing, sending, memory and anything that leaves this machine still ask.",
  },
  {
    id: "read_only",
    label: "Read-only",
    summary: "Raiker can read and answer but never changes files, memory or git, runs programs or sends anything.",
  },
];

/** The mode a posture gives one capability. */
export function postureMode(posture: PostureId, capability: string): PostureMode {
  if (posture === "sandbox" && SANDBOX_ALLOWED.includes(capability)) return "allow";
  if (posture === "read_only" && READ_ONLY_DENIED.includes(capability)) return "deny";
  return "ask";
}

/** Gates a posture may set: they report a decision mode. */
function settable(gates: CapabilityGate[]): CapabilityGate[] {
  return gates.filter((gate) => typeof gate.decision_mode === "string" && gate.decision_mode !== "");
}

/** What applying a posture would change: one entry per capability whose mode differs. */
export function postureChanges(
  posture: PostureId,
  gates: CapabilityGate[],
): { capability: string; from: string; to: PostureMode }[] {
  return settable(gates)
    .map((gate) => ({ capability: gate.capability, from: gate.decision_mode as string, to: postureMode(posture, gate.capability) }))
    .filter((change) => change.from !== change.to);
}

/** The posture the current modes match exactly, or `custom` when none does. */
export function currentPosture(gates: CapabilityGate[]): PostureId | "custom" {
  const rows = settable(gates);
  if (rows.length === 0) return "custom";
  for (const { id } of POSTURES) {
    if (postureChanges(id, rows).length === 0) return id;
  }
  return "custom";
}

/**
 * Whether the command sandbox is fully enforced, so *Work in the sandbox* may
 * be offered. Unread is not enforced.
 */
export function sandboxEnforced(view: CommandSandboxView | null): boolean {
  if (view === null) return false;
  if (!view.applies) return true;
  return view.windows_backend === "wsl" && view.wsl_configured;
}
