from __future__ import annotations

from collections.abc import Callable
from typing import Any

from raiker.execution.commands.backends.base import CommandBackendError
from raiker.execution.commands.models import CommandFeatures, CommandRequest
from raiker.execution.commands.runner import (
    CommandSink,
    MemoryCommandSink,
    StreamingCommandRunner,
    pty_supported,
)
from raiker.runtime.command_policy import (
    ALLOWED_SHELL_COMMANDS,
    CommandRejected,
    portable_command,
    sandbox_environment,
    validate_command,
)


class LocalStrictBackend:
    # BUG-194 — background and PTY are now measured properties of the platform
    # rather than blanket refusals. `background` is a lifecycle the service owns
    # (a lease, a supervisor that dies with Raiker, and a durable run row), and
    # costs this backend nothing extra: the runner has always been asynchronous,
    # what was missing was somewhere to observe it from. `pty` is only claimed
    # where `openpty` exists, which is why it is read from the platform probe.
    features = CommandFeatures(
        shell=False,
        concurrent_runs=True,
        background=True,
        pty=pty_supported(),
        input=pty_supported(),
    )

    def __init__(self, *, runner: Callable[..., Any] | None = None) -> None:
        self._runner = runner or StreamingCommandRunner().start

    def start(self, request: CommandRequest, sink: CommandSink | None = None) -> Any:
        if request.shell:
            raise CommandBackendError("local_strict_shell_source_denied")
        if request.interactive and not pty_supported():
            raise CommandBackendError("command_pty_platform_unsupported")
        if request.network_policy_id:
            raise CommandBackendError("selected_environment_network_unsupported")
        if request.credential_bindings:
            raise CommandBackendError("selected_environment_credential_unsupported")
        try:
            validate_command(
                request.argv_template,
                workspace_root=request.workspace_root,
                allowlist=ALLOWED_SHELL_COMMANDS,
            )
        except CommandRejected as exc:
            raise CommandBackendError(exc.reason_code) from None
        cwd = (request.workspace_root / request.cwd).resolve()
        environment = sandbox_environment(workspace_root=request.workspace_root)
        return self._runner(
            request,
            list(portable_command(request.argv_template)),
            cwd,
            environment,
            sink or MemoryCommandSink(),
            pty=request.interactive,
        )
