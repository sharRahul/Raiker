// Server-sent event streams: a governed turn, and its continuation after an
// approval. A POST read incrementally, since an EventSource can send neither
// the bearer token nor a body (OPT-02).
import type {
  PromptRequestBody,
  StreamEvent,
} from "../apiTypes";
import { ApiError, authHeaders, instancePath, reasonCodeFrom } from "./core";

/**
 * Stream a governed turn over SSE (POST /api/prompts/stream). The turn is created by the
 * stream from the prompt body, so this is a POST that reads the response body incrementally
 * rather than an EventSource (which can't send the bearer token or a request body).
 *
 * `onEvent` is invoked for each parsed `StreamEvent`; the promise resolves once the stream
 * closes (the final event carries the complete AgentResponse). Tool execution still flows
 * through the governed broker/policy/approval path — this only observes the turn.
 */
export async function streamPrompt(
  body: PromptRequestBody,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(
    "/api/prompts/stream",
    JSON.stringify(body),
    onEvent,
    signal,
  );
}

/**
 * Stream the continuation of a turn that was parked for an approval (B2).
 *
 * Resolving an approval closes the tool call the model was waiting on, so the
 * *same* turn can pick up from where it stopped instead of the owner re-prompting
 * and the model losing its working state. Same governed path as an ordinary
 * turn — this only surfaces the continuation as it happens.
 */
export async function streamResumeAfterApproval(
  approvalId: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(
    `/api/approvals/${encodeURIComponent(approvalId)}/resume/stream`,
    null,
    onEvent,
    signal,
  );
}

async function streamSse(
  path: string,
  body: string | null,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = authHeaders(new Headers({ "Content-Type": "application/json" }), "POST");
  // Streaming routes go through `instancePath` like every other call, so a
  // dashboard served under /instances/<name> streams from its own instance
  // rather than the default workspace.
  const url = instancePath(path);
  const resp = await fetch(url, {
    method: "POST",
    headers,
    credentials: "same-origin",
    ...(body === null ? {} : { body }),
    signal,
  });
  if (!resp.ok || resp.body === null) {
    // BUG-196 — a refused stream carries the same `reason_code` a refused plain
    // request does. Dropping it here is what made a lost resume race read as
    // "The turn could not continue (409)" underneath a turn that had in fact
    // completed: the surface had a status number and no way to tell why.
    let reasonCode: string | null = null;
    if (!resp.ok) {
      try {
        reasonCode = reasonCodeFrom(await resp.json());
      } catch {
        /* Non-JSON error response */
      }
    }
    throw new ApiError(
      resp.status,
      reasonCode,
      `Stream failed: ${resp.status} ${url}`,
    );
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = drainSseBuffer(buffer, onEvent);
    }
  } finally {
    reader.releaseLock();
  }
  // Flush any trailing event that wasn't terminated by a blank line.
  drainSseBuffer(buffer + "\n\n", onEvent);
}

/** Parse complete `data:` SSE records out of `buffer`, returning the unconsumed remainder. */
function drainSseBuffer(
  buffer: string,
  onEvent: (event: StreamEvent) => void,
): string {
  let rest = buffer;
  let sep = rest.indexOf("\n\n");
  while (sep !== -1) {
    const chunk = rest.slice(0, sep);
    rest = rest.slice(sep + 2);
    const event = parseSseChunk(chunk);
    if (event !== null) onEvent(event);
    sep = rest.indexOf("\n\n");
  }
  return rest;
}

function parseSseChunk(chunk: string): StreamEvent | null {
  const data = chunk
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (data === "") return null;
  try {
    return JSON.parse(data) as StreamEvent;
  } catch {
    return null;
  }
}
