/**
 * Settings → Web access (REM-SET-WEB).
 *
 * Two things this page used to get wrong. It showed deployment configuration as
 * a card of the same weight as the owner's own rules, so it read as policy that
 * could be edited here and could not — and it never said who *could* change it.
 * And it never stated the number a fetch is actually evaluated against, so an
 * owner had to add three lists up themselves and hope they matched.
 */
import { render, screen, waitFor } from "@testing-library/svelte";
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
