/**
 * Words and numbers for the llama.cpp engine panel, kept out of the Svelte
 * files so they can be tested on their own.
 *
 * Every reason code the engine, the installer, the planner and the supervisor
 * can return has an owner-facing sentence here. A code with no sentence falls
 * back to a generic one rather than showing the raw code.
 */

export type BackendId = "cuda" | "vulkan" | "metal" | "cpu";

export const BACKEND_LABELS: Record<string, string> = {
  auto: "Automatic",
  cuda: "NVIDIA CUDA",
  vulkan: "Vulkan (AMD, Intel, NVIDIA)",
  metal: "Apple Metal",
  cpu: "Processor only",
};

export function backendLabel(backend: string | null | undefined): string {
  if (!backend) return "Unknown";
  return BACKEND_LABELS[backend] ?? backend;
}

export const SLOT_STATE_LABELS: Record<string, string> = {
  starting: "Loading",
  ready: "Serving",
  unhealthy: "Not responding",
  restarting: "Restarting",
  failed: "Stopped after repeated failures",
};

export function slotStateLabel(state: string): string {
  return SLOT_STATE_LABELS[state] ?? state;
}

/** `ok`, `busy` or `bad`, for the badge colour. */
export function slotTone(state: string): "ok" | "busy" | "bad" {
  if (state === "ready") return "ok";
  if (state === "starting" || state === "restarting") return "busy";
  return "bad";
}

export const REASON_LABELS: Record<string, string> = {
  llama_server_missing: "The llama.cpp engine is not installed.",
  local_runtime_insufficient_memory:
    "Not enough free memory for this model with these settings. Close other programs, lower the context, or choose a smaller model.",
  local_runtime_out_of_memory: "The model ran out of memory while loading. Raiker retried with fewer GPU layers.",
  local_runtime_exited: "The model server stopped unexpectedly.",
  local_runtime_unresponsive: "The model server stopped answering and was restarted.",
  local_server_not_ready: "The model took too long to load.",
  local_runtime_port_in_use: "Another program is using this slot's port.",
  local_runtime_in_use: "Stop every served model before removing the engine.",
  local_runtime_slot_not_deployed: "Nothing is deployed in this slot.",
  local_runtime_restore_failed: "This model could not be started again after Raiker restarted.",
  local_model_unreadable: "The model file could not be read.",
  local_model_not_found: "The model is no longer in your library.",
  model_outside_approved_library: "The model is outside the folders you approved.",
  llama_cpp_model_unsupported: "This model needs a newer llama.cpp. Update the engine and try again.",
  llama_cpp_libraries_missing: "The engine is missing a system library. Try the processor-only engine.",
  llama_cpp_release_unreachable: "GitHub could not be reached to download llama.cpp.",
  llama_cpp_release_not_found: "That llama.cpp release does not exist.",
  llama_cpp_release_unreadable: "GitHub's answer about llama.cpp releases could not be read.",
  llama_cpp_release_unverified: "The release has no published checksum, so it was not installed.",
  llama_cpp_digest_mismatch: "The download did not match its published checksum and was discarded.",
  llama_cpp_download_failed: "The download failed. Check your connection and try again.",
  llama_cpp_download_truncated: "The download was cut short. Try again.",
  llama_cpp_download_oversize: "The download was larger than published and was discarded.",
  llama_cpp_download_host_refused: "The download was redirected somewhere other than GitHub and was refused.",
  llama_cpp_archive_unsafe: "The downloaded archive contained unsafe paths and was discarded.",
  llama_cpp_server_not_in_archive: "The download did not contain llama-server.",
  llama_cpp_install_unrunnable: "The downloaded engine could not run on this computer.",
  llama_cpp_backend_no_device: "That engine could not find a GPU it can use.",
  llama_cpp_backend_unsupported: "That engine is not available for this computer.",
  llama_cpp_asset_missing: "This release has no build for this computer.",
  llama_cpp_cuda_driver_too_old: "The NVIDIA driver is too old for CUDA builds. Update it, or use Vulkan.",
  llama_cpp_platform_unsupported: "llama.cpp has no build for this computer.",
  llama_cpp_install_in_progress: "An install is already running.",
  llama_cpp_install_failed: "The llama.cpp engine could not be installed.",
  local_model_deploy_failed: "The model could not be started.",
  host_restarted: "Raiker restarted while this was running.",
};

export function reasonLabel(code: string | null | undefined): string {
  if (!code) return "";
  return REASON_LABELS[code] ?? "Something went wrong. Open the logs for details.";
}

/** The most specific reason an operation or slot carries. */
export function operationReason(op: { error_code: string | null; error_detail: string | null }): string {
  return reasonLabel(op.error_detail ?? op.error_code);
}

const GIB = 1024 ** 3;
const MIB = 1024 ** 2;

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "unknown";
  if (bytes >= GIB) return `${(bytes / GIB).toFixed(bytes >= 10 * GIB ? 0 : 1)} GB`;
  return `${Math.max(1, Math.round(bytes / MIB))} MB`;
}

export function formatTokens(tokens: number): string {
  if (tokens >= 1024 && tokens % 1024 === 0) return `${tokens / 1024}K`;
  return tokens.toLocaleString("en-US");
}

/** "33 of 32 layers" reads wrong; a full offload says so in words. */
export function offloadLabel(plan: { gpu_layers: number; total_layers: number; full_offload: boolean; backend: string }): string {
  if (plan.backend === "cpu" || plan.gpu_layers === 0) return "Processor only";
  if (plan.full_offload) return "Entirely on the GPU";
  return `${plan.gpu_layers} of ${plan.total_layers} layers on the GPU`;
}

export const VERDICT_LABELS: Record<string, string> = {
  fits: "Fits comfortably",
  tight: "Fits, but close to the limit",
  insufficient_memory: "Does not fit in free memory",
};

export function verdictLabel(verdict: string): string {
  return VERDICT_LABELS[verdict] ?? verdict;
}

/** Fraction used, clamped to [0, 1], or null when the limit is unknown. */
export function usage(used: number, limit: number | null | undefined): number | null {
  if (limit === null || limit === undefined || limit <= 0) return used > 0 ? 1 : null;
  return Math.max(0, Math.min(1, used / limit));
}

/** Context sizes offered in the picker, up to what the model was trained on. */
export function contextChoices(trained: number | null | undefined): number[] {
  const all = [2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144];
  const limit = trained ?? 32768;
  const offered = all.filter((size) => size <= limit);
  if (trained && !offered.includes(trained)) offered.push(trained);
  return offered.length > 0 ? offered : [2048];
}

export const INSTALL_PHASES: Record<string, string> = {
  queued: "Waiting to start",
  installing_llama_cpp: "Preparing",
  resolving_llama_cpp_release: "Finding the latest release",
  downloading_llama_cpp: "Downloading",
  unpacking_llama_cpp: "Unpacking",
  verifying_llama_cpp: "Checking the engine runs",
  starting_llama_cpp: "Starting the model",
  complete: "Done",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function phaseLabel(phase: string): string {
  return INSTALL_PHASES[phase] ?? phase;
}
