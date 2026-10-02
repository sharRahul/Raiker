/*
 * UX-MEM-04 — what a memory's confidence and trust numbers mean, said as
 * reasons rather than decimals.
 *
 * `confidence 0.62 · trust 0.75` read as calibrated probabilities, and they
 * are not: confidence is the proposing step's own estimate that a sentence
 * states a durable fact, and trust is a fixed weight set by how the record
 * was written. An owner cannot evaluate either number, but they can evaluate
 * *who said it* and *on what evidence* — which is what these labels say. The
 * raw values stay available under Advanced for anyone checking the arithmetic.
 */
import type { MemoryControlView } from "./apiTypes";

export type EvidenceStrength = "strong" | "some" | "weak";

/** The confidence bands. Thresholds, not a calibration: see the module note. */
export function evidenceStrength(confidence: number): EvidenceStrength {
  if (confidence >= 0.85) return "strong";
  if (confidence >= 0.6) return "some";
  return "weak";
}

export const STRENGTH_LABELS: Record<EvidenceStrength, string> = {
  strong: "Strong evidence",
  some: "Some evidence",
  weak: "Weak evidence",
};

export interface EvidenceReading {
  /** Who put this into memory, in the owner's words. */
  origin: string;
  /** How sure the proposing step was. Absent when the owner wrote it. */
  strength: EvidenceStrength | null;
  /** The short label a card shows. */
  label: string;
  /** The answer to "Why?". */
  why: string;
}

const NOT_A_PROBABILITY =
  "These are Raiker's own estimates, not measured probabilities — read them as a reason to check, not as a score.";

function sourceType(memory: Pick<MemoryControlView, "source" | "provenance">): string {
  const recorded = memory.provenance?.["source_type"];
  return typeof recorded === "string" && recorded !== "" ? recorded : memory.source;
}

/** One reading per approved record. */
export function memoryEvidence(
  memory: Pick<MemoryControlView, "source" | "provenance" | "confidence">,
): EvidenceReading {
  const kind = sourceType(memory);
  if (kind === "human_correction" || memory.source === "human_correction") {
    return {
      origin: "You corrected this",
      strength: null,
      label: "You corrected this",
      why: "You wrote these words yourself when correcting an earlier memory, so nothing about them is inferred.",
    };
  }
  if (kind === "user_ui") {
    return {
      origin: "You wrote this",
      strength: null,
      label: "You wrote this",
      why: "You wrote these words yourself, so nothing about them is inferred.",
    };
  }
  if (kind === "user_import") {
    return {
      origin: "Imported by you",
      strength: null,
      label: "Imported by you",
      why: "It came from a file you chose to import. Raiker did not check where that file got it from, so it is only as reliable as the file.",
    };
  }
  const strength = evidenceStrength(memory.confidence);
  const approved = kind === "memory_proposal" || memory.source === "human_approved_proposal";
  const origin = approved ? "Suggested by Raiker, approved by you" : "Written by Raiker with your approval";
  return {
    origin,
    strength,
    label: `${STRENGTH_LABELS[strength]} · ${approved ? "approved by you" : "written by Raiker"}`,
    // The step that proposed the record rated its own evidence; it recorded no
    // reason, so none is invented here — the band is the whole claim.
    why: `${origin}. When it was proposed, Raiker rated its own evidence as ${STRENGTH_LABELS[strength].toLowerCase()}. ${NOT_A_PROBABILITY}`,
  };
}

/** A proposal has not been approved yet, so only the strength is said. */
export function proposalEvidence(confidence: number): Pick<EvidenceReading, "strength" | "label" | "why"> {
  const strength = evidenceStrength(confidence);
  return {
    strength,
    label: STRENGTH_LABELS[strength],
    why: `How sure Raiker was that this states something worth remembering. ${NOT_A_PROBABILITY}`,
  };
}
