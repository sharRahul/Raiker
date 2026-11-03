# Native voice conversation

**Status:** V1 implemented, V2 implemented as Preview (see §12a); opened 2026-11-02. Tracked in
[BETA_RELEASE_PLAN.md](BETA_RELEASE_PLAN.md) as VD-1 (beta, **P0**) and VD-5
(conversation, **Preview** in beta). Supersedes nothing: today's dictation and
read-aloud (BUG-256, *Local voice delivery — release blockers* in
[TO_BE_FIXED.md](TO_BE_FIXED.md)) become Phase V1 of this plan.

## 1. What this is for

Raiker should be able to hold a **spoken conversation with its owner, entirely
on the owner's computer**. The owner talks, Raiker listens, thinks with the
model the owner chose, and answers aloud, with the latency and turn-taking of a
conversation rather than a voice memo. Nothing is sent off the device unless
the owner has chosen a hosted model for the thinking step, and even then only
the transcript text goes, never audio.

The pipeline:

```
Microphone ─► Silero VAD ─► Whisper ─► Raiker (governed turn, any LLM) ─► Kokoro-82M / Piper / system voice ─► Speaker
  (16 kHz)    (is anyone     (speech     (plans, uses tools under          (sentence-by-sentence speech,
               speaking?)     → text)     the owner's permissions)           interrupted when the owner speaks)
```

Whisper is the speech-to-**text** stage only; it does not speak. The voices
that answer are Kokoro-82M, Piper, or the operating system's own on-device
voice.

## 2. The reference concept: a whole assistant on a Raspberry Pi

The concept the owner shared runs this pipeline on a single Raspberry Pi with a
camera:

| Stage | Component in the concept | What it does | Raiker equivalent |
|---|---|---|---|
| Ears | **Whisper** | Listens: speech to text | Managed whisper.cpp engine (§5.2) |
| Brain | **qwen3:1.7B** | Interprets and comes up with the response | **Always the owner's choice**: whatever model they selected for the conversation, local (Ollama, LM Studio, the llama.cpp engine from PR #245) or hosted. Voice profiles never choose, install or replace it |
| Mouth | **Piper** | Answers aloud | Managed Piper engine (§5.3), or Kokoro-82M where there is room |
| Eyes | **Moondream** + camera | Describes what the camera sees, as text the brain can use | Optional *Look* step (§5.5): a camera frame goes to a local vision model (Moondream 2 GGUF with its projector on llama.cpp, or any vision-capable model the owner serves); the description joins the turn as context |

Two lessons are taken from it.

1. **Small speech engines are enough for a natural conversation.** A small
   Whisper and Piper together need only a few hundred megabytes and keep up
   in real time on modest hardware. Raiker therefore ships a **Lite** voice
   profile with that ears-and-mouth stack for 8 GB laptops, ARM64 Linux boards
   and machines with no GPU. The brain is not part of any profile: it is the
   model the owner chose, as everywhere else in Raiker. The concept's
   qwen3:1.7B is simply one model an owner might pick.
2. **Every stage is a separate local process with a narrow job.** That is
   already how Raiker runs llama.cpp, and it is what makes resource
   management possible: each engine can be placed on CPU or GPU, sized, paused
   and restarted on its own.

## 3. Goals and non-goals

**Goals**

- G1. Conversation: under **1.5 s** from the end of the owner's sentence to the
  first spoken word on the *Balanced* profile on a reference laptop (16 GB,
  6 GB GPU); under **2.5 s** on *Lite* with no GPU.
- G2. Turn-taking: the owner can interrupt (barge-in) and Raiker stops talking
  within **200 ms**.
- G3. Choice at install and later: Off, Lite, Balanced, High quality or Custom,
  chosen in the installer's optional step or in Settings → Voice at any time.
- G4. Resource management: Raiker places each engine on CPU or GPU, sizes it
  next to the model being served, unloads idle engines, and never starts a
  combination that does not fit (§7).
- G5. Same governance: a spoken turn is an ordinary governed turn. Tools,
  permissions, approvals, budgets and receipts are identical.
