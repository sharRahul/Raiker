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
| **Lite** | 8 GB of memory, no graphics card | Whisper base | Piper |
| **Balanced** | 16 GB of memory | Whisper small, or large-v3-turbo when a graphics card has room | Kokoro-82M |
| **High quality** | 32 GB of memory, or a graphics card with 12 GB | Whisper large-v3-turbo | Kokoro-82M (full precision) |

**Install** downloads the profile's files in the background. You can follow
it in Settings › Voice and in Activity. Every file is checked against the
SHA-256 in Raiker's voice catalogue before it is kept, and a file that does
not match is deleted. **Remove** stops the engines and deletes every voice
file, and the page says how much space that freed.

Settings shows each component's state. A component that cannot be offered
yet says why instead of being hidden. In this build:

- **Speaking with Kokoro** (Balanced, High quality) is installable today.
- **Speech recognition** (the Whisper models) and **Piper's voices** are
  listed but not yet offered. Their files are hosted on Hugging Face, and
  their digests are pinned with `python -m scripts.pin_voice_catalogue
  --write` on a machine that can reach it. Piper voices also need their
  dataset licences reviewed.
- **whisper-server** is published upstream for Windows only. Linux and macOS
  builds come from Raiker's release workflow.
- **Kokoro's runtime** is the `kokoro-onnx` Python package. It is not bundled
  in packaged builds until the licence review of its espeak-ng phonemizer
  (GPL-3.0) is signed off. On a source install, `pip install kokoro-onnx`
  enables it. Without it, Kokoro reports *runtime missing* and read-aloud
  uses the system voice.

## Where it runs

Each engine is a separate process on `127.0.0.1`, started when you use it and
stopped after the idle time you choose (10 minutes by default). Engines also
stop first of all when memory runs short. Resources in Settings › Voice says
where each engine runs, for example *"Speech recognition runs on the processor
because the GPU is busy with the model you chose."*

- A local model keeps priority on the graphics card.
- Whisper goes on the graphics card only when there is room beside that model.
- Kokoro and Piper run on the processor.
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
- **Conversation.** See the conversation panel (*Preview*). Hands-free
  listening is behind **Settings › Voice › Hands-free conversation**.
