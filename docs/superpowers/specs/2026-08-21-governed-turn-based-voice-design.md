# Governed Turn-Based Voice for Chat and Build

## Status

**Approved on 2026-08-21.** This specification completes GAP-CHAT C16 for
turn-based voice and applies the same control set to Build. Full-duplex live
conversation is recorded separately as a future improvement; it is not part of
this delivery's acceptance boundary.

## Outcome

Add provider-neutral voice interaction to Raiker's two conversation surfaces:

- dictate into the existing Chat or Build composer in real time;
- review and edit the transcription before an explicit send;
- cancel dictation without losing the draft that existed before recording;
- manually read a completed response aloud and stop playback; and
- carry dictated prompts through the same governed runtime, model, tools,
  approvals, sandbox and audit path as typed prompts.

The feature must work with Anthropic, OpenAI, OpenRouter, Ollama and every other
model profile Raiker can already submit text to. Voice is an input/output
adapter, not a second agent runtime and not a provider-specific mode.

## Scope boundary

This delivery is **governed turn-based voice**. A microphone action starts one
dictation session. Speech becomes editable text. The owner stops or cancels the
session and explicitly sends the resulting prompt. A separate owner action
reads one completed response aloud.

The following are deliberately outside this implementation:

- continuous or background listening;
- automatic submission after silence;
- simultaneous listening and speaking;
- barge-in or interruption by speech;
- wake words;
- voice cloning or user-uploaded voices;
- retained audio, audio attachments or audio transcript export; and
- a Raiker-hosted STT/TTS provider gateway.

Those capabilities belong to the future full-duplex design described below.
They must not be implied by copy, icons, compatibility tables or tests in this
delivery.

## Reference-platform review

The comparison is scoped to voice controls that affect Raiker Chat, Build and
their governed backend. It does not treat a product's unrelated visual style as
a compatibility requirement.

| Reference | Verified behavior relevant to this delivery | Raiker requirement |
|---|---|---|
| Claude Chat | Claude voice supports spoken input/output, text/voice continuity, language selection and connected tools. Dictation produces text with explicit send and cancel. | Match editable dictation, language choice, transcript continuity and normal tool access. Manual read-aloud supplies the selected spoken-output scope without claiming Claude's hands-free voice mode. |
| Claude Cowork / Claude Code | Anthropic documents dictation as available while full voice mode is not available in Cowork or Code. | Build must have the same dictation control as Chat and must retain Build modes, workspace selection and governance. |
| ChatGPT Chat | Dictation records a prompt, returns editable text and sends only after an owner action. Voice can remain in the same text conversation. | Match editable pre-send text and conversation continuity. Do not retain raw audio in Raiker. |
| ChatGPT Work / Codex | OpenAI documents voice task start, progress questions and agent coordination through the permissions of the selected experience. | Dictated Build prompts must enter the ordinary Build turn and inherit its exact modes and permissions. Full-duplex coordination remains future work. |
| OpenClaw | Voice Wake and Talk Mode coordinate one active audio owner, route speech to sessions, expose interruption and support continuous STT→agent→TTS loops. | Adopt the single-audio-owner discipline now. Record wake, continuous listening, interruption and routing as future requirements. |
| DeepSeek Harness | The official harness is plugin-composed and exposes agent/session/tool boundaries; no first-party voice control was verified in its documented default Web UI or SDK during this review. | Keep voice behind a replaceable adapter and out of the agent core so a future audio plugin does not fork session semantics. |
| Hermes Agent | Hermes supports configurable local and hosted STT, several TTS providers, push-to-talk, silence detection and voice channels. | Keep the adapter seam compatible with future local/hosted STT/TTS selection. Do not claim provider depth in this delivery. |

Primary references reviewed on 2026-08-21:

- Claude voice and Cowork/Code boundary:
  <https://support.claude.com/en/articles/11101966-use-voice-mode>
- Claude dictation:
  <https://support.claude.com/en/articles/10065434-using-dictation-on-the-claude-mobile-apps>
- ChatGPT Dictation:
  <https://help.openai.com/en/articles/12168547-voice-dictation-faq>
- ChatGPT Voice, Work and Codex:
  <https://help.openai.com/en/articles/20001274/>
- OpenClaw Voice Wake:
  <https://github.com/openclaw/openclaw/blob/main/docs/nodes/voicewake.md>
