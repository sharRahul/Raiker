/**
 * The Project the owner is working in, shared by Chat, Build and Design.
 *
 * VIS2-11 / COMPOSER-11 — *"switching Chat → Build → Design should retain
 * Project identity"*. Before this, each surface answered that question
 * separately: Build kept a stored id, Chat kept whichever project the current
 * conversation happened to be filed under, and Design had none at all. So
 * choosing a project in one Work mode and switching to another lost it, and the
 * owner re-chose the same boundary two or three times to do one piece of work.
 *
 * **This is deliberately not the account-level "active project" that used to
 * exist**, and the distinction is the whole reason this module is careful. That
 * value was set from the Projects page and silently changed what a turn on
 * another page retrieved — a boundary nobody had chosen at the moment it
 * applied. What is stored here is set only from a Work composer, by the owner,
 * about the work they are doing now, and it means one thing:
 *
 * > the Project a **new** piece of work starts in.
 *
 * Three rules keep that honest.
 *
 * * **It never re-files anything that already exists.** A conversation already
 *   filed under a project keeps that project. Changing this value changes where
 *   the *next* chat is filed and which boundary the *next* Build turn runs in;
 *   it does not reach backwards.
 * * **It is a starting point, not an authority.** Every surface still
 *   re-resolves the id against the owner's real projects before treating it as
 *   a boundary, so a stale or deleted id reads as "no project selected" rather
 *   than standing as one.
 * * **It is visible wherever it applies.** Each Work composer names the project
 *   in its context line, so a boundary that came from another surface is
 *   something the owner can see before they press Send — which is exactly what
 *   the old account-level value did not do.
 */

/** The one key. Kept at its original name so an existing preference survives. */
const WORK_PROJECT_KEY = "raiker.build.project";

const store = $state<{ projectId: string }>({ projectId: read() });

function read(): string {
  try {
    return window.localStorage.getItem(WORK_PROJECT_KEY) ?? "";
  } catch {
    return "";
  }
}

/**
 * The project new work starts in, or `""`.
 *
 * Svelte does not allow exporting `$derived` from a module, so this is a
 * function; callers wrap it in a one-line `$derived` to stay reactive. That
 * reactivity is the point: Chat and Build stay mounted across route visits, so
 * a project chosen in one has to reach the other without a reload.
 */
export function workProject(): string {
  return store.projectId;
}

/** Set the project new work starts in. */
export function setWorkProject(projectId: string): void {
  store.projectId = projectId;
  try {
    if (projectId === "") window.localStorage.removeItem(WORK_PROJECT_KEY);
    else window.localStorage.setItem(WORK_PROJECT_KEY, projectId);
  } catch {
    // A blocked storage is a lost preference, never a blocked turn. The value
    // still stands for this session, because the owner did choose it.
  }
}

/** Select a project and open Build in it. */
export function startInBuild(projectId: string): void {
  setWorkProject(projectId);
  window.location.hash = "#/build";
}

/** Clear the shared value. For test isolation between cases. */
export function resetWorkProject(): void {
  store.projectId = "";
  try {
    window.localStorage.removeItem(WORK_PROJECT_KEY);
  } catch {
    // Nothing to undo.
  }
}
