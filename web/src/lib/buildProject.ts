/**
 * Build's selected project — the one piece of shared state behind it.
 *
 * Build's project is not a preference about presentation; it is the execution
 * and retrieval boundary the turn runs inside, and it is carried on every turn
 * rather than read from the server. It still has to survive leaving the route,
 * and Projects has to be able to hand Build a project through "Start in Build",
 * so exactly one key is written and both views go through here rather than
 * agreeing on a string literal in two places.
 *
 * This deliberately replaces the account-level "active project": that value was
 * set from one page and silently changed what a turn on another page retrieved.
 * A stored id here means "the project Build opens with", nothing more — Build
 * still re-resolves it against the owner's real projects before treating it as a
 * boundary, so a stale id reads as "no project selected" rather than standing.
 */
const BUILD_PROJECT_KEY = "raiker.build.project";

export function readBuildProject(): string {
  try {
    return window.localStorage.getItem(BUILD_PROJECT_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberBuildProject(projectId: string): void {
  try {
    if (projectId === "") window.localStorage.removeItem(BUILD_PROJECT_KEY);
    else window.localStorage.setItem(BUILD_PROJECT_KEY, projectId);
  } catch {
    // A blocked storage is a lost preference, never a blocked turn.
  }
}

/** Select a project for Build and open it there. */
export function startInBuild(projectId: string): void {
  rememberBuildProject(projectId);
  window.location.hash = "#/build";
}
