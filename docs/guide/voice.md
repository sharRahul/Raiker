# Voice

Raiker can listen to you and answer aloud entirely on this computer. Audio
never leaves it. The model that *thinks* is still the one you chose for the
conversation; voice only changes how you talk to it.

Voice is set up in **Settings › Voice**, or at the optional *Talk to Raiker*
step of first-run setup.

## Choosing a profile

A profile chooses the speech engines. Raiker recommends one from this
computer's memory and graphics card.

| Profile | For | Listening | Speaking |
|---|---|---|---|
| **Lite** | 8 GB of memory, no graphics card | Whisper base | Kokoro-82M (int8) |
| **Balanced** | 16 GB of memory | Whisper small, or large-v3-turbo when a graphics card has room | Kokoro-82M |
| **High quality** | 32 GB of memory, or a graphics card with 12 GB | Whisper large-v3-turbo | Kokoro-82M (full precision) |

**Install** downloads the profile's files in the background. You can follow
it in Settings › Voice and in Activity. Every file is checked against the
SHA-256 in Raiker's voice catalogue before it is kept, and a file that does
not match is deleted. **Remove** stops the engines and deletes every voice
file, and the page says how much space that freed.

Settings shows each component's state. A component that cannot be offered
yet says why instead of being hidden. In this build:

- **Speaking with Kokoro** uses Kokoro-82M in every profile: int8 for Lite
  and Balanced, full precision for High quality. Model and voice files are
  pinned and verified before installation. Piper is no longer offered.
- **Speech recognition** has pinned Whisper models. Windows has a verified
  upstream engine; Linux and macOS engine packaging remains pending.
- **Kokoro's runtime** is `kokoro-onnx` (tested here with version `0.6.1`). On
  a source install, `pip install kokoro-onnx==0.6.1` enables it. Frozen runtime
  packaging still needs verification; *runtime missing* uses the system-voice
  fallback. Removing Piper does not by itself bundle Kokoro's dependencies.
- The app keeps its memory guard. When available memory is too low, free
  resources or select a smaller profile; it does not start an unsafe workload.

## Where it runs

Each engine is a separate process on `127.0.0.1`, started when you use it and
stopped after the idle time you choose (10 minutes by default). Engines also
stop first of all when memory runs short. Resources in Settings › Voice says
where each engine runs, for example *"Speech recognition runs on the processor
because the GPU is busy with the model you chose."*

- A local model keeps priority on the graphics card.
- Whisper goes on the graphics card only when there is room beside that model.
- Kokoro runs on the processor.
- A profile that does not fit next to what is already running is refused, and
  the next smaller profile is offered.

The speaking engine answers only requests that carry a token Raiker writes
for each start, so other programs on the computer cannot use it.

## Using it

- **Dictation.** The microphone in the composer uses the installed Whisper
  engine. A transcription server you set up yourself under Models still takes
  precedence.
- **Read aloud.** The installed speaking engine reads answers sentence by
  sentence. Without one, read-aloud uses an on-device system voice, never a
  browser or cloud voice.
- **Test.** Speaks a phrase, transcribes it back when listening is installed,
  and shows how many words matched.
## Talking to Raiker (Preview)

When listening and speaking are both installed, Chat shows **Talk**. It opens
a conversation panel over the chat:

- **Hold to talk** (or hold Space), and release when you have finished.
  With **Hands-free conversation** turned on in Settings › Voice, Raiker
  listens for the end of your sentence itself, using the Silero voice-activity
  model that runs in the page.
- Raiker answers aloud sentence by sentence as the answer is written, so it
  starts speaking before the whole answer is ready. Captions show what you
  said and what it says, and both stay in the chat as ordinary messages.
- **Interrupt** by speaking over it, or press any key or **Stop talking**.
  Speech stops at once and the turn is cancelled.
- **Approvals are never given by voice.** A step that needs your OK stops
  speech, says *"I need your OK on screen"*, and shows the normal approval
  card. After you decide, press **Continue**.
- The status shows one of five states, each with its own shape and words:
  *Listening*, *Hearing you*, *Thinking*, *Speaking* and *Paused*.
- The privacy line under the controls says where your words go. With a
  hosted model it names the provider that receives your words as text; audio
  never leaves the computer.
- Pressing Escape or **End**, or hiding the window, releases the microphone.

A spoken message is an ordinary turn. The same permissions, tools, approvals,
budgets and receipts apply, and the model receives exactly the transcript you
see. It is also asked for a short, spoken-style answer.
