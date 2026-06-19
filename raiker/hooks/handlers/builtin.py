from __future__ import annotations

from collections.abc import Callable

from raiker.hooks.contracts import HookInput, HookOutput

BuiltinHandler = Callable[[HookInput], HookOutput]

_DESTRUCTIVE_MARKERS = ("rm -rf", "rm -fr", "mkfs", "dd if=", ":(){", "shutdown", "reboot")


def block_destructive_shell(hook_input: HookInput) -> HookOutput:
    """Deny obviously destructive shell commands. Trusted in-process handler."""

    if hook_input.tool_name != "shell":
        return HookOutput(decision="no_decision")
    command = str(hook_input.tool_input.get("command", "")).lower()
    if any(marker in command for marker in _DESTRUCTIVE_MARKERS):
        return HookOutput(
            decision="deny",
            decision_reason="destructive_command_blocked",
        )
    return HookOutput(decision="no_decision")


BUILTIN_HANDLERS: dict[str, BuiltinHandler] = {
    "block_destructive_shell": block_destructive_shell,
}


class BuiltinHookError(ValueError):
    pass


def run_builtin(name: str, hook_input: HookInput) -> HookOutput:
    handler = BUILTIN_HANDLERS.get(name)
    if handler is None:
        raise BuiltinHookError(f"unknown_builtin_handler:{name}")
    return handler(hook_input)
