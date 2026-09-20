/**
 * Settings → Git credential (REM-SET-GIT).
 *
 * The page's job is an ordering: what the credential will be used for comes
 * before the field that asks for it, and what it says about the boundary is the
 * runtime's own answer rather than a sentence typed here that can go stale.
 */
import { render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import GitCredential from "./GitCredential.svelte";
import { stubFetch } from "../../test-helpers";

const STATUS = {
  credential_configured: false,
  credential_source: "none",
  grant: null,
  scopes: ["once", "session"],
  grant_seconds: { once: 300, session: 3600 },
  hosts: ["github.com", "www.github.com"],
  operations: ["Push a branch you approved"],
  checked_at: "2026-09-20T10:00:00Z",
};

function mount(overrides: Partial<typeof STATUS> = {}) {
  stubFetch({ "GET /api/git-credential": { ...STATUS, ...overrides } });
  return render(GitCredential);
}

describe("Settings → Git credential", () => {
  it("states the scope the runtime issues the credential inside", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("github.com")).toBeInTheDocument());
    expect(screen.getByText("www.github.com")).toBeInTheDocument();
    expect(screen.getByText("Push a branch you approved")).toBeInTheDocument();
  });

  it("asks what the credential is for before it asks for the credential", async () => {
    const { container } = mount();
    await waitFor(() => expect(screen.getByLabelText("GitHub token")).toBeInTheDocument());

    const scope = screen.getByRole("heading", { name: /Where it may be used/ });
    const field = screen.getByLabelText("GitHub token");
    // `DOCUMENT_POSITION_FOLLOWING` — the field comes after the scope, which is
    // the whole of this row: a decision made after the secret is pasted is not
    // a decision.
    expect(scope.compareDocumentPosition(field) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container).toBeTruthy();
  });

  it("says which supply method is supported and which is refused, with the reason", async () => {
    mount();
    await waitFor(() =>
      expect(screen.getByText("A scoped GitHub token")).toBeInTheDocument(),
    );
    expect(screen.getByText(/Not this machine's credential manager/)).toBeInTheDocument();
    expect(screen.getByText(/a credential nobody governed/)).toBeInTheDocument();
  });

  it("names the host list from the answer rather than from its own prose", async () => {
    mount({ hosts: ["git.example.test"] });
    await waitFor(() => expect(screen.getByText("git.example.test")).toBeInTheDocument());
    expect(screen.queryByText("github.com")).not.toBeInTheDocument();
  });

  it("will not approve a use before a credential exists to use", async () => {
    mount();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Approve Once/ })).toBeDisabled(),
    );
    expect(screen.getByText(/Store a token above before approving anything/)).toBeInTheDocument();
  });
});
