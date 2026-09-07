import type { ExecutionEnvironment, ProbeVerdict } from "./apiTypes";

/**
 * How a measured boundary is described to the owner.
 *
 * Two rules the copy has to keep, because they are the difference between an
 * honest posture and a reassuring one:
 *
 * 1. A boundary is named by what was *measured*, never by what was configured.
 *    `local_native` is host access with reduced isolation and says so.
 * 2. `indeterminate` is not a softer `enforced`. It means the control arm
 *    failed — the same attempt outside the boundary also failed — so the
 *    observation proves nothing. It is rendered as "not proven", never as a
 *    partial pass.
 */

export const OBSERVATION_ORDER = [
  "relay",
  "workspace_write",
  "escape_write",
  "masked_read",
  "egress",
  "descendant_reaped",
] as const;

export type ObservationName = (typeof OBSERVATION_ORDER)[number];

const OBSERVATION_LABEL: Record<ObservationName, string> = {
  relay: "Command output reaches Raiker",
  workspace_write: "Can write inside the workspace",
  escape_write: "Cannot write outside the workspace",
  masked_read: "Cannot read Raiker's own state",
  egress: "Cannot reach the network",
  descendant_reaped: "Stopping ends every descendant",
};

const VERDICT_LABEL: Record<ProbeVerdict, string> = {
  enforced: "Enforced",
  unenforced: "Not enforced",
  indeterminate: "Not proven",
};

export interface ObservationRow {
  name: ObservationName;
  label: string;
  verdict: ProbeVerdict;
  verdictLabel: string;
}

export function observationRows(
  observations: Record<string, ProbeVerdict> | undefined,
): ObservationRow[] {
  if (!observations) return [];
  return OBSERVATION_ORDER.filter((name) => name in observations).map((name) => {
    const verdict = observations[name];
    return {
      name,
      label: OBSERVATION_LABEL[name],
      verdict,
      verdictLabel: VERDICT_LABEL[verdict] ?? "Not proven",
    };
  });
}

/** The chip a work surface shows for the environment a command actually ran in. */
export function boundaryLabel(environment: ExecutionEnvironment | null): string {
  if (environment === null) return "Environment unavailable";
  if (environment.kind === "local") return "Host access — reduced isolation";
  if (!environment.available) return `${environment.name} — unavailable`;
  const network =
    environment.probe_observations?.egress === "enforced"
      ? "network denied"
      : "network not proven";
  switch (environment.boundary) {
    case "appcontainer":
      return `AppContainer · ${network}`;
    case "bubblewrap":
      return `bubblewrap · ${network}`;
    case "seatbelt":
      return `Seatbelt · ${network}`;
    case "container":
      return `Container · ${network}`;
    default:
      return environment.name;
  }
}

/**
 * The one-line posture under the chip. Deliberately says what is *not* there:
 * a surface that lists only what works reads as a complete boundary.
 */
export function posturaLine(environment: ExecutionEnvironment | null): string {
  if (environment === null) return "No environment selected";
  if (environment.kind === "local") {
    return "Argv only · no credential inheritance · no PTY · foreground";
  }
  if (environment.kind === "native") {
    return "OS boundary · foreground only · no PTY, background or network grant";
  }
  return "No host fallback";
}

/**
 * Every observation must be `enforced` for a boundary to be offered.
 *
 * Written as an explicit check rather than trusting the server's `available`
 * so the surface cannot drift from the rule if a future field is added.
 */
export function fullyProven(environment: ExecutionEnvironment | null): boolean {
  const rows = observationRows(environment?.probe_observations);
  return rows.length > 0 && rows.every((row) => row.verdict === "enforced");
}
