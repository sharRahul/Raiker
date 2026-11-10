"""The native OS sandbox backend.

Raiker decides *whether* a command may run — the capability gate, the approval
or standing grant, the argv policy, the constructed environment, and the
redaction of everything that comes back. None of that is an operating-system
boundary. `raiker-command-runner` is, and this module is how Python reaches it.

Two rules shape everything here.

**Nothing is claimed that was not measured.** :meth:`NativeSandboxDriver.probe`
runs the real boundary over the real workspace and reads back six observations,
each against a control arm taken outside the boundary. A `CommandFeatures` field
is only true when its observation said `enforced` — never because a profile said
so. An observation whose control arm failed is `indeterminate`, which is not
proof of anything and never turns a capability on.

**Nothing falls back.** A boundary that cannot be built is a named reason and a
refusal. Silently running the command on the host instead would be worse than
not offering the sandbox at all, because the receipt would still say it ran in
one.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.execution.commands.backends.base import CommandBackendError
from raiker.execution.commands.egress_runtime import (
    CommandEgressSettings,
    EgressRun,
    EgressSink,
)
from raiker.execution.commands.egress_runtime import load_settings as load_egress_settings
from raiker.execution.commands.home_toolchains import home_toolchain, with_path_entry
from raiker.execution.commands.models import CommandFeatures, CommandRequest
from raiker.execution.commands.process_lifetime import bind_to_runtime_lifetime
from raiker.execution.commands.runner import (
    CommandSink,
    MemoryCommandSink,
    StreamingCommandRunner,
    native_runner_process_factory,
)
from raiker.execution.commands.supervisor_client import (
    SupervisorUnavailable,
    spawn_supervised,
    supervisor_supported,
)
from raiker.execution.runner_publisher import runner_trust
from raiker.execution.workspaces import TaskWorkspaceRegistry, WorkspaceError
from raiker.runtime.command_policy import (
    ALLOWED_SHELL_COMMANDS,
    CommandRejected,
    sandbox_environment,
    validate_command,
)
from raiker.storage.internal_paths import internal_io_path

#: Workspace-relative paths a command may never read or write. `.raiker` holds
#: the runtime's own encrypted state; a command that could read it could read
#: every approval, receipt and credential reference Raiker has.
PROTECTED_DENY_PATHS = (".raiker",)
_ACCOUNT_BASE_TTL_SECONDS = 30.0
#: The boundary the runner reports for Raiker's WSL2 distribution.
WSL_BOUNDARY = "wsl_bubblewrap"
# Only known boundary-specific blockers may be surfaced from runner reports.
# Measured subsets cannot override these missing mandatory isolation controls.
ACTIONABLE_PROBE_REFUSALS = frozenset({
    ("restricted_account", "native_sandbox_account_profile_isolation_unavailable"),
})


#: Importing the distribution and installing Bubblewrap in it.
WSL_SETUP_TIMEOUT_SECONDS = 900


def _runner_error(stderr: str) -> str | None:
    """The reason code the runner names on stderr, if any."""
    for line in reversed(stderr.splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get("raiker_runner_error"), str):
            return str(value["raiker_runner_error"])[:120]
    return None


def _on_windows() -> bool:
    """One place the driver asks; tests stand in a Windows host here."""
    return sys.platform == "win32"
_ACCOUNT_BASE_CACHE: dict[str, tuple[float, Path | None]] = {}

#: Workspace-relative paths a command may read but never write. `.git` changes
#: only through the separately governed git executors. The known consequence:
#: most `git` subcommands want to write the index, so `git status` fails inside
#: the sandbox. That is the invariant working, not a defect.
PROTECTED_READONLY_PATHS = (".git",)

#: An observation whose control arm failed proves nothing. Only this value may
#: turn a capability on.
ENFORCED = "enforced"


@dataclass(frozen=True)
class NativeSandboxProof:
    """What this host was measured to enforce, and when."""

    available: bool
    reason_code: str | None
    boundary: str
    checked_at: str
    observations: Mapping[str, str] = field(default_factory=dict)
    connect_destination: str | None = None
    runner_trust: str = "development_unverified"

    @property
    def features(self) -> CommandFeatures:
        """Capabilities derived from measurements, never from configuration.

        Background and interactive runs need the whole process tree to stop
        when the run is stopped or Raiker exits. Bubblewrap measures that
        (`descendant_reaped`; its PID namespace dies with the runner), and so
        does the Windows restricted account (a kill-on-close Job Object owns
        the tree; runs in one copy may overlap, other copies wait). Only
        Every one of those offers a terminal: on Windows the account's runner
        builds a pseudo-console as the account and relays it, because
        `CreateProcessWithLogonW` cannot attach one directly. On macOS a
        pool of sandbox accounts serves runs, each account one run at a time,
        and the account owns every process its run starts, so the run's tree
        stops with it (`macos_account`) and runs in different copies overlap;
        plain Seatbelt cannot contain a detached descendant.
        """
        tree_stop = self.available and self.observations.get("descendant_reaped") == ENFORCED
        # WSL2 runs Bubblewrap in Raiker's distribution: the same tree stop,
        # and the Linux runner opens the terminal itself over `wsl.exe`'s pipes.
        terminal = tree_stop and self.boundary in {
            "bubblewrap",
            "macos_account",
            "restricted_account",
            "wsl_bubblewrap",
        }
        background = tree_stop and self.boundary in {
            "bubblewrap",
            "restricted_account",
            "macos_account",
            "wsl_bubblewrap",
        }
        # A background run outlives a restart where a detached supervisor runs
        # it (POSIX), downloads included: the supervisor holds the proxy.
        recovery = background and supervisor_supported()
        return CommandFeatures(
            shell=False,
            pty=terminal,
            background=background,
            input=terminal,
            process_tree_stop=tree_stop,
            network_escalation=False,
            filtered_network=False,
            persistent_environment=False,
            persistent=False,
            restart_recovery=recovery,
            recoverable=False,
            concurrent_runs=False,
            credential_delivery=False,
            credential_delta_quarantine=False,
        )

    def isolation_evidence(self) -> dict[str, Any]:
        return {
            "boundary": self.boundary,
            "probe_observations": dict(self.observations),
            "probe_checked_at": self.checked_at,
            "connect_destination": self.connect_destination,
            "runner_trust": self.runner_trust,
        }


def _platform_tag() -> str:
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    return f"{system}-{platform.machine().lower()}"


class NativeSandboxDriver:
    """Locate, verify, measure and drive the packaged runner."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        helper_root: Path | None = None,
        run_probe: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
        run_setup: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self._run_setup = run_setup or run_probe or self._default_setup_runner
        self.helper_root = (
            Path(helper_root).resolve()
            if helper_root is not None
            else Path(__file__).resolve().parents[3] / "native" / _platform_tag()
        )
        self._run_probe = run_probe or self._default_probe_runner

    # -- locating the runner ------------------------------------------------

    def runner_path(self) -> Path:
        name = "raiker-command-runner.exe" if sys.platform == "win32" else "raiker-command-runner"
        return self.helper_root / name

    def locate(self) -> tuple[Path | None, str | None]:
        """The runner, or the reason there isn't one.

        The digest recorded at build time is checked before the binary is used.
        It detects corruption and casual replacement; it is not protection
        against an attacker with write access to the install directory, who
        could replace Raiker itself.
        """
        binary = self.runner_path()
        manifest = self.helper_root / "digest.json"
        if not binary.is_file():
            return None, "native_sandbox_artifact_missing"
        if not manifest.is_file():
            return None, "native_sandbox_runner_digest_missing"
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or not isinstance(document.get("sha256"), str):
                return None, "native_sandbox_runner_digest_missing"
            recorded = document["sha256"]
            actual = hashlib.sha256(binary.read_bytes()).hexdigest()
        except (OSError, ValueError):
            return None, "native_sandbox_runner_digest_missing"
        if recorded != actual:
            return None, "native_sandbox_runner_digest_mismatch"
        return binary, None

    # -- measuring the host -------------------------------------------------

    @staticmethod
    def _default_probe_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
        # The probe is trusted infrastructure, but it launches a sandboxed
        # child. Do not pass host credentials or loader injection variables to
        # either process. Home/profile paths are needed for outside controls.
        allowed = (
            "PATH", "HOME", "USERPROFILE", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR",
            "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL",
        )
        environment = {name: os.environ[name] for name in allowed if name in os.environ}
        return subprocess.run(  # noqa: S603 - argv is built from a verified binary path
            argv,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

    @staticmethod
    def _default_setup_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
        # Importing a distribution and installing Bubblewrap in it can take
        # minutes; the probe's three-minute limit is too short for it.
        allowed = (
            "PATH", "HOME", "USERPROFILE", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR",
            "TMP", "TEMP", "LANG", "LC_ALL",
        )
        environment = {name: os.environ[name] for name in allowed if name in os.environ}
        return subprocess.run(  # noqa: S603 - argv is built from a verified binary path
            argv,
            env=environment,
            capture_output=True,
            text=True,
            timeout=WSL_SETUP_TIMEOUT_SECONDS,
            check=False,
        )

    def setup_wsl(self, rootfs: Path) -> tuple[bool, str]:
        """Import and configure Raiker's distribution with the bundled runner.

        Returns ``(True, "")`` or ``(False, reason)``. No elevation: WSL
        distributions belong to the user. The root filesystem must be a
        tarball the owner chose; Raiker never exports one of theirs.
        """
        if not _on_windows():
            return False, "native_sandbox_wsl_unavailable"
        binary, reason = self.locate()
        if binary is None:
            return False, reason or "native_sandbox_artifact_missing"
        linux_runner = self.wsl_runner()
        if linux_runner is None:
            return False, "native_sandbox_wsl_runner_missing"
        if not rootfs.is_file() or not rootfs.name.lower().endswith((".tar", ".tar.gz", ".tgz")):
            return False, "native_sandbox_wsl_rootfs_invalid"
        argv = [str(binary), "--setup-wsl", "--linux-runner", str(linux_runner), "--rootfs", str(rootfs)]
        return self._setup_outcome(argv)

    def reset_wsl(self) -> tuple[bool, str]:
        """Unregister Raiker's distribution, and every copy inside it."""
        if not _on_windows():
            return False, "native_sandbox_wsl_unavailable"
        binary, reason = self.locate()
        if binary is None:
            return False, reason or "native_sandbox_artifact_missing"
        return self._setup_outcome([str(binary), "--reset-wsl"])

    def _setup_outcome(self, argv: list[str]) -> tuple[bool, str]:
        try:
            completed = self._run_setup(argv)
        except subprocess.TimeoutExpired:
            return False, "native_sandbox_wsl_setup_timed_out"
        except (OSError, subprocess.SubprocessError):
            return False, "native_sandbox_wsl_setup_failed"
        # Status answers are cached briefly; this one just changed.
        for key in [key for key in _ACCOUNT_BASE_CACHE if key.startswith("wsl:")]:
            del _ACCOUNT_BASE_CACHE[key]
        if completed.returncode == 0:
            return True, ""
        return False, _runner_error(completed.stderr) or "native_sandbox_wsl_setup_failed"

    def uses_wsl(self) -> bool:
        """Whether the owner chose WSL2 for commands (Windows only)."""
        if not _on_windows():
            return False
        from raiker.execution.commands.sandbox_backend import load_windows_backend  # noqa: PLC0415

        return load_windows_backend(self.workspace_root) == "wsl"

    def probe(self, *, for_programs: bool = False) -> NativeSandboxProof:
        """Measure the boundary commands run in.

        With WSL2 chosen, commands run in Raiker's distribution, so that is
        what is measured. Hooks, MCP servers and plugin code run Windows
        interpreters and stay on the account: ``for_programs`` measures that.
        """
        checked_at = utc_now()
        boundary_flag = ["--boundary", "wsl"] if self.uses_wsl() and not for_programs else []
        binary, reason = self.locate()
        if binary is None:
            return NativeSandboxProof(False, reason, "none", checked_at)
        if boundary_flag:
            _, reason = self.wsl_execution_pin()
            if reason is not None:
                return NativeSandboxProof(False, reason, WSL_BOUNDARY, checked_at)
        try:
            # Windows probing grants ACLs and modifies protected DACLs. Probe a
            # private temporary directory and its own runner copy, never the
            # owner's project or the application's installation directory.
            with tempfile.TemporaryDirectory(prefix="raiker-native-probe-") as temporary:
                scratch = Path(temporary)
                isolated_binary = scratch / binary.name
                shutil.copy2(binary, isolated_binary)
                recorded = json.loads(
                    (self.helper_root / "digest.json").read_text(encoding="utf-8")
                )["sha256"]
                if hashlib.sha256(isolated_binary.read_bytes()).hexdigest() != recorded:
                    raise OSError("native_sandbox_runner_digest_mismatch")
                try:
                    completed = self._run_probe(
                        [str(isolated_binary), "--probe", "--workspace", str(scratch), *boundary_flag]
                    )
                finally:
                    if sys.platform == "win32":
                        cleanup = self._run_probe(
                            [str(isolated_binary), "--revoke-grant", "--workspace", str(scratch)]
                        )
                        if cleanup.returncode != 0:
                            raise OSError("native_sandbox_probe_cleanup_failed")
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            return NativeSandboxProof(False, "native_sandbox_probe_failed", "none", checked_at)
        try:
            report = json.loads(completed.stdout.strip() or "{}")
        except ValueError:
            return NativeSandboxProof(False, "native_sandbox_probe_failed", "none", checked_at)
        if (
            completed.returncode != 0
            or not isinstance(report, dict)
            or not isinstance(report.get("available"), bool)
            or not isinstance(report.get("observations"), dict)
        ):
            return NativeSandboxProof(False, "native_sandbox_probe_failed", "none", checked_at)
        observations = {
            str(key): str(value) for key, value in dict(report.get("observations", {})).items()
        }
        available = bool(report.get("available"))
        # A headline success cannot substitute for any mandatory observation.
        # An indeterminate control arm is not evidence of enforcement.
        required: tuple[str, ...] = (
            "relay",
            "workspace_write",
            "escape_write",
            "masked_read",
            "egress",
            "descendant_reaped",
        )
        if sys.platform.startswith("linux") or report.get("platform") == "linux":
            required += ("seccomp",)
        if report.get("boundary") == "restricted_account":
            # Windows Firewall does not filter loopback; the account's WFP
            # filter does, and a host set up before it has none. Such a host
            # refuses until the owner runs setup again.
            required += ("loopback",)
        if report.get("boundary") == "wsl_bubblewrap":
            # The Linux boundary, plus the one thing WSL adds: nothing in the
            # distribution may start a Windows program.
            required += ("seccomp", "windows_interop")
        # Availability is decided here, from the measurements alone. The
        # runner's own headline is always false: it cannot know that the
        # backend runs every command in a disposable task copy, which is what
        # keeps the owner's project out of reach. Every mandatory observation
        # must be enforced; an indeterminate control arm is not evidence.
        boundary = report.get("boundary")
        reason = report.get("reason")
        refusal = (
            reason
            if isinstance(boundary, str) and isinstance(reason, str)
            and (boundary, reason) in ACTIONABLE_PROBE_REFUSALS
            else None
        )
        available = refusal is None and all(observations.get(name) == ENFORCED for name in required)
        return NativeSandboxProof(
            available=available,
            reason_code=None if available else refusal or "native_sandbox_not_enforced",
            boundary=str(report.get("boundary") or "none"),
            checked_at=checked_at,
            observations=observations,
            connect_destination=(
                str(report["connect_destination"]) if report.get("connect_destination") else None
            ),
            # The package's digest beside the binary detects corruption but is
            # replaceable with it; only a platform signature by the publisher
            # pinned in Raiker's code is called publisher verification.
            runner_trust=runner_trust(binary),
        )

    # -- driving a command --------------------------------------------------

    def policy_document(self, request: CommandRequest) -> dict[str, Any]:
        return {
            "workspace_root": str(request.workspace_root),
            "cwd": str((request.workspace_root / request.cwd).resolve()),
            "profile_name": self.profile_name(request),
            "deny_paths": list(PROTECTED_DENY_PATHS),
            "readonly_paths": list(PROTECTED_READONLY_PATHS),
            "network": "none",
            "pty": request.interactive,
            "deadline_seconds": max(1, int(request.timeout_seconds) + 5),
            "max_cpu_seconds": max(1, int(request.timeout_seconds) + 5),
            "max_processes": 64,
            "max_memory_bytes": 2 * 1024 * 1024 * 1024,
        }

    @staticmethod
    def profile_name(request: CommandRequest) -> str:
        """One container per run.

        A predictable name is a hole: the container SID is a pure function of
        the name, so anything local could enter a container the workspace
        already trusts.
        """
        digest = hashlib.sha256(request.run_id.encode()).hexdigest()[:16]
        return f"raiker.cmd.{digest}"

    def policy_path(self, request: CommandRequest) -> Path:
        directory = internal_io_path(request.workspace_root / ".raiker" / "command-policies")
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{request.run_id}.json"

    def account_base(self) -> Path | None:
        """The sandbox account's copy base, when the owner has set it up.

        Windows: the restricted account (`C:\\RaikerSandbox`). macOS: the
        `_raikersandbox` account (`/Library/RaikerSandbox/copies`), whose
        ownership of every process a run starts is what stops detached
        descendants there.
        """
        if not (_on_windows() or sys.platform == "darwin"):
            return None
        binary, _ = self.locate()
        if binary is None:
            return None
        # Every turn and every file action asks; the answer changes only when
        # the owner runs the elevated setup, so a short-lived answer is enough.
        cached = _ACCOUNT_BASE_CACHE.get(str(binary))
        if cached is not None and time.monotonic() - cached[0] < _ACCOUNT_BASE_TTL_SECONDS:
            return cached[1]
        base = self._account_base_uncached(binary)
        _ACCOUNT_BASE_CACHE[str(binary)] = (time.monotonic(), base)
        return base

    def wsl_base(self) -> Path | None:
        """The copy base inside Raiker's WSL distribution, once it is set up."""
        if not _on_windows():
            return None
        binary, _ = self.locate()
        if binary is None:
            return None
        key = f"wsl:{binary}"
        cached = _ACCOUNT_BASE_CACHE.get(key)
        if cached is not None and time.monotonic() - cached[0] < _ACCOUNT_BASE_TTL_SECONDS:
            return cached[1]
        base = self._status_base([str(binary), "--wsl-status"])
        _ACCOUNT_BASE_CACHE[key] = (time.monotonic(), base)
        return base

    def copy_base(self) -> Path | None:
        """Where task copies for commands and file tools live.

        WSL2's distribution when the owner chose it, else the account's base
        (or None: copies then sit beside the workspace).
        """
        if self.uses_wsl():
            return self.wsl_base()
        return self.account_base()

    def wsl_runner(self) -> Path | None:
        """The static Linux runner shipped for WSL2, digest-checked.

        It sits beside the platform runner in ``raiker/native/wsl-x86_64/``;
        `--setup-wsl --linux-runner` installs it into Raiker's distribution.
        """
        directory = self.helper_root.parent / "wsl-x86_64"
        binary = directory / "raiker-command-runner"
        try:
            recorded = json.loads((directory / "digest.json").read_text(encoding="utf-8"))["sha256"]
            actual = hashlib.sha256(binary.read_bytes()).hexdigest()
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return binary if recorded == actual else None

    def wsl_status(self) -> dict[str, Any] | None:
        """`--wsl-status` as reported, or None off Windows or without a runner."""
        if not _on_windows():
            return None
        binary, _ = self.locate()
        if binary is None:
            return None
        try:
            completed = self._run_probe([str(binary), "--wsl-status"])
            status = json.loads(completed.stdout.strip() or "{}")
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        return status if isinstance(status, dict) else None

    def wsl_execution_pin(self) -> tuple[str | None, str | None]:
        """Require the installed distro runner to match the verified package.

        Called for both probing and every launch: cached enforcement evidence
        cannot license a changed/missing executable in the distribution.
        """
        runner = self.wsl_runner()
        if runner is None:
            return None, "native_sandbox_wsl_runner_missing"
        try:
            expected = hashlib.sha256(runner.read_bytes()).hexdigest()
        except OSError:
            return None, "native_sandbox_wsl_runner_missing"
        status = self.wsl_status()
        if status is None or status.get("configured") is not True:
            return None, "native_sandbox_wsl_unconfigured"
        if status.get("runner_sha256") != expected:
            return None, "native_sandbox_wsl_runner_mismatch"
        return expected, None

    def _status_base(self, argv: list[str]) -> Path | None:
        try:
            completed = self._run_probe(argv)
            status = json.loads(completed.stdout.strip() or "{}")
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0 or status.get("configured") is not True:
            return None
        base = status.get("base")
        return Path(base) if isinstance(base, str) and base else None

    def _account_base_uncached(self, binary: Path) -> Path | None:
        try:
            completed = self._run_probe([str(binary), "--account-status"])
            status = json.loads(completed.stdout.strip() or "{}")
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0 or status.get("configured") is not True:
            return None
        # Setup/credential readiness is separate from the account boundary's
        # ability to isolate a task. Older/macOS status contracts omit this
        # field; a Windows report that supplies it must explicitly permit use.
        if _on_windows() and "execution_available" in status and status["execution_available"] is not True:
            return None
        base = status.get("base")
        return Path(base) if isinstance(base, str) and base else None

    def revoke_workspace_grant(self) -> None:
        """Remove the workspace grant.

        The Windows boundary's filesystem grant is an ACE on the owner's own
        repository. It is durable and machine-wide, so environment reset and
        uninstall have to be able to take it back; otherwise it outlives Raiker.
        """
        binary, _ = self.locate()
        if binary is None:
            return
        subprocess.run(  # noqa: S603 - argv is built from a verified binary path
            [str(binary), "--revoke-grant", "--workspace", str(self.workspace_root)],
            capture_output=True,
            timeout=60,
            check=False,
        )


class NativeSandboxBackend:
    """`CommandBackend` over the packaged runner.

    `features` is a constructor argument, never a class attribute: a literal
    here would be a capability claim made before anything was measured, which is
    the failure this whole path exists to avoid.
    """

    def __init__(
        self,
        *,
        driver: NativeSandboxDriver,
        proof: NativeSandboxProof,
        workspaces: TaskWorkspaceRegistry | None = None,
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.driver = driver
        self.proof = proof
        # Without a registry there is no disposable copy, and the command would
        # write to the owner's project: refuse rather than run there.
        self.workspaces = workspaces
        self.features = proof.features
        self._runner = runner or StreamingCommandRunner(
            process_factory=native_runner_process_factory
        ).start

    def start(self, request: CommandRequest, sink: CommandSink | None = None) -> Any:
        if not self.proof.available:
            raise CommandBackendError(self.proof.reason_code or "native_sandbox_unavailable")
        if request.shell:
            raise CommandBackendError("native_sandbox_shell_source_denied")
        if request.background and not self.features.background:
            raise CommandBackendError("selected_environment_background_unsupported")
        if request.interactive and not self.features.pty:
            raise CommandBackendError("selected_environment_pty_unsupported")
        if request.network_policy_id:
            raise CommandBackendError("filtered_egress_windows_unsupported")
        if request.credential_bindings:
            raise CommandBackendError("selected_environment_credential_unsupported")
        if self.workspaces is None:
            raise CommandBackendError("native_disposable_workspace_required")
        wsl_pin = None
        if self.proof.boundary == WSL_BOUNDARY:
            wsl_pin, reason = self.driver.wsl_execution_pin()
            if reason is not None:
                raise CommandBackendError(reason)
        original = request
        request = self._in_task_copy(request)

        # The argv policy is applied here *and* the boundary is applied by the
        # runner. Two independent checks of the same rule is deliberate: neither
        # side is trusted to be the only one.
        try:
            validate_command(
                request.argv_template,
                workspace_root=request.workspace_root,
                allowlist=ALLOWED_SHELL_COMMANDS,
            )
        except CommandRejected as exc:
            raise CommandBackendError(exc.reason_code) from None

        binary, reason = self.driver.locate()
        if binary is None:
            raise CommandBackendError(reason or "native_sandbox_artifact_missing")

        environment = sandbox_environment(workspace_root=request.workspace_root)
        in_wsl = self.proof.boundary == WSL_BOUNDARY
        if in_wsl:
            # A Linux program, found on the distribution's PATH or relative to
            # the command's folder by the Linux runner. Nothing of Windows'
            # PATH applies inside the distribution.
            executable: str | None = request.argv_template[0]
        else:
            executable = command_executable(
                request.argv_template[0],
                cwd=request.workspace_root / request.cwd,
                search_path=environment.get("PATH", ""),
                project=original.workspace_root,
            )
        home_install = None
        if executable is None and not in_wsl:
            # rustup and nvm install into the owner's home, which is never
            # mounted; their own folders are, read-only, on governed terms.
            home_install = home_toolchain(
                request.argv_template[0], environment.get("PATH", "")
            )
            if home_install is not None:
                executable = home_install.executable
                environment.update(home_install.environment)
                with_path_entry(environment, home_install.path_entry)
        if executable is None:
            # `portable_command`'s Windows shim rewrites `echo` and `cat` into
            # the interpreter Raiker itself runs on. That is right for the host
            # backend and wrong here: the interpreter lives outside the
            # boundary, so the container cannot load its libraries and the child
            # dies with a status code that names nothing. A shell builtin has no
            # program to run inside a sandbox, and saying so is the honest
            # answer.
            raise CommandBackendError("native_sandbox_executable_unreachable")
        document = self.driver.policy_document(request)
        if wsl_pin is not None:
            document["wsl_runner_sha256"] = wsl_pin
        document["toolchain_paths"] = (
            [] if in_wsl else toolchain_mounts(executable, request.workspace_root)
        )
        if home_install is not None:
            document["toolchain_paths"] = [
                *document["toolchain_paths"],
                *(path for path in home_install.mounts if path not in document["toolchain_paths"]),
            ]
        # Downloads stay off in WSL: the proxy's socket is on Windows.
        egress_settings = None if in_wsl else self._egress_settings(original)
        # BUG-194 — a background run goes into a detached supervisor where the
        # platform has one, so a restart of Raiker reattaches to it instead of
        # reconciling it to `lost`. The supervisor runs the runner, so the
        # boundary is the same one, and it holds the run's download proxy, so
        # that survives the restart too.
        supervised = request.background and supervisor_supported()
        egress = (
            None
            if egress_settings is None or supervised
            else self._start_egress(original, egress_settings)
        )
        sink = sink or MemoryCommandSink()
        if egress is not None:
            document.update(egress.policy_fields)
            environment.update(egress.environment)
            sink = EgressSink(sink, egress)
        # The policy is Raiker state: it is written beside the original
        # workspace's own state, never into the copy the command can touch.
        policy_path = self.driver.policy_path(original)
        policy_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        argv = [
            str(binary),
            "--policy",
            str(policy_path),
            "--",
            executable,
            *request.argv_template[1:],
        ]
        if supervised:
            supervised_egress = (
                None
                if egress_settings is None
                else {
                    "run_id": original.run_id,
                    "owner_principal_id": original.owner_principal_id,
                    "domains": list(egress_settings.domains),
                }
            )
            try:
                return spawn_supervised(
                    workspace_root=original.workspace_root,
                    run_id=request.run_id,
                    argv=argv,
                    cwd=request.workspace_root,
                    environment=environment,
                    sink=sink,
                    deadline_seconds=request.timeout_seconds,
                    max_output_bytes=request.max_output_bytes,
                    pty=request.interactive,
                    egress=supervised_egress,
                    policy_path=policy_path,
                    policy=document,
                )
            except SupervisorUnavailable as exc:
                raise CommandBackendError(exc.reason_code) from None
        try:
            process = self._runner(
                request,
                argv,
                request.workspace_root,
                environment,
                sink,
                pty=request.interactive,
            )
        except BaseException:
            if egress is not None:
                egress.close()
            raise
        # The runner must not outlive Raiker. On Windows the kernel reaps it
        # through a job the runtime owns; on Linux the runner sets a parent-death
        # signal itself.
        bind_to_runtime_lifetime(getattr(getattr(process, "process", None), "pid", None))
        return process

    def _egress_settings(self, request: CommandRequest) -> CommandEgressSettings | None:
        """The owner's download allow-list, when it is on and can be enforced.

        Only where the boundary can make the proxy the single route: on Windows
        that is the restricted account (an AppContainer cannot reach loopback
        without an elevated exemption), so without it the run keeps no network
        rather than failing.
        """
        settings = load_egress_settings(request.workspace_root)
        if not settings.enabled:
            return None
        if sys.platform == "win32" and self.driver.account_base() is None:
            return None
        return settings

    def _start_egress(
        self, request: CommandRequest, settings: CommandEgressSettings
    ) -> EgressRun:
        """This run's proxy, in Raiker's process (a run with no supervisor)."""
        try:
            return EgressRun(request.run_id, request.owner_principal_id, settings).start(
                request.timeout_seconds + 5
            )
        except OSError as exc:
            # Every port the loopback filter permits is taken: refuse by name
            # rather than run with a proxy the sandbox could not reach.
            raise CommandBackendError("command_egress_port_unavailable") from exc

    def _in_task_copy(self, request: CommandRequest) -> CommandRequest:
        """The same request, rooted in this session's disposable copy.

        The copy is the session's task tree: the project root a project turn
        bound, which the agent's file edits use too, so a command sees every
        edit made before it. Without a binding it holds only the command's
        working directory. Its parent folders, siblings, `.git` and `.raiker`
        are not in it at all.
        """
        assert self.workspaces is not None
        root = request.workspace_root.resolve()
        cwd = (root / request.cwd).resolve()
        if cwd != root and root not in cwd.parents:
            raise CommandBackendError("command_cwd_outside_workspace")
        owner, session = request.owner_principal_id, request.session_id
        try:
            _, workspace = self.workspaces.acquire(
                owner, session, self.workspaces.scope_for(owner, session, cwd)
            )
        except WorkspaceError as exc:
            raise CommandBackendError(exc.reason_code) from None
        inside = cwd.relative_to(workspace.source.resolve()).as_posix() or "."
        if not (workspace.root / inside).is_dir():
            raise CommandBackendError("command_cwd_not_a_directory")
        return dataclasses.replace(request, workspace_root=workspace.root, cwd=inside)

    def isolation_evidence(self, request: CommandRequest) -> dict[str, Any]:
        """What this run's boundary actually was, separate from host readiness.

        A probe observation is evidence about the *host*, taken earlier by a
        different process. It does not license a claim about this command. The
        two are recorded side by side and the interface states them as two
        sentences, not one.
        """
        evidence = self.proof.isolation_evidence()
        evidence["boundary_constructed"] = {
            "profile_name": self.driver.profile_name(request),
            "network_capability": False,
            "deny_paths": list(PROTECTED_DENY_PATHS),
            "readonly_paths": list(PROTECTED_READONLY_PATHS),
            "runner_digest": _runner_digest(self.driver),
            "workspace": "disposable_task_copy",
        }
        return evidence


def _runner_digest(driver: NativeSandboxDriver) -> str | None:
    binary, _ = driver.locate()
    if binary is None:
        return None
    return hashlib.sha256(binary.read_bytes()).hexdigest()


def native_sandbox_supported() -> bool:
    """Whether this platform has a boundary implementation at all."""
    if sys.platform in {"win32", "darwin"}:
        return True
    return shutil.which("bwrap") is not None


def task_workspace_registry(
    workspace_root: str | Path, driver: NativeSandboxDriver | None = None
) -> TaskWorkspaceRegistry:
    """The registry commands and the review API share.

    On Windows with the restricted account set up, copies live under its base
    (the only place that account may write); records stay in Raiker's state.
    """
    base = (driver or NativeSandboxDriver(workspace_root)).copy_base()
    return TaskWorkspaceRegistry.for_workspace(workspace_root, base=base)



# ── One-shot sandboxed programs (command hooks) ──────────────────────────────

#: Hooks fire on every tool call. Probing the host each time would cost more
#: than most hooks take, so a hook reuses a measurement this recent; commands
#: keep probing per run, because their receipts state what was measured.
_HOOK_PROOF_TTL_SECONDS = 30.0
def command_executable(name: str, *, cwd: Path, search_path: str, project: Path) -> str | None:
    """The program a sandboxed command names, as the sandbox will find it.

    A name with a separator is the copy's own (`.venv/bin/python`), so it is
    looked up from the command's folder in the copy, not from Raiker's. A bare
    name is the first on the path the sandbox can reach: never in the project
    or the owner's home, and on Windows only on the system drive.
    """
    from raiker.execution.commands.sandboxed_program import sandbox_interpreter

    if "/" in name or "\\" in name:
        candidate = cwd / name
        for option in (candidate, candidate.with_name(candidate.name + ".exe")):
            if option.is_file():
                return str(option)
        return None
    try:
        return str(sandbox_interpreter(name, search_path, project.resolve()))
    except FileNotFoundError:
        return None


#: Interpreters whose install prefix is mounted read-only when it lives
#: outside `/usr`: a hosted runner's Python, a pyenv or nvm install. Nothing
#: else is: a tool's prefix in the owner's home can hold its credentials
#: (`~/.cargo/credentials.toml`), so it needs a governed mount of its own.
TOOLCHAIN_INTERPRETERS = frozenset({"python", "python3", "pip", "pip3", "node", "npm", "npx"})


#: An interpreter's own file name, versioned or not (`python3.12`, `node`).
_INTERPRETER_NAME = re.compile(r"(python|pip|node|npm|npx)(\d+(\.\d+)*)?")

#: Never mounted, whatever links point there: every user's home, not only the
#: owner's, and root's.
_HOME_ROOTS = (Path("/home"), Path("/root"))


def toolchain_mounts(executable: str | Path, workspace_root: Path) -> list[str]:
    """Install prefixes the Linux boundary must mount for *executable* to run.

    `/usr` is always mounted, so an interpreter there needs nothing. One in
    `/usr/local`, `/opt` or another system folder needs its prefix (the folder
    above its `bin`), read-only, both as found on the path and after resolving
    links. Both names must be an interpreter's, and no prefix is ever in a
    home folder, holding the project, or inside it.

    The link is the reason for the last rules: a command can make a link in
    its own copy (`.venv/bin/python` to `~/notes/bin/python`), and the prefix
    of its target would otherwise be mounted into the very sandbox that keeps
    the owner's home out of reach.
    """
    if not sys.platform.startswith("linux"):
        return []
    path = Path(executable)
    if path.name not in TOOLCHAIN_INTERPRETERS:
        return []
    homes = (Path.home().resolve(), *_HOME_ROOTS)
    root = workspace_root.resolve()
    usr, local = Path("/usr"), Path("/usr/local")
    mounts: list[str] = []
    for candidate in (path.absolute(), path.resolve()):
        if candidate.parent.name != "bin" or not _INTERPRETER_NAME.fullmatch(candidate.name):
            continue
        prefix = candidate.parent.parent
        if root == prefix or root in prefix.parents:
            continue  # the copy's own, already in the sandbox
        if prefix in root.parents:
            return []  # would hold the project
        if prefix == usr or (usr in prefix.parents and local not in (prefix, *prefix.parents)):
            continue
        if len(prefix.parts) < 3 or any(
            prefix == home or home in prefix.parents or prefix in home.parents for home in homes
        ):
            return []  # a home folder, or something holding one: never mounted
        if str(prefix) not in mounts:
            mounts.append(str(prefix))
    return mounts


_HOOK_PROOFS: dict[str, tuple[float, NativeSandboxProof]] = {}


def _recent_proof(driver: NativeSandboxDriver, workspace_root: Path) -> NativeSandboxProof:
    key = str(workspace_root)
    cached = _HOOK_PROOFS.get(key)
    if cached is not None and time.monotonic() - cached[0] < _HOOK_PROOF_TTL_SECONDS:
        return cached[1]
    proof = driver.probe(for_programs=True)
    _HOOK_PROOFS[key] = (time.monotonic(), proof)
    return proof


class ScratchRun:
    """A throwaway folder under the copy base, and the runner argv for it.

    The caller fills :attr:`folder` with what the program may see, then asks
    for :meth:`command`. Nothing else of the project is in reach, and there is
    no network. The folder and its policy are removed when the context ends.
    """

    def __init__(self, root: Path, binary: Path, folder: Path, label: str, memory_bytes: int,
                 timeout_seconds: float) -> None:
        self.folder = folder
        self._root = root
        self._binary = binary
        self._label = label
        self._memory_bytes = memory_bytes
        self._deadline = max(1, int(timeout_seconds) + 5)
        self._policies: list[Path] = []

    def command(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        read_only: tuple[Path, ...] = (),
        max_processes: int = 64,
    ) -> list[str]:
        """Write this run's policy and return the runner argv for *argv*.

        *read_only* folders outside the copy are mounted read-only (Linux), for
        a caller that must hand the program large inputs it may not change.
        """
        directory = (cwd or self.folder).resolve()
        if directory != self.folder.resolve() and self.folder.resolve() not in directory.parents:
            raise CommandBackendError("sandbox_cwd_outside_folder")
        document = {
            "workspace_root": str(self.folder),
            "cwd": str(directory),
            "profile_name": f"raiker.{self._label}.{hashlib.sha256(self.folder.name.encode()).hexdigest()[:16]}",
            "deny_paths": list(PROTECTED_DENY_PATHS),
            "readonly_paths": list(PROTECTED_READONLY_PATHS),
            "network": "none",
            "pty": False,
            "deadline_seconds": self._deadline,
            "max_cpu_seconds": self._deadline,
            "max_processes": max_processes,
            "max_memory_bytes": self._memory_bytes,
            "toolchain_paths": [
                *(toolchain_mounts(argv[0], self.folder) if argv else []),
                *(str(path) for path in read_only),
            ],
        }
        policies = internal_io_path(self._root / ".raiker" / "command-policies")
        policies.mkdir(parents=True, exist_ok=True)
        policy_path = policies / f"{self.folder.name}-{len(self._policies)}.json"
        policy_path.write_text(json.dumps(document), encoding="utf-8")
        self._policies.append(policy_path)
        return [str(self._binary), "--policy", str(policy_path), "--", *argv]

    def environment(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        """The constructed environment, with HOME and the work folder in here."""
        return sandbox_environment(workspace_root=self.folder, extra=dict(extra or {}))

    def close(self) -> None:
        for policy in self._policies:
            with contextlib.suppress(OSError):
                policy.unlink()
        shutil.rmtree(self.folder, ignore_errors=True)


@contextlib.contextmanager
def scratch_run(
    workspace_root: str | Path,
    label: str,
    *,
    timeout_seconds: float,
    memory_bytes: int = 512 * 1024 * 1024,
) -> Iterator[ScratchRun]:
    """A :class:`ScratchRun` for one sandboxed program, removed afterwards.

    Raises :class:`CommandBackendError` when the host's boundary is not
    enforced, so the caller refuses rather than run the program on the host.
    """
    root = Path(workspace_root).resolve()
    driver = NativeSandboxDriver(root)
    proof = _recent_proof(driver, root)
    if not proof.available:
        raise CommandBackendError(proof.reason_code or "native_sandbox_unavailable")
    binary, reason = driver.locate()
    if binary is None:
        raise CommandBackendError(reason or "native_sandbox_artifact_missing")
    # Programs run Windows interpreters, so never in the WSL distribution.
    base = driver.account_base() or TaskWorkspaceRegistry.for_workspace(root).base
    base.mkdir(parents=True, exist_ok=True)
    folder = base / f"{label}_{secrets.token_hex(8)}"
    folder.mkdir()
    run = ScratchRun(root, binary, folder, label, memory_bytes, timeout_seconds)
    try:
        yield run
    finally:
        run.close()


def run_sandboxed_program(
    workspace_root: str | Path,
    program: Path,
    args: list[str],
    *,
    stdin: str,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    """Run one workspace program in the native boundary, fed *stdin*.

    The program is copied alone into a throwaway folder under the copy base and
    runs there with no network: it sees the event it was handed and itself,
    never the project or Raiker's state. The folder is removed afterwards.
    Raises :class:`CommandBackendError` when the host's boundary is not
    enforced, so a hook is refused rather than run on the host.
    """
    with scratch_run(workspace_root, "hook", timeout_seconds=timeout_seconds) as run:
        copied = run.folder / program.name
        shutil.copyfile(program, copied)
        copied.chmod(0o755)
        return subprocess.run(
            run.command([str(copied), *args]),
            input=stdin,
            capture_output=True,
            text=True,
            env=run.environment(),
            timeout=timeout_seconds,
            check=False,
        )
