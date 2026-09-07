/**
 * Spotting a skill link in what the owner typed.
 *
 * Chat and Build both accept free text, and a link to a published skill is a
 * thing the owner wants *installed*, not summarised. This module answers only
 * "does this text contain a link that could be a skill" — whether it really is
 * one is decided by the server, which fetches and validates the document before
 * anything is stored. Nothing here reaches the network.
 */

const SKILL_HOSTS = new Set([
  "raw.githubusercontent.com",
  "github.com",
  "gist.githubusercontent.com",
]);

const URL_PATTERN = /https:\/\/[^\s<>()[\]"']+/g;

/** True when the URL's own path names a skill document or bundle. */
function looksLikeSkill(url: URL): boolean {
  const path = url.pathname.toLowerCase();
  return (
    path.endsWith("/skill.md") ||
    path.endsWith(".skill") ||
    /(^|\/)skills?\//.test(path) ||
    path.endsWith("-skill.md")
  );
}

/**
 * Every distinct skill-looking link in `text`, in the order they appear.
 *
 * Only HTTPS links on the published-skill hosts are returned — the same host
 * list the server enforces, so the composer never offers an import the server
 * would refuse on sight.
 */
export function findSkillLinks(text: string): string[] {
  const found: string[] = [];
  for (const match of text.matchAll(URL_PATTERN)) {
    // A URL at the end of a sentence picks up its punctuation; drop it.
    const raw = match[0].replace(/[.,;:!?]+$/, "");
    let url: URL;
    try {
      url = new URL(raw);
    } catch {
      continue;
    }
    if (url.protocol !== "https:" || !SKILL_HOSTS.has(url.hostname)) continue;
    if (!looksLikeSkill(url)) continue;
    if (!found.includes(raw)) found.push(raw);
  }
  return found;
}

/** A `.skill` archive URL cannot be imported — the owner has to upload the file. */
export function isArchiveLink(url: string): boolean {
  return /\.(skill|zip)$/i.test(new URL(url).pathname);
}

/** Short label for a link, so the notice reads as a file rather than a URL. */
export function skillLinkLabel(url: string): string {
  try {
    const parts = new URL(url).pathname.split("/").filter(Boolean);
    const file = parts[parts.length - 1] ?? url;
    // `.../my-skill/SKILL.md` is better named by its folder than by SKILL.md.
    if (file.toLowerCase() === "skill.md" && parts.length > 1) return parts[parts.length - 2];
    return file;
  } catch {
    return url;
  }
}