- DeepSeek Harness:
  <https://github.com/deepseek-ai/deepseek-harness>
- Hermes voice mode:
  <https://github.com/clauxel/hermes-agent/blob/main/doc/hermesagent.studio/features/voice.md>

## Categorical compatibility decisions

Each proposed addition is classified rather than presented as automatic
competitive superiority.

| Addition | Meaningful improvement? | Decision |
|---|---|---|
| Shared Dictate control in Chat and Build | **Yes.** It closes C16 and matches the selected Claude/ChatGPT dictation behavior. | Build. |
| Explicit send after editable transcription | **Yes.** It preserves owner intent and prevents silence detection or a recognition mistake from starting governed work. | Build; mandatory. |
| `typed` / `dictated` / `mixed` provenance | **Yes.** It adds backend observability without retaining audio or duplicating prompt text in audit payloads. This is a Raiker differentiator over the reviewed dictation documentation. | Build. |
| Provider-neutral voice adapter | **Yes.** Dictation works with every text model profile rather than only the provider performing speech recognition. | Build. |
| Raiker-side zero audio retention | **Yes, with precise wording.** Raiker neither receives nor stores audio in this architecture. The browser speech engine may process audio externally and the UI must disclose that fact. | Build. |
| Manual read-aloud with one active speaker | **Yes.** It supplies accessible spoken output without introducing automatic playback or overlapping responses. | Build. |
| Persisted language preference | **Yes.** It matches a control exposed by Claude and ChatGPT and improves recognition reliability. | Build. |
| Full-duplex live conversation | **Potentially, but not yet.** Parity alone is not a Raiker differentiator. It becomes meaningful only when continuous audio inherits explicit task authority, visible listening state, interrupt/stop controls, bounded idle behavior and evidence. | Future design, not this implementation. |
| Voice cloning or unrestricted custom voices | **No demonstrated improvement.** It adds impersonation and consent risk without helping governed work. | Do not add. |

Raiker will not claim that this turn-based delivery exceeds ChatGPT, Claude,
OpenClaw or Hermes in raw voice capability. It goes beyond the reviewed
turn-based controls specifically in governed input provenance, model-provider
independence and keeping audio outside Raiker's storage and audit systems.

## Architecture

### Shared browser adapter

Create a focused browser voice module that owns feature detection and wraps the
browser's speech-recognition and speech-synthesis APIs behind typed interfaces.
Components consume those interfaces rather than referencing vendor-prefixed
globals directly. Tests inject fakes through the same boundary.

The adapter exposes:

```text
VoiceRecognitionAdapter
  supported(): boolean
  start(language, handlers): void
  stop(): void
  abort(): void

VoicePlaybackCoordinator
  supported(): boolean
  speak(text, language, handlers): void
  stop(): void
  activeId(): string | null
```

Only one recognition session and one playback session may own audio at a time.
Starting recognition stops playback. Starting playback aborts recognition.
Starting another playback stops the first response. This rule is shared across
routes rather than reimplemented inside each view.

### Dictation component

One `VoiceDictationControl` is mounted in the lower action row of both composer
cards, beside Attach and the surface toggle. It receives the current draft,
the textarea selection and callbacks that replace the draft and restore focus.

Its states are exact and owner-visible:

```text
unavailable → idle → listening → stopped
                     ↘ error
```

- **Idle:** microphone icon and accessible name **Dictate**.
- **Listening:** an accent recording indicator, status text **Listening…**,
  **Done** and **Cancel** controls.
- **Done:** stops recognition, retains all final recognized text and returns
  focus to the composer. Sending remains separate.
- **Cancel:** aborts recognition and restores the complete draft and selection
  snapshot from immediately before dictation began.
- **Error:** keeps already-finalized text, names the reason and the next action.

Final recognition segments are inserted at the selection position. Existing
text on either side is preserved. Whitespace is normalized only at the two
insertion boundaries; Raiker does not rewrite punctuation or wording produced
by the speech engine. Interim text may be shown as a visually distinct composer
preview, but it must not become the submitted draft until finalized.

Dictation never submits the form. Enter while recognition is active stops and
keeps the text; a second explicit Enter or the Send button submits it. This
prevents an accidental key press from collapsing stop and send into one action.

### Input provenance

The web prompt request gains a constrained input field:

```text
input_mode: typed | dictated | mixed
```

