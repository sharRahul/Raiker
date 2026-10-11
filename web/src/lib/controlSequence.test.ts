// DEC-22 steps 1–2 — every stop and steer a tab sends is numbered in order.
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, nextControlSequence } from "./api";
import { stubFetch } from "./test-helpers";

describe("control command sequence", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("names this tab and counts up, one number per command", () => {
    const first = nextControlSequence();
    const second = nextControlSequence();
    expect(first.client_id).toMatch(/^web-[0-9a-f]{16}$/);
    expect(second.client_id).toBe(first.client_id);
    expect(second.client_sequence).toBe(first.client_sequence + 1);
  });

  it("sends the tab's id and the next number with an interrupt", async () => {
    const fetchMock = stubFetch({
      "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { action: "stop", queued: 0 } },
    });
    await api.interrupt({ session_id: "sess_1", all: true, action_type: "cancel" });
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.session_id).toBe("sess_1");
    expect(body.client_id).toMatch(/^web-/);
    expect(Number.isInteger(body.client_sequence)).toBe(true);
  });

  it("loads where randomUUID does not exist, as on plain http to a LAN address", async () => {
    vi.resetModules();
    vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });
    const fresh = await import("./api");
    expect(fresh.nextControlSequence().client_id).toMatch(/^web-[0-9a-f]{16}$/);
  });
});