- G6. Privacy: audio never leaves the device. Audio is not written to disk
  unless the owner turns on *Keep recordings*. The microphone is open only
  while a visible indicator says so.

**Non-goals for beta**

- An always-listening wake word (V4, opt-in, local only).
- Voice approval of consequential actions: an approval is always a click
  (§9).
- Speaker identification, voice cloning, or phone calls.
- Browser or cloud speech services, ever. This rule is already enforced for
  dictation and read-aloud.

## 4. Profiles

Profiles choose the **speech** components only. The thinking model is never
part of a profile: it is always the owner's choice, any model Raiker can reach,
local or hosted. Sizes and memory below are for the voice components alone; a
local thinking model's own footprint is planned separately by its engine and
counted in the same resource ledger (§7).

Sizes are approximate download sizes of the quantised files; they are
re-measured when the catalogue is built (§5.6) and shown from the catalogue,
never hard-coded in the UI.

| Profile | For | VAD | Speech to text | Speech | Download | Resident memory |
|---|---|---|---|---|---|---|
| **Lite** | 8 GB RAM, no GPU, ARM64 boards | Silero v5 (2 MB) | Whisper **base** q5_1 (~60 MB), English-only variant offered | **Piper** medium voice (~60 MB) | ~0.1 GB | ~0.4 GB |
| **Balanced** *(default recommendation for 16 GB)* | 16 GB RAM, any GPU or none | Silero v5 | Whisper **small** q5_1 (~190 MB), or **large-v3-turbo** q5_0 (~550 MB) when a GPU has room | **Kokoro-82M** int8 (~90 MB + voices) | 0.3–0.7 GB | 1–1.5 GB |
| **High quality** | ≥ 32 GB RAM or ≥ 12 GB VRAM | Silero v5 | Whisper **large-v3-turbo** q8_0 (~870 MB) on GPU | **Kokoro-82M** fp32 (~330 MB) | ~1.2 GB | ~2.5 GB |
| **Custom** | Anyone | Silero v5 | Any catalogue tier: tiny, base, small, medium, large-v3-turbo; multilingual or English-only; q5/q8/f16 | Kokoro (fp32 / fp16 / int8) · Piper (x_low / low / medium / high per voice) · system voice | per choice | per choice |

The installer and Settings recommend one profile from detected hardware, using
the same hardware probe as the llama.cpp engine
(`raiker/models/llama_cpp/hardware.py`). For example: *"Balanced — your NVIDIA
RTX 4060 (8 GB) can run speech recognition on the GPU next to a 7B model."*

## 5. Components

### 5.1 Voice activity detection — Silero VAD

- **Model:** Silero VAD v5 ONNX (MIT, ~2 MB), shipped inside Raiker. It is not
  downloaded, because it is too small to be worth a choice.
- **Where it runs:** in the client, as an `AudioWorklet` capture at 16 kHz mono
  feeding a Web Worker that runs the model with `onnxruntime-web` (WASM, CPU).
  Running it in the client means silence never leaves the page, the
  *listening* indicator reacts at once, and the host receives only
  utterances. A host-side runner (Python `onnxruntime`) exists for channels and
  the CLI, where there is no page.
- **Endpointing:** the speech probability is computed on 32 ms frames. Speech
  starts after 64 ms above 0.5 and ends after the **end-of-speech silence**
  (default 500 ms, adjustable from 250 to 1500 ms in Settings). A 300 ms
  pre-roll is kept, so first syllables are not cut. Utterances are capped at
  30 s in conversation and 6 minutes in dictation (today's `MAX_AUDIO_BYTES`).
- **Barge-in:** while Raiker speaks, VAD keeps running on the microphone with
  echo cancellation on (`getUserMedia` constraints `echoCancellation`,
  `noiseSuppression`). Speech above threshold for 150 ms stops playback,
  cancels the in-flight model turn (the existing cancel path) and starts a new
  utterance.

### 5.2 Speech to text — managed whisper.cpp

- **Engine:** `whisper-server` from ggml-org/whisper.cpp (MIT), managed exactly
  like llama.cpp in PR #245. It reuses that work's hardware detection, release
  resolution, SHA-256 verification, safe unpacking, self-check, supervisor,
  logs and process containment (`raiker/models/llama_cpp/*` is generalised
  into a shared `raiker/models/engines/` package rather than copied).
- **Builds:** CUDA, Vulkan, Metal and CPU, chosen like llama.cpp. Where
  ggml-org publishes no prebuilt `whisper-server` for a platform and backend,
  Raiker's own CI builds it from the pinned upstream tag (the way
  `build_native_runner.py` builds the sandbox runner). It is published as a
  Raiker release asset with a digest and verified the same way. The asset list
  is confirmed against upstream's release workflow when this is implemented,
  as it was for llama.cpp.
