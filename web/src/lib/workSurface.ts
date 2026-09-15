/*
 * The shared Work contract.
 *
 * Chat, Build and Design have to feel like one product without becoming one
 * layout. The review states the rule in one line — *shared controls should look
 * related; primary workspaces should look purpose-built* — and the failure mode
 * it warns against is solving consistency by pushing every surface toward the
 * same shape, which is how Design became a third chat screen in the first
 * place.
 *
 * So the contract is written down here, in two halves that are deliberately
 * different kinds of thing:
 *
 * `SHARED_WORK_CONTRACT` is what every Work mode owes the owner whatever it is
 * about — the same answers to *which project, which model, what posture, how do
 * I bring something in, how do I stop a running turn, how do I find a command,
 * what does loading or a refusal look like*. A mode that drops one of these has
 * not specialised, it has simply lost an answer the owner needs.
 *
 * `WORK_SURFACES` is what each mode is *about*, and is where the three are
 * required to differ. The primary object decides the shape of the main region,
 * and density decides how tightly it packs: a conversation is read, a workbench
 * is scanned, a canvas is looked at. Two modes claiming the same object would
 * mean one of them has no reason to exist as a separate mode — which is exactly
 * what `workSurface.test.ts` refuses.
 */

import type { IconName } from "./icons";

export const WORK_MODES = ["chat", "build", "design"] as const;
export type WorkMode = (typeof WORK_MODES)[number];

/**
 * The answers every Work mode owes, in the order an owner needs them: what this
 * turn runs inside, what will answer it, what it is allowed to do, how to add
 * to it, how to stop it, how to find the rest, and what it looks like while it
 * is working or when it refuses.
 */
export const SHARED_WORK_CONTRACT = [
  "project",
  "model",
  "posture",
  "attachments",
  "turn-control",
  "palette",
  "states",
] as const;
export type WorkContractTerm = (typeof SHARED_WORK_CONTRACT)[number];

/** How tightly a surface packs what it holds. */
export type WorkDensity = "low" | "high" | "spatial";

export interface WorkSurface {
  mode: WorkMode;
  /** The thing the surface is about — what fills its main region. */
  primaryObject: string;
  /** What sits beside the object, in the order this mode puts it. */
  secondaryContext: readonly string[];
  /** Low reads, high is scanned, spatial is looked at. */
  density: WorkDensity;
}

export const WORK_SURFACES: Record<WorkMode, WorkSurface> = {
  chat: {
    mode: "chat",
    primaryObject: "conversation",
    secondaryContext: ["sources", "files", "memory"],
    density: "low",
  },
  build: {
    mode: "build",
    primaryObject: "change",
    secondaryContext: ["repository", "plan", "terminal"],
    density: "high",
  },
  design: {
    mode: "design",
    primaryObject: "asset",
    secondaryContext: ["research", "history"],
    density: "spatial",
  },
};

export function workSurface(mode: WorkMode): WorkSurface {
  return WORK_SURFACES[mode];
}

/**
 * The gap a surface puts between the things it holds.
 *
 * Density is a real dimension rather than a label: a transcript wants air
 * between turns because it is read in order, a workbench wants none because its
 * panes are scanned together, and a canvas wants the middle because the object
 * needs room around it to be looked at. One token, so the three cannot drift
 * into each other's spacing by accident.
 */
export function densityGap(density: WorkDensity): string {
  switch (density) {
    case "high":
      return "var(--space-2)";
    case "spatial":
      return "var(--space-4)";
    default:
      return "var(--space-5)";
  }
}

/**
 * How a Work mode is offered as a place to start.
 *
 * Home listed Chat and Build beside Tasks and Projects, and left Design out
 * entirely — so the shell said three peer Work modes and the first screen an
 * owner sees said two. Both now read the same list, and each entry describes
 * the mode by its *object*, which is the thing that actually tells an owner
 * which of the three they want.
 */
export interface StartWorkEntry {
  mode: WorkMode;
  route: string;
  icon: IconName;
  title: string;
  detail: string;
}

export const START_WORK: readonly StartWorkEntry[] = [
  {
    mode: "chat",
    route: "#/new-chat",
    icon: "chat",
    title: "Start a conversation",
    detail: "Ask, think, work with a file",
  },
  {
    mode: "build",
    route: "#/build",
    icon: "code",
    title: "Start a build",
    detail: "Change a repository under governance",
  },
  {
    mode: "design",
    route: "#/design",
    icon: "design",
    title: "Start a design",
    detail: "Describe an image a connected model draws",
  },
];
