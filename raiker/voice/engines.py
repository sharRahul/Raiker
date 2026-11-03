"""The running voice engines of one workspace: started on use, stopped when idle.

Voice spec §7, *warm and cold*. Engines start when a voice feature is used
(dictation, read-aloud, the Test button, a conversation) and stop after the
idle timeout, or first of all when memory runs short. Each is a separate,
contained process on loopback, started with a fixed argv through the same
``spawn`` the llama.cpp server uses (a Windows job object; orphan reaping on
macOS and Linux), and each registers its planned memory in the shared
:class:`~raiker.models.engines.resources.ResourceLedger` while it runs.

* **Listening** — ``whisper-server`` from the verified catalogue build, with
  the chosen Whisper model. Dictation and conversation post to it through the
  existing transcription client (``speech_runtime.transcribe``).
* **Speaking** — the speaking worker (:mod:`raiker.voice.tts_worker`) with
  Kokoro or Piper, reached with a per-start token.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import signal
import socket
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from raiker.models.engines.resources import Reservation, ResourceLedger, ledger_for
from raiker.models.llama_cpp.process import _process_command, read_log_tail, spawn

#: How long an engine may take to answer its first health check.
READY_SECONDS = 90.0
DEFAULT_IDLE_SECONDS = 600.0


class VoiceEngineError(RuntimeError):
    bounded_reason = True


def voice_log_dir(workspace_root: Path) -> Path:
    path = Path(workspace_root) / "logs" / "voice"
    path.mkdir(parents=True, exist_ok=True)
    return path


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def worker_argv() -> list[str]:
    """How to start Raiker's own speaking worker from this process."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--voice-tts-worker"]
    # The worker's own file, by path: it imports nothing from Raiker, and naming
    # the file guarantees the child runs the same code as this host rather than
    # whichever `raiker` the interpreter would find first.
    return [sys.executable, str(Path(__file__).with_name("tts_worker.py"))]


@dataclass
class RunningEngine:
    name: str
    process: Any
    port: int
    argv: list[str]
    log_path: Path
    pid_path: Path
    started_at: float
    last_used: float
    device: str
    token: str = ""
    detail: str = ""

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None


