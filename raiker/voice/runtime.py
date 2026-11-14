# SPDX-License-Identifier: Apache-2.0
"""The Python packages voice runs on, and installing them when they are missing.

Voice spec §5.3. Speaking runs Kokoro through ``kokoro-onnx`` and
``onnxruntime``; the built-in listener runs whisper.cpp through
``pywhispercpp``. A packaged build carries them (``--bundle-voice``). Raiker run
from a source checkout did not, so **Test** and **▶ Preview** failed with
"Kokoro's runtime is not part of this Raiker build yet" and nothing on the page
could change that.

**Install** now also installs these packages when they are missing and Raiker
is running from source: the exact versions and every published hash in
``requirements/voice.txt``, with ``--require-hashes --no-deps``, into the
interpreter running Raiker. Nothing is installed in a packaged build, where a
missing package is a build defect and is reported as one.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parents[2] / "requirements" / "voice.txt"

#: The importable modules each side needs.
MODULES: dict[str, tuple[str, ...]] = {
    "speaking": ("kokoro_onnx", "onnxruntime", "numpy"),
    "listening": ("pywhispercpp", "numpy"),
}

#: The longest a runtime install may take before it is abandoned.
INSTALL_TIMEOUT_SECONDS = 900


class VoiceRuntimeError(RuntimeError):
    bounded_reason = True


def _importable(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def available(side: str) -> bool:
    """Whether every package ``side`` needs is importable here."""
    return all(_importable(module) for module in MODULES.get(side, ()))


def can_install() -> bool:
    """Whether Raiker may install the runtime itself: a source run with the lock file."""
    return not getattr(sys, "frozen", False) and REQUIREMENTS.is_file()


def missing_sides(sides: Iterable[str]) -> list[str]:
    return [side for side in sides if not available(side)]


def install_command() -> list[str]:
    """pip in this interpreter, or ``uv pip`` aimed at it when pip is absent (uv venvs)."""
    base = ["install", "--require-hashes", "--no-deps", "-r", str(REQUIREMENTS)]
    if _importable("pip"):
        return [sys.executable, "-m", "pip", *base, "--disable-pip-version-check"]
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", *base, "--python", sys.executable]
    raise VoiceRuntimeError("voice_runtime_installer_missing")


def install() -> None:
    """Install ``requirements/voice.txt`` into this interpreter, or raise a reason code."""
    if not can_install():
        raise VoiceRuntimeError("voice_runtime_not_in_build")
    command = install_command()
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, hash-locked requirements
            command, check=False, capture_output=True, timeout=INSTALL_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VoiceRuntimeError("voice_runtime_install_failed") from exc
    if completed.returncode != 0:
        raise VoiceRuntimeError("voice_runtime_install_failed")
    importlib.invalidate_caches()
