/**
 * The owner's timezone, as the page reads and proposes it.
 *
 * The runtime owns the clock; this module owns two smaller questions the page
 * has to answer honestly beside it.
 *
 * **What zone is actually in force, and where did it come from?** The backend's
 * precedence is explicit setting → device proposal → host → UTC, and the page
 * has to show the same answer the turn will get. Recomputing that here in
 * different words is how the settings screen ends up telling the owner one thing
 * while their turns do another, so {@link resolvedTimezone} mirrors the same
 * order over the same two keys and reports which one won.
 *
 * **What does the browser think?** A device zone is a *proposal*. It is offered
 * as a row the owner can accept, and it never writes itself over an explicit
 * choice — somebody who sets `Europe/London` and then opens Raiker from a hotel
 * in Denver has said something about their schedule, and silently rewriting it
 * would move every recurring task by seven hours to fix a problem they do not
 * have.
 */

/** The settings key holding the owner's explicit choice. Backend truth. */
export const TIMEZONE_KEY = "general.timezone";
/** The settings key holding what a browser last reported. A proposal only. */
export const DEVICE_TIMEZONE_KEY = "general.device_timezone";
/** The optional broad city/region weather falls back to. Separate on purpose. */
export const WEATHER_LOCATION_KEY = "general.weather_location";

export type TimezoneSource = "owner_setting" | "device_preference" | "host" | "fallback";

export interface ResolvedTimezone {
  zone: string;
  source: TimezoneSource;
}

/**
 * BUG-321 — zones the IANA database renamed and ICU still lists by the old name.
 *
 * Chromium answers `supportedValuesOf("timeZone")` with ICU's canonical ids, and
 * for these that is the name the place no longer uses: an owner looking for
 * Kolkata or Kyiv did not find it. Both spellings are links in zoneinfo, so the
 * server reads either; the list offers, and stores, the current one.
 */
const RENAMED_ZONES: Readonly<Record<string, string>> = {
  "Asia/Calcutta": "Asia/Kolkata",
  "Asia/Katmandu": "Asia/Kathmandu",
  "Asia/Rangoon": "Asia/Yangon",
  "Asia/Saigon": "Asia/Ho_Chi_Minh",
  "Atlantic/Faeroe": "Atlantic/Faroe",
  "America/Godthab": "America/Nuuk",
  "Europe/Kiev": "Europe/Kyiv",
  "Pacific/Enderbury": "Pacific/Kanton",
  "Pacific/Ponape": "Pacific/Pohnpei",
  "Pacific/Truk": "Pacific/Chuuk",
};

/** The current IANA name for *zone*; unchanged when it was not renamed. */
export function currentZoneName(zone: string): string {
  return RENAMED_ZONES[zone] ?? zone;
}

/** Every zone this browser knows, or a short list when it cannot enumerate them. */
export function timezoneOptions(): string[] {
  try {
    const supported = (
      Intl as unknown as { supportedValuesOf?: (key: string) => string[] }
    ).supportedValuesOf?.("timeZone");
    if (Array.isArray(supported) && supported.length > 0) {
      const current = [...new Set(supported.map(currentZoneName))].sort();
      return current.includes("UTC") ? current : ["UTC", ...current];
    }
  } catch {
    // An older engine without `supportedValuesOf` falls through to the list
    // below rather than leaving the control empty. A short honest list beats a
    // select the owner cannot use.
  }
  return [
    "UTC",
    "Europe/London",
    "Europe/Dublin",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Madrid",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Sao_Paulo",
    "Asia/Kolkata",
    "Asia/Dubai",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Australia/Sydney",
  ];
}

/** What this browser reports for the device, or null when it will not say. */
export function deviceTimezone(): string | null {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return typeof zone === "string" && zone.trim() ? currentZoneName(zone.trim()) : null;
  } catch {
    return null;
  }
}

/**
 * The zone in force for this owner, by the backend's own precedence.
 *
 * `host` is deliberately unreachable from the browser: a page cannot read the
 * server's operating-system zone, so when neither stored key holds a value the
 * page says `fallback` — which is the honest thing to say, because it does not
 * know whether the host will supply one.
 */
export function resolvedTimezone(settings: Record<string, unknown>): ResolvedTimezone {
  const owner = asZone(settings[TIMEZONE_KEY]);
  if (owner) return { zone: owner, source: "owner_setting" };
  const device = asZone(settings[DEVICE_TIMEZONE_KEY]);
  if (device) return { zone: device, source: "device_preference" };
  return { zone: "UTC", source: "fallback" };
}

/**
 * A device zone worth offering, or null.
 *
 * Null when the browser will not say, when the owner has already chosen that
 * same zone, or when there is nothing new to propose. Offering a row that
 * changes nothing is noise the owner has to read and dismiss.
 */
export function timezoneProposal(settings: Record<string, unknown>): string | null {
  const device = deviceTimezone();
  if (!device) return null;
  const current = resolvedTimezone(settings);
  return current.zone === device ? null : device;
}

/** How the owner's local time reads right now, in *zone*. Empty when unknown. */
export function localTimeIn(zone: string, at: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: zone,
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(at);
  } catch {
    return "";
  }
}

/**
 * DEC-21 — the zone's offset from UTC at `at`, as `UTC+05:30`, `UTC−04:00` or
 * `UTC`. A short zone name ("BST", "IST") is ambiguous across the world; the
 * offset is the fact a schedule is computed from, and it changes at a clock
 * change, which is why it is read for an instant rather than for the zone.
 */
export function utcOffset(zone: string, at: Date = new Date()): string {
  try {
    const part = new Intl.DateTimeFormat("en-US", {
      timeZone: zone,
      timeZoneName: "longOffset",
    })
      .formatToParts(at)
      .find((piece) => piece.type === "timeZoneName")?.value;
    if (!part) return "";
    const match = /^GMT(?:([+-\u2212])(\d{1,2})(?::(\d{2}))?)?$/.exec(part);
    if (!match) return "";
    // Engines differ on zero: some say `GMT`, others `GMT+00:00`. Both are UTC.
    if (!match[1] || (Number(match[2]) === 0 && Number(match[3] ?? 0) === 0)) return "UTC";
    const sign = match[1] === "+" ? "+" : "\u2212";
    return `UTC${sign}${match[2].padStart(2, "0")}:${match[3] ?? "00"}`;
  } catch {
    return "";
  }
}

/** Plain words for where the zone came from, for the line under the control. */
export function timezoneSourceLabel(source: TimezoneSource): string {
  switch (source) {
    case "owner_setting":
      return "You chose this.";
    case "device_preference":
      return "Proposed by this device. Choose one to make it explicit.";
    case "host":
      return "From the machine Raiker runs on.";
    default:
      return "No time zone is set, so Raiker falls back to UTC.";
  }
}

function asZone(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}