class VoiceEngines:
    """Start, reuse and stop the voice engines of one workspace."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        ledger: ResourceLedger | None = None,
        spawner: Callable[..., Any] = spawn,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.ledger = ledger or ledger_for(workspace_root)
        self._spawn = spawner
        self._clock = clock
        self._lock = threading.RLock()
        self._running: dict[str, RunningEngine] = {}
        #: Why an engine is not running when it last stopped: ``idle`` or ``memory``.
        self.paused_reason: dict[str, str] = {}
        #: The owner's idle timeout, set each time an engine is used.
        self.idle_seconds = DEFAULT_IDLE_SECONDS

    # ── lifecycle ──────────────────────────────────────────────────────

    def _start(self, name: str, argv: list[str], port: int, *, device: str, ram: int, vram: int,
               gpu: str | None, health: Callable[[RunningEngine], bool], token: str = "") -> RunningEngine:
        logs = voice_log_dir(self.workspace_root)
        log_path, pid_path = logs / f"{name}.log", logs / f"{name}.pid"
        try:
            process = self._spawn(argv, log_path=log_path, pid_path=pid_path)
        except OSError as exc:
            raise VoiceEngineError(f"voice_{name}_unrunnable") from exc
        now = self._clock()
        engine = RunningEngine(name=name, process=process, port=port, argv=argv, log_path=log_path,
                               pid_path=pid_path, started_at=now, last_used=now, device=device, token=token)
        deadline = time.monotonic() + READY_SECONDS
        while time.monotonic() < deadline:
            if not engine.alive():
                tail = read_log_tail(log_path)
                if "voice_kokoro_runtime_missing" in tail:
                    raise VoiceEngineError("voice_kokoro_runtime_missing")
                raise VoiceEngineError(f"voice_{name}_exited")
            if health(engine):
                break
            time.sleep(0.2)
        else:
            self._terminate(engine)
            raise VoiceEngineError(f"voice_{name}_not_ready")
        self.ledger.reserve(Reservation(owner=f"voice:{name}", kind="voice", ram_bytes=ram,
                                        gpu_id=gpu, vram_bytes=vram))
        self._running[name] = engine
        self.paused_reason.pop(name, None)
        return engine

    def _terminate(self, engine: RunningEngine) -> None:
        process = engine.process
        if process is not None and process.poll() is None:
            with contextlib.suppress(Exception):
                process.terminate()
                process.wait(timeout=5)
            if process.poll() is None:
                with contextlib.suppress(Exception):
                    process.kill()
        engine.pid_path.unlink(missing_ok=True)
        self.ledger.release(f"voice:{engine.name}")

    def stop(self, name: str, *, reason: str = "stopped") -> None:
        with self._lock:
            engine = self._running.pop(name, None)
            if engine is not None:
                self._terminate(engine)
                self.paused_reason[name] = reason

    def stop_all(self, *, reason: str = "stopped") -> None:
        with self._lock:
            for name in list(self._running):
                self.stop(name, reason=reason)

    def running(self, name: str) -> RunningEngine | None:
        with self._lock:
            engine = self._running.get(name)
            if engine is not None and not engine.alive():
                self._terminate(engine)
                self._running.pop(name, None)
                self.paused_reason[name] = "exited"
                return None
            return engine

    def touch(self, name: str) -> None:
        engine = self._running.get(name)
        if engine is not None:
            engine.last_used = self._clock()

    def tick(self, idle_seconds: float = DEFAULT_IDLE_SECONDS, *, memory_short: bool = False) -> list[str]:
        """Stop idle engines, or every engine when memory is short. Returns what stopped."""
        stopped: list[str] = []
        with self._lock:
            now = self._clock()
            for name, engine in list(self._running.items()):
                if memory_short:
                    self.stop(name, reason="memory")
                    stopped.append(name)
                elif now - engine.last_used >= idle_seconds:
                    self.stop(name, reason="idle")
                    stopped.append(name)
        return stopped

    def reap_orphans(self) -> list[int]:
        """Stop voice engines a previous Raiker run left behind (not on Windows)."""
        stopped: list[int] = []
        directory = Path(self.workspace_root) / "logs" / "voice"
        if sys.platform == "win32" or not directory.is_dir():
            return stopped
        for pid_file in directory.glob("*.pid"):
            try:
                record = json.loads(pid_file.read_text(encoding="utf-8"))
                pid, argv = int(record["pid"]), [str(item) for item in record["argv"]]
            except (OSError, ValueError, KeyError, TypeError):
                pid_file.unlink(missing_ok=True)
                continue
            command = _process_command(pid)
            if command and argv and argv[0] in command and (
                "whisper-server" in command or "tts_worker" in command or "--voice-tts-worker" in command
            ):
                with contextlib.suppress(OSError):
                    os.kill(pid, signal.SIGTERM)
                    stopped.append(pid)
            pid_file.unlink(missing_ok=True)
        return stopped

    # ── listening ──────────────────────────────────────────────────────

    def ensure_whisper(self, executable: Path, model: Path, *, threads: int, device: str,
                       ram: int, vram: int, gpu: str | None, language: str | None = None) -> RunningEngine:
        with self._lock:
            current = self.running("whisper")
            if current is not None:
                current.last_used = self._clock()
                return current
            port = free_port()
            argv = [str(executable), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
                    "-t", str(max(1, threads))]
            if device == "cpu":
                argv.append("--no-gpu")
            if language:
                argv += ["-l", language]

            def healthy(engine: RunningEngine) -> bool:
                try:
                    return httpx.get(f"{engine.endpoint}/", timeout=1.0).status_code < 500
                except httpx.HTTPError:
                    return False

            return self._start("whisper", argv, port, device=device, ram=ram, vram=vram, gpu=gpu, health=healthy)

    # ── speaking ───────────────────────────────────────────────────────

    def ensure_speaker(self, engine: str, *, model: Path, voices: Path | None = None,
                       piper: Path | None = None, threads: int, ram: int) -> RunningEngine:
        with self._lock:
            current = self.running("speaker")
            if current is not None and current.detail == engine:
                current.last_used = self._clock()
                return current
            if current is not None:
                self.stop("speaker", reason="changed")
            port = free_port()
            token = secrets.token_urlsafe(24)
            token_file = voice_log_dir(self.workspace_root) / "speaker.token"
            token_file.write_text(token, encoding="utf-8")
            with contextlib.suppress(OSError):
                token_file.chmod(0o600)
            argv = [*worker_argv(), "--engine", engine, "--model", str(model), "--port", str(port),
                    "--threads", str(max(1, threads)), "--token-file", str(token_file)]
            if voices is not None:
                argv += ["--voices", str(voices)]
            if piper is not None:
                argv += ["--piper", str(piper)]

            def healthy(running: RunningEngine) -> bool:
                try:
                    answer = httpx.get(f"{running.endpoint}/health", timeout=1.0,
                                       headers={"X-Raiker-Voice-Token": token})
                    return answer.status_code == 200
                except httpx.HTTPError:
                    return False

            started = self._start("speaker", argv, port, device="cpu", ram=ram, vram=0, gpu=None,
                                  health=healthy, token=token)
            started.detail = engine
            return started

    def synthesise(self, text: str, *, voice: str | None, speed: float = 1.0) -> bytes:
        engine = self.running("speaker")
        if engine is None:
            raise VoiceEngineError("voice_speaker_not_running")
        engine.last_used = self._clock()
        try:
            answer = httpx.post(f"{engine.endpoint}/synthesize", timeout=60.0,
                                headers={"X-Raiker-Voice-Token": engine.token},
                                json={"text": text, "voice": voice, "speed": speed})
        except httpx.HTTPError as exc:
            raise VoiceEngineError("voice_speaker_unreachable") from exc
        if answer.status_code != 200:
            raise VoiceEngineError("voice_synthesis_failed")
        return answer.content

    def status(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name in ("whisper", "speaker"):
            engine = self.running(name)
            out[name] = {
                "running": engine is not None,
                "device": engine.device if engine else None,
                "engine": (engine.detail or name) if engine else None,
                "paused_reason": None if engine else self.paused_reason.get(name),
            }
        return out


_ENGINES: dict[str, VoiceEngines] = {}
_ENGINES_LOCK = threading.Lock()


def engines_for(workspace_root: str | Path) -> VoiceEngines:
    with _ENGINES_LOCK:
        key = str(workspace_root)
        if key not in _ENGINES:
            _ENGINES[key] = VoiceEngines(workspace_root)
        return _ENGINES[key]
