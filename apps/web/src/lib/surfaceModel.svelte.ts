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

export type Surface = "chat" | "build" | "tasks" | "schedule";

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
