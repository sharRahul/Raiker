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

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.execution.commands.backends.base import CommandBackendError
from raiker.execution.commands.models import CommandFeatures, CommandRequest
from raiker.execution.commands.process_lifetime import bind_to_runtime_lifetime
from raiker.execution.commands.runner import CommandSink, MemoryCommandSink, StreamingCommandRunner
from raiker.runtime.command_policy import (
    ALLOWED_SHELL_COMMANDS,
    CommandRejected,
    sandbox_environment,
    validate_command,
)

#: Workspace-relative paths a command may never read or write. `.raiker` holds
#: the runtime's own encrypted state; a command that could read it could read
#: every approval, receipt and credential reference Raiker has.
PROTECTED_DENY_PATHS = (".raiker",)

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

    @property
    def features(self) -> CommandFeatures:
        """Capabilities derived from measurements, never from configuration."""
        return CommandFeatures(
            shell=False,
            pty=False,
            background=False,
            input=False,
            process_tree_stop=self.observations.get("descendant_reaped") == ENFORCED,
            network_escalation=False,
            filtered_network=False,
            persistent_environment=False,
            persistent=False,
            restart_recovery=False,
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
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
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
            recorded = json.loads(manifest.read_text(encoding="utf-8")).get("sha256")
        except (OSError, ValueError):
            return None, "native_sandbox_runner_digest_missing"
        actual = hashlib.sha256(binary.read_bytes()).hexdigest()
        if recorded != actual:
            return None, "native_sandbox_runner_digest_mismatch"
        return binary, None

    # -- measuring the host -------------------------------------------------

    @staticmethod
    def _default_probe_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - argv is built from a verified binary path
            argv,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

    def probe(self) -> NativeSandboxProof:
        checked_at = utc_now()
        binary, reason = self.locate()
        if binary is None:
            return NativeSandboxProof(False, reason, "none", checked_at)
        try:
            completed = self._run_probe(
                [str(binary), "--probe", "--workspace", str(self.workspace_root)]
            )
        except (OSError, subprocess.SubprocessError):
            return NativeSandboxProof(False, "native_sandbox_probe_failed", "none", checked_at)
        try:
            report = json.loads(completed.stdout.strip() or "{}")
        except ValueError:
            return NativeSandboxProof(False, "native_sandbox_probe_failed", "none", checked_at)
        observations = {
            str(key): str(value) for key, value in dict(report.get("observations", {})).items()
        }
        available = bool(report.get("available"))
        # The headline row is egress. A host whose firewall service is stopped
        # measures `unenforced`; a host with no route measures `indeterminate`.
        # Neither is a sandbox, so neither is offered as one.
        if observations.get("egress") != ENFORCED:
            available = False
        return NativeSandboxProof(
            available=available,
            reason_code=(
                str(report.get("reason"))
                if report.get("reason")
                else (None if available else "native_sandbox_not_enforced")
            ),
            boundary=str(report.get("boundary") or "none"),
            checked_at=checked_at,
            observations=observations,
            connect_destination=(
                str(report["connect_destination"]) if report.get("connect_destination") else None
            ),
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
            "pty": False,
            "deadline_seconds": max(1, int(request.timeout_seconds) + 5),
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
        directory = request.workspace_root / ".raiker" / "command-policies"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{request.run_id}.json"

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
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.driver = driver
        self.proof = proof
        self.features = proof.features
        self._runner = runner or StreamingCommandRunner().start

    def start(self, request: CommandRequest, sink: CommandSink | None = None) -> Any:
        if not self.proof.available:
            raise CommandBackendError(self.proof.reason_code or "native_sandbox_unavailable")
        if request.shell:
            raise CommandBackendError("native_sandbox_shell_source_denied")
        if request.background:
            raise CommandBackendError("selected_environment_background_unsupported")
        if request.interactive:
            raise CommandBackendError("selected_environment_pty_unsupported")
        if request.network_policy_id:
            raise CommandBackendError("filtered_egress_windows_unsupported")
        if request.credential_bindings:
            raise CommandBackendError("selected_environment_credential_unsupported")

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

        policy_path = self.driver.policy_path(request)
        policy_path.write_text(
            json.dumps(self.driver.policy_document(request), indent=2), encoding="utf-8"
        )
        environment = sandbox_environment(workspace_root=request.workspace_root)
        executable = shutil.which(request.argv_template[0], path=environment.get("PATH"))
        if executable is None:
            # `portable_command`'s Windows shim rewrites `echo` and `cat` into
            # the interpreter Raiker itself runs on. That is right for the host
            # backend and wrong here: the interpreter lives outside the
            # boundary, so the container cannot load its libraries and the child
            # dies with a status code that names nothing. A shell builtin has no
            # program to run inside a sandbox, and saying so is the honest
            # answer.
            raise CommandBackendError("native_sandbox_executable_unreachable")
        argv = [
            str(binary),
            "--policy",
            str(policy_path),
            "--",
            executable,
            *request.argv_template[1:],
        ]
        process = self._runner(
            request,
            argv,
            request.workspace_root,
            environment,
            sink or MemoryCommandSink(),
            pty=False,
        )
        # The runner must not outlive Raiker. On Windows the kernel reaps it
        # through a job the runtime owns; on Linux the runner sets a parent-death
        # signal itself.
        bind_to_runtime_lifetime(getattr(getattr(process, "process", None), "pid", None))
        return process

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
