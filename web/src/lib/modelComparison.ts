/*
 * UX-MODEL-04 — the models an owner has, as one comparable table.
 *
 * Cost, context, privacy and tool support were spread across the Overview, the
 * per-model details, Usage and the provider cards, so choosing between two
 * models meant opening each and remembering what the last one said. DEC-08
 * step 4 asks for one projection: locality, context, tools, vision, estimated
 * cost and availability, with one rule over all of it — **an unknown fact
 * renders Unknown, never a guessed default.** That is why every field here
 * keeps `null` distinct from `false` and from zero: a profile that declares
 * nothing about vision is Unknown, not No; a price no source names is Unknown,
 * not free.
 *
 * A plain module rather than component code because each column is a claim, and
 * each claim is tested on its own.
 */
import type { ModelProfile } from "./apiTypes";
import { readinessLabel, UNPINNED_MODEL } from "./modelReadinessLabels";

export const UNKNOWN = "Unknown";

export type Locality = "On this device" | "Private server" | "Hosted service" | typeof UNKNOWN;

export interface ComparisonRow {
  key: string;
  profile: ModelProfile;
  locality: Locality;
  /** Whether the prompt leaves this machine, said in the row's own words. */
  leavesDevice: boolean | null;
  context: string;
  tools: string;
  vision: string;
  cost: string;
  availability: string;
  ready: boolean;
}

/** Where a turn on this model runs — the question DEC-08 asks first. */
export function localityOf(profile: ModelProfile): Locality {
  if (profile.local_only || profile.endpoint_kind === "local_process" || profile.endpoint_kind === "loopback") {
    return "On this device";
  }
  if (profile.endpoint_kind === "private_network") return "Private server";
  if (profile.endpoint_kind === "remote_hosted" || profile.endpoint_kind === "hosted") {
    return "Hosted service";
  }
  return UNKNOWN;
}

/** "200k tokens", or Unknown when no source states a window. */
export function contextOf(profile: ModelProfile): string {
  const tokens = profile.context_window_tokens;
  if (tokens === null || tokens === undefined || tokens <= 0) return UNKNOWN;
  if (tokens >= 1_000_000) {
    const millions = tokens / 1_000_000;
    return `${Number.isInteger(millions) ? millions : millions.toFixed(1)}M tokens`;
  }
  return `${Math.round(tokens / 1000)}k tokens`;
}

/** Yes, No, or Unknown — a declared absence and a silence are different facts. */
export function declared(value: boolean | null | undefined): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return UNKNOWN;
}

function money(amount: string, currency: string | null): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount;
  const symbol = currency === null || currency === "USD" ? "$" : `${currency} `;
  return `${symbol}${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 3,
  })}`;
}

/**
 * The list rate, per million tokens in and out.
 *
 * A model that runs here has no API bill, which is a fact, not an absence of
 * one. A hosted model with no stated rate is Unknown — printing $0 would tell
 * the owner the expensive option is free.
 */
export function costOf(profile: ModelProfile): string {
  if (profile.rate_input_per_mtok !== null && profile.rate_output_per_mtok !== null) {
    return `${money(profile.rate_input_per_mtok, profile.rate_currency)} in · ${money(
      profile.rate_output_per_mtok,
      profile.rate_currency,
    )} out per 1M tokens`;
  }
  if (!profile.billable && localityOf(profile) === "On this device") return "No API cost";
  return UNKNOWN;
}

/** The readiness the gate measured, in the words every other surface uses. */
export function availabilityOf(profile: ModelProfile): string {
  if (profile.ready) return "Ready";
  return readinessLabel(profile.readiness_state) ?? "Not checked";
}

/**
 * Whether a profile is a model this owner has set up: it names a model that
 * exists here (`configured`) and, if it runs off this machine, the owner has
 * connected the account. A managed slot with nothing deployed, a hosted
 * provider never connected, or a profile still waiting for a model would only
 * be a row of Unknowns about something they could not pick.
 *
 * Deliberately not `isChoosableModel`: that also drops a model whose check
 * answered badly, and the comparison has an Availability column precisely so a
 * stopped runtime or an exhausted quota can be seen beside the alternatives.
 */
export function isComparable(profile: ModelProfile): boolean {
  if (profile.configured === false) return false;
  if (profile.off_machine && profile.connection_configured !== true) return false;
  return profile.model !== "" && profile.model !== UNPINNED_MODEL && !profile.model.includes("<");
}

/** One row per model the owner has set up, ready ones first, then by name. */
export function comparisonRows(profiles: ModelProfile[]): ComparisonRow[] {
  return profiles
    .filter(isComparable)
    .map((profile) => {
      const locality = localityOf(profile);
      return {
        key: `${profile.profile_id}\u0000${profile.model}`,
        profile,
        locality,
        leavesDevice:
          locality === UNKNOWN ? null : locality !== "On this device",
        context: contextOf(profile),
        tools: declared(profile.supports_tool_calls),
        vision: declared(profile.supports_vision),
        cost: costOf(profile),
        availability: availabilityOf(profile),
        ready: profile.ready,
      };
    })
    .sort(
      (left, right) =>
        Number(right.ready) - Number(left.ready) ||
        left.profile.model.localeCompare(right.profile.model),
    );
}
