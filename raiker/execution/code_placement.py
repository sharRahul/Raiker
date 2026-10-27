"""Classify command risk separately from native sandbox placement.

Risk classification retains existing authorization gates. It never authorizes
host execution; the command service probes and enforces the boundary at launch.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

#: The capability a code-running command answers to when it would run with the
#: host's network.
HOST_NETWORK_CODE_CAPABILITY = "host_network_code_execution"

#: Programs whose job is to run code the command line does not show. ``pip``
#: is here because installing a source package runs its build script.
CODE_RUNNERS: frozenset[str] = frozenset({"python", "python3", "pip", "pip3", "node", "npm", "npx"})

#: The two command capabilities a code runner can arrive through.
COMMAND_CAPABILITIES: frozenset[str] = frozenset({"shell_execution", "process_execution"})

PlacementKind = Literal["sandbox", "unavailable"]
RiskClassification = Literal["not_code", "owner_environment", "sandbox", "host_network"]


@dataclass(frozen=True)
class CodePlacement:
    """Risk classification and advisory native placement for one command."""

    kind: PlacementKind
    binary: str = ""
    reason: str = ""
    classification: RiskClassification = "not_code"
    placement_reason: str = ""

    @property
    def needs_host_network_capability(self) -> bool:
        return self.classification == "host_network"


def code_runner(argv: Sequence[str]) -> str | None:
    """The code runner *argv* invokes, or ``None`` when it invokes none."""
    if not argv:
        return None
    binary = Path(str(argv[0])).name.lower()
    if binary.endswith(".exe"):
        binary = binary[:-4]
    return binary if binary in CODE_RUNNERS else None


# ── Is the sandbox here? ──────────────────────────────────────────────────────

#: How long a probe answer is reused for *classification*. Running a command
#: always probes again (``CommandService`` does), so a stale "available" here can
#: only ever make a command refuse, never run it outside a boundary.
_PROBE_TTL_SECONDS = 30.0
_PROBE_LOCK = threading.Lock()
_PROBES: dict[str, tuple[float, bool]] = {}

Prober = Callable[[Path], bool]


def _probe_native_sandbox(workspace_root: Path) -> bool:
    # Imported here: the driver pulls in the command runner package.
    from raiker.execution.commands.backends.native import NativeSandboxDriver

    return bool(NativeSandboxDriver(workspace_root).probe().available)


_prober: Prober = _probe_native_sandbox


def set_sandbox_prober(prober: Prober | None) -> None:
    """Replace how availability is measured (tests), or restore the real probe."""
    global _prober
    with _PROBE_LOCK:
        _prober = prober or _probe_native_sandbox
        _PROBES.clear()


def sandbox_available(workspace_root: str | Path, *, fresh: bool = False) -> bool:
    """Whether the native OS sandbox is enforced on this host for this workspace."""
    root = Path(workspace_root).resolve()
    key = str(root)
    now = time.monotonic()
    with _PROBE_LOCK:
        cached = _PROBES.get(key)
        if not fresh and cached is not None and now - cached[0] < _PROBE_TTL_SECONDS:
            return cached[1]
        prober = _prober
    try:
        available = bool(prober(root))
    except Exception:  # noqa: BLE001 - an unmeasured boundary is not a boundary
        available = False
    with _PROBE_LOCK:
        _PROBES[key] = (time.monotonic(), available)
    return available


# ── The rule ──────────────────────────────────────────────────────────────────


def place_code(
    store: Any,
    owner_principal_id: str,
    argv: Sequence[str],
    workspace_root: str | Path,
    *,
    background: bool = False,
    interactive: bool = False,
    fresh: bool = False,
) -> CodePlacement:
    """Classify the request without treating risk as an execution destination."""
    binary = code_runner(argv) or ""
    chosen = bool(store.execution_environment_was_chosen(owner_principal_id))
    selected = str(store.selected_execution_environment(owner_principal_id))
    available = sandbox_available(workspace_root, fresh=fresh)
    classification: RiskClassification = "not_code"
    reason = ""
    if binary:
        if chosen and selected != "local_native":
            classification, reason = "owner_environment", f"owner_chose:{selected}"
        elif chosen:
            classification, reason = "host_network", "owner_chose_host"
        elif background or interactive:
            classification, reason = "host_network", "sandbox_cannot_host_background_or_terminal"
        elif available:
            classification, reason = "sandbox", "native_sandbox_available"
        else:
            classification, reason = "host_network", "no_sandbox_on_this_host"
    kind: PlacementKind
    if chosen and selected not in {"local_native", "native_sandbox"}:
        kind, placement_reason = "unavailable", "native_sandbox_required"
    elif background or interactive:
        kind, placement_reason = "unavailable", "native_sandbox_mode_unsupported"
    elif not available:
        kind, placement_reason = "unavailable", "native_sandbox_unavailable"
    else:
        kind, placement_reason = "sandbox", "native_sandbox_available"
    return CodePlacement(kind, binary, reason, classification, placement_reason)


def argv_of(capability: str, arguments: dict[str, Any]) -> list[str]:
    """The argv a ``shell`` or ``process`` action would run, or ``[]``."""
    import shlex

    if capability == "process_execution":
        executable = str(arguments.get("executable", "")).strip()
        args = arguments.get("args", [])
        return [executable, *(str(part) for part in args)] if executable else []
    source = arguments.get("command")
    if not isinstance(source, str):
        return []
    try:
        return shlex.split(source, posix=True)
    except ValueError:
        return []
