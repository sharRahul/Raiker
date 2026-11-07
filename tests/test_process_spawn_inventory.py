"""Every place Raiker starts a process is reviewed (beta plan SB-4).

The beta rule is that agent commands, plugins, hooks and local MCP servers run
in the native sandbox or not at all. The way to keep that rule from eroding is
to know every call site that can start a process, and to make adding one a
reviewed change rather than an accident. This test scans ``raiker/`` and
fails when:

* a module starts a process and is not listed in :data:`REVIEWED` with the
  reason it may — so a new ``subprocess.run`` cannot land unnoticed;
* a listed module no longer starts one — so the list cannot quietly grow stale;
* anything uses a shell (``shell=True``, ``create_subprocess_shell``,
  ``os.system``, ``os.popen``) — every argv in Raiker is built as a list.

The categories say *why* a site may run outside the agent sandbox. Only
``sandbox`` sites run agent-chosen work, and they are the sandbox itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "raiker"

SUBPROCESS_CALLS = frozenset({"Popen", "run", "call", "check_call", "check_output", "getoutput", "getstatusoutput"})
ASYNCIO_CALLS = frozenset({"create_subprocess_exec", "create_subprocess_shell"})
OS_CALLS = frozenset(
    {"system", "popen", "execv", "execve", "execvp", "execvpe", "execl", "execle", "execlp", "execlpe",
     "spawnv", "spawnve", "spawnvp", "spawnvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe", "posix_spawn",
     "posix_spawnp", "startfile"}
)

#: The sandbox boundary itself: runs agent-chosen work, always inside it.
SANDBOX = "sandbox"
#: A program Raiker ships or installs and verifies, with a fixed argv
#: (model servers, the native runner, the SQLCipher probe).
OWNED = "raiker-owned program"
#: Starting, stopping, updating or packaging Raiker itself.
LIFECYCLE = "host lifecycle"
#: A fixed system tool read for facts (memory, GPU, signatures); no side effects.
FACTS = "read-only system facts"
#: An owner-approved operation on the owner's own repository or account,
#: hardened against configuration-driven execution.
OWNER = "owner-approved host operation"

REVIEWED: dict[str, tuple[str, str]] = {
    "raiker/execution/commands/backends/native.py": (SANDBOX, "Launches the native runner that applies the boundary"),
    "raiker/execution/commands/runner.py": (SANDBOX, "The command lifecycle under the native runner; process-tree stop via a fixed OS tool"),
    "raiker/execution/commands/sandboxed_program.py": (SANDBOX, "Plugins and local MCP stdio servers, copied into a throwaway folder inside the boundary"),
    "raiker/execution/commands/supervisor_client.py": (SANDBOX, "The detached supervisor that keeps sandboxed background runs alive"),
    "raiker/execution/commands/remote_supervisor.py": (SANDBOX, "Remote execution profiles: a fixed, validated transport"),
    "raiker/execution/commands/backends/remote.py": (SANDBOX, "Remote execution profiles: a fixed transport and a literal probe"),
    "raiker/models/slot_runtime.py": (OWNED, "llama.cpp / MLX servers with a fixed argv on loopback"),
    "raiker/models/llama_cpp/process.py": (OWNED, "The digest-verified llama.cpp server, in a Windows job object"),
    "raiker/models/llama_cpp/installer.py": (OWNED, "Self-check of the digest-verified llama.cpp build (--version, --list-devices)"),
    "raiker/models/llama_cpp/hardware.py": (FACTS, "nvidia-smi and sysctl for GPU memory and CUDA version"),
    "raiker/voice/tts_worker.py": (OWNED, "The digest-verified Piper binary, fixed argv, text on stdin, from Raiker's speaking worker"),
    "raiker/models/conversion.py": (SANDBOX, "Model conversion through the native runner, never on the host"),
    "raiker/models/codex_app_server.py": (OWNER, "The owner's Codex app server for ChatGPT sign-in, over stdio"),
    "raiker/storage/sqlcipher_probe.py": (OWNED, "Raiker's own SQLCipher capability probe, in a child interpreter"),
    "raiker/execution/windows_authenticode.py": (FACTS, "Reads a binary's Authenticode signature"),
    "raiker/app/platform_signatures.py": (FACTS, "Release CI only: reads Authenticode signatures and verifies gpg detached signatures against the pinned keys"),
    "raiker/app/system_check.py": (FACTS, "sysctl for memory and CPU name"),
    "raiker/app/launcher.py": (LIFECYCLE, "Starts the Raiker host and opens the browser"),
    "raiker/app/service.py": (LIFECYCLE, "Registers Raiker's own service with the OS"),
    "raiker/app/desktop_shell.py": (LIFECYCLE, "Starts the desktop window"),
    "raiker/app/desktop_build.py": (LIFECYCLE, "Packaging, developer and CI only"),
    "raiker/app/desktop_smoke.py": (LIFECYCLE, "Packaging smoke test, CI only"),
    "raiker/app/desktop_update.py": (LIFECYCLE, "Hands a verified update to the platform installer"),
    "raiker/app/update_handoff.py": (LIFECYCLE, "The verified update helper"),
    "raiker/tools/git.py": (OWNER, "Git on the owner's repository after Apply; filter drivers, fsmonitor and foreign credential helpers disabled"),
    "raiker/github/local_methods.py": (OWNER, "Discovers the owner's own gh sign-in and credential helper when selected"),
    "raiker/notify/approval_notifier.py": (OWNER, "The owner's own RAIKER_OS_NOTIFY_CMD, off by default, redacted arguments only"),
}


def _spawn_name(node: ast.AST) -> str | None:
    """``subprocess.run``-style access, whether called or passed as a value."""
    if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
        return None
    base, name = node.value.id, node.attr
    if (base == "subprocess" and name in SUBPROCESS_CALLS) or (
        base == "asyncio" and name in ASYNCIO_CALLS
    ) or (base == "os" and name in OS_CALLS) or (base == "pty" and name == "spawn"):
        return f"{base}.{name}"
    return None


def _spawns(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {"subprocess", "os", "asyncio", "pty"}:
            names = {alias.name for alias in node.names}
            spawning = names & (SUBPROCESS_CALLS | ASYNCIO_CALLS | OS_CALLS | {"spawn"})
            if node.module == "os":
                spawning &= OS_CALLS
            for name in sorted(spawning):
                found.append((node.lineno, f"from {node.module} import {name}"))
        spawned = _spawn_name(node)
        if spawned is not None:
            found.append((getattr(node, "lineno", 0), spawned))
    return found


def _uses_shell(tree: ast.AST) -> list[int]:
    """A spawn call given ``shell=`` anything but ``False``, or a shell API."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _spawn_name(node.func)
        if name in {"asyncio.create_subprocess_shell", "os.system", "os.popen"}:
            lines.append(node.lineno)
            continue
        if name is None:
            continue
        for keyword in node.keywords:
            if keyword.arg == "shell" and not (
                isinstance(keyword.value, ast.Constant) and keyword.value.value is False
            ):
                lines.append(node.lineno)
    return lines


