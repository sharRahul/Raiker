/** QUI-G06 — Sessions errors keep what was read and say how to check before repeating a delete. */
import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import SessionsView from "./SessionsView.svelte";
import { stubFetch } from "../test-helpers";

const SESSION = {
  session_id: "sess_b",
  title: "Second chat",
  status: "open",
  created_at: "2026-07-10T00:00:00Z",
  updated_at: "2026-07-10T00:01:00Z",
  turn_count: 1,
  pinned: false,
  tags: [],
  project_id: null,
  archived: false,
  archived_at: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Sessions recovery (QUI-G06)", () => {
  it("retries a failed read and keeps rows when a refresh fails", async () => {
    const routes: Record<string, unknown> = { "GET /api/sessions": { __status: 503 } };
    stubFetch(routes);
    render(SessionsView);
    expect(await screen.findByText(/sessions could not be read \(HTTP 503\)\. Which conversations exist is unknown/i)).toBeInTheDocument();
    routes["GET /api/sessions"] = [SESSION];
    await fireEvent.click(screen.getByRole("button", { name: "Retry sessions" }));
    expect(await screen.findByText("Second chat")).toBeInTheDocument();
    routes["GET /api/sessions"] = { __status: 500 };
    await fireEvent.click(screen.getByRole("button", { name: "Refresh sessions" }));
    expect(await screen.findByText(/the list below may be out of date/i)).toBeInTheDocument();
    expect(screen.getByText("Second chat")).toBeInTheDocument();
  });

  it("keeps the selection after an unconfirmed bulk delete", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    stubFetch({ "GET /api/sessions": [SESSION], "DELETE /api/sessions/bulk": { __status: 502 } });
    render(SessionsView);
    await fireEvent.click(await screen.findByRole("checkbox", { name: /Second chat/i }));
    await fireEvent.click(screen.getByRole("button", { name: /delete selected/i }));
    expect(await screen.findByText(/deleting the selected conversations was not confirmed \(HTTP 502\)/i)).toBeInTheDocument();
    expect(screen.getByText(/check which are still listed before deleting again/i)).toBeInTheDocument();
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
  });

  it("opens a session again after its detail could not be read", async () => {
    const routes: Record<string, unknown> = { "GET /api/sessions": [SESSION], "GET /api/sessions/sess_b": { __status: 500 } };
    stubFetch(routes);
    render(SessionsView, { sessionId: "sess_b" });
    expect(await screen.findByText(/this session could not be opened \(HTTP 500\)/i)).toBeInTheDocument();
    routes["GET /api/sessions/sess_b"] = { session: SESSION, turns: [] };
    await fireEvent.click(screen.getByRole("button", { name: "Open it again" }));
    expect(await screen.findByRole("heading", { name: "Second chat" })).toBeInTheDocument();
  });
});
