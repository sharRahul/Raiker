# Governed Turn-Based Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete GAP-CHAT C16 by adding editable, explicit-send dictation and manual response read-aloud to Raiker Chat and Build, with governed input provenance and no Raiker-side audio retention.

**Architecture:** A shared browser adapter owns speech recognition, speech synthesis and single-audio-owner coordination. Focused Svelte components expose that state in both existing composers and response action rows. The existing prompt API carries only a constrained `typed | dictated | mixed` provenance field through prompt metadata and the safe event payload; raw audio never reaches the Raiker backend.

**Tech Stack:** Svelte 5, TypeScript 5, browser Web Speech APIs, Vitest, Testing Library, FastAPI, Python 3.11 dataclasses/Pydantic request parsing, pytest, Playwright CLI/project tests.

## Global Constraints

- Implement only governed turn-based voice in this delivery; continuous listening, automatic silence submission, simultaneous listening/speaking, barge-in, wake words, voice cloning, retained audio and a hosted STT/TTS gateway remain out of scope.
- Dictation must never submit a prompt. The owner stops or cancels it, reviews the draft, and separately sends.
- Chat and Build must consume the same adapter and UI components.
- Voice must work with every existing text model profile and must not bypass model readiness, capabilities, approvals, Build mode, sandboxing or tool governance.
- Raiker must neither receive nor store raw audio. UI copy must disclose that the browser speech engine may process audio externally.
- Only one recognition or playback owner may be active. Starting one audio action stops the previous one.
- Persist the speech language per owner through the existing settings API.
- The accepted speech languages are Auto plus `en`, `fr`, `de`, `hi`, `it`, `ja`, `ko`, `pt`, `ru`, `es`, `tr` and `uk`.
- Record only `typed`, `dictated` or `mixed` input provenance. Do not duplicate prompt text or add audio/language to the audit event.
- All new production behavior follows red-green-refactor. Each failing test must be observed before its production change.
- Preserve existing UI tokens and component vocabulary; support keyboard, touch, 320 CSS-pixel width, reduced motion, dark/high-contrast themes and print omission.
- Never place provider credentials in source, commands, logs, screenshots or documentation.

---

### Task 1: Browser voice adapters and readable speech text

**Files:**
- Create: `apps/web/src/lib/voice.ts`
- Create: `apps/web/src/lib/voice.test.ts`
- Modify: `apps/web/src/test-setup.ts`

**Interfaces:**
- Produces: `VoiceInputMode`, `SpeechLanguage`, `VoiceRecognitionAdapter`, `RecognitionHandlers`, `browserRecognitionAdapter`, `voicePlayback`, `speechText(markdown: string): string`, and `inputModeForDraft(state): VoiceInputMode`.
- Consumes: browser `SpeechRecognition`/`webkitSpeechRecognition`, `speechSynthesis`, `SpeechSynthesisUtterance`, and deterministic injected fakes in tests.

- [ ] **Step 1: Write failing adapter and text-conversion tests**

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createRecognitionAdapter,
  createVoicePlaybackCoordinator,
  inputModeForDraft,
  speechText,
} from "./voice";

describe("voice recognition adapter", () => {
  it("forwards interim and final segments without submitting anything", () => {
    const FakeRecognition = recognitionFake();
    const interim = vi.fn();
    const final = vi.fn();
    const adapter = createRecognitionAdapter(FakeRecognition);
    adapter.start("en", { interim, final, end: vi.fn(), error: vi.fn() });
    FakeRecognition.instance.emitResult([
      { transcript: "draft words", isFinal: false },
      { transcript: "final words", isFinal: true },
    ]);
    expect(interim).toHaveBeenCalledWith("draft words");
    expect(final).toHaveBeenCalledWith("final words");
  });

  it("aborts the current recognition owner before playback starts", () => {
    const abort = vi.fn();
    const synth = synthesisFake();
    const coordinator = createVoicePlaybackCoordinator(synth, () => abort());
    coordinator.speak("turn-1", "Answer", "en", { end: vi.fn(), error: vi.fn() });
    expect(abort).toHaveBeenCalledOnce();
    expect(synth.speak).toHaveBeenCalledOnce();
  });
});

