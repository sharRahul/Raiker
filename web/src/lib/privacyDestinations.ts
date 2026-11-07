/**
 * Beta plan §6 — "What leaves this computer", as concrete destinations.
 *
 * The capability table on Privacy says what *could* leave. This says where the
 * installation is set up to send right now: each connected model whose
 * requests go off the device (by the same rule the composer uses), and the
 * update channel. A local model is listed only when its service reports a
 * remote host, or when Raiker cannot confirm where it runs.
 */
import type { ModelProfile } from "./apiTypes";
import { providerName } from "./format";
import { remoteDestinations } from "./inferenceLocation";

export interface Destination {
  key: string;
  destination: string;
  carries: string;
  where: string;
  whereLabel: string;
}

const PROMPTS = "Model prompts: your message, attachments and as much of the conversation as the turn needs.";

function hostOf(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url;
  }
}

export function configuredDestinations(
  profiles: readonly Pick<ModelProfile, "profile_id" | "provider" | "local_only" | "configured" | "connection_configured" | "model_locations">[],
  updateChannelUrl: string | null,
): Destination[] {
  // One row for every place a model prompt can go: the list is what the
  // owner reads, and one row per provider repeated the same sentence.
  const hosts: string[] = [];
  for (const profile of profiles) {
    if (!profile.configured && !profile.connection_configured) continue;
    for (const host of profile.local_only ? remoteDestinations(profile) : [providerName(profile.provider)]) {
      if (!hosts.includes(host)) hosts.push(host);
    }
  }
  const rows: Destination[] = [];
  if (hosts.length > 0) {
    rows.push({ key: "models", destination: hosts.join(", "), carries: PROMPTS, where: "#/models", whereLabel: "Models" });
  }
  if (updateChannelUrl) {
    rows.push({
      key: "updates",
      destination: hostOf(updateChannelUrl),
      carries: "Update checks: this build's version and platform. Nothing from your workspace.",
      where: "#/settings?tab=updates",
      whereLabel: "About & updates",
    });
  }
  return rows;
}
