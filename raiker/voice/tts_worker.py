"""The speaking worker: one loopback process that turns text into WAV audio.

Voice spec §5.3. Kokoro-82M runs in Raiker's own Python with ``onnxruntime``
and the ``kokoro-onnx`` package; Piper runs as its upstream binary, called by
this worker once per request. Either way the host talks to the worker the same
way:

* ``GET /health`` → ``{"ok": true, "engine": …, "voices": […]}``
* ``POST /synthesize`` with ``{"text", "voice", "speed"}`` → ``audio/wav``

The worker listens on ``127.0.0.1`` only and answers only a request carrying
the token the host wrote for this start (``X-Raiker-Voice-Token``), so another
program on the computer cannot use it to speak. It holds no audio after a
response, and writes nothing to disk.

Started by the host as ``python -m raiker.voice.tts_worker`` or, in a packaged
build, as ``raiker --voice-tts-worker`` (:mod:`raiker.app.launcher`).
"""

from __future__ import annotations

import argparse
import contextlib
import hmac
import io
import json
import subprocess
import sys
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol

#: The longest text one request may ask to speak. The session splits answers
#: into sentences of at most 220 characters; this bounds a misbehaving caller.
MAX_TEXT_CHARS = 2000
MAX_BODY_BYTES = 16 * 1024


class Synthesiser(Protocol):
    engine: str

    def voices(self) -> list[str]: ...

    def synthesise(self, text: str, voice: str | None, speed: float) -> tuple[bytes, int]:
        """PCM16 mono samples and their sample rate."""
        ...


def pcm16_wav(pcm: bytes, rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


class KokoroSynthesiser:
    engine = "kokoro"

    def __init__(self, model: Path, voices: Path, threads: int) -> None:
        import onnxruntime  # type: ignore[import-not-found,unused-ignore]
        from kokoro_onnx import Kokoro  # type: ignore[import-not-found,unused-ignore]

        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = max(1, threads)
        session = onnxruntime.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
        self._kokoro = Kokoro.from_session(session, str(voices))
        self._lock = threading.Lock()

    def voices(self) -> list[str]:
        return sorted(self._kokoro.get_voices())

    def synthesise(self, text: str, voice: str | None, speed: float) -> tuple[bytes, int]:
        import numpy as np  # type: ignore[import-not-found,unused-ignore]

        chosen = voice or "af_heart"
        lang = "en-gb" if chosen.startswith(("bf_", "bm_")) else "en-us"
        with self._lock:
            samples, rate = self._kokoro.create(text, voice=chosen, speed=speed, lang=lang)
        clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
        return (clipped * 32767.0).astype("<i2").tobytes(), int(rate)


class PiperSynthesiser:
    engine = "piper"

    def __init__(self, executable: Path, voice_model: Path, threads: int) -> None:
        self._executable = executable
        self._model = voice_model
        config = json.loads(Path(str(voice_model) + ".json").read_text(encoding="utf-8"))
        self._rate = int(config.get("audio", {}).get("sample_rate", 22050))

    def voices(self) -> list[str]:
        return [self._model.name.removesuffix(".onnx")]

    def synthesise(self, text: str, voice: str | None, speed: float) -> tuple[bytes, int]:
        length_scale = f"{1.0 / max(0.5, min(2.0, speed)):.3f}"
        completed = subprocess.run(  # noqa: S603 - the verified Piper binary, fixed argv, text on stdin
            [str(self._executable), "--model", str(self._model), "--output_raw", "--length_scale", length_scale],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=60,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0 or not completed.stdout:
            raise RuntimeError("piper_failed")
        return completed.stdout, self._rate


def make_handler(synth: Synthesiser, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # never log text
            return

        def _authorised(self) -> bool:
            presented = self.headers.get("X-Raiker-Voice-Token", "")
            return bool(token) and hmac.compare_digest(presented, token)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib name
            if not self._authorised():
                self._json(403, {"reason_code": "voice_worker_token"})
                return
            if self.path != "/health":
                self._json(404, {"reason_code": "not_found"})
                return
            self._json(200, {"ok": True, "engine": synth.engine, "voices": synth.voices()})

        def do_POST(self) -> None:  # noqa: N802 - stdlib name
            if not self._authorised():
                self._json(403, {"reason_code": "voice_worker_token"})
                return
            if self.path != "/synthesize":
                self._json(404, {"reason_code": "not_found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                self._json(413, {"reason_code": "voice_text_too_long"})
                return
            try:
                request = json.loads(self.rfile.read(length))
                text = str(request.get("text") or "").strip()
                voice = request.get("voice")
                speed = float(request.get("speed") or 1.0)
            except (ValueError, TypeError, AttributeError):
                self._json(400, {"reason_code": "voice_request_invalid"})
                return
            if not text or len(text) > MAX_TEXT_CHARS:
                self._json(413 if text else 400, {"reason_code": "voice_text_invalid"})
                return
            try:
                pcm, rate = synth.synthesise(text, str(voice) if voice else None, max(0.5, min(2.0, speed)))
            except Exception:  # noqa: BLE001 - one failed sentence is a code, not a crash
                self._json(500, {"reason_code": "voice_synthesis_failed"})
                return
            body = pcm16_wav(pcm, rate)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def build_synthesiser(args: argparse.Namespace) -> Synthesiser:
    if args.engine == "kokoro":
        return KokoroSynthesiser(Path(args.model), Path(args.voices), args.threads)
    if args.engine == "piper":
        return PiperSynthesiser(Path(args.piper), Path(args.model), args.threads)
    raise SystemExit(2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="raiker-voice-tts-worker")
    parser.add_argument("--engine", choices=("kokoro", "piper"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--voices", default="")
    parser.add_argument("--piper", default="")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--token-file", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    token = Path(args.token_file).read_text(encoding="utf-8").strip()
    try:
        synth = build_synthesiser(args)
    except ImportError:
        print("voice_kokoro_runtime_missing", file=sys.stderr, flush=True)
        return 3
    except Exception as exc:  # noqa: BLE001 - reported to the host's log by type
        print(f"voice_engine_failed:{type(exc).__name__}", file=sys.stderr, flush=True)
        return 4
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(synth, token))
    print(f"voice worker ready on 127.0.0.1:{args.port}", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