- `typed`: no finalized dictation segment contributed to the submitted draft.
- `dictated`: the submitted draft consists only of finalized dictation text.
- `mixed`: typed content existed before dictation or the finalized transcript
  was edited before submission.

The server rejects every other value. It places the mode in the existing prompt
metadata and the safe `prompt_received` event payload. It does not add audio,
transcript text or language to the audit event. The ordinary turn row remains
the single stored copy of the submitted prompt.

Edit, Retry, Branch and restored sessions keep their existing semantics. A
retried text prompt is `typed` for the new request unless the owner dictates
into it before submitting. Provenance describes the current submission path,
not the historical origin of copied text.

### Read aloud

Every completed assistant answer in Chat and Build gains a quiet **Read aloud**
action beside the existing Copy action. While that response owns playback, the
same control reads **Stop speaking** and exposes pressed state. Streaming,
failed, empty and approval-waiting responses do not offer playback.

The synthesizer receives readable plain text derived from the rendered answer:

- Markdown control characters and citation markers are omitted;
- link labels are spoken, not raw destination URLs;
- fenced code is introduced as **Code block** and omitted from speech by
  default; and
- redaction markers remain redaction markers.

No audio blob is created, downloaded, cached or attached. Playback stops on
route change, sign-out, new dictation, a second read-aloud action or explicit
Stop speaking.

### Language preference

Settings → General gains a **Speech language** control with **Auto (device
language)** plus English (`en`), French (`fr`), German (`de`), Hindi (`hi`),
Italian (`it`), Japanese (`ja`), Korean (`ko`), Portuguese (`pt`), Russian
(`ru`), Spanish (`es`), Turkish (`tr`) and Ukrainian (`uk`). This matches the
currently documented Claude Dictation set without presenting an unbounded list
that a particular browser may not recognize. The preference is owner-scoped and
persisted through the existing settings API, not only in one browser's local
storage. Recognition and synthesis use that language where supported. Changing
it does not mutate application display language or model selection.

The setting contains the same browser-processing disclosure as the composer:
Raiker does not receive or retain audio; the browser's speech service may
process it according to the browser or operating-system provider's terms.

## UI and accessibility

The work extends Raiker's existing composer and message-action language. It
does not introduce a separate voice page, modal orb or visual identity.

- Chat and Build use the same components, labels, state colors and keyboard
  behavior.
- The active recording state is conveyed by text and icon, never color alone.
- State changes use a polite live region; permission and capture failures use
  `role="alert"` only when owner action is required.
- All controls have visible focus, at least 44-by-44 CSS-pixel touch targets on
  coarse-pointer layouts and stable accessible names.
- Recording animation respects `prefers-reduced-motion`.
- The composer remains usable at 320 CSS pixels wide and neither model nor mode
  controls are pushed outside the card.
- Print/export surfaces omit voice controls.

The visual signature is intentionally small: the microphone's active state
uses Raiker's existing accent pulse paired with a live waveform line whose
motion reflects state, not captured audio amplitude. It makes the listening
boundary unmistakable without implying that Raiker is storing a waveform.

## Errors and recovery

Every adapter error maps to stable owner-facing copy:

| Condition | UI outcome |
|---|---|
| Recognition API unavailable | Dictate remains visible but disabled; explanation says this browser does not provide speech recognition and typing remains available. |
| Permission denied | Stop the session, keep the original draft, and tell the owner to allow microphone and speech-recognition access in browser/system settings. |
| No microphone / capture unavailable | Stop, keep the draft, and state that no usable microphone was found or another application may own it. |
| No speech recognized | Keep the draft and invite Retry; never insert an empty segment. |
| Recognition network/service failure | Keep finalized text, label the browser speech service unavailable, and leave typing/send operational. |
| Recognition aborted by navigation or another audio action | Stop silently unless unfinalized speech would be lost; retained finalized text stays in the draft. |
| Speech synthesis unavailable | Read aloud remains disabled with an explanation; response text and Copy remain operational. |
| Playback failure | Stop the active state and report that the device could not play the response. |

Recognition errors never clear an existing prompt, change the selected model or
surface mode, attach a file, or start a turn. Voice failure cannot make text
conversation failure.

## Safeguards and authority

- Microphone access begins only after the owner activates Dictate.
- No wake listener or background recorder exists.
- Recognition ends on Done, Cancel, navigation, sign-out, submission or audio
  ownership transfer.
