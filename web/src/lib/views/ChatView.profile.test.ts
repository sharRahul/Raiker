/**
 * QUI-P02 — the profile chip on Chat's composer: Careful asks before every
 * change for this conversation, sent as a per-turn override that can only
 * tighten; Standard sends nothing.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../test-helpers";
import { resetModels } from "../models.svelte";

const streamPromptMock = vi.hoisted(() => vi.fn());
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, streamPrompt: streamPromptMock };
});

import ChatView from "./ChatView.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  streamPromptMock.mockReset();
  resetModels();
});

const READY_PROFILE = {
  profile_id: "test-ready",
  provider: "ollama",
  model: "test-model",
  selected: true,
  ready: true,
  readiness_state: "ready",
};

const GATES = [
  { capability: "file_write_execution", side_effect: "reversible" },
  { capability: "web_fetch_runtime", side_effect: "read" },
  { capability: "connector_write_runtime", side_effect: "external" },
];

function routes() {
  return {
    "GET /api/models": { profiles: [READY_PROFILE], chat_profiles: [READY_PROFILE] },
    "GET /api/settings": { settings: {}, status: { vault: "ok", mfa_enrolled: false, username: "owner" } },
    "GET /api/capability-gates": GATES,
    "GET /api/settings/composer-approval-mode": { approval_mode: "manual" },
  };
}

async function send(text: string) {
  await fireEvent.input(screen.getByLabelText("Prompt"), { target: { value: text } });
  await fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("ChatView — profile chip (QUI-P02)", () => {
  // Found live (RT-QUI-29): the first streamed chunk gave the new chat its id,
  // and the chip went back to Standard.
  it("keeps Careful when a new chat learns its id from the first chunk", async () => {
    const fetch = stubFetch({ ...routes(), "PUT /api/sessions/sess_new/profile": { ok: true, session_id: "sess_new", profile: "careful" } });
    streamPromptMock.mockImplementation(async (_body: unknown, onEvent: (event: unknown) => void) => {
      onEvent({ kind: "token", text: "Hi", event_type: "", payload: {}, session_id: "sess_new" });
    });
    render(ChatView, {});
    await fireEvent.click(await screen.findByRole("button", { name: /without asking: Standard/ }));
    await fireEvent.click(screen.getByRole("radio", { name: /Careful/ }));
    await waitFor(async () => {
      streamPromptMock.mockClear();
      await send("Hello");
      expect(streamPromptMock).toHaveBeenCalled();
    });
    // Kept on the conversation (decided 2026-10-25), not in this browser.
    await waitFor(() =>
      expect(
        fetch.mock.calls.some(
          ([input, init]) =>
            String(input).includes("/api/sessions/sess_new/profile") &&
            (init as RequestInit | undefined)?.method === "PUT" &&
            JSON.parse(String((init as RequestInit).body)).profile === "careful",
        ),
      ).toBe(true),
    );
    expect(screen.getByRole("button", { name: /without asking: Careful/ })).toBeInTheDocument();
  });

  it("sends no override in Standard, the default", async () => {
    stubFetch(routes());
    render(ChatView, {});
    expect(await screen.findByRole("button", { name: /without asking: Standard/ })).toBeInTheDocument();
    await send("Hello");
    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0]).not.toHaveProperty("capability_modes");
  });

  it("asks before every change in Careful, leaving reads alone", async () => {
    stubFetch(routes());
    render(ChatView, {});
    await fireEvent.click(await screen.findByRole("button", { name: /without asking: Standard/ }));
    expect(screen.getByText(/Asks before every change, even ones your permissions allow/)).toBeInTheDocument();
    expect(screen.queryByText(/Within limits/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Skip/)).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole("radio", { name: /Careful/ }));
    expect(screen.getByRole("button", { name: /without asking: Careful/ })).toBeInTheDocument();

    await waitFor(async () => {
      streamPromptMock.mockClear();
      await send("Tidy my notes");
      expect(streamPromptMock).toHaveBeenCalled();
      expect(streamPromptMock.mock.calls[0][0].capability_modes).toEqual({
        file_write_execution: "ask",
        connector_write_runtime: "ask",
      });
    });
  });
});