- **Models:** ggml files from the official `ggerganov/whisper.cpp` model
  repository, pinned to a revision with SHA-256 per file in the catalogue:
  `tiny`, `base`, `small`, `medium`, `large-v3-turbo`, with `.en` variants for
  tiny to medium and `q5_0`, `q5_1` and `q8_0` quantisations.
- **Interface:** the existing `/inference` and `/v1/audio/transcriptions`
  paths (`speech_runtime.py`), so dictation keeps working unchanged and a
  manually configured server remains supported.
- **Placement:** GPU when the resource planner finds headroom (§7), otherwise
  CPU with `-t` set by the planner.

### 5.3 Speech — Kokoro-82M and Piper

| | Kokoro-82M | Piper | System voice |
|---|---|---|---|
| Quality | Most natural; expressive | Clear, slightly synthetic | Varies by OS |
| Speed on CPU | Real-time or better on a modern laptop (int8) | Far faster than real-time, even on a Raspberry Pi | Fast |
| Size | int8 ~90 MB, fp16 ~170 MB, fp32 ~330 MB, voices ~27 MB | ~20–110 MB per voice | 0 |
| Languages | English (US/UK) first; others per upstream voices | Many, one model per voice | Per OS |
| Output | 24 kHz | 16–22 kHz | Native |
| Licence | Weights Apache-2.0 | Engine: see §11 | OS |

- **Kokoro** runs in a Raiker-managed worker process. That process is Raiker's
  own Python with `onnxruntime` (bundled, CPU) and the `kokoro-onnx` package,
  started and supervised like any engine and talking to the host over a
  loopback socket. The CPU execution provider is the default; DirectML on
  Windows and CoreML on macOS are used only in the High-quality profile, and
  only when the planner allows.
- **Piper** runs as the upstream `piper` binary per voice, managed and verified
  like the others. Its catalogue lists **only voices whose dataset licence
  permits this use**; voices under non-commercial licences are excluded.
- **System voice** is today's read-aloud, limited to `localService` voices. It
  is the zero-download option and the fallback when no engine is installed.
- **Streaming:** the model's answer is split into sentences as tokens stream
  (abbreviation-aware, a maximum of 220 characters, with code blocks and
  tables removed; `speechText()` is reused). Each sentence is synthesised and
  queued while the next is still being generated, so speaking starts after the
  first sentence, not after the whole answer.

### 5.4 Thinking — the governed turn

A spoken utterance becomes a normal prompt on the active conversation, marked
`origin: voice`. Everything after that is unchanged: model selection, tools,
approvals, budgets, memory and receipts. The voice session subscribes to the
turn's existing stream and speaks the assistant text parts. Tool activity is
spoken as one short line (*"Searching your files…"*) only when it lasts longer
than 1.5 s.

A **spoken-style system hint** is added to voice turns. It asks for short,
conversational answers and offers to show detail on screen, without changing
the owner's own instructions.

### 5.5 Eyes — the optional *Look* step (V3)

From the concept's camera and Moondream:

- A **Look** button (and the spoken *"look at this"*, when the setting is on)
  captures one frame from the selected camera.
- The frame goes to a local vision model:
  - **Moondream 2** (Apache-2.0) as a GGUF with its multimodal projector on a
    llama.cpp slot (`--mmproj`); or
  - the conversation's own model, if it accepts images.
