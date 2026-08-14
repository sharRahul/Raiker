from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from raiker.execution.commands.models import CommandRequest


@dataclass(frozen=True)
class NativeSandboxPolicy:
    network: str
    protected_paths: tuple[str, ...]
    git_write: bool
    outside_workspace_write: bool


@dataclass(frozen=True)
class NativeSandboxProof:
    available: bool
    reason_code: str | None


class NativeSandboxDriver:
    def __init__(self, platform: str, *, helper_root: Path) -> None:
        self.platform = platform
        self.helper_root = helper_root.resolve()

    def policy(self, request: CommandRequest) -> NativeSandboxPolicy:
        del request
        return NativeSandboxPolicy(
            network="none",
            protected_paths=(".raiker", ".git"),
            git_write=False,
            outside_workspace_write=False,
        )

    def command(self, request: CommandRequest, argv: list[str]) -> list[str]:
        workspace = str(request.workspace_root)
        if self.platform == "linux":
            return [
                shutil.which("bwrap") or "bwrap",
                "--unshare-all",
                "--die-with-parent",
                "--bind",
                workspace,
                workspace,
                "--ro-bind",
                str(request.workspace_root / ".git"),
                str(request.workspace_root / ".git"),
                "--tmpfs",
                str(request.workspace_root / ".raiker"),
                "--chdir",
                str(request.workspace_root / request.cwd),
                "--",
                *argv,
            ]
        if self.platform == "darwin":
            profile = self.helper_root / "raiker-command.sb"
            return ["sandbox-exec", "-f", str(profile), *argv]
        if self.platform == "win32":
            return [str(self.helper_root / "raiker-command-runner.exe"), "--", *argv]
        raise ValueError("native_sandbox_platform_unsupported")

    def probe(self, workspace_root: Path) -> NativeSandboxProof:
        del workspace_root
        if self.platform == "linux":
            available = shutil.which("bwrap") is not None
        elif self.platform == "darwin":
            available = shutil.which("sandbox-exec") is not None
        elif self.platform == "win32":
            available = (self.helper_root / "raiker-command-runner.exe").is_file()
        else:
            return NativeSandboxProof(False, "native_sandbox_platform_unsupported")
        return NativeSandboxProof(
            available,
            None if available else "native_sandbox_artifact_missing",
        )
