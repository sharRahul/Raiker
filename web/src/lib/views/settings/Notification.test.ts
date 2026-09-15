import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Notification from "./Notification.svelte";

/**
 * REM-SET-NOTIFY. The page carried two switches under a heading that read
 * **Alerts** and neither said what it reached: one governed a banner mounted on
 * a single destination, and the other claimed a scope narrower than it had.
 * These assert what each one is now allowed to say.
 */
describe("Notification settings", () => {
  it("names what each switch reaches, rather than calling both 'alerts'", () => {
    render(Notification, { settings: {}, save: vi.fn() });

    expect(screen.getByLabelText("Show unread notices inside Raiker")).toBeInTheDocument();
    expect(screen.getByLabelText("Alert me outside Raiker")).toBeInTheDocument();
    // The old copy claimed the desktop switch covered approvals. It covers
    // every unread notice, and saying less than it does is still saying the
    // wrong thing.
    expect(screen.queryByText(/cover approvals waiting on you/)).not.toBeInTheDocument();
  });

  it("says plainly that muting is not deciding", () => {
    render(Notification, { settings: {}, save: vi.fn() });
    expect(
      screen.getByText(/an approval nobody is alerted about still waits for you/i),
    ).toBeInTheDocument();
  });

  it("links the record that survives both switches being off", () => {
    render(Notification, { settings: {}, save: vi.fn() });
    expect(screen.getByRole("link", { name: "Open notifications" })).toHaveAttribute(
      "href",
      "#/observe?tab=notifications",
    );
  });

  it("says so when the browser has blocked what the switch promises", () => {
    // A preference that is on while the browser refuses is a switch that
    // silently does nothing — which is the thing an owner discovers by a notice
    // never arriving.
    vi.stubGlobal("Notification", { permission: "denied", requestPermission: vi.fn() });
    render(Notification, { settings: { "notification.desktop": true }, save: vi.fn() });

    expect(screen.getByRole("status")).toHaveTextContent(
      /This browser has blocked notifications for Raiker/,
    );
    vi.unstubAllGlobals();
  });

  it("stays quiet about permission while the switch is off", () => {
    vi.stubGlobal("Notification", { permission: "denied", requestPermission: vi.fn() });
    render(Notification, { settings: { "notification.desktop": false }, save: vi.fn() });

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("saves each switch under the key the runtime reads", async () => {
    const save = vi.fn();
    render(Notification, { settings: {}, save });

    await fireEvent.click(screen.getByLabelText("Show unread notices inside Raiker"));
    expect(save).toHaveBeenCalledWith({ "notification.in_app": false });
  });
});
