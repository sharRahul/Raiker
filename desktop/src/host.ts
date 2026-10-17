// SPDX-License-Identifier: Apache-2.0
/**
 * Starting the Raiker host from a packaged desktop application.
 *
 * The host is a service, not a child of the window: closing the window must not
 * stop scheduled work, and quitting the host is the owner's explicit act in the
 * Host control or the tray (DESKTOP_DISTRIBUTION_DESIGN.md, "Browser closed").
 * So the host is spawned detached, with its output discarded rather than piped
 * — a pipe this process later closed would turn the host's next log line into a
 * broken-pipe error — and it reports readiness through a file instead:
 * `raiker-app --no-browser --ready-file PATH` writes one JSON object to PATH
 * once `/api/health` answers, or immediately when it joins a host that is
 * already running.
 */
import { spawn } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";

import { loopbackOrigin } from "./origin";

export interface HostReady {
  url: string;
  /** True when an already-running host was joined rather than started. */
  joined: boolean;
}

/** Parse the ready file's contents; `null` when it is not a loopback Raiker. */
export function parseReady(text: string): HostReady | null {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  if (typeof record.url !== "string") return null;
  const origin = loopbackOrigin(record.url);
  if (origin === null) return null;
  return { url: `${origin}/`, joined: record.joined === true };
}

/**
 * The host command for this installation, or `null` when there is none.
 *
 * An explicit `RAIKER_HOST_COMMAND` wins (development and tests). A packaged
 * shell carries the frozen host under `resources/host/`, where
 * `electron-builder.yml` puts it.
 */
export function resolveHostCommand(options: {
  explicit: string[] | null;
  resourcesPath: string;
  platform: NodeJS.Platform;
  packaged: boolean;
}): string[] | null {
  if (options.explicit !== null) return options.explicit;
  if (!options.packaged) return null;
  const executable = join(options.resourcesPath, "host", options.platform === "win32" ? "Raiker.exe" : "Raiker");
  return existsSync(executable) ? [executable] : null;
}

export class HostStartError extends Error {}

/**
 * Start the host and resolve with its URL once it is ready.
 *
 * Rejects if the process exits first or the timeout passes — with a message an
 * owner can act on, because it is shown in the window instead of the app.
 */
export function startHost(command: string[], readyFile: string, timeoutMs = 120_000): Promise<HostReady> {
  rmSync(readyFile, { force: true });
  return new Promise((resolve, reject) => {
    let settled = false;
    const child = spawn(command[0], [...command.slice(1), "--no-browser", "--ready-file", readyFile], {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    const finish = (error: Error | null, ready?: HostReady) => {
      if (settled) return;
      settled = true;
      clearInterval(poll);
      clearTimeout(timer);
      child.unref();
      if (error !== null) reject(error);
      else if (ready !== undefined) resolve(ready);
    };
    child.once("error", (error) => {
      finish(new HostStartError(`Raiker could not start its host: ${error.message}`));
    });
    child.once("exit", (code) => {
      // A joining host exits 0 straight after writing the file; read it first.
      const ready = readReady(readyFile);
      if (ready !== null) finish(null, ready);
      else finish(new HostStartError(`Raiker's host stopped before it was ready (exit code ${code ?? "unknown"}).`));
    });
    const poll = setInterval(() => {
      const ready = readReady(readyFile);
      if (ready !== null) finish(null, ready);
    }, 250);
    const timer = setTimeout(() => {
      finish(new HostStartError(`Raiker's host did not become ready within ${Math.round(timeoutMs / 1000)} seconds.`));
    }, timeoutMs);
  });
}

function readReady(path: string): HostReady | null {
  try {
    return parseReady(readFileSync(path, "utf-8"));
  } catch {
    return null;
  }
}
