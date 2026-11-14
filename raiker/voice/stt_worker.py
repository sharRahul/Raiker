# SPDX-License-Identifier: Apache-2.0
"""The listening worker: Whisper in Raiker's own Python, where no build exists.

Voice spec §5.2. Raiker listens with ``whisper-server`` from a verified
catalogue build. Upstream publishes that build only for Windows; on Linux and
macOS the catalogue entry waits for Raiker's own release build, and until now
that left **Install** downloading the speaking half only and **Test** reporting
that listening was "not available yet" with nothing the owner could do.

This worker runs the same whisper.cpp, through the ``pywhispercpp`` binding,
on the same GGML Whisper model the catalogue already verifies, and answers the
same route ``whisper-server`` does, so the transcription client
(:func:`raiker.models.speech_runtime.transcribe`) needs no second path:

* ``GET /`` → ``{"ok": true, "engine": "whisper.cpp (built in)"}``
* ``POST /inference`` with a multipart ``file`` (16-bit PCM WAV) and an
  optional ``language`` → ``{"text": …}``

It listens on ``127.0.0.1`` only, holds a clip only for the length of one
request, and writes nothing to disk. Like ``whisper-server`` it carries no
token: the host reaches it by a port chosen at start, on loopback.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import threading
import wave
from email.parser import BytesParser
from email.policy import default as default_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

#: The largest clip one request may carry (about ten minutes of 16 kHz mono).
MAX_BODY_BYTES = 25 * 1024 * 1024
#: Whisper's own sample rate.
WHISPER_RATE = 16_000


class Recogniser(Protocol):
    def transcribe(self, samples: Any, language: str | None) -> str: ...


def wav_to_samples(data: bytes) -> Any:
    """16 kHz mono float32 samples from a PCM WAV clip, resampled if needed."""
    import numpy as np  # type: ignore[import-not-found,unused-ignore]

    with wave.open(io.BytesIO(data), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width == 2:
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    elif width == 1:
        samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError("unsupported_sample_width")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != WHISPER_RATE and samples.size:
        duration = samples.size / float(rate)
        target = max(1, int(round(duration * WHISPER_RATE)))
        positions = np.linspace(0.0, samples.size - 1, num=target)
        samples = np.interp(positions, np.arange(samples.size), samples).astype(np.float32)
    return samples.astype(np.float32)


class WhisperCppRecogniser:
    engine = "whisper.cpp (built in)"

    def __init__(self, model: str, threads: int) -> None:
        from pywhispercpp.model import Model  # type: ignore[import-not-found,unused-ignore]

        self._model = Model(model, n_threads=max(1, threads), print_progress=False, print_realtime=False,
                            redirect_whispercpp_logs_to=None)
        self._lock = threading.Lock()

    def transcribe(self, samples: Any, language: str | None) -> str:
        params: dict[str, Any] = {}
        if language and language != "auto":
            params["language"] = language
        with self._lock:
            segments = self._model.transcribe(samples, **params)
        return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()


def _form(content_type: str, body: bytes) -> dict[str, tuple[bytes, str | None]]:
    """The parts of a ``multipart/form-data`` body, by field name."""
    message = BytesParser(policy=default_policy).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    parts: dict[str, tuple[bytes, str | None]] = {}
    if not message.is_multipart():
        return parts
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True)
        parts[str(name)] = (payload if isinstance(payload, bytes) else b"", part.get_filename())
    return parts


def make_handler(recogniser: Recogniser, engine: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # never log what was heard
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib name
            if self.path in {"/", "/health"}:
                self._json(200, {"ok": True, "engine": engine})
                return
            self._json(404, {"reason_code": "not_found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib name
            if self.path != "/inference":
                self._json(404, {"reason_code": "not_found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                self._json(413, {"reason_code": "speech_audio_too_large"})
                return
            body = self.rfile.read(length)
            try:
                form = _form(self.headers.get("Content-Type", ""), body)
                audio = form.get("file", (b"", None))[0]
                language_raw = form.get("language", (b"", None))[0].decode("utf-8", "ignore").strip()
                samples = wav_to_samples(audio)
            except ImportError:
                self._json(500, {"reason_code": "voice_whisper_runtime_missing"})
                return
            except (ValueError, EOFError, wave.Error):
                self._json(400, {"reason_code": "speech_audio_invalid"})
                return
            try:
                text = recogniser.transcribe(samples, language_raw or None)
            except Exception:  # noqa: BLE001 - one failed clip is a code, not a crash
                self._json(500, {"reason_code": "speech_transcription_failed"})
                return
            self._json(200, {"text": text})

    return Handler


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="raiker-voice-stt-worker")
    parser.add_argument("--model", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--threads", type=int, default=4)
    return parser.parse_args(argv)


def runtime_available() -> bool:
    """Whether this interpreter can run the built-in listener."""
    try:
        import importlib.util

        return importlib.util.find_spec("pywhispercpp") is not None and importlib.util.find_spec("numpy") is not None
    except (ImportError, ValueError):
        return False


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        recogniser = WhisperCppRecogniser(args.model, args.threads)
    except ImportError:
        print("voice_whisper_runtime_missing", file=sys.stderr, flush=True)
        return 3
    except Exception as exc:  # noqa: BLE001 - reported to the host's log by type
        print(f"voice_engine_failed:{type(exc).__name__}", file=sys.stderr, flush=True)
        return 4
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(recogniser, WhisperCppRecogniser.engine))
    print(f"voice listener ready on 127.0.0.1:{args.port}", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
