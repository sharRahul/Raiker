/*
 * UX-CHAT-01 / UX-BUILD-01 / UX-MODEL-01 — the controllers the three large
 * views were split into, tested on their own. The view suites keep the
 * behaviour as an owner sees it; these hold each state machine's own rules,
 * so a later change to one cannot lean on a view to notice.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { ComposerLookups } from "./composerLookups.svelte";
import { ApprovalReview } from "./views/build/approvalReview.svelte";
import { InlineSources } from "./views/build/inlineSources.svelte";
import { RecallLedger } from "./views/chat/recallLedger.svelte";
import { TurnContinuity } from "./views/chat/turnContinuity.svelte";
import { stubFetch } from "./test-helpers";

afterEach(() => vi.unstubAllGlobals());

describe("ComposerLookups", () => {
  it("drops a mention answer that a newer lookup has overtaken", async () => {
    let resolveFirst: (value: unknown) => void = () => {};
    const order: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        order.push(String(url));
        const body = String(url).includes("old")
          ? await new Promise((resolve) => (resolveFirst = resolve))
          : { status: "success", paths: [{ path: "src/new.ts", language: "ts" }] };
        return { ok: true, status: 200, json: async () => body } as Response;
      }),
    );
    const lookups = new ComposerLookups({ href: "#/build", label: "Build" });
    const first = lookups.loadMentions("old");
    await lookups.loadMentions("new");
    resolveFirst({ status: "success", paths: [{ path: "src/old.ts", language: "ts" }] });
    await first;
    expect(lookups.mentionItems.map((item) => item.id)).toEqual(["src/new.ts"]);
    expect(order).toHaveLength(2);
  });

  it("names the surface's own place to build the code map", async () => {
    stubFetch({
      "GET /api/code/map/paths": { status: "error", error: { type: "code_map_not_built", message: "No map yet." } },
    });
    const lookups = new ComposerLookups({ href: "#/build?tab=repositories", label: "Repositories" });
    await lookups.loadMentions("x");
    expect(lookups.mentionNotice).toEqual({
      text: "No map yet.",
      href: "#/build?tab=repositories",
      linkLabel: "Repositories",
    });
  });
});

describe("TurnContinuity", () => {
  it("says there is nothing to rewind to when the turn wrote no checkpoint", async () => {
    stubFetch({ "GET /api/checkpoints": [] });
    const notices: Array<string | null> = [];
    const closed = vi.fn();
    const continuity = new TurnContinuity(() => "sess_1", () => false, (text) => notices.push(text), closed);
    await continuity.rewindFromTurn("turn_1");
    expect(notices.at(-1)).toBe("No checkpoint was written for that turn, so there is nothing to rewind to.");
    expect(continuity.rewindCheckpointId).toBeNull();
    expect(closed).not.toHaveBeenCalled();
  });

  it("does nothing while a turn is streaming", async () => {
    const mock = stubFetch({});
    const continuity = new TurnContinuity(() => "sess_1", () => true, () => {}, () => {});
    await continuity.compactThroughTurn("turn_1");
    expect(mock).not.toHaveBeenCalled();
  });
});

describe("RecallLedger", () => {
  it("reads the strip again after a correction", async () => {
    const mock = stubFetch({
      "PUT /api/memory/mem_1": { ok: true },
      "GET /api/sessions/sess_1/recall": { memories: [] },
    });
    const ledger = new RecallLedger(() => "sess_1");
    await ledger.correct({ memory_id: "mem_1", text: "old", turn_id: "t1" } as never, "new");
    expect(ledger.notice).toBe("Corrected.");
    expect(mock.mock.calls.some(([url]) => String(url).endsWith("/api/sessions/sess_1/recall"))).toBe(true);
  });
});

describe("InlineSources", () => {
  it("closes a source that is opened twice", async () => {
    stubFetch({ "GET /api/sessions/sess_1/turns/turn_1/sources/s1": { status: "ok", excerpt: "x" } });
    const sources = new InlineSources(() => "sess_1");
    const source = { source_id: "s1", turn_id: "turn_1", openable: true } as never;
    await sources.show(source);
    expect(sources.isOpen(source)).toBe(true);
    await sources.show(source);
    expect(sources.isOpen(source)).toBe(false);
  });
});

describe("ApprovalReview", () => {
  it("tells a decision that ran and failed apart from one governance stopped", async () => {
    let pending = [{ approval_id: "appr_1", session_id: "sess_1", status: "pending" }];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).endsWith("/api/approvals/appr_1/resolve")) {
          pending = [];
          return {
            ok: false,
            status: 409,
            json: async () => ({ detail: { reason_code: "target_not_executed:exit_code:1" } }),
          } as Response;
        }
        if (String(url).includes("/api/approvals?") && (init?.method ?? "GET") === "GET") {
          return { ok: true, status: 200, json: async () => pending } as Response;
        }
        return { ok: true, status: 200, json: async () => ({ preview_kind: "none" }) } as Response;
      }),
    );
    const checkNow = vi.fn();
    const review = new ApprovalReview(() => "sess_1", async () => {}, checkNow);
    await review.load();
    await review.resolve(review.approvals[0], true);
    expect(review.notice).toBe(
      "Approved and run once — it did not succeed (exit code 1). The turn continues with the output.",
    );
    expect(checkNow).toHaveBeenCalled();
    expect(review.busy).toBeNull();
  });
});
