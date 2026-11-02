/**
 * Beta feedback: a prefilled GitHub issue, written by the owner, sent by them.
 *
 * Raiker sends nothing itself. These helpers build the link to one of the
 * repository's issue forms (`.github/ISSUE_TEMPLATE/`), filled in with what a
 * maintainer needs first — which build, which operating system, which area —
 * and nothing that identifies the owner or their work. The owner reads the form
 * in their own browser and decides whether to submit it.
 *
 * The redacted support bundle is never put into the link. It is offered
 * separately, copied to the clipboard on request, for the owner to paste if they
 * choose: a URL is logged by browsers and proxies, and an issue body is public.
 */

export const REPOSITORY_URL = "https://github.com/sharRahul/Raiker";

export type FeedbackKind = "bug" | "feedback";

/** The issue form each kind opens; the file names in `.github/ISSUE_TEMPLATE/`. */
export const ISSUE_FORMS: Record<FeedbackKind, string> = {
  bug: "beta-bug.yml",
  feedback: "beta-feedback.yml",
};

/** The `area` dropdown's options, in the order the issue forms list them. */
export const FEEDBACK_AREAS = [
  "Installation or updates",
  "Chat",
  "Build",
  "Design",
  "Models and local AI",
  "Voice",
  "Tasks and schedule",
  "Memory",
  "Extensions and connections",
  "Permissions and sandbox",
  "Settings",
  "Other",
] as const;

export type FeedbackArea = (typeof FEEDBACK_AREAS)[number];

export interface FeedbackEnvironment {
  /** The host's build, as Settings → Updates writes it. */
  host: string;
  /** The page's own bundle, when it differs from the host. */
  client: string;
  /** A coarse operating-system name, never the full user-agent string. */
  os: string;
}

/**
 * A coarse operating system from what the browser reports.
 *
 * Deliberately coarse: "Windows", "macOS", "Linux". A full user-agent string
 * carries versions and engine details that add little to a first report and
 * are fingerprint material in a public issue.
 */
export function detectOs(nav: { userAgent?: string; platform?: string } | undefined = globalThis.navigator): string {
  const text = `${nav?.platform ?? ""} ${nav?.userAgent ?? ""}`.toLowerCase();
  if (text.includes("win")) return "Windows";
  if (text.includes("mac") || text.includes("darwin")) return "macOS";
  if (text.includes("android")) return "Android";
  if (text.includes("iphone") || text.includes("ipad")) return "iOS";
  if (text.includes("linux") || text.includes("x11")) return "Linux";
  return "Unknown";
}

/** Bounded so a link stays well under the length browsers and GitHub accept. */
const MAX_FIELD = 300;

function clip(value: string): string {
  return value.length > MAX_FIELD ? `${value.slice(0, MAX_FIELD - 1)}…` : value;
}

/**
 * The link to a prefilled issue form.
 *
 * Field names are the `id`s declared in the issue forms; GitHub fills a field
 * from a query parameter of the same name. Only `https://github.com/…` is ever
 * produced, so a caller can open it without further checks.
 */
export function issueUrl(
  kind: FeedbackKind,
  environment: FeedbackEnvironment,
  options: { area?: FeedbackArea; title?: string } = {},
): string {
  const params = new URLSearchParams();
  params.set("template", ISSUE_FORMS[kind]);
  params.set("labels", kind === "bug" ? "beta,bug" : "beta,feedback");
  if (options.title) params.set("title", clip(options.title));
  const build =
    environment.client && environment.client !== environment.host
      ? `${environment.host} (page ${environment.client})`
      : environment.host;
  params.set("version", clip(build));
  params.set("os", clip(environment.os));
  if (options.area) params.set("area", options.area);
  return `${REPOSITORY_URL}/issues/new?${params.toString()}`;
}
