"""Where a command that runs code runs, and whether it has the host's network (BUG-308).

CR-09 of the security review: ``python``, ``node``, ``npm`` and ``npx`` are on
the governed command allowlist, their inline-code flags are refused and every
path they name must stay in the workspace — and none of that is a network
boundary. A script in the workspace can open a socket the egress policy never
sees. The command parser cannot tell what a script will do; only where it runs
decides that.

The owner's decision (2026-09-28) is what this module implements:

* **Where this machine has the native OS sandbox, code runs inside it** — no
  network, the same boundary the ``native_sandbox`` environment provides —
  unless the owner chose an environment themselves.
* **Where it has none, the code still runs**, as it did before, but under its
  own capability, :data:`HOST_NETWORK_CODE_CAPABILITY`, which says what it is:
  code running with this machine's network. It has its own switch in
  Permissions and, like every capability, its decision mode starts at *Ask me*.
  Nothing that worked before starts refusing; it starts saying so.

An owner who *chose* an environment keeps it. One who chose the host has chosen
its network, and is asked under the same named capability; one who chose a
container or a remote machine gets that boundary, which is theirs to reason
about.

The sandbox cannot host a background run or a terminal, so a request for either
is placed on the host — again under the named capability, never silently.
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

PlacementKind = Literal["not_code", "owner_environment", "sandbox", "host_network"]


@dataclass(frozen=True)
class CodePlacement:
    """Where one command will run, and why."""

    kind: PlacementKind
    binary: str = ""
    reason: str = ""

    @property
    def needs_host_network_capability(self) -> bool:
        return self.kind == "host_network"


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
    """Decide where *argv* runs. The router and the command service both ask this."""
    binary = code_runner(argv)
    if binary is None:
        return CodePlacement("not_code")
    chosen = bool(store.execution_environment_was_chosen(owner_principal_id))
    selected = str(store.selected_execution_environment(owner_principal_id))
    if chosen and selected != "local_native":
        return CodePlacement("owner_environment", binary, f"owner_chose:{selected}")
    if chosen:
        return CodePlacement("host_network", binary, "owner_chose_host")
    if background or interactive:
        return CodePlacement(
            "host_network", binary, "sandbox_cannot_host_background_or_terminal"
        )
    if sandbox_available(workspace_root, fresh=fresh):
        return CodePlacement("sandbox", binary, "native_sandbox_available")
    return CodePlacement("host_network", binary, "no_sandbox_on_this_host")


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