- The description, or the image itself for a vision-capable model, is added to
  the next turn as an attachment and appears in the transcript as a
  thumbnail.
- The camera is never on continuously; each frame is an explicit act with a
  shutter sound and an on-screen flash.

### 5.6 The voice catalogue

`raiker/config/voice-catalogue.json` lists every downloadable item: engine
builds, Whisper models and TTS models and voices. Each entry carries the
source URL, pinned revision, SHA-256, size, licence, languages, profile
membership, and measured resident memory on CPU and GPU. A test validates
that every entry has a digest and a permissive licence. Nothing outside the
catalogue is downloaded.

## 6. Installation and settings

### 6.1 During installation

The installer's requirements page (Windows NSIS, and the first-run *Raiker
Setup* on every platform) gets an optional step after the account and before
the AI provider:

> **Talk to Raiker** *(optional)*
> Raiker can listen and answer aloud, entirely on this computer.
>
> ◯ Not now *(default)*
> ◯ Lite — 0.1 GB, works on any computer
> ◉ **Balanced — 0.6 GB · Recommended for this computer** (NVIDIA RTX 4060 detected)
> ◯ High quality — 1.2 GB
> ◯ Choose components…
>
> Downloads start after setup and pause when you are on a metered network.

- The choice is stored; downloads run in the background after first start as
  model operations (the durable, cancellable jobs that already back model
  downloads), with progress in Settings → Voice and in Activity.
- No voice profile selects, installs or changes the thinking model. A voice
  turn uses the model the owner chose for the conversation, local or hosted,
  exactly as a typed turn does. If no model is configured yet, setup's
  existing *choose an AI provider* step is where that is decided.

### 6.2 Settings → Voice

A new Settings page with four sections:

1. **Engines.** Cards for *Listening* (Whisper) and *Speaking* (Kokoro / Piper
   / system). Each shows its state (*Ready*, *Downloading 42%*,
   *Not installed*, *Paused to save memory*), the model, where it runs
   (*GPU · RTX 4060* or *Processor · 4 threads*), its memory, and **Change**,
   **Test** and **Remove**. Test plays a phrase, then transcribes it back and
   shows the accuracy.
2. **Models.**
   - A Whisper tier picker: one row per tier with size, speed on this computer
     (measured once by the Test button), languages, and *English only*.
   - A voice picker for the speaking engine, with a ▶ preview per voice.
3. **Conversation.**
   - *Push to talk* or *hands-free* (hands-free is Labs in beta).
   - End-of-speech silence, *interrupt Raiker when I speak* (on), and
     *speak tool progress*.
   - *Keep recordings* (off).
   - Idle unload after 10 minutes.
   - Run on: *Automatic / Processor only / Prefer GPU*.
4. **Resources.** A meter of what voice holds next to the served models (RAM
   and VRAM), and the planner's sentence: *"Speech recognition runs on the
   processor because the GPU is busy with the model you chose."*

## 7. Resource management

Voice engines and model slots share one ledger, so neither plans into memory
the other holds.

