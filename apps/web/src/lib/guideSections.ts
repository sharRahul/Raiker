/**
 * Which guide section explains which surface (BUG-208 slice B).
 *
 * One map, so a page's "How this works" and any future contextual link resolve
 * to the same place, and so a guide section that gets renamed breaks in one
 * file rather than in fifteen templates.
 *
 * `label` is the whole link text rather than a noun slotted into a template.
 * A template produced "How projects works": the subjects are a mix of singular
 * and plural, and a sentence that reads wrong on a page header is not worth the
 * one line it saves. Each label also names the topic rather than the page — a
 * reader on Models wants "connecting a model", not "Models".
 */
export interface GuideTarget {
  slug: string;
  label: string;
}

const SECTIONS: Record<string, GuideTarget> = {
  models: { slug: "connecting-a-model", label: "How connecting a model works" },
  capabilities: { slug: "permissions-and-runtime-modes", label: "How permissions work" },
  approvals: { slug: "permissions-and-runtime-modes", label: "How approvals work" },
  projects: { slug: "tasks-and-projects", label: "How projects work" },
  tasks: { slug: "tasks-and-projects", label: "How tasks work" },
  extensions: { slug: "extensions-and-mcp", label: "How extensions work" },
  connections: { slug: "extensions-and-mcp", label: "How connectors work" },
  "new-chat": { slug: "working-in-chat", label: "How Chat works" },
  "search-chat": { slug: "working-in-chat", label: "How chat history works" },
  checkpoints: { slug: "permissions-and-runtime-modes", label: "How checkpoints work" },
  observe: { slug: "troubleshooting", label: "How to read the record" },
  diagnostics: { slug: "troubleshooting", label: "How diagnostics work" },
  settings: { slug: "permissions-and-runtime-modes", label: "How the runtime works" },
  // Two surfaces that carried standing explanation on the page itself. The
  // explanation is the same on every visit and is read once, so it moved to the
  // guide — which only works if the page can reach it.
  home: { slug: "tasks-and-projects", label: "How the work board works" },
  memory: { slug: "working-in-chat", label: "How memory and recall work" },
};

/** The guide target for a route, or null when the guide does not cover it yet. */
export function guideSectionFor(route: string): GuideTarget | null {
  return SECTIONS[route] ?? null;
}

/** Every route the guide covers — the fixture the mapping test reads. */
export function mappedRoutes(): string[] {
  return Object.keys(SECTIONS);
}
