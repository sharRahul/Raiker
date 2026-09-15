import { describe, expect, it } from "vitest";
import { routeStateFromHash } from "./routeState";

describe("route state contract", () => {
  it("accepts only documented non-secret selection state", () => {
    expect(routeStateFromHash("#/sessions?project=proj_1&session=sess_1&filter=open&token=nope")).toEqual({
      projectId: "proj_1", sessionId: "sess_1", turnId: null, recordId: null, assetId: null, taskId: null, filter: "open", tab: null,
    });
  });

  it("drops empty and oversized values", () => {
    expect(routeStateFromHash(`#/home?session=&record=${"x".repeat(257)}`)).toEqual({
      projectId: null, sessionId: null, turnId: null, recordId: null, assetId: null, taskId: null, filter: null, tab: null,
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
      assetId: null,
      taskId: null,
      filter: null,
      tab: null,
    });
  });

  // NEW-PROJ-02 — the asset a link points at, on a surface whose object is an
  // asset. Same rule as every key beside it: a coordinate the reader may
  // already open, carrying no payload, credential or decision.
  it("carries the asset a project's image links to", () => {
    expect(routeStateFromHash("#/design?project=proj_1&asset=img_7")).toEqual({
      projectId: "proj_1",
      sessionId: null,
      turnId: null,
      recordId: null,
      assetId: "img_7",
      taskId: null,
      filter: null,
      tab: null,
    });
  });

  // BUG-299 — the task a link points at. Same rule again: a coordinate the
  // reader may already open, resolved against this account's own tasks on the
  // server, carrying no payload, credential or decision.
  it("carries the task a history link points at", () => {
    expect(routeStateFromHash("#/tasks?task=task_9")).toEqual({
      projectId: null,
      sessionId: null,
      turnId: null,
      recordId: null,
      assetId: null,
      taskId: "task_9",
      filter: null,
      tab: null,
    });
  });
});