- **Shared ledger.** The llama.cpp supervisor's `committed_bytes` is
  generalised into a `ResourceLedger` (RAM and per-GPU VRAM) in
  `raiker/models/engines/resources.py`. Every running engine (LLM slots,
  Whisper, Kokoro, Piper, vision) registers its *planned* footprint. The
  llama.cpp planner already subtracts committed memory (PR #245); voice
  engines use the same planner pattern.
- **Placement policy.**
  1. When the owner's chosen model runs locally, it keeps priority on the
     GPU, since generation speed dominates conversation latency. When it is
     hosted, the GPU is free for the speech engines.
  2. Whisper goes to the GPU only if, after the model's plan, free VRAM covers
     Whisper plus 512 MB. Otherwise it runs on the CPU, with threads set to
     half the physical cores (at most 8).
  3. Kokoro runs on the CPU (int8) unless the profile is High quality and VRAM
     headroom covers it. Piper always runs on the CPU.
  4. VAD runs in the client on the CPU, at under 1% of one core.
- **Time-sharing instead of over-subscription.** A conversation is
  half-duplex.
  - While Whisper transcribes, nothing else in the voice pipeline runs.
  - While the model generates on the CPU, TTS is capped to 2 threads, so the
    two do not fight.
  - When the model generates on the GPU, TTS may use 4 threads.
  - These limits are set per request where the engine allows it, otherwise at
    start.
- **Warm and cold.** Engines start when the conversation panel opens or the
  microphone is pressed, and unload after the idle timeout. Under memory
  pressure (available RAM below the planner's reserve) they are unloaded
  first, before any model slot, and the panel says *"Paused to save memory"*.
- **Refusal, never thrashing.** If a profile cannot fit next to the served
  model, Settings says so and offers the next smaller profile. The engine is
  not started anyway.
- **Measured, not guessed.** Resident memory and real-time factor per
  component are measured on the reference machines and stored in the
  catalogue. The Test button measures this computer and replaces the estimate.

## 8. UI and UX

### 8.1 Entry points

- **Composer microphone** (exists):
  - **Press** to dictate.
  - **Long-press**, or the new **Talk** button beside it, to start a
    conversation.
  - With no voice engine installed it reads *Set up voice*, and links to
    Settings → Voice with the recommended profile preselected.
- **Keyboard:** `Ctrl/⌘ + Shift + Space` starts or ends a conversation;
  holding `Space` in push-to-talk mode talks.
- **Tray / menu bar:** *Talk to Raiker* (desktop app).

### 8.2 The conversation panel

A calm panel that docks over the chat, so the transcript stays readable:

- **One status orb** with five states, each with a distinct shape and text,
  never colour alone: *Listening* (a slow pulse), *Hearing you* (follows your
  voice level), *Thinking*, *Speaking* (follows Raiker's voice) and *Paused*.
- **Live captions:** the owner's words appear as Whisper returns them, and
  Raiker's as they are spoken, highlighted sentence by sentence. Both land in
  the chat as normal messages, marked with a small microphone icon.
- **Controls:** *Mute*, *Stop talking* (also any key, or speaking), *Look*
  (V3), *End*, and a *Show on screen* chip when an answer has more detail than
  was spoken.
- **Privacy line:** *"On this device · Whisper small · Kokoro"*. If the
  thinking model is hosted it says so: *"Your words are sent as text to
  Claude."*
- **Approvals:** a needed approval stops speech, plays a short tone, says
  *"I need your OK on screen,"* and shows the normal approval card. It is never
  approved by voice.
- **Errors** are spoken and shown once in plain words with one action
  (*"I couldn't hear anything — check the microphone"* · **Choose
  microphone**).

### 8.3 Accessibility

- Captions are always on.
- Everything is reachable by keyboard.
- Orb states are announced in an `aria-live="polite"` region.
- Reduced-motion settings replace the pulse with text.
- Dictation and conversation are usable with a screen reader running: TTS is
  ducked while the screen reader speaks.

## 9. Security and privacy

- **Microphone and camera:** used only after the OS and browser permission,
  only while the indicator is shown, and released on *End*, on page hide and
  on idle.
- **Audio** is held in memory for one utterance, posted to the loopback engine
  and discarded. *Keep recordings* stores utterances under the workspace with
  the same encryption-at-rest rules as attachments.
- **Engines** are loopback-only, launched with fixed argv, verified by digest,
  and contained like llama.cpp: a job object on Windows, orphan reaping on
  macOS and Linux.
- **Spoken prompt injection** is treated like any untrusted input. A voice turn
  has no extra authority, consequential actions still require a click, and the
  transcript the owner sees is the transcript the model gets.
- **The *Look* step** sends a frame to a local model by default. A hosted
  vision model is used only if the owner selected one, and the privacy line
  says so before the frame is taken.

## 10. Architecture and code layout

```
raiker/models/engines/           # generalised from raiker/models/llama_cpp (PR #245)
  hardware.py  releases.py  installer.py  supervisor.py  process.py  resources.py
raiker/voice/
  catalogue.py      # voice-catalogue.json loader + validation
  profiles.py       # Lite/Balanced/High/Custom → concrete components, recommendation
  stt_whisper.py    # whisper-server engine (install, plan, start, transcribe)
  tts_kokoro.py     # Kokoro worker engine
  tts_piper.py      # Piper engine
  tts_worker.py     # the Kokoro worker process entry point
  session.py        # conversation state machine, sentence splitter, barge-in
  planner.py        # placement on CPU/GPU from the shared ledger
raiker/api/routes_voice.py
  GET/PUT  /api/voice/settings        GET  /api/voice/status
  POST     /api/voice/install         POST /api/voice/test
  WS       /api/voice/session         (PCM16 16 kHz up, audio chunks + events down)
web/src/lib/voice/
  capture.worklet.ts  vad.worker.ts  playbackQueue.ts  conversation.svelte.ts
web/src/lib/views/settings/Voice.svelte
web/src/lib/components/ConversationPanel.svelte
```

**Session protocol (WebSocket, loopback, authenticated like the stream
route).**
- Client → host: `start` {profile}, `utterance` {pcm16 frames},
  `barge_in`, `end`.
- Host → client: `transcript` {text, final}, `turn` {turn_id},
  `speak` {sentence_id, audio chunk, sample_rate}, `state` {orb state},
  `approval_needed`, `error` {reason_code}.

**State machine:** `idle → listening → capturing → transcribing → thinking →
speaking → listening`. `barge_in` moves `thinking` or `speaking` to
`capturing` and cancels the turn. Any error goes to `listening` with the error
spoken, and three errors in a row go to `idle`.

## 11. Licensing review

Raiker is Apache-2.0. Every component is downloaded on demand as a separate
program or model, never linked, and listed in the catalogue with its licence.
Items marked ⚠ need sign-off under
[LICENSING_POLICY.md](../licensing/LICENSING_POLICY.md) before they enter the
catalogue.

| Component | Licence | Note |
|---|---|---|
| whisper.cpp, Whisper weights | MIT | — |
| Silero VAD | MIT | Shipped with Raiker |
| onnxruntime, onnxruntime-web | MIT | Bundled |
| Kokoro-82M weights | Apache-2.0 | — |
| kokoro-onnx | MIT | — |
| misaki (English G2P) | Apache-2.0 | — |
| espeak-ng (Kokoro fallback G2P, Piper phonemes) | GPL-3.0 ⚠ | Used as a separate program or data; confirm the aggregation reading, or restrict Kokoro to misaki-only English in beta |
| Piper engine | rhasspy/piper MIT (archived); successor OHF-Voice/piper1-gpl GPL-3.0 ⚠ | Prefer the last MIT release for beta; review the successor |
| Piper voices | Per voice (dataset licences vary) ⚠ | Catalogue includes only permissive voices |
| Moondream 2 | Apache-2.0 | V3 |

## 12. Delivery phases

| Phase | Scope | Beta |
|---|---|---|
| **V0** (shipped) | Dictation to an owner-configured local server; read-aloud with local OS voices; no browser speech | — |
| **V1** | Managed whisper.cpp with the tier choice; managed Kokoro and Piper; Settings → Voice; installer step; dictation and read-aloud on the managed engines; the shared resource ledger | **beta.1, P0** |
| **V2** | Conversation panel: push-to-talk first, then hands-free with Silero VAD, streaming TTS and barge-in; spoken-style hint; approvals by click | **Preview** in beta.1, Ship in beta.2 |
| **V3** | *Look* (camera → Moondream or a vision model); the Lite profile validated on ARM64 Linux (Raspberry Pi 5, 8 GB) as in the reference concept | after beta |
| **V4** | Opt-in local wake word; voice on messaging channels | later |

## 12a. Implementation status (2026-11-03)

**V1 — implemented.** Code: `raiker/voice/`, `raiker/models/engines/`,
`raiker/api/routes_voice.py`, `web/src/lib/views/settings/Voice.svelte`, the
*Voice* setup stage. Kokoro speaking was installed from the catalogue,
verified and run for real (`tests/test_voice_live.py`). What remains before the
§14 acceptance:

- Whisper models and Piper voices are listed with `pending_reason` until
  `scripts/pin_voice_catalogue.py` pins them from Hugging Face. Piper voices
  also need their dataset licences reviewed.
- Upstream publishes `whisper-server` for Windows only. The Linux and macOS
  builds are pending in Raiker's release workflow (§5.2).
- `kokoro-onnx` pulls in espeak-ng (GPL-3.0, §11 ⚠). It is not bundled until
  that is signed off, and a build without it reports
  `voice_kokoro_runtime_missing`.
- The installer step starts downloads when the step is answered. Pausing on a
  metered network is not implemented.

**V2 — Preview implemented.** Code: `web/src/lib/speech/`,
`web/src/lib/components/ConversationPanel.svelte`, the *Talk* button in Chat,
and `input_mode: spoken` with `SPOKEN_STYLE_PROMPT`. Two deliberate
departures from §10:

- **No WebSocket session.** The panel posts each utterance to the existing
  dictation route (which uses the managed Whisper engine), sends the
  transcript through the ordinary Chat stream path, and speaks the streamed
  answer with `/api/voice/speak`. A spoken turn is therefore the same governed
  turn as a typed one by construction, with no second turn path to keep in
  step.
- **VAD on the page's main thread**, with onnxruntime-web on one thread rather
  than in a Web Worker. One 32 ms frame costs well under a millisecond, and
  this avoids the cross-origin isolation a threaded WebAssembly worker would
  need. Running WebAssembly requires `'wasm-unsafe-eval'` in `script-src`,
  which permits compiling WebAssembly only (verified in Chromium against the
  real policy).

Not done yet: the §14 V2 latency acceptance on the reference laptop, the
Playwright fake-microphone end-to-end run (§13), `Ctrl/⌘+Shift+Space` and the
tray *Talk to Raiker* entry, ducking under a screen reader, and spoken tool
progress (the setting is stored; nothing speaks it yet).

## 13. Testing

| Level | What | Where |
|---|---|---|
| Unit | Profile recommendation per hardware fixture; placement decisions against a ledger; sentence splitter; state machine transitions including barge-in; catalogue validation (digest and licence present) | `tests/test_voice_*.py`, `voice/*.test.ts` |
| Integration | Fake whisper-server (returns fixed text), fake TTS worker (returns a tone), a real WebSocket session through the host: utterance → transcript → turn (stub provider) → speak events → barge-in cancels the turn | `tests/test_voice_session.py` |
| Real engines (opt-in, CI weekly on three OSes) | Install each catalogue tier from its real source; transcribe the JFK fixture (WER ≤ 10% on base); **round trip**: synthesise a sentence with Kokoro and Piper and transcribe it with Whisper (WER ≤ 15%); measure the real-time factor | `tests/test_voice_live.py`, `.github/workflows/voice.yml` |
| End to end | Playwright with Chromium's fake microphone (`--use-file-for-fake-audio-capture`) feeding a WAV: a spoken question appears as a caption, Raiker answers with a local model, audio playback is observed through a WebAudio analyser, and speaking over it interrupts. Screenshots of every orb state | `web/e2e/voice-conversation-live.spec.ts` |
| Performance | Mouth-to-ear latency P50/P95 per profile on the reference machines; CPU and RAM while talking; no regression over 10% between releases | Recorded in TESTING.md run records |
| Privacy | A recording proxy shows no audio bytes leave loopback; no audio is on disk after a session unless *Keep recordings* is on | Part of the MM-5 egress audit |

## 14. Acceptance (V1 and V2)

- V1: a fresh install chooses Balanced in the installer. After first start the
  engines download, verify and report *Ready*. Dictation and read-aloud use
  them on all three OSes, Test round-trips with WER within the threshold, and
  removing voice frees its disk and memory.
- V2: on the reference laptop, ten consecutive spoken questions are answered
  with P50 first-audio latency under 1.5 s. Each interruption stops speech
  within 200 ms. An approval-requiring request stops and asks on screen, and
  the transcript in chat matches what was heard and said.
