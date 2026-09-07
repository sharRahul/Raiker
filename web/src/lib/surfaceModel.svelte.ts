// A default model per work surface.
//
// Raiker had a global default and a model captured on an individual task.
// Neither expressed "Chat on the small local model, Build on the big one": the
// per-turn picker was view state that reset on every reload, so both surfaces
// silently fell back to the same global choice.
//
// This is a *preference*. It decides where a surface's picker starts; the turn
// it produces still names an exact profile and model, and the readiness gate
// judges that pair on its own evidence. Remembering a choice can never make an
// unproven model runnable.
//
// Deliberately stateless. An earlier version cached the read across surfaces to
// save a request; a surface then wrote its own choice into that shared object,
// so one surface's pick could surface as another's default. Two small reads per
// page load are not worth a shared mutable cache.
import { api } from "./api";
import type { ModelDecision } from "./apiTypes";

/**
 * The surfaces that may hold a default of their own.
 *
 * MODEL-02 — `design` was missing while the product model was Chat | Build |
 * Design, so an owner who put Chat on a small local model had their image
 * prompts follow it there. The union mirrors `raiker.models.decision.SURFACES`
 * exactly; a surface added on one side and not the other is the same defect.
 */
export type Surface = "chat" | "build" | "design" | "tasks" | "schedule";

/** The three Work modes, which are the surfaces a person switches between. */
export const WORK_SURFACES: readonly Surface[] = ["chat", "build", "design"];

export interface SurfaceModel {
  profileId: string;
  model: string;
}

/** The surface's remembered model, or null when it has no opinion of its own. */
export async function surfaceModel(
  surface: Surface,
): Promise<SurfaceModel | null> {
  try {
    const body = await api.surfaceModels();
    const found = body.surfaces[surface];
    return found?.profile_id && found.model
      ? { profileId: found.profile_id, model: found.model }
      : null;
  } catch {
    // No stored preference is the same outcome as an unreadable one: the
    // surface falls back to the global model rather than failing to load.
    return null;
  }
}

/**
 * Remember this surface's model. A partial choice is never stored: an empty
 * profile or model means "no opinion", and writing that would clear a default
 * the owner did not ask to clear.
 */
export async function rememberSurfaceModel(
  surface: Surface,
  profileId: string,
  model: string,
): Promise<void> {
  if (!profileId || !model) return;
  try {
    await api.setSurfaceModel(surface, profileId, model);
  } catch {
    // A preference that fails to persist must not interrupt the work the owner
    // came to do; the picker keeps the choice for this page load.
  }
}

/**
 * MODEL-01 — the authoritative decision for this surface.
 *
 * `surfaceModel()` above answers "where should the picker start", which is a
 * preference. This answers the harder question the interface actually has to
 * render: what is selected, what will really run, is it ready, and if not, what
 * fixes it. Every surface reads the same one, so the Models page and the
 * composer cannot disagree about which model is in force.
 *
 * A failed read returns null rather than throwing: a composer that will not
 * render is worse for the owner than a composer without the explanatory line.
 */
export async function modelDecision(
  surface: Surface,
  projectId?: string,
): Promise<ModelDecision | null> {
  try {
    const body = await api.modelDecision(surface, projectId);
    return isModelDecision(body) ? body : null;
  } catch {
    return null;
  }
}

/**
 * Whether a body really is a decision, before any surface renders from it.
 *
 * Found by the mocked end-to-end fixture, which answers an unrouted path with
 * `{}` and HTTP 200 — and the composer's model picker then read
 * `decision.selected.profile_id` off it and took the page down. The fixture is
 * artificial; the failure it produced is not. A truncated body, a proxy's error
 * page served as JSON, a version skew between a running host and a newer build
 * all arrive the same way: a 200 whose shape is wrong.
 *
 * A read model exists so that every surface can trust one answer. That is only
 * true if the answer is checked once, here, rather than by each caller
 * remembering to guard the field it happens to use — the guard that is missed
 * is the one that throws. A body that does not carry the contract is not a
 * degraded decision, it is no decision, and the surfaces already render
 * correctly without one.
 */
export function isModelDecision(value: unknown): value is ModelDecision {
  if (value === null || typeof value !== "object") return false;
  const body = value as Partial<ModelDecision>;
  const pair = (part: unknown) =>
    part !== null &&
    typeof part === "object" &&
    typeof (part as { profile_id?: unknown }).profile_id === "string" &&
    typeof (part as { model?: unknown }).model === "string";
  return pair(body.selected) && pair(body.effective) && typeof body.ready === "boolean";
}

/**
 * Every surface's decision, keyed by surface, or null when the read failed or
 * answered with something that is not one.
 */
export async function modelDecisions(): Promise<Record<string, ModelDecision> | null> {
  try {
    const body = await api.modelDecisions();
    const surfaces = body?.surfaces;
    if (surfaces === null || typeof surfaces !== "object") return null;
    const checked = Object.entries(surfaces).filter(([, value]) => isModelDecision(value));
    return checked.length > 0 ? Object.fromEntries(checked) : null;
  } catch {
    return null;
  }
}
