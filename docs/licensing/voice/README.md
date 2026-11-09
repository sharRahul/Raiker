# Optional personal Kokoro runtime

`--bundle-voice` is an explicit personal-build option. It is not enabled in the
public release workflow. Install the hash-locked `requirements/voice.txt`
alongside `requirements/release-build.txt` before freezing. The build refuses
missing or different dependency versions and copies their distribution
metadata/licence files into the frozen payload. Model and voice assets keep
separate catalogue hashes and are downloaded only when requested.

Kokoro-82M weights are Apache-2.0; kokoro-onnx is MIT; ONNX Runtime is MIT.
Phonemizer and the espeak-ng library retain GPL-3.0 terms. `GPL-3.0.txt` is the
unmodified licence text retained from the phonemizer 3.6.0 wheel. This option
does not declare those dependencies Apache-2.0 or silently add a permissive
exception to the general distribution licence policy.

Exact runtime wheel/source artifact hashes are in `requirements/voice.txt`.
Upstream source and licence records:

- https://huggingface.co/hexgrad/Kokoro-82M
- https://github.com/thewh1teagle/kokoro-onnx
- https://github.com/microsoft/onnxruntime
- https://github.com/bootphon/phonemizer
- https://github.com/thewh1teagle/espeakng-loader
- https://github.com/espeak-ng/espeak-ng

The loader supplies a native espeak-ng library and data. Its wheel lacks a
licence file; the GPL text above is therefore included explicitly in addition
to dependency metadata, and `espeakng-loader-MIT.txt` is the loader's own MIT
licence taken from its pinned upstream source.

`runtime-sources.json` pins the unmodified corresponding sources for the
phonemizer stack (espeak-ng 1.52.0, espeakng-loader 0.2.4, phonemizer 3.6.0)
by URL, size and SHA-256. `python -m scripts.package_voice_sources --out DIR`
downloads each one, refuses any that does not match, and writes them beside
these notices, a `git archive` of the building Raiker commit, the voice
requirements, a runtime inventory and an SPDX SBOM. The personal Windows
workflow (`.github/workflows/personal-windows-voice.yml`) uploads that
directory with the unsigned installer and its speech-test evidence. Personal use does not require production publisher
infrastructure. A public redistributable variant still needs its corresponding
sources and complete notices reviewed; the opt-in private build is not that
approval. No third-party source is modified here.
