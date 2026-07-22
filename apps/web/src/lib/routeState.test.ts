import { describe, expect, it } from "vitest";
import { routeStateFromHash } from "./routeState";

describe("route state contract", () => {
  it("accepts only documented non-secret selection state", () => {
    expect(routeStateFromHash("#/sessions?project=proj_1&session=sess_1&filter=open&token=nope")).toEqual({
      projectId: "proj_1", sessionId: "sess_1", recordId: null, filter: "open", tab: null,
    });
  });

  it("drops empty and oversized values", () => {
    expect(routeStateFromHash(`#/home?session=&record=${"x".repeat(257)}`)).toEqual({
      projectId: null, sessionId: null, recordId: null, filter: null, tab: null,
    });
  });
});
