/*
 * NEW-ACCOUNT-01 — the one moment in Raiker where a wrong impression cannot be
 * undone.
 *
 * Deleting an account elevates, then deletes. Both are requests, so there is a
 * window between pressing the button and the account being gone — and through
 * that whole window the confirmation offered a control labelled **Cancel**
 * which only hid the form. Pressing it returned the owner to a page that looked
 * untouched while the deletion carried on behind it.
 *
 * A control named Cancel must not imply that an irreversible operation has been
 * cancelled when all it does is close a form.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Account from "./Account.svelte";
import { setToken } from "../../api";

afterEach(() => {
  setToken(null);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** Elevation answers at once; the deletion is held open by the test. */
function stubHeldDelete() {
  const calls: string[] = [];
  let release: ((value: unknown) => void) | undefined;
  let rejectWith: ((reason: unknown) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push(`${method} ${url.replace(/^https?:\/\/[^/]+/, "")}`);
      if (url.includes("/api/auth/elevate")) {
        return new Response(JSON.stringify({ token: "elevated" }), { status: 200 });
      }
      if (url.includes("/api/account") && method === "DELETE") {
        return new Promise((resolve, reject) => {
          release = resolve;
          rejectWith = reject;
        });
      }
      return new Response(JSON.stringify({}), { status: 200 });
    }),
  );
  return {
    calls,
    refuse: () => release?.(new Response(JSON.stringify({ detail: {} }), { status: 500 })),
    drop: () => rejectWith?.(new TypeError("network")),
    deleteCalls: () => calls.filter((call) => call.startsWith("DELETE")).length,
  };
}

function mount() {
  return render(Account, {
    props: {
      settings: { "account.display_name": "Rahul" },
      save: () => {},
      status: { username: "rahul" },
    },
  });
}

async function startDeletion() {
  await fireEvent.click(screen.getByRole("button", { name: /delete my account/i }));
  await fireEvent.input(screen.getByLabelText(/confirm your password/i), {
    target: { value: "hunter2" },
  });
  await fireEvent.click(screen.getByRole("button", { name: /permanently delete/i }));
}

describe("deleting an account", () => {
  it("offers no Cancel once the deletion has been submitted", async () => {
    const server = stubHeldDelete();
    mount();
    await startDeletion();

    await waitFor(() => expect(server.deleteCalls()).toBe(1));
    expect(screen.queryByRole("button", { name: /^cancel$/i })).toBeNull();
    expect(screen.getByRole("button", { name: /deleting account…/i })).toBeDisabled();
    // And the page says what is happening, rather than looking idle.
    expect(screen.getByRole("status").textContent).toMatch(/cannot be cancelled or undone/i);
  });

  it("cannot be submitted twice while the first request is out", async () => {
    // The button was disabled while busy, and a disabled button is a
    // presentation. The guard belongs in the function.
    const server = stubHeldDelete();
    mount();
    await startDeletion();
    await waitFor(() => expect(server.deleteCalls()).toBe(1));

    await fireEvent.click(screen.getByRole("button", { name: /deleting account…/i }));
    expect(server.deleteCalls()).toBe(1);
  });

  it("gives the owner the form back when the deletion is refused", async () => {
    // The recovery path is unchanged: a refused deletion is an ordinary failure
    // and must leave the owner able to try again or to leave.
    const server = stubHeldDelete();
    mount();
    await startDeletion();
    await waitFor(() => expect(server.deleteCalls()).toBe(1));

    server.refuse();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/could not delete account/i),
    );
    expect(screen.getByRole("button", { name: /^cancel$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /permanently delete/i })).toBeInTheDocument();
  });

  it("still lets the owner back out before anything has been submitted", async () => {
    stubHeldDelete();
    mount();
    await fireEvent.click(screen.getByRole("button", { name: /delete my account/i }));

    await fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(screen.getByRole("button", { name: /delete my account/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/confirm your password/i)).toBeNull();
  });
});
