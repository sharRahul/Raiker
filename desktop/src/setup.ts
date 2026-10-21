// SPDX-License-Identifier: Apache-2.0
/**
 * DIST-05 — finishing the installation, before Raiker opens.
 *
 * The platform installer copies files; it cannot tell whether this computer can
 * run Raiker, and on macOS and Linux (a dragged app, an AppImage) there is no
 * installer step at all. So the first start of a packaged shell is the last
 * stage of installation, shown in its own Setup window: check this computer,
 * prepare the encrypted store and start the host, verify the result. Only then
 * does the owner see Raiker — and an account is never created on a computer
 * that cannot run it.
 *
 * The shape is a bootstrap installer's: a fixed list of
 * named stages, each reported as it starts and ends with how long it took, a
 * hidden-by-default log, and a failure stated in one plain sentence with
 * Retry beside it. A receipt in the shell's profile records that setup
 * finished for this version; a newer version runs it again, as an update.
 *
 * Everything here is free of Electron so `test/setup.test.ts` can run it.
 */
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export const SETUP_STAGES = [
  { id: "check", title: "Checking this computer" },
  { id: "start", title: "Starting Raiker" },
  { id: "verify", title: "Verifying" },
] as const;
export type StageId = (typeof SETUP_STAGES)[number]["id"];

/** What the Setup window is doing: a first install, an update, or a repair. */
export type SetupMode = "install" | "update" | "repair";

/** The actions the Setup page may ask for; anything else is ignored. */
export const SETUP_ACTIONS = ["start", "retry", "open", "logs", "quit"] as const;
export type SetupAction = (typeof SETUP_ACTIONS)[number];
export const SETUP_CHANNELS = { event: "raiker-setup:event", action: "raiker-setup:action" } as const;

export function isSetupAction(value: unknown): value is SetupAction {
  return typeof value === "string" && (SETUP_ACTIONS as readonly string[]).includes(value);
}

export interface SetupReceipt {
  schema: 1;
  version: string;
  completedAt: string;
}

export function readReceipt(path: string): SetupReceipt | null {
  try {
    const value: unknown = JSON.parse(readFileSync(path, "utf-8"));
    if (typeof value !== "object" || value === null) return null;
    const record = value as Record<string, unknown>;
    if (record.schema !== 1 || typeof record.version !== "string" || typeof record.completedAt !== "string") {
      return null;
    }
    return { schema: 1, version: record.version, completedAt: record.completedAt };
  } catch {
    return null;
  }
}

/** Written last, atomically: a receipt exists only for a setup that finished. */
export function writeReceipt(path: string, version: string, now: Date = new Date()): void {
  mkdirSync(dirname(path), { recursive: true });
  const partial = `${path}.partial`;
  const receipt: SetupReceipt = { schema: 1, version, completedAt: now.toISOString() };
  writeFileSync(partial, `${JSON.stringify(receipt)}\n`, "utf-8");
  renameSync(partial, path);
}

/** Whether this start needs the Setup window, and why; `null` to go straight in. */
export function setupMode(receipt: SetupReceipt | null, version: string, repair: boolean): SetupMode | null {
  if (repair) return "repair";
  if (receipt === null) return "install";
  return receipt.version === version ? null : "update";
}

export type CheckState = "pass" | "warn" | "fail" | "info";

export interface SystemCheck {
  id: string;
  label: string;
  state: CheckState;
  detail: string;
  remedy: string;
  mandatory: boolean;
}

export interface SystemReadiness {
  checks: SystemCheck[];
  blocking: string[];
  ready: boolean;
}

const STATES: readonly string[] = ["pass", "warn", "fail", "info"];

/** The host's `system-check --output` file, or `null` when it is not one. */
export function parseSystemCheck(text: string): SystemReadiness | null {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  if (!Array.isArray(record.checks) || !Array.isArray(record.blocking) || typeof record.ready !== "boolean") {
    return null;
  }
  const checks: SystemCheck[] = [];
  for (const item of record.checks) {
    if (typeof item !== "object" || item === null) return null;
    const check = item as Record<string, unknown>;
    if (typeof check.id !== "string" || typeof check.label !== "string" || !STATES.includes(String(check.state))) {
      return null;
    }
    checks.push({
      id: check.id,
      label: check.label,
      state: check.state as CheckState,
      detail: typeof check.detail === "string" ? check.detail : "",
      remedy: typeof check.remedy === "string" ? check.remedy : "",
      mandatory: check.mandatory === true,
    });
  }
  const blocking = record.blocking.filter((id): id is string => typeof id === "string");
  return { checks, blocking, ready: record.ready };
}

