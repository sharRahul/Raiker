import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import ConversationIncognito from "./ConversationIncognito.svelte";

vi.mock("../api", () => ({ api: {
  startIncognitoConversation: vi.fn(), setSessionIncognito: vi.fn(),
} }));
import { api } from "../api";

describe("Conversation Incognito", () => {
  it("creates a saved private conversation before the first turn", async () => {
    vi.mocked(api.startIncognitoConversation).mockResolvedValue({ ok: true, session_id: "sess_private", incognito: true });
    const saved = vi.fn();
    render(ConversationIncognito, { onsaved: saved });
    await fireEvent.click(screen.getByRole("switch", { name: "Incognito for this conversation" }));
    expect(await screen.findByRole("switch", { checked: true })).toBeInTheDocument();
    expect(screen.getByText(/Messages in this chat are still saved/)).toBeInTheDocument();
    expect(saved).toHaveBeenCalledWith("sess_private");
  });
  it("keeps the saved setting when a change fails", async () => {
    vi.mocked(api.setSessionIncognito).mockRejectedValue(new Error("offline"));
    render(ConversationIncognito, { sessionId: "sess_private", incognito: true });
    await fireEvent.click(screen.getByRole("switch"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not change/i);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });
  it("cannot change recall while a turn runs", () => {
    render(ConversationIncognito, { disabled: true });
    expect(screen.getByRole("switch")).toBeDisabled();
  });
});
