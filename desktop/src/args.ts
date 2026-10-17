// SPDX-License-Identifier: Apache-2.0
/**
 * How the shell was asked to start.
 *
 * Two ways in, and they are the only two:
 *
 * * **Attach** — `raiker-app` already started (or joined) the host and passes
 *   `--raiker-url http://127.0.0.1:PORT/`. This is the source-checkout path and
 *   the one the tray's **Open Raiker** uses.
 * * **Start** — no URL, so the shell starts the host itself and waits for its
 *   ready file. This is the packaged-application path; the command comes from
 *   `RAIKER_HOST_COMMAND` (a JSON array, for development) or the host bundled
 *   next to the shell.
 */
import { loopbackOrigin } from "./origin";

export interface ShellArgs {
  /** The loopback Raiker URL to attach to, or `null` to start a host. */
  url: string | null;
  /** Set when `--raiker-url` was given but is not a loopback Raiker address. */
  rejectedUrl: string | null;
  /** The host command from `RAIKER_HOST_COMMAND`, when one was supplied. */
  hostCommand: string[] | null;
  /** `--repair`: run the Setup window again, as the installer's Repair does. */
  repair: boolean;
}

const URL_FLAG = "--raiker-url";

export function parseShellArgs(argv: readonly string[], env: Record<string, string | undefined>): ShellArgs {
  let requested: string | null = null;
  const repair = argv.includes("--repair");
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === URL_FLAG && index + 1 < argv.length) {
      requested = argv[index + 1];
      index += 1;
    } else if (arg.startsWith(`${URL_FLAG}=`)) {
      requested = arg.slice(URL_FLAG.length + 1);
    }
  }
  let url: string | null = null;
  let rejectedUrl: string | null = null;
  if (requested !== null) {
    const origin = loopbackOrigin(requested);
    if (origin === null) rejectedUrl = requested;
    else url = `${origin}/`;
  }
  return { url, rejectedUrl, hostCommand: parseHostCommand(env.RAIKER_HOST_COMMAND), repair };
}

/** `RAIKER_HOST_COMMAND` as an argv, or `null` when absent or malformed. */
export function parseHostCommand(raw: string | undefined): string[] | null {
  if (raw === undefined || raw.trim() === "") return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (Array.isArray(value) && value.length > 0 && value.every((part) => typeof part === "string" && part !== "")) {
      return value as string[];
    }
  } catch {
    // Fall through: a malformed command is no command, and the shell says so.
  }
  return null;
}
