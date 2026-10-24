import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import QuickEntryView from "./QuickEntryView.svelte";
import { routeFromHash } from "../nav";
import { stubFetch } from "../test-helpers";

function bridge() {
  const value = {
    bridgeVersion: 1, platform: "linux", onCommand: () => () => {}, setTitleBarColours: () => {},
    focusWindow: vi.fn(), closeWindow: vi.fn(),
  };
  (window as { raikerDesktop?: unknown }).raikerDesktop = value;
  return value;
}

afterEach(() => {
  vi.unstubAllGlobals();
  delete (window as { raikerDesktop?: unknown }).raikerDesktop;
});

describe("QUI-F01 Quick Entry", () => {
  it("is a route of its own", () => {
    expect(routeFromHash("#/quick-entry")).toBe("quick-entry");
  });

  it("files a new task, hides at once, and keeps the main window where it is", async () => {
    const shell = bridge();
    const fetchMock = stubFetch({
      "GET /api/sessions": [],
      "POST /api/tasks": { task_id: "t1", title: "Book flights", status: "queued" },
    });
    render(QuickEntryView);
    const box = screen.getByRole("textbox", { name: "Ask Raiker" });
    await fireEvent.input(box, { target: { value: "Book flights to Lisbon" } });
    await fireEvent.keyDown(box, { key: "Enter" });
    expect(shell.closeWindow).toHaveBeenCalled();
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/api/tasks") && (init as RequestInit).method === "POST")).toBe(true),
    );
    expect(shell.focusWindow).not.toHaveBeenCalled();
  });

  it("sends to a recent conversation, and comes back with the message when it fails", async () => {
    const shell = bridge();
    stubFetch({
      "GET /api/sessions": [{ session_id: "s1", title: "Trip planning", updated_at: "2026-10-24T08:00:00Z" }],
      "POST /api/prompts": { __status: 409, detail: { reason_code: "model_not_ready" } },
    });
    render(QuickEntryView);
    const picker = (await screen.findByRole("combobox", { name: "Send to" })) as HTMLSelectElement;
    await screen.findByRole("option", { name: "Trip planning" });
    await fireEvent.change(picker, { target: { value: "s1" } });
    const box = screen.getByRole("textbox", { name: "Ask Raiker" }) as HTMLInputElement;
    await fireEvent.input(box, { target: { value: "Add a hotel" } });
    await fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(shell.focusWindow).toHaveBeenCalled());
    expect(screen.getByRole("alert")).toHaveTextContent(/kept/);
    expect(box.value).toBe("Add a hotel");
  });

  it("Esc hides it", async () => {
    const shell = bridge();
    stubFetch({ "GET /api/sessions": [] });
    render(QuickEntryView);
    await fireEvent.keyDown(screen.getByRole("textbox", { name: "Ask Raiker" }), { key: "Escape" });
    expect(shell.closeWindow).toHaveBeenCalled();
  });
});
