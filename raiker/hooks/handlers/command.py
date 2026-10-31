from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.hooks.contracts import HookHandler, HookInput, HookOutput

_MAX_OUTPUT_CHARS = 10_000


class CommandHookError(ValueError):
    pass


class CommandHookTimeout(TimeoutError):
    pass


def run_command(
    handler: HookHandler, hook_input: HookInput, workspace_root: str | Path
) -> HookOutput:
    """Refuse workspace hook code until the native broker supports controlled stdio."""
    raise CommandHookError("native_sandbox_required")


def _parse_output(stdout: str, stderr: str, returncode: int) -> HookOutput:
    text = (stdout or "")[:_MAX_OUTPUT_CHARS]
    decoded = _maybe_json(text)
    if isinstance(decoded, dict) and "decision" in decoded:
        return HookOutput(
            decision=str(decoded.get("decision", "no_decision")),
            decision_reason=_opt_str(decoded.get("decision_reason")),
            additional_context=_opt_str(decoded.get("additional_context")),
            metadata=decoded.get("metadata", {}) if isinstance(decoded.get("metadata"), dict) else {},
        )
    # No structured decision: use the exit-code convention (non-zero blocks the action).
    if returncode != 0:
        reason = (stderr or text or f"exit_{returncode}").strip()[:500]
        return HookOutput(decision="deny", decision_reason=reason)
    return HookOutput(decision="no_decision")


def _maybe_json(text: str) -> Any:
    snippet = text.strip()
    if not snippet:
        return None
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return None


def _opt_str(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None
