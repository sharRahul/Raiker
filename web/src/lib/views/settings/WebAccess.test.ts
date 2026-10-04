/**
 * Settings → Web access (REM-SET-WEB).
 *
 * Two things this page used to get wrong. It showed deployment configuration as
 * a card of the same weight as the owner's own rules, so it read as policy that
 * could be edited here and could not — and it never said who *could* change it.
 * And it never stated the number a fetch is actually evaluated against, so an
 * owner had to add three lists up themselves and hope they matched.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import WebAccess from "./WebAccess.svelte";
import { stubFetch } from "../../test-helpers";

const BLOCKLIST = {
  stored: [
    { rule_id: "r1", rule: "ads.example.com", kind: "domain", note: "", created_at: "2026-09-20T10:00:00Z" },
  ],
  environment: ["tracker.example.net"],
  environment_variable: "RAIKER_WEB_BLOCKLIST",
  builtin: ["metadata.google.internal", "169.254.169.254"],
  effective_count: 4,
  address_guard: {
    enforced: true,
    editable: false,
    description: "Private, loopback and link-local addresses are refused on every fetch.",
  },
};

function mount(overrides: Partial<typeof BLOCKLIST> = {}) {
  stubFetch({ "GET /api/web-access/blocklist": { ...BLOCKLIST, ...overrides } });
  return render(WebAccess);
}

describe("Settings → Web access", () => {
  it("states the number of rules a fetch is evaluated against", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("4")).toBeInTheDocument());
    expect(screen.getByText(/1 yours/)).toBeInTheDocument();
    expect(screen.getByText(/2 built in/)).toBeInTheDocument();
  });

  it("says the private-address guard admits no grant", async () => {
    mount();
    await waitFor(() =>
      expect(screen.getByText(/No setting on this page and no approval lifts it/)).toBeInTheDocument(),
    );
  });

  it("says so when the guard is something the owner can change", async () => {
    mount({ address_guard: { ...BLOCKLIST.address_guard, editable: true } });
    await waitFor(() =>
      expect(screen.getByText("This can be changed below.")).toBeInTheDocument(),
    );
  });

  it("folds deployment configuration away and marks it read-only", async () => {
    mount();
    const summary = await screen.findByText("Set outside this app");
    const disclosure = summary.closest("details");
    expect(disclosure).not.toBeNull();
    expect(disclosure?.open).toBe(false);
    expect(screen.getByText(/Read-only · 3/)).toBeInTheDocument();
  });

  it("names who can change each fixed source, not only that this page cannot", async () => {
    mount();
    await waitFor(() =>
      expect(screen.getByText(/whoever starts Raiker on this machine/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/installing a Raiker that ships a different list/)).toBeInTheDocument();
  });

  it("keeps the owner's own rules editable in the open", async () => {
    mount();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Unblock ads.example.com" })).toBeInTheDocument(),
    );
  });
});

// DEC-21 — a refused check says why in words and names the rule that said it,
// with the list it is on; it never prints only a reason code.
describe("Settings → Web access — checking a destination", () => {
  async function check(probe: Record<string, unknown>) {
    stubFetch({
      "GET /api/web-access/blocklist": BLOCKLIST,
      "POST /api/web-access/blocklist/test": probe,
    });
    render(WebAccess);
    const input = await screen.findByLabelText("Hostname or address");
    await fireEvent.input(input, { target: { value: String(probe.host) } });
    await fireEvent.click(screen.getByRole("button", { name: "Check" }));
  }

  it("names the matching rule and the list it is on", async () => {
    await check({
      host: "eu.ads.example.com",
      allowed: false,
      reason: "web_egress_blocked:eu.ads.example.com",
      addresses: [],
      explanation: "That destination is on your blocked list.",
      rule: "ads.example.com",
      rule_source: "yours",
    });
    expect(await screen.findByText(/is refused/)).toBeInTheDocument();
    const why = screen.getByText(/on your list below/);
    expect(why).toHaveTextContent("Matched ads.example.com, on your list below.");
    // The rule is the whole reason; the general sentence would only repeat it.
    expect(screen.queryByText(/on your blocked list/)).toBeNull();
    expect(screen.queryByText(/web_egress_blocked/)).toBeNull();
  });

  it("explains a refusal no rule made, in words", async () => {
    await check({
      host: "no-such-host.invalid",
      allowed: false,
      reason: "web_host_unresolved:no-such-host.invalid",
      addresses: [],
      explanation: "That name does not resolve to any address from this machine.",
      rule: null,
      rule_source: null,
    });
    expect(await screen.findByText(/does not resolve to any address/)).toBeInTheDocument();
    expect(screen.queryByText(/Matched/)).toBeNull();
  });

  it("says a reachable host is reachable, with where it resolved", async () => {
    await check({
      host: "docs.python.org",
      allowed: true,
      reason: "",
      addresses: ["151.101.0.223"],
      explanation: "",
      rule: null,
      rule_source: null,
    });
    expect(await screen.findByText(/is reachable/)).toBeInTheDocument();
    expect(screen.getByText(/151\.101\.0\.223/)).toBeInTheDocument();
  });
});
