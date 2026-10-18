/**
 * BUG-340 — where a model's requests are processed, said once for every surface.
 *
 * A runtime on this machine is not the same claim as a model on this machine:
 * Ollama lists its cloud models beside its local ones, and a prompt sent to
 * `gpt-oss:20b-cloud` leaves the device for ollama.com. Device-only wording is
 * therefore earned per model, from the service's own answer
 * (`model_locations`, read from Ollama's `remote_host`), and a model the
 * service did not describe is said to be unverified rather than assumed local.
 */
import type { ModelProfile } from "./apiTypes";
import { providerName } from "./format";

export type InferenceLocation =
  | { kind: "device" }
  | { kind: "remote"; destination: string }
  | { kind: "unknown" };

/** True when a model's own name says it runs in a provider's cloud. */
function namedCloud(model: string): boolean {
  const lowered = model.trim().toLowerCase();
  return lowered.endsWith("-cloud") || lowered.endsWith(":cloud");
}

/** Where `model`, served through `profile`, is processed. */
export function inferenceLocation(
  profile: Pick<ModelProfile, "provider" | "local_only"> &
    Partial<Pick<ModelProfile, "model_locations">>,
  model: string,
): InferenceLocation {
  if (!profile.local_only) return { kind: "remote", destination: providerName(profile.provider) };
  const located = profile.model_locations?.[model];
  if (located === "device") return { kind: "device" };
  if (located) return { kind: "remote", destination: located };
  // Not described by the running service. A name that says Cloud is enough to
  // withhold the device claim; anything else is unverified, not local.
  if (namedCloud(model)) return { kind: "remote", destination: "ollama.com" };
  return { kind: "unknown" };
}

/** One sentence naming where a chosen model's requests go. */
export function inferenceSentence(location: InferenceLocation): string {
  if (location.kind === "device") return "It runs on this device; its requests do not leave it.";
  if (location.kind === "remote") return `Its requests are sent to ${location.destination}, off this device.`;
  return "Raiker cannot confirm where it runs, so treat its requests as leaving this device.";
}

/**
 * The remote hosts a local runtime's served models reach, de-duplicated.
 * Empty when every model it describes runs on this device.
 */
export function remoteDestinations(
  profile: Partial<Pick<ModelProfile, "model_locations">>,
): string[] {
  const hosts = Object.values(profile.model_locations ?? {}).filter((where) => where !== "device");
  return [...new Set(hosts)];
}