/** The sentence the failure screen leads with when a check blocks setup. */
export function blockingSummary(readiness: SystemReadiness): string {
  const failed = readiness.checks.filter((check) => readiness.blocking.includes(check.id));
  if (failed.length === 0) return "This computer does not meet Raiker's requirements.";
  return failed.map((check) => check.remedy || `${check.label}: ${check.detail}`).join(" ");
}

/**
 * One plain sentence for a raw failure, as a good boot screen gives: the raw
 * text stays available behind Show details, never as the headline.
 */
export function plainCause(message: string): string {
  const text = message.toLowerCase();
  if (/enospc|no space left|disk full|not enough space/.test(text)) {
    return "This computer is out of disk space. Free some space, then try again.";
  }
  if (/eacces|eperm|permission denied|access is denied|operation not permitted/.test(text)) {
    return "Raiker was not allowed to write its data folder. Check that folder's permissions, then try again.";
  }
  if (/eaddrinuse|address already in use|port/.test(text) && /in use|eaddrinuse/.test(text)) {
    return "Another program is using the port Raiker needs. Close it, or restart the computer, then try again.";
  }
  if (/did not become ready|timed out|timeout/.test(text)) {
    return "Raiker took too long to start. This can happen on a busy computer; try again.";
  }
  if (/enoent|could not start|not found|no raiker host/.test(text)) {
    return "Part of Raiker is missing. Reinstall Raiker, then try again.";
  }
  if (/stopped before it was ready|exit code/.test(text)) {
    return "Raiker stopped while it was starting. Try again; if it happens again, open the logs.";
  }
  return "Setup did not finish. Try again; if it happens again, open the logs.";
}

export class SetupStageError extends Error {
  constructor(
    message: string,
    /** The one sentence the failure screen leads with. */
    readonly plain: string,
  ) {
    super(message);
  }
}

/**
 * Run the bundled host's `system-check` and read its answer.
 *
 * It creates nothing — not even the data folder — so an owner told that this
 * computer cannot run Raiker has nothing to clean up.
 */
export function runSystemCheck(command: string[], outputFile: string, timeoutMs = 60_000): Promise<SystemReadiness> {
  rmSync(outputFile, { force: true });
  return new Promise((resolve, reject) => {
    let settled = false;
    const child = spawn(command[0], [...command.slice(1), "system-check", "--output", outputFile], {
      stdio: "ignore",
      windowsHide: true,
    });
    const finish = (error: Error | null, answer?: SystemReadiness) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error !== null) reject(error);
      else if (answer !== undefined) resolve(answer);
    };
    child.once("error", (error) => finish(new SetupStageError(`Could not start the system check: ${error.message}`, plainCause(error.message))));
    child.once("exit", (code) => {
      let answer: SystemReadiness | null;
      try {
        answer = parseSystemCheck(readFileSync(outputFile, "utf-8"));
      } catch {
        answer = null;
      }
      // Exit 1 with an answer is "this computer cannot run Raiker", which the
      // caller reports from the answer; no answer at all is a broken check.
      if (answer !== null) finish(null, answer);
      else finish(new SetupStageError(`The system check gave no answer (exit code ${code ?? "unknown"}).`, plainCause("exit code")));
    });
    const timer = setTimeout(() => {
      child.kill();
      finish(new SetupStageError("The system check did not finish in time.", plainCause("timed out")));
    }, timeoutMs);
  });
}

export interface Verification {
  ok: boolean;
  detail: string;
}

type Fetch = (url: string) => Promise<{ ok: boolean; status: number; headers: { get(name: string): string | null }; json(): Promise<unknown> }>;

/**
 * Verify the started host from outside, the way the window will use it: the
 * encrypted store opens, text search is available, and the interface is served.
 */
export async function verifyHost(url: string, fetcher: Fetch = fetch): Promise<Verification> {
  const base = url.endsWith("/") ? url : `${url}/`;
  const health = await fetcher(`${base}api/health`);
  if (!health.ok) return { ok: false, detail: `The health check answered ${health.status}.` };
  const body = (await health.json()) as Record<string, unknown>;
  if (body.store !== "ok") {
    return { ok: false, detail: `The encrypted store did not open (${String(body.reason ?? body.detail ?? "unknown")}).` };
  }
  if (typeof body.text_search_engine !== "string") {
    return { ok: false, detail: "Text search is not available in the store." };
  }
  const page = await fetcher(base);
  const type = page.headers.get("content-type") ?? "";
  if (!page.ok || !type.includes("text/html")) {
    return { ok: false, detail: "The interface files were not served." };
  }
  return { ok: true, detail: `Encrypted store open, ${body.text_search_engine} search ready, interface served.` };
}