it("classifies the submitted draft from actual dictation contribution", () => {
  expect(inputModeForDraft({ dictated: false, typedBefore: false, editedAfter: false })).toBe("typed");
  expect(inputModeForDraft({ dictated: true, typedBefore: false, editedAfter: false })).toBe("dictated");
  expect(inputModeForDraft({ dictated: true, typedBefore: true, editedAfter: false })).toBe("mixed");
  expect(inputModeForDraft({ dictated: true, typedBefore: false, editedAfter: true })).toBe("mixed");
});

it("speaks answer text without markdown syntax, raw URLs, citations or code bodies", () => {
  expect(speechText("See [the guide](https://example.test) [s1].\n```ts\nconst secret = 1\n```"))
    .toBe("See the guide. Code block.");
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm --prefix apps/web test -- src/lib/voice.test.ts`

Expected: FAIL because `./voice` does not exist.

- [ ] **Step 3: Implement the minimal typed adapters and coordinator**

```ts
export type VoiceInputMode = "typed" | "dictated" | "mixed";
export type SpeechLanguage = "auto" | "en" | "fr" | "de" | "hi" | "it" | "ja" | "ko" | "pt" | "ru" | "es" | "tr" | "uk";

export interface RecognitionHandlers {
  interim(text: string): void;
  final(text: string): void;
  end(): void;
  error(code: string): void;
}

export interface VoiceRecognitionAdapter {
  supported(): boolean;
  start(language: SpeechLanguage, handlers: RecognitionHandlers): void;
  stop(): void;
  abort(): void;
}

export function inputModeForDraft(state: {
  dictated: boolean;
  typedBefore: boolean;
  editedAfter: boolean;
}): VoiceInputMode {
  if (!state.dictated) return "typed";
  return state.typedBefore || state.editedAfter ? "mixed" : "dictated";
}
```

The implementation must resolve `window.SpeechRecognition ?? window.webkitSpeechRecognition`, set `continuous = true`, `interimResults = true`, translate result ranges into interim/final strings, and expose `supported() === false` without throwing. The playback coordinator must cancel the current utterance before another starts and expose the active response id. `speechText` must remove citation markers, preserve link labels, collapse Markdown syntax, and replace every fenced code block with `Code block.`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm --prefix apps/web test -- src/lib/voice.test.ts`

Expected: PASS with no warnings.

- [ ] **Step 5: Commit the adapter slice**

```powershell
git add -- apps/web/src/lib/voice.ts apps/web/src/lib/voice.test.ts apps/web/src/test-setup.ts
git commit -m "feat: add shared browser voice adapters"
```

---

### Task 2: Dictation control with explicit Done and Cancel

**Files:**
- Create: `apps/web/src/lib/components/VoiceDictationControl.svelte`
- Create: `apps/web/src/lib/components/VoiceDictationControl.test.ts`
- Modify: `apps/web/src/lib/icons.ts`

**Interfaces:**
- Consumes: `VoiceRecognitionAdapter`, `SpeechLanguage`, draft value, textarea selection, and `onchange`, `onmodechange`, `onactivechange` callbacks.
- Produces: one accessible Dictate/Listening/Done/Cancel control that both views mount.

- [ ] **Step 1: Write failing component behavior tests**

```ts
import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import VoiceDictationControl from "./VoiceDictationControl.svelte";

it("keeps recognized words editable and never sends", async () => {
  const adapter = recognitionAdapterFake();
  const onchange = vi.fn();
  render(VoiceDictationControl, {
    draft: "Review  today",
    selectionStart: 7,
    selectionEnd: 7,
    language: "en",
    adapter,
    onchange,
  });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  adapter.final("the plan");
  expect(onchange).toHaveBeenLastCalledWith("Review the plan today", 15);
  await fireEvent.click(screen.getByRole("button", { name: "Done dictating" }));
  expect(screen.getByRole("button", { name: "Dictate" })).toBeInTheDocument();
});

it("cancel restores the complete draft and selection snapshot", async () => {
  const adapter = recognitionAdapterFake();
  const onchange = vi.fn();
  render(VoiceDictationControl, {
    draft: "keep this",
    selectionStart: 4,
    selectionEnd: 4,
    language: "auto",
    adapter,
    onchange,
  });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  adapter.final("discarded");
  await fireEvent.click(screen.getByRole("button", { name: "Cancel dictation" }));
  expect(onchange).toHaveBeenLastCalledWith("keep this", 4);
});

it.each([
  ["not-allowed", /Allow microphone and speech-recognition access/],
  ["audio-capture", /No usable microphone was found/],
  ["no-speech", /No speech was recognized/],
  ["network", /browser speech service is unavailable/],
])("maps %s to exact recovery guidance", async (code, message) => {
  const adapter = recognitionAdapterFake();
  render(VoiceDictationControl, { draft: "", language: "auto", adapter, onchange: vi.fn() });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  adapter.error(code);
  expect(screen.getByRole("alert")).toHaveTextContent(message);
});
```

- [ ] **Step 2: Run the component test and verify RED**

Run: `npm --prefix apps/web test -- src/lib/components/VoiceDictationControl.test.ts`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the component and microphone icon state**

The component must snapshot draft/selection at start, maintain interim text separately from finalized draft text, normalize only insertion-boundary spaces, and expose these exact labels: **Dictate**, **Listening…**, **Done dictating**, and **Cancel dictation**. Unsupported recognition renders a disabled Dictate control plus “Dictation is unavailable because this browser does not provide speech recognition. You can keep typing.” Recording state uses text plus the existing accent token; any pulse/wave line disables motion under `prefers-reduced-motion`.

- [ ] **Step 4: Run the component test and verify GREEN**

Run: `npm --prefix apps/web test -- src/lib/components/VoiceDictationControl.test.ts`

Expected: PASS with no accessibility warnings.

- [ ] **Step 5: Commit the dictation component**

```powershell
git add -- apps/web/src/lib/components/VoiceDictationControl.svelte apps/web/src/lib/components/VoiceDictationControl.test.ts apps/web/src/lib/icons.ts
git commit -m "feat: add governed dictation control"
```

---

### Task 3: Manual response read-aloud control

**Files:**
- Create: `apps/web/src/lib/components/ReadAloudButton.svelte`
- Create: `apps/web/src/lib/components/ReadAloudButton.test.ts`
- Modify: `apps/web/src/lib/icons.ts`

**Interfaces:**
- Consumes: completed visible answer text, response id, chosen speech language, and the shared playback coordinator.
- Produces: **Read aloud** / **Stop speaking** button with pressed state and visible failure status.

- [ ] **Step 1: Write failing read-aloud tests**

```ts
it("reads only the visible answer and toggles to Stop speaking", async () => {
  const playback = playbackFake();
  render(ReadAloudButton, { responseId: "turn-1", text: "**Ready** [s1]", language: "en", playback });
  await fireEvent.click(screen.getByRole("button", { name: "Read aloud" }));
  expect(playback.speak).toHaveBeenCalledWith("turn-1", "Ready", "en", expect.any(Object));
  expect(screen.getByRole("button", { name: "Stop speaking" })).toHaveAttribute("aria-pressed", "true");
  await fireEvent.click(screen.getByRole("button", { name: "Stop speaking" }));
  expect(playback.stop).toHaveBeenCalledOnce();
});

it("states playback failure and leaves text controls usable", async () => {
  const playback = playbackFake();
  render(ReadAloudButton, { responseId: "turn-1", text: "Answer", language: "auto", playback });
  await fireEvent.click(screen.getByRole("button", { name: "Read aloud" }));
  playback.error();
  expect(screen.getByRole("status")).toHaveTextContent("This device could not play the response.");
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npm --prefix apps/web test -- src/lib/components/ReadAloudButton.test.ts`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement manual playback only**

Render a disabled button with “Read aloud is unavailable on this device.” when synthesis is unsupported. Never mount the control for streaming, empty, failed or approval-waiting responses; the views enforce that boundary in Task 5. Use only `speechText(text)` output and never reasoning/tool/approval payloads.

- [ ] **Step 4: Run the test and verify GREEN**

Run: `npm --prefix apps/web test -- src/lib/components/ReadAloudButton.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit the playback component**

```powershell
git add -- apps/web/src/lib/components/ReadAloudButton.svelte apps/web/src/lib/components/ReadAloudButton.test.ts apps/web/src/lib/icons.ts
git commit -m "feat: add manual response read aloud"
```

---

### Task 4: Governed prompt provenance and speech-language settings contract

**Files:**
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_prompts.py`
- Modify: `raiker/gateway/agent_gateway.py`
- Modify: `raiker/api/routes_settings.py`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Test: `tests/test_api_prompts.py`
- Test: `tests/test_routes_settings.py`

**Interfaces:**
- Produces: `PromptRequest.input_mode`, `PromptRequestBody.input_mode`, prompt metadata `input_mode`, `prompt_received.payload.input_mode`, and validated `general.speech_language` persistence.
- Consumes: existing prompt envelope, event writer and opaque owner settings blob.

- [ ] **Step 1: Write failing Python contract tests**

```py
def test_prompt_input_mode_reaches_metadata_and_safe_event(workspace, mark_model_ready) -> None:
    envelope = _build_envelope(PromptRequest(text="spoken draft", input_mode="dictated"))
    assert envelope.prompt.metadata["input_mode"] == "dictated"
    gateway = AgentGateway(workspace, principal_id="principal_owner")
    gateway._prepare_turn(envelope)
    event = next(
        json.loads(line)
        for line in gateway.writer.path_for_session(envelope.session_id).read_text().splitlines()
        if json.loads(line)["event_type"] == "prompt_received"
    )
    assert event["payload"] == {
        "client_type": "web_ui",
        "prompt_length": len("spoken draft"),
        "input_mode": "dictated",
    }
    assert "spoken draft" not in json.dumps(event["payload"])

def test_prompt_rejects_unknown_input_mode(client) -> None:
    response = client.post(
        "/api/prompts",
        json={"text": "hello", "input_mode": "always-listening"},
        headers=_headers(_token(client)),
    )
    assert response.status_code == 422

def test_settings_reject_unknown_speech_language_and_preserve_previous(client) -> None:
    token = _token(client, "alice")
    accepted = client.put(
        "/api/settings",
        json={"settings": {"general.speech_language": "fr"}},
        headers=_h(token),
    )
    assert accepted.status_code == 200
    rejected = client.put(
        "/api/settings",
        json={"settings": {"general.speech_language": "unbounded"}},
        headers=_h(token),
    )
    assert rejected.status_code == 422
    assert client.get("/api/settings", headers=_h(token)).json()["settings"] == {
        "general.speech_language": "fr"
    }
```

- [ ] **Step 2: Run the focused backend tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api_prompts.py tests/test_routes_settings.py -q`

Expected: FAIL because the prompt field, metadata/event field and settings validation are absent.

- [ ] **Step 3: Implement constrained provenance and language validation**

```py
VOICE_INPUT_MODES = {"typed", "dictated", "mixed"}
SPEECH_LANGUAGES = {"auto", "en", "fr", "de", "hi", "it", "ja", "ko", "pt", "ru", "es", "tr", "uk"}

@dataclass
class PromptRequest:
    text: str
    input_mode: Literal["typed", "dictated", "mixed"] = "typed"
    # existing fields stay unchanged
```

`_build_envelope` must validate direct Python callers as well as FastAPI parsing, then add `input_mode` beside `entry_command` in prompt metadata. `_prepare_turn` reads the constrained metadata value and writes only that value, client type and prompt length. `put_settings` validates `general.speech_language` before writing and returns HTTP 422 without mutating the previous settings row.

- [ ] **Step 4: Add the TypeScript request field**

```ts
export interface PromptRequestBody {
  text: string;
  input_mode?: "typed" | "dictated" | "mixed";
  // existing fields unchanged
}
```

- [ ] **Step 5: Run the focused backend tests and verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api_prompts.py tests/test_routes_settings.py -q`

Expected: PASS.

- [ ] **Step 6: Run schema/type checks for the contract slice**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api_contract_schemas.py -q`

Run: `npm --prefix apps/web run check`

Expected: both exit 0.

- [ ] **Step 7: Commit the backend contract slice**

```powershell
git add -- raiker/api/schemas.py raiker/api/routes_prompts.py raiker/gateway/agent_gateway.py raiker/api/routes_settings.py apps/web/src/lib/apiTypes.ts tests/test_api_prompts.py tests/test_routes_settings.py
git commit -m "feat: govern voice prompt provenance"
```

---

### Task 5: Integrate voice parity into Chat, Build and General settings

**Files:**
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Modify: `apps/web/src/lib/views/BuildView.svelte`
- Modify: `apps/web/src/lib/views/settings/General.svelte`
- Modify: `apps/web/src/lib/views/ChatView.composerParity.test.ts`
- Modify: `apps/web/src/lib/views/BuildView.test.ts`
- Create: `apps/web/src/lib/views/settings/General.test.ts`

**Interfaces:**
- Consumes: Task 1 adapters, Task 2/3 controls, `PromptRequestBody.input_mode`, and owner `general.speech_language`.
- Produces: identical Dictate behavior in both composers, Read aloud on completed answers, and persisted language selection.

- [ ] **Step 1: Write failing Chat and Build parity tests**

```ts
it.each([
  ["Chat", ChatView, "Prompt"],
  ["Build", BuildView, "Describe the change"],
])("%s sends a dictated draft only after explicit Send", async (_name, View, label) => {
  const recognition = installRecognitionFake();
  stubFetch(voiceReadyRoutes());
  render(View);
  await fireEvent.click(await screen.findByRole("button", { name: "Dictate" }));
  recognition.final("check the repository");
  await fireEvent.click(screen.getByRole("button", { name: "Done dictating" }));
  expect(streamPromptMock).not.toHaveBeenCalled();
  expect(screen.getByLabelText(label)).toHaveValue("check the repository");
  await fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(streamPromptMock.mock.calls[0][0]).toMatchObject({
    text: "check the repository",
    input_mode: "dictated",
  });
});

it("marks a typed and edited dictated draft as mixed", async () => {
  const recognition = installRecognitionFake();
  render(ChatView, { projects });
  const prompt = await screen.findByLabelText("Prompt");
  await fireEvent.input(prompt, { target: { value: "Please " } });
  await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
  recognition.final("summarize this");
  await fireEvent.click(screen.getByRole("button", { name: "Done dictating" }));
  await fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(streamPromptMock.mock.calls[0][0].input_mode).toBe("mixed");
});
```

Add a completed-response test to each view asserting **Read aloud** appears beside Copy, while streaming/approval-waiting answers have no read-aloud control.

- [ ] **Step 2: Write the failing General settings test**

```ts
it("offers the exact persisted speech language set and disclosure", async () => {
  const save = vi.fn();
  render(General, { settings: { "general.speech_language": "fr" }, save });
  const select = screen.getByLabelText("Speech language");
  expect(select).toHaveValue("fr");
  expect(within(select).getAllByRole("option").map((o) => o.getAttribute("value")))
    .toEqual(["auto", "en", "fr", "de", "hi", "it", "ja", "ko", "pt", "ru", "es", "tr", "uk"]);
  expect(screen.getByText(/browser's speech service may process audio externally/)).toBeInTheDocument();
  await fireEvent.change(select, { target: { value: "ja" } });
  expect(save).toHaveBeenCalledWith({ "general.speech_language": "ja" });
});
```

- [ ] **Step 3: Run view/settings tests and verify RED**

Run: `npm --prefix apps/web test -- src/lib/views/ChatView.composerParity.test.ts src/lib/views/BuildView.test.ts src/lib/views/settings/General.test.ts`

Expected: FAIL because the controls, request provenance and setting are not mounted.

- [ ] **Step 4: Integrate the shared components without duplicating voice logic**

Each view loads `general.speech_language` with default `auto`, tracks whether finalized dictation contributed to the current draft, resets provenance after a successful submit/new conversation, and passes `input_mode: inputModeForDraft(...)` to `streamPrompt`. The view's Enter handler must call the dictation component's Done behavior and return while recognition is active; only the next Enter can submit. On submit, route change or component teardown, stop recognition/playback through the shared coordinator.

Mount `VoiceDictationControl` in `.bar-left` immediately after `ComposerAttach`. Mount `ReadAloudButton` in a shared `.response-actions` row beside Copy for completed visible answers. General settings adds the exact language options and disclosure in the existing Language and region card.

- [ ] **Step 5: Run view/settings tests and verify GREEN**

Run: `npm --prefix apps/web test -- src/lib/views/ChatView.composerParity.test.ts src/lib/views/BuildView.test.ts src/lib/views/settings/General.test.ts`

Expected: PASS.

- [ ] **Step 6: Run the complete web unit/check/lint/build gate**

Run: `npm --prefix apps/web test`

Run: `npm --prefix apps/web run check`

Run: `npm --prefix apps/web run lint`

Run: `npm --prefix apps/web run build`

Expected: all exit 0 with no warnings introduced by this change.

- [ ] **Step 7: Commit the integrated UI slice**

```powershell
git add -- apps/web/src/lib/views/ChatView.svelte apps/web/src/lib/views/BuildView.svelte apps/web/src/lib/views/settings/General.svelte apps/web/src/lib/views/ChatView.composerParity.test.ts apps/web/src/lib/views/BuildView.test.ts apps/web/src/lib/views/settings/General.test.ts
git commit -m "feat: add voice to Chat and Build"
```

---

### Task 6: Browser-level accessibility, layout and screenshot verification

**Files:**
- Modify: `apps/web/e2e/composer.spec.ts`
- Create: `apps/web/e2e/voice-live.spec.ts`
- Create during verification: `output/playwright/voice-chat-desktop.png`
- Create during verification: `output/playwright/voice-build-desktop.png`
- Create during verification: `output/playwright/voice-chat-mobile.png`
- Create during verification: `output/playwright/voice-settings.png`

**Interfaces:**
- Consumes: built SPA, deterministic browser speech fakes, real local Raiker service for live checks.
- Produces: mocked CI regression plus key-free live visual evidence.

- [ ] **Step 1: Extend mocked Playwright with deterministic speech APIs before app load**

```ts
await page.addInitScript(() => {
  class FakeRecognition {
    static instance: FakeRecognition;
    continuous = false;
    interimResults = false;
    lang = "";
    onresult: ((event: unknown) => void) | null = null;
    onerror: ((event: unknown) => void) | null = null;
    onend: (() => void) | null = null;
    constructor() { FakeRecognition.instance = this; }
    start() { document.documentElement.dataset.voiceListening = "true"; }
    stop() { this.onend?.(); }
    abort() { this.onend?.(); }
  }
  Object.assign(window, { SpeechRecognition: FakeRecognition });
});
```

The mocked scenario must assert Dictate is present in Chat and Build, Done does not submit, Cancel restores text, Read aloud is present only on completed answers, language settings persist through the mocked PUT, and no console error occurs. Capture desktop, 390×844 mobile and settings screenshots. Run `@axe-core/playwright` against listening and idle states.

- [ ] **Step 2: Run mocked Playwright and verify it passes**

Run: `npm run build`

Run: `npm run test:e2e:mocked`

Expected: mocked project exits 0 and writes the four screenshot files.

- [ ] **Step 3: Start the live Raiker service and run the focused live voice scenario**

Start only after confirming no old listener remains. Use the repository's established loopback launcher and existing Rahul account. Enter provider credentials through the UI only. The live test must exercise real navigation, permission/error copy, Chat/Build parity, language persistence and read-aloud state. A manual real-microphone check confirms actual browser recognition; Playwright uses a deterministic fake for the transcript so external recognition accuracy is not presented as a product test.

Run: `npm --prefix apps/web run test:e2e:live -- voice-live.spec.ts`

Expected: PASS with no browser console errors, failed network requests or accessibility violations.

- [ ] **Step 4: Inspect every screenshot and correct encountered UI defects test-first**

Use the screenshot/image viewer on each artifact. If controls wrap outside the composer, overlap model/mode controls, disappear on touch layouts, lose visible focus, animate under reduced motion, or render inconsistent Chat/Build labels, write a failing view or Playwright assertion before correcting the shared component/CSS. Re-run Step 2 and Step 3 after every fix.

- [ ] **Step 5: Commit browser verification**

```powershell
git add -- apps/web/e2e/composer.spec.ts apps/web/e2e/voice-live.spec.ts
git commit -m "test: verify voice across Chat and Build"
```

Do not commit provider-bearing traces or raw live test state. Commit screenshots only if the repository's existing evidence convention tracks that exact output path.

---

### Task 7: Compatibility, guide and gap-ledger closure

**Files:**
- Modify: `docs/plans/GAP_BUILD_CHAT.md`
- Modify: `docs/REFERENCE_PLATFORM_COMPATIBILITY.md`
- Modify: `docs/FEATURE_COVERAGE_MATRIX.md`
- Modify: `docs/ACCEPTANCE_TESTS_BY_PHASE.md`
- Modify: `docs/API_AND_CONTRACT_SCHEMAS.md`
- Modify: `docs/CHANNELS_SPEC.md`
- Modify: `docs/guide/working-in-chat.md`
- Modify or create: `docs/guide/working-in-build.md`
- Modify: `README.md`
- Modify only when an issue remains: `docs/plans/TO_BE_FIXED.md`
- Test: `tests/test_repo_truthfulness_validator.py`
- Test: `tests/test_repository_code_map.py` or the repository's existing documentation-drift test selected by `rg`.

**Interfaces:**
- Consumes: verified implementation behavior and screenshot/live evidence.
- Produces: one truthful compatibility story, C16 closure, future full-duplex backlog and removal of stale “Voice deferred/no control” text.

- [ ] **Step 1: Write or update failing documentation-truth assertions**

Add exact assertions that the guide no longer says there is no voice-input control, C16 is complete for Chat and Build, the acceptance matrix names Dictate/Done/Cancel/Read aloud, and `REFERENCE_PLATFORM_COMPATIBILITY.md` contains categorical **Yes / Potentially / No** decisions plus the future full-duplex control requirements.

- [ ] **Step 2: Run documentation truth tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_repo_truthfulness_validator.py -q`

Expected: FAIL on stale voice/deferred wording.

- [ ] **Step 3: Update documentation in each document's existing structure**

`docs/REFERENCE_PLATFORM_COMPATIBILITY.md` must include a dated voice control-set section covering Claude Chat/Cowork/Code, ChatGPT Chat/Work/Codex, OpenClaw, DeepSeek Harness and Hermes Agent; list functional parity, compatibility requirements, safeguards, differentiators, residual gaps and the categorical assessment for every proposed addition. It must state that the shipped turn-based feature does not equal full-duplex voice.

`GAP_BUILD_CHAT.md` marks C16 complete and points to implementation/tests. `README.md` removes only stale voice limits and retains the honest full-duplex/local-or-hosted STT/TTS provider gap. Guide copy explains Dictate, Done, Cancel, editing, explicit send, language choice, Read aloud, browser processing and permission recovery.

- [ ] **Step 4: Run documentation truth tests and verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_repo_truthfulness_validator.py -q`

Run: `rg -n -i "voice.*deferred|no voice-input|coming soon" README.md docs apps/web/src`

Expected: pytest exits 0; remaining search hits refer only to explicitly future full-duplex/provider voice and no shipped control is labelled absent.

- [ ] **Step 5: Commit documentation closure**

```powershell
git add -- README.md docs/plans/GAP_BUILD_CHAT.md docs/REFERENCE_PLATFORM_COMPATIBILITY.md docs/FEATURE_COVERAGE_MATRIX.md docs/ACCEPTANCE_TESTS_BY_PHASE.md docs/API_AND_CONTRACT_SCHEMAS.md docs/CHANNELS_SPEC.md docs/guide tests/test_repo_truthfulness_validator.py
git commit -m "docs: close governed voice compatibility gap"
```

If an issue cannot be fixed in this run, add its reproduction, impact, root cause, exact required fix and required UI outcome to `docs/plans/TO_BE_FIXED.md` before this commit.

---

### Task 8: Full verification, live provider matrix, push and CI closure

**Files:**
- Modify only for failures found by verification: files directly responsible for those failures.
- Evidence: existing `output/playwright/` and repository-approved screenshot paths.

**Interfaces:**
- Consumes: all implementation and documentation tasks.
- Produces: fresh local gate evidence, four-provider live evidence, pushed `origin/main` commit and green GitHub workflows.

- [ ] **Step 1: Run the complete Python quality gate**

Run: `.venv\Scripts\python.exe -m pytest tests`

Run: `.venv\Scripts\python.exe -m ruff check .`

Run: `.venv\Scripts\python.exe -m mypy raiker apps tests`

Expected: each exits 0 with zero failures/errors.

- [ ] **Step 2: Run the complete web quality gate**

Run: `npm test`

Run: `npm run check`

Run: `npm run lint`

Run: `npm run build`

Run: `npm run test:e2e:mocked`

Expected: each exits 0 with zero failures/errors and no new warnings.

- [ ] **Step 3: Live-test each requested provider through the dictated-text path**

Using the existing Rahul test account, add/update credentials through Models UI only, run exact readiness, select an available model, create a dictated draft, explicitly send it and observe one real answer in both Chat and Build where practical:

| Provider | Required live evidence |
|---|---|
| Anthropic | Connected/readiness-proven model, dictated Chat prompt, governed answer. |
| OpenAI | Connected/readiness-proven model, dictated Chat prompt, governed answer and manual Read aloud state. |
| OpenRouter | Connected/readiness-proven model, dictated Build prompt under Plan mode, governed answer with no permission change. |
| Ollama | `gemma4:31b-cloud` readiness, dictated Build prompt, governed answer. |

If a valid account has no quota/entitlement or a named remote model is unavailable, record the exact redacted product state; do not replace external account state with a false pass. Do not screenshot credential fields.

- [ ] **Step 4: Verify the final diff and requirement checklist**

Run: `git diff --check`

Run: `git status --short --branch`

Re-read `docs/superpowers/specs/2026-08-21-governed-turn-based-voice-design.md` and check every shipped requirement against a test, live observation or documentation entry. Confirm no raw audio path, automatic submit, wake listener, provider key, unbounded language value or full-duplex claim entered the implementation.

- [ ] **Step 5: Commit any verification-owned fixes through their owning task**

If Step 4 finds a defect, return to the task that owns that file, add a failing
test there, make it pass, and use that task's explicit `git add -- ...` list.
Use commit message `fix: close voice verification gaps`. Skip this step when
Step 4 reports a clean tree.

- [ ] **Step 6: Push main and monitor GitHub Actions**

Run: `git push origin main`

Then use the repository's GitHub workflow tooling to monitor every workflow for the pushed SHA. Inspect failing job logs, reproduce repository-owned failures locally, fix them test-first, commit, push and monitor again. Repeat until CI, Ruff, lint, mypy, Python tests, web tests/build and every other required workflow are green.

- [ ] **Step 7: Final evidence summary**

Report the pushed SHA, local command results, provider outcomes, screenshot paths, workflow conclusions, C16 closure, full-duplex future gap and every issue added to `TO_BE_FIXED.md`. Never repeat credentials or the test password.
