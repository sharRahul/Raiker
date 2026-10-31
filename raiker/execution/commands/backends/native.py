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

import dataclasses
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.execution.commands.backends.base import CommandBackendError
from raiker.execution.commands.models import CommandFeatures, CommandRequest
from raiker.execution.commands.process_lifetime import bind_to_runtime_lifetime
from raiker.execution.commands.runner import CommandSink, MemoryCommandSink, StreamingCommandRunner
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

    def probe(self) -> NativeSandboxProof:
        checked_at = utc_now()
        binary, reason = self.locate()
        if binary is None:
            return NativeSandboxProof(False, reason, "none", checked_at)
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
                        [str(isolated_binary), "--probe", "--workspace", str(scratch)]
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
        # Availability is decided here, from the measurements alone. The
        # runner's own headline is always false: it cannot know that the
        # backend runs every command in a disposable task copy, which is what
        # keeps the owner's project out of reach. Every mandatory observation
        # must be enforced; an indeterminate control arm is not evidence.
        available = all(observations.get(name) == ENFORCED for name in required)
        return NativeSandboxProof(
            available=available,
            reason_code=None if available else "native_sandbox_not_enforced",
            boundary=str(report.get("boundary") or "none"),
            checked_at=checked_at,
            observations=observations,
            connect_destination=(
                str(report["connect_destination"]) if report.get("connect_destination") else None
            ),
            # The current package stores the digest beside the binary. It
            # detects corruption but is replaceable with the binary and is
            # therefore never called publisher verification.
            runner_trust="package_relative_integrity",
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
        if self.workspaces is None:
            raise CommandBackendError("native_disposable_workspace_required")
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

        # The policy is Raiker state: it is written beside the original
        # workspace's own state, never into the copy the command can touch.
        policy_path = self.driver.policy_path(original)
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

    def _in_task_copy(self, request: CommandRequest) -> CommandRequest:
        """The same request, rooted in this session's disposable copy.

        The copy holds only the command's working directory, the least of the
        project it needs; its parent folders, siblings, `.git` and `.raiker`
        are not in it at all.
        """
        assert self.workspaces is not None
        root = request.workspace_root.resolve()
        scope = (root / request.cwd).resolve()
        if scope != root and root not in scope.parents:
            raise CommandBackendError("command_cwd_outside_workspace")
        try:
            _, workspace = self.workspaces.acquire(
                request.owner_principal_id, request.session_id, scope
            )
        except WorkspaceError as exc:
            raise CommandBackendError(exc.reason_code) from None
        return dataclasses.replace(request, workspace_root=workspace.root, cwd=".")

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