def _scan() -> tuple[dict[str, list[tuple[int, str]]], dict[str, list[int]]]:
    spawning: dict[str, list[tuple[int, str]]] = {}
    shells: dict[str, list[int]] = {}
    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT.parent).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        sites = _spawns(tree)
        if sites:
            spawning[relative] = sites
        shell = _uses_shell(tree)
        if shell:
            shells[relative] = shell
    return spawning, shells


def test_every_process_spawning_module_is_reviewed() -> None:
    spawning, _ = _scan()
    unreviewed = {module: sites for module, sites in spawning.items() if module not in REVIEWED}
    assert unreviewed == {}, (
        "These modules start processes and are not in REVIEWED. Agent-chosen work must go "
        "through the native sandbox (sandbox.run_command / sandboxed_program); anything else "
        f"needs a category and a reason here: {unreviewed}"
    )


def test_the_reviewed_list_has_no_stale_entries() -> None:
    spawning, _ = _scan()
    stale = sorted(module for module in REVIEWED if module not in spawning)
    assert stale == [], f"Listed in REVIEWED but no longer start a process: {stale}"


def test_nothing_in_raiker_uses_a_shell() -> None:
    _, shells = _scan()
    assert shells == {}, f"A shell turns a string into commands; build an argv list instead: {shells}"


def test_every_entry_names_a_known_category_and_a_reason() -> None:
    categories = {SANDBOX, OWNED, LIFECYCLE, FACTS, OWNER}
    for module, (category, reason) in REVIEWED.items():
        assert category in categories, module
        assert len(reason) > 15, module


def test_the_scanner_finds_what_it_is_meant_to() -> None:
    """A scanner that finds nothing would make every assertion above free."""
    sample = ast.parse(
        "import subprocess, asyncio, os\n"
        "from subprocess import Popen\n"
        "subprocess.run(['x'])\n"
        "asyncio.create_subprocess_exec('x')\n"
        "os.execv('x', [])\n"
        "subprocess.run('x', shell=True)\n"
        "Request(shell=True)\n"
        "runner = subprocess.run\n"
    )
    kinds = {site for _line, site in _spawns(sample)}
    assert {"subprocess.run", "asyncio.create_subprocess_exec", "os.execv", "from subprocess import Popen"} <= kinds
    assert _uses_shell(sample) == [6]
