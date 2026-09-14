/**
 * What an approval would actually do, read off the proposal it carries.
 *
 * REM-APPROVAL — an approval with no diff fell through to one thing: a `<pre>`
 * of `JSON.stringify(arguments)`. For a file change or a patch the page shows
 * the change itself, which is the decision; for everything else — a command, an
 * outbound request, a message, a push — the owner was handed the request body
 * and left to work out what pressing Approve would cause. A payload is evidence.
 * It is not a consequence, and it is the wrong thing to read first.
 *
 * So the salient facts are lifted out and said in words, above the payload, and
 * the payload moves below them where evidence belongs.
 *
 * Three rules this follows, and they are what keep it safe to show:
 *
 * * **It never invents.** A key that is not present produces no row. There is
 *   no "probably", no default filled in on the proposal's behalf, and no
 *   guessing at a destination from a capability name.
 * * **It never authorises.** This is presentation over a payload the server
 *   already redacted. The runtime decides what an approval permits; nothing here
 *   is read back by anything that enforces.
 * * **It never replaces the payload.** Everything it lifts is still in the
 *   arguments below it, so a reviewer who wants the exact bytes has them.
 */

/** One fact about what would happen, in the owner's words. */
export interface ConsequenceFact {
  label: string;
  value: string;
}

/** The keys worth lifting, in the order a reviewer needs them. */
const FIELDS: { keys: string[]; label: string }[] = [
  { keys: ["command", "argv", "cmd"], label: "Command" },
  { keys: ["cwd", "working_directory"], label: "Working directory" },
  { keys: ["path", "file_path", "target_path", "target"], label: "Path" },
  { keys: ["paths", "files"], label: "Paths" },
  { keys: ["url", "endpoint_url", "endpoint"], label: "Destination" },
  { keys: ["method", "http_method"], label: "Method" },
  { keys: ["host", "hostname"], label: "Host" },
  { keys: ["repository", "repo", "remote"], label: "Repository" },
  { keys: ["branch", "ref"], label: "Branch" },
  { keys: ["channel", "conversation", "recipient", "recipients", "to"], label: "Sent to" },
  { keys: ["server", "server_id"], label: "Server" },
  { keys: ["tool", "tool_name"], label: "Tool" },
  { keys: ["scope", "scopes"], label: "Scope" },
];

/** Beyond this a "fact" is a payload wearing a label. */
const MAX_VALUE_CHARS = 240;

function readable(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const parts = value
      .map((entry) => (typeof entry === "object" && entry !== null ? "" : readable(entry)))
      .filter((entry) => entry !== "");
    // An array of objects is a structure, not a sentence: it belongs in the
    // payload rather than being flattened into something that reads like prose.
    return parts.length === value.length ? parts.join(" ") : "";
  }
  return "";
}

/**
 * The facts this proposal states about its own effect.
 *
 * Empty when the arguments say nothing liftable — in which case the page says
 * so, rather than implying that an empty list means an empty consequence.
 */
export function consequenceFacts(args: Record<string, unknown> | null | undefined): ConsequenceFact[] {
  if (args === null || args === undefined) return [];
  const facts: ConsequenceFact[] = [];
  const seen = new Set<string>();
  for (const field of FIELDS) {
    for (const key of field.keys) {
      if (!(key in args) || seen.has(field.label)) continue;
      const value = readable(args[key]);
      if (value === "") continue;
      seen.add(field.label);
      facts.push({
        label: field.label,
        value: value.length > MAX_VALUE_CHARS ? `${value.slice(0, MAX_VALUE_CHARS)}…` : value,
      });
      break;
    }
  }
  return facts;
}

/**
 * The host an outbound request would reach, when the proposal names a URL.
 *
 * Said separately from the URL because it is the part that decides whether the
 * request leaves the machine, and a long URL buries it.
 */
export function destinationHost(args: Record<string, unknown> | null | undefined): string {
  if (args === null || args === undefined) return "";
  for (const key of ["url", "endpoint_url", "endpoint"]) {
    const raw = args[key];
    if (typeof raw !== "string" || raw.trim() === "") continue;
    try {
      return new URL(raw).host;
    } catch {
      // Not a URL this browser can parse. The string itself is already shown as
      // the destination; inventing a host from it would be a guess.
      return "";
    }
  }
  return "";
}