- Dictation provides text only. It grants no capability and cannot change Plan,
  Edit or Auto mode.
- Submitted dictated text remains untrusted owner input for the same prompt
  injection, provider, tool, policy, approval and sandbox boundaries as typing.
- Read-aloud never reads hidden reasoning, tool payloads, credentials, approval
  secrets or collapsed governance evidence; it reads only the visible answer.
- No credential or provider key is added for browser voice.
- Screenshots are captured only after provider credential fields are cleared or
  masked.

## Test strategy

Implementation follows red-green-refactor in independently testable slices:

1. Adapter feature detection, recognition lifecycle, playback exclusivity and
   cleanup using injected browser fakes.
2. Dictation insertion, interim/final handling, Done, Cancel restoration and
   stable error mapping.
3. Plain-text speech rendering and manual playback controls.
4. Chat and Build composer parity, response actions, narrow/touch layouts and
   accessibility.
5. Persisted language setting and authenticated settings contract.
6. Prompt `input_mode` schema validation, event metadata and absence of audio or
   duplicate prompt text in audit payloads.
7. Playwright navigation with simulated speech APIs and microphone permission,
   screenshots and automated accessibility checks.
8. Live text turns created from a dictated draft through Anthropic, OpenAI,
   OpenRouter and Ollama `gemma4:31b-cloud`.

The live provider check proves that voice-originated text uses the selected
provider and unchanged governance path. Browser speech recognition itself is
verified with deterministic fakes plus a manual real-microphone check because
CI and Playwright cannot assert the accuracy of a person's microphone or an
external browser speech service.

## Documentation and compatibility closure

When implementation passes:

- mark C16 complete in `docs/plans/GAP_BUILD_CHAT.md`, explicitly covering both
  Chat and Build;
- update `docs/REFERENCE_PLATFORM_COMPATIBILITY.md` with the reference matrix,
  categorical decisions, shipped controls and future full-duplex gap;
- update feature, acceptance, API/contract and channel documentation wherever
  it still says Voice is deferred or unavailable;
- update the relevant `docs/guide/` pages with Dictate, Cancel, Done, language,
  Read aloud and browser-permission recovery;
- remove stale Voice-related known limits from `README.md` while retaining the
  honest full-duplex limit; and
- record any discovered issue that cannot be fixed in this run in
  `docs/plans/TO_BE_FIXED.md` with reproduction, cause, required fix and UI
  outcome.

## Future improvement: governed full-duplex live conversation

Future work should provide continuous listening and speaking, natural
interruption and hands-free task control across Chat and Build. It requires a
separate design because it introduces long-lived microphone ownership,
automatic turn boundaries, audio transport, latency budgets and new authority
risks.

The future design must include:

- explicit entry and exit from a visibly distinct live session;
- continuous STT and TTS with streaming partials;
- barge-in that stops spoken output before accepting the interruption;
- push-to-talk fallback and mute;
- bounded silence and idle timers plus a hard session cap;
- optional wake words only with an owner-visible foreground/listening state;
- hands-free start, status, steer, stop and approval handoff for governed tasks;
- visual confirmation for every high-risk approval—voice alone cannot authorize
  an irreversible or elevated action;
- one audio owner across devices/routes and recovery after backend reconnect;
- local-first STT/TTS where available, explicit hosted-provider selection,
  egress disclosure, retention policy and usage/cost visibility;
- transcript/audio correction and deletion controls;
- accessibility captions and a text fallback throughout; and
- parity tests against current Claude Voice, ChatGPT Voice/Work/Codex,
  OpenClaw Talk/Voice Wake and Hermes voice providers at implementation time.

It represents a meaningful improvement only if it preserves Raiker's governed
task controls while reducing friction. A continuous microphone without bounded
idle behavior, visible state, interruption, explicit elevated approval and
auditable task attribution would not go beyond the reference platforms and
must not ship.

## Delivery closure

After focused and full local verification, run the repository's Python tests,
Ruff, mypy, web unit tests, Svelte check, ESLint, production build and Playwright
flows. Commit scoped implementation and documentation, push `main`, then monitor
the GitHub Actions runs for that commit until every repository-owned workflow is
green. Live screenshots and key-free evidence go under the repository's
existing Playwright evidence paths. Credentials entered for testing remain in
the encrypted UI-backed store and never appear in source, commands, logs,
screenshots or documentation.
