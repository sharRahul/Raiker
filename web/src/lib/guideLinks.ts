/**
 * BUG-301 — resolve a guide chapter's own cross-references before it is rendered.
 *
 * `docs/guide/` is written as ordinary Markdown for a reader with the checkout
 * in front of them, so one chapter points at another with a relative file path:
 * `[Connecting a model](connecting-a-model.md)`. In the product that path
 * addresses nothing, and `renderMarkdown` — correctly — refuses to emit an
 * anchor for a scheme it does not recognise, so the reference rendered as its
 * own punctuation: square brackets, parentheses and a filename.
 *
 * The renderer is not the place to fix that. It draws model-authored answers
 * with the same code, and there a link is untrusted input; relaxing the scheme
 * rule for every caller would be the wrong trade for the sake of a
 * documentation link. So the reference is resolved *here*, at the guide layer,
 * where two things are true that are not true of a model answer:
 *
 * 1. The content is the product's own, shipped in the build.
 * 2. The set of addressable chapters is known — it is the guide index the page
 *    already loaded — so a target either is a chapter or is not, and nothing
 *    has to be guessed.
 *
 * What comes out is a hash address the app router already understands. The
 * renderer still has to opt in (`inAppLinks`) before it will emit one, which is
 * what keeps a model-authored answer exactly where it was.
 *
 * A `.md` reference that is *not* a chapter — `../architecture/KNOWN_LIMITS.md`
 * and its neighbours — is a repository document, and a reader inside the app
 * cannot open it however it is marked up. Those become the sentence they were
 * meant to be, with the repository path named once in plain text, rather than a
 * link that would not work or punctuation that reads as a typo.
 */

/** The address the Guide page uses for one chapter. */
export function guideSectionHref(slug: string): string {
  return `#/guide?section=${slug}`;
}

/**
 * A Markdown link target, as the guide writes them.
 *
 * Bounded deliberately: a target with a space, a parenthesis, a quote or a
 * colon is left exactly as it was, because this rewrites *relative* references
 * rather than parsing Markdown. Excluding the colon is what keeps
 * `https://example.com/a.md` — a real external link that happens to end in
 * `.md` — out of this pass entirely, so the renderer downstream still decides
 * what may become an anchor.
 */
const MD_LINK = /\[([^\]\n]*)\]\(([^()\s:]+\.md(?:#[^()\s]*)?)\)/g;

/** Turn `../architecture/KNOWN_LIMITS.md` into the path a reader would cite. */
function repositoryPath(target: string): string {
  const withoutFragment = target.split("#")[0];
  const parts = withoutFragment.split("/").filter((part) => part !== "" && part !== ".");
  const resolved: string[] = [];
  for (const part of parts) {
    if (part === "..") resolved.pop();
    else resolved.push(part);
  }
  // Every guide page lives at `docs/guide/<name>.md`, so a reference that
  // climbed out of that directory is named from `docs/`.
  return `docs/${resolved.join("/")}`;
}

/**
 * Rewrite a chapter's cross-references for the in-product Guide.
 *
 * `slugs` is the chapter set the page loaded from `/api/guide`. A target is a
 * chapter only if it names one of those, so a chapter that a build did not ship
 * is not linked to as though it had been.
 */
export function resolveGuideLinks(markdown: string, slugs: ReadonlySet<string>): string {
  return markdown.replace(MD_LINK, (_whole: string, label: string, target: string) => {
    // A sibling chapter: no directory, and a stem the index listed. An
    // intra-chapter fragment is dropped rather than carried into an address
    // that would not resolve — the Guide addresses a chapter, not a heading
    // inside one.
    const path = target.split("#")[0];
    if (!path.includes("/")) {
      const slug = path.slice(0, -".md".length).toLowerCase();
      if (slugs.has(slug)) return `[${label}](${guideSectionHref(slug)})`;
    }
    // Everything else is a repository document, which a reader inside the app
    // cannot open however it is marked up. The path is named once, in plain
    // prose: stripping it would lose the pointer, and keeping the brackets
    // would keep the defect.
    const cited = repositoryPath(target);
    const shown = label.trim() === "" ? cited : label;
    return shown === cited ? shown : `${shown} (${cited})`;
  });
}
