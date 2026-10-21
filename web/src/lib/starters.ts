/**
 * QUI-W05 / QUI-H02 / QUI-C10 — the four ways to start, one per kind of work.
 *
 * The same four everywhere they appear (Home on a first day, an empty Chat), so
 * the product gives one answer to "what can I do here". A starter that is a
 * question fills the composer for the owner to edit and send; it never sends on
 * its own. Build and Design are places, so their starters open them.
 */
import type { IconName } from "./icons";

export type Starter =
  | { readonly id: string; readonly label: string; readonly icon: IconName; readonly kind: "prompt"; readonly prompt: string }
  | { readonly id: string; readonly label: string; readonly icon: IconName; readonly kind: "route"; readonly href: string };

export const STARTERS: readonly Starter[] = [
  {
    id: "summarise",
    label: "Summarise a document",
    icon: "chat",
    kind: "prompt",
    prompt: "Summarise the document I attach in five bullet points.",
  },
  {
    id: "plan-week",
    label: "Plan my week",
    icon: "tasks",
    kind: "prompt",
    prompt: "Help me plan my week. Ask me what is already on before you suggest anything.",
  },
  { id: "fix-bug", label: "Fix a bug in a repository", icon: "code", kind: "route", href: "#/build" },
  { id: "make-image", label: "Make an image", icon: "design", kind: "route", href: "#/design" },
];
