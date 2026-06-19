from __future__ import annotations

import fnmatch
import re


def matches(pattern: str, value: str | None) -> bool:
    """Match a hook matcher pattern against a tool/event value.

    Supported forms (per docs/HOOKS_SPEC.md):
    - ``*``            matches anything;
    - ``re:<regex>``   regular expression (explicitly marked);
    - ``a|b|c``        pipe-separated exact alternatives;
    - ``exact``        exact string match.
    """

    if pattern == "*":
        return True
    if value is None:
        return False
    if pattern.startswith("re:"):
        try:
            return re.search(pattern[3:], value) is not None
        except re.error:
            return False
    if "|" in pattern:
        return value in {part.strip() for part in pattern.split("|")}
    return pattern == value


def guard_matches(if_guard: str | None, tool_name: str | None, tool_input: dict[str, object]) -> bool:
    """Evaluate an optional ``if`` guard such as ``shell(rm -rf *)``.

    The guard fires only when the tool matches and a glob over the flattened arguments matches.
    A malformed guard fails closed (does not match), so it cannot accidentally widen a rule.
    """

    if if_guard is None:
        return True
    open_paren = if_guard.find("(")
    if not if_guard.endswith(")") or open_paren == -1:
        return False
    guard_tool = if_guard[:open_paren].strip()
    arg_pattern = if_guard[open_paren + 1 : -1].strip()
    if guard_tool and guard_tool != tool_name:
        return False
    flattened = " ".join(str(value) for value in tool_input.values())
    return fnmatch.fnmatch(flattened, arg_pattern) or arg_pattern in flattened
