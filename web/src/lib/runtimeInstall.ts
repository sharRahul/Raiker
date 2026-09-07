/**
 * Opening a local runtime's official installer, from one place.
 *
 * BUG-270 gave Raiker a detector for the runtimes a profile depends on, so a
 * provider card can now say "Not installed on this machine". Saying it is only
 * half of an answer: the owner then has to find the install panel further up
 * the page and work out which card corresponds to the row that told them. The
 * row offers the setup itself, and this is the path it and the install panel
 * both take.
 *
 * **The `https://` check is the reason this is shared rather than copied.** The
 * plan comes from the server, and `window.open` on whatever it returns is the
 * one line here that could matter; two copies of it is one copy that can drift.
 * The scheme is checked at the point of use, not at the point of fetch, so no
 * caller can bypass it by holding a plan.
 *
 * Nothing is downloaded or executed by Raiker: the plan names a vendor URL,
 * this opens it, and the owner accepts that vendor's terms themselves.
 */
import { api } from "./api";
import type { RuntimeInstallPlan } from "./apiTypes";

/**
 * Which runtime installer a profile's provider needs, or absent when that
 * provider has none.
 *
 * The keys are the `provider` field a model profile carries and the values are
 * the runtime ids `RuntimeInstallerRegistry` knows. A provider missing here is
 * one Raiker has no reviewed vendor source for — MLX ships with its own
 * toolchain, vLLM is a Python package — so no setup is offered for it rather
 * than a button that would fail.
 */
export const INSTALLER_RUNTIME_BY_PROVIDER: Record<string, string> = {
  ollama: "ollama",
  "llama.cpp": "llama.cpp",
  "lm-studio": "lm-studio-desktop",
};

/** The runtime installer for `provider`, or null when there is none. */
export function installerRuntimeFor(provider: string): string | null {
  return INSTALLER_RUNTIME_BY_PROVIDER[provider] ?? null;
}

/**
 * Open the reviewed vendor download for `runtime` in a new tab.
 *
 * Throws when the server's plan does not name an `https://` source, so a
 * caller's catch is what the owner sees rather than a navigation nobody
 * checked.
 */
export async function openRuntimeInstaller(runtime: string): Promise<void> {
  const plan = (await api.previewModelOperation("install", runtime)) as RuntimeInstallPlan;
  if (!plan.source_url.startsWith("https://")) throw new Error("unsafe source");
  window.open(plan.source_url, "_blank", "noopener,noreferrer");
}
