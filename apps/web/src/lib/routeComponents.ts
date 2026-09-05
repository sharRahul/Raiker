import type { Component } from "svelte";

/**
 * Route-level code splitting for the secondary destinations (BUG-74).
 *
 * The production build put every view in one chunk — about 690 kB, above Vite's
 * 500 kB warning — so opening Chat paid to parse the Knowledge Map's force
 * simulation, the Models acquisition panels and the whole of Settings. That is
 * not a correctness failure, but it is real download and parse cost on a
 * lower-powered device.
 *
 * The split is deliberate about *where*. The first-paint surfaces — Workbench,
 * Chat and Build — stay statically imported, because they are what a session
 * opens with and Chat and Build additionally stay mounted across route visits
 * to keep their transcripts alive. Everything else loads on demand.
 *
 * No-flash navigation is preserved two ways: every loaded module is cached, so
 * a second visit to a route resolves synchronously; and `prefetchRoutes()` warms
 * the whole map when the browser is next idle after sign-in, so in practice the
 * first visit is synchronous too. The dynamic `import()` calls below are static
 * string literals rather than a computed path, which is what lets the bundler
 * emit one stable chunk per route.
 */
export type LazyRouteId =
  | "search-chat"
  | "memory"
  | "approvals"
  | "tasks"
  | "brain"
  | "sessions"
  | "projects"
  | "capabilities"
  | "models"
  | "extensions"
  | "messaging"
  | "observe"
  | "settings"
  | "guide"
  | "model-setup";

// The props each route takes differ, so the map is typed at the loosest shape
// that still guarantees a Svelte component: App passes the same props it always
// did, and `svelte-check` still checks them at each call site.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type RouteComponent = Component<any, any, any>;
type Loader = () => Promise<{ default: RouteComponent }>;

const LOADERS: Record<LazyRouteId, Loader> = {
  "search-chat": () => import("./views/SearchChatView.svelte"),
  guide: () => import("./views/GuideView.svelte"),
  memory: () => import("./views/MemoryView.svelte"),
  approvals: () => import("./views/ApprovalsView.svelte"),
  tasks: () => import("./views/TasksView.svelte"),
  brain: () => import("./views/BrainView.svelte"),
  sessions: () => import("./views/SessionsView.svelte"),
  projects: () => import("./views/ProjectsView.svelte"),
  capabilities: () => import("./views/CapabilitiesView.svelte"),
  models: () => import("./views/ModelsView.svelte"),
  extensions: () => import("./views/ExtensionsView.svelte"),
  messaging: () => import("./views/MessagingView.svelte"),
  observe: () => import("./views/ObserveView.svelte"),
  settings: () => import("./views/SettingsView.svelte"),
  "model-setup": () => import("./views/ModelSetupView.svelte"),
};

const cache = new Map<LazyRouteId, RouteComponent>();
const inFlight = new Map<LazyRouteId, Promise<RouteComponent>>();

/** The component if it is already loaded, else `null`. Never triggers a load. */
export function peekRoute(route: LazyRouteId): RouteComponent | null {
  return cache.get(route) ?? null;
}

/** Load one route's component, de-duplicating concurrent requests. */
export function loadRoute(route: LazyRouteId): Promise<RouteComponent> {
  const cached = cache.get(route);
  if (cached !== undefined) return Promise.resolve(cached);
  const pending = inFlight.get(route);
  if (pending !== undefined) return pending;
  const promise = LOADERS[route]()
    .then((module) => {
      cache.set(route, module.default);
      inFlight.delete(route);
      return module.default;
    })
    .catch((error: unknown) => {
      inFlight.delete(route);
      throw error;
    });
  inFlight.set(route, promise);
  return promise;
}

/**
 * Warm every route chunk when the browser is next idle.
 *
 * This is what keeps navigation feeling identical to the single-chunk build:
 * the cost moves off the critical path rather than onto the first click. A
 * chunk that fails to prefetch is simply not cached — the route loads it again
 * on demand and reports its own failure there.
 */
export function prefetchRoutes(): void {
  if (typeof window === "undefined") return;
  const warm = () => {
    for (const route of Object.keys(LOADERS) as LazyRouteId[]) {
      void loadRoute(route).catch(() => undefined);
    }
  };
  const idle = (window as unknown as { requestIdleCallback?: (cb: () => void) => number })
    .requestIdleCallback;
  if (typeof idle === "function") idle(warm);
  else window.setTimeout(warm, 1_000);
}
