/**
 * BUG-285 — what a turn says when it did not finish.
 *
 * The reported symptom was a model that passed Ollama's own provider test and
 * ran under `ollama run`, and a Chat turn that ended with **"Could not reach
 * the local runtime."** The sentence is the surface's, not the runtime's: Chat
 * produced it for anything that was not an `ApiError`, and reduced an
 * `ApiError` — which carries the reason the runtime gave — to its HTTP status.
 *
 * What these hold is the interface outcome the entry names: a turn reports the
 * specific refusal, and never claims a reachability fact it does not have.
 */
import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { turnFailureMessage } from "./turnFailure";

describe("turnFailureMessage", () => {
  it("says what the runtime said, and keeps the code it said it with", () => {
    const message = turnFailureMessage(
      new ApiError(422, "build_requires_project", "Stream failed: 422"),
    );

    expect(message).toContain("Build works inside a project");
    expect(message).toContain("build_requires_project");
    // The status number is not the answer to anything.
    expect(message).not.toContain("422");
  });

  it("names an unrecognised code rather than swallowing it", () => {
    const message = turnFailureMessage(
      new ApiError(500, "provider_http_error:401", "Stream failed: 500"),
    );

    expect(message).toContain("provider_http_error:401");
  });

  it("says plainly when a refusal carried no reason code at all", () => {
    const message = turnFailureMessage(new ApiError(503, null, "Stream failed: 503"));

    expect(message).toContain("gave no reason code");
    expect(message).toContain("503");
  });

  it("never claims the runtime was unreachable when the turn had already spoken", () => {
    const message = turnFailureMessage(new TypeError("network error"), { produced: true });

    expect(message).toContain("connection to Raiker ended");
    expect(message).toContain("already sent");
    expect(message.toLowerCase()).not.toContain("could not reach");
  });

  it("does not blame the local runtime for a dropped connection", () => {
    // The old sentence sent an owner to check a service that was running. This
    // one says what is known — the connection ended — and what to do next.
    const message = turnFailureMessage(new TypeError("network error"));

    expect(message).toContain("connection to Raiker ended");
    expect(message).toContain("may still be running");
    expect(message.toLowerCase()).not.toContain("could not reach the local runtime");
  });
});
