import { describe, expect, it } from "vitest";
import { routeStateFromHash } from "./routeState";

describe("route state contract", () => {
  it("accepts only documented non-secret selection state", () => {
    expect(routeStateFromHash("#/sessions?project=proj_1&session=sess_1&filter=open&token=nope")).toEqual({
      projectId: "proj_1", sessionId: "sess_1", turnId: null, recordId: null, filter: "open", tab: null,
    });
  });

  it("drops empty and oversized values", () => {
    expect(routeStateFromHash(`#/home?session=&record=${"x".repeat(257)}`)).toEqual({
      projectId: null, sessionId: null, turnId: null, recordId: null, filter: null, tab: null,
    });
  });

  // MEM-08 — the exchange a link points at. A coordinate beside the session id,
  // held to the same rule as every other key here: it names something the
  // reader may already open, and carries no payload, credential or decision.
  it("carries the turn a link is anchored to", () => {
    expect(routeStateFromHash("#/new-chat?session=sess_1&turn=turn_9")).toEqual({
      projectId: null,
      sessionId: "sess_1",
      turnId: "turn_9",
      recordId: null,
      filter: null,
      tab: null,
    });
  });
});
