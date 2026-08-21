// C16 — audio ends when the conversation surface leaves the screen.
//
// Chat and Build are kept mounted across route visits so a long conversation
// survives a trip to Permissions. That is right for the transcript and wrong for
// the microphone: the unmount cleanup carrying the `route` reason never fires on
// an ordinary navigation, so dictation could keep listening behind a hidden
// composer whose only Stop control was hidden with it.
//
// These tests drive the real `visible` prop App.svelte passes, and assert
// against the shared audio coordinator rather than against a mock, because the
// property that matters is that the single audio owner is actually released.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeGate, stubFetch } from "../test-helpers";
import { resetModels } from "../models.svelte";
import { audioSessionCoordinator } from "../voice";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, streamPrompt: vi.fn() };
});

import ChatView from "./ChatView.svelte";
import BuildView from "./BuildView.svelte";

class FakeRecognition {
  static instance: FakeRecognition;
  static aborted = 0;
  continuous = false;
  interimResults = false;
  lang = "";
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  constructor() { FakeRecognition.instance = this; }
  start() {}
  stop() { this.onend?.(); }
  abort() { FakeRecognition.aborted += 1; this.onend?.(); }
  final(text: string) {
    this.onresult?.({ resultIndex: 0, results: [Object.assign([{ transcript: text }], { isFinal: true })] });
  }
}

afterEach(() => {
  audioSessionCoordinator.stopAll("route");
  vi.unstubAllGlobals();
  resetModels();
  FakeRecognition.aborted = 0;
});

const READY_PROFILE = {
  profile_id: "test-ready", provider: "ollama", model: "test-model",
  selected: true, configured: true, ready: true, readiness_state: "ready",
};

function routes() {
  return {
    "GET /api/models": { profiles: [READY_PROFILE], chat_profiles: [READY_PROFILE] },
    "GET /api/code/repos": { repos: [], selected_repo_id: null },
    "GET /api/tasks": [],
    "GET /api/capability-gates": [
      "file_write_execution",
      "patch_apply_execution",
      "shell_execution",
      "process_execution",
    ].map((capability) => makeGate({ capability, decision_mode: "ask" })),
  };
}

describe.each([
  {
    name: "Chat",
    Component: ChatView,
    props: { projects: null },
    promptLabel: "Prompt",
  },
  {
    name: "Build",
    Component: BuildView,
    props: {},
    promptLabel: "Describe the change",
  },
])("$name keeps dictation on the surface that owns it", ({ Component, props, promptLabel }) => {
  it("stops listening when the surface is navigated away from", async () => {
    vi.stubGlobal("SpeechRecognition", FakeRecognition);
    stubFetch(routes());
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const view = render(Component as any, { ...props, visible: true });

    await fireEvent.click(await screen.findByRole("button", { name: "Dictate" }));
    FakeRecognition.instance.final("keep these words");
    expect(await screen.findByRole("button", { name: "Cancel dictation" })).toBeInTheDocument();

    // The owner navigates elsewhere. The view stays mounted; the microphone
    // must not.
    await view.rerender({ ...props, visible: false });

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Cancel dictation" })).not.toBeInTheDocument(),
    );
    expect(FakeRecognition.aborted).toBeGreaterThan(0);
    // Finalized words are kept, exactly as pressing Done would leave them —
    // stopping the microphone must not discard what was already dictated.
    expect(screen.getByLabelText(promptLabel)).toHaveValue("keep these words");
  });
});
