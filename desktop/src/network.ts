// SPDX-License-Identifier: Apache-2.0
/** The shell only talks to local hosts; governed remote requests belong to Python. */
import { loopbackOrigin } from "./origin";

export function isLoopbackNetworkRequest(raw: string): boolean {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return false;
  }
  // Interactive terminals may use a websocket on the same local host.
  if (url.protocol === "ws:") url.protocol = "http:";
  return loopbackOrigin(url.href) !== null;
}
