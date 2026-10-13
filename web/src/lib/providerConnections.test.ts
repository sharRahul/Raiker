/**
 * BUG-319 — the connection lifecycle both Models and first-run setup call.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  listCatalogue,
  refusedForWorkspace,
  removeConnection,
  saveConnection,
  saveWorkspace,
} from "./providerConnections";
import { stubFetch } from "./test-helpers";

afterEach(() => vi.unstubAllGlobals());

const PATH = "PUT /api/models/anthropic-hosted/connection";

describe("one connection lifecycle", () => {
  it("stores a key and says so, never echoing it", async () => {
    const mock = stubFetch({ [PATH]: { ok: true } });
    expect(await saveConnection("anthropic-hosted", { apiKey: "  sk-test  " })).toEqual({ ok: true });
    const body = JSON.parse(String((mock.mock.calls[0][1] as RequestInit).body));
    expect(body).toEqual({ endpoint: null, api_key: "sk-test", admin_api_key: null, workspace_id: null });
  });

  it("adds a workspace on its own and removes with nothing", async () => {
    const mock = stubFetch({ [PATH]: { ok: true } });
    await saveWorkspace("anthropic-hosted", "wrkspc_1");
    await removeConnection("anthropic-hosted");
    const bodies = mock.mock.calls.map((call) => JSON.parse(String((call[1] as RequestInit).body)));
    expect(bodies[0].workspace_id).toBe("wrkspc_1");
    expect(bodies[0].api_key).toBeNull();
    expect(bodies[1]).toEqual({ endpoint: null, api_key: null, admin_api_key: null, workspace_id: null });
  });

  it("reads a refusal the same way for every caller", async () => {
    stubFetch({
      [PATH]: { __status: 400, detail: { reason_code: "provider_workspace_required" } },
    });
    const outcome = await saveConnection("anthropic-hosted", { apiKey: "sk-ant-usr-x" });
    expect(outcome.ok).toBe(false);
    if (outcome.ok) return;
    expect(outcome.workspaceRefused).toBe(true);
    expect(outcome.reasonCode).toBe("provider_workspace_required");
    expect(outcome.guidance?.message).toBeTruthy();
  });

  it("returns a listing as the provider answered it", async () => {
    stubFetch({
      "GET /api/models/anthropic-hosted/provider-models": {
        status: "unavailable", models: [], reason_code: "provider_workspace_required",
      },
    });
    const outcome = await listCatalogue("anthropic-hosted");
    expect(outcome.ok).toBe(true);
    if (outcome.ok) expect(outcome.list.reason_code).toBe("provider_workspace_required");
  });

  it("names a workspace refusal by its governed code only", () => {
    expect(refusedForWorkspace("provider_workspace_invalid")).toBe(true);
    expect(refusedForWorkspace("provider_auth_failed")).toBe(false);
    expect(refusedForWorkspace(null)).toBe(false);
  });
});
