"""Review a server's advertised tool list against the design rules.

Every MCP server ends up needing the same audit: are the descriptions written
for an agent, are the schemas narrow enough to prevent bad calls, are list
responses bounded. Doing it by eye means it happens once, before the tool count
grows. This does it from the server's own ``tools/list`` output, so it stays
true as the server changes.

Feed it the JSON array of tool definitions — from an MCP inspector, from
``tools/list``, or dumped from the server in-process:

    python review_tools.py tools.json

Findings are advisory. They flag the shapes that reliably go wrong; a flagged
tool can still be correct, and the script says why it was flagged so you can
judge rather than obey.
"""

from __future__ import annotations

import json
import sys
from typing import Any

# Names that describe the transport rather than the user's intent. An agent
# choosing between `get` and `post` is choosing by HTTP verb, which is not
# information it has.
VAGUE_NAMES = frozenset(
    {"get", "post", "put", "patch", "delete", "call", "run", "execute", "query", "request",
     "api", "api_call", "handler", "invoke", "do", "fetch", "send", "process"}
)

# A list-shaped tool without one of these has no way to bound its response.
BOUNDING_PARAMS = frozenset({"limit", "per_page", "page_size", "max_results", "count", "top"})

MIN_DESCRIPTION_CHARS = 80
CROWDED_TOOL_COUNT = 15


def _finding(tool: str, rule: str, detail: str) -> dict[str, str]:
    return {"tool": tool, "rule": rule, "detail": detail}


def review_tool(tool: dict[str, Any]) -> list[dict[str, str]]:
    """Findings for one tool definition."""
    name = str(tool.get("name", "<unnamed>"))
    description = str(tool.get("description") or "")
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    properties: dict[str, Any] = dict(schema.get("properties") or {})
    required = set(schema.get("required") or [])
    findings: list[dict[str, str]] = []

    if name.lower() in VAGUE_NAMES or any(
        part in VAGUE_NAMES for part in name.lower().split("_")[:1]
    ):
        findings.append(_finding(
            name, "name_describes_transport",
            "Name reads as an HTTP verb rather than an intent. An agent picks by intent "
            "(`search_issues`), not by method.",
        ))

    if not description.strip():
        findings.append(_finding(
            name, "no_description",
            "No description. This is the only documentation the agent ever reads.",
        ))
    elif len(description) < MIN_DESCRIPTION_CHARS:
        findings.append(_finding(
            name, "description_too_thin",
            f"{len(description)} chars. Say what it does, when to use it and when not to, "
            "and what it returns.",
        ))
    elif " use " not in description.lower() and "when" not in description.lower():
        findings.append(_finding(
            name, "description_omits_when_to_use",
            "Describes what it does but never when to reach for it, so the agent has to "
            "guess between this and its neighbours.",
        ))

    for param, spec in properties.items():
        if not isinstance(spec, dict):
            continue
        if not str(spec.get("description") or "").strip() and param not in required:
            findings.append(_finding(
                name, "optional_param_undocumented",
                f"`{param}` is optional and undescribed, so it will rarely be used correctly.",
            ))
        # A free string where the domain is a fixed set is a category of bad
        # call the schema could have made impossible.
        if spec.get("type") == "string" and not (spec.get("enum") or spec.get("format")):
            hint = str(spec.get("description") or "").lower()
            if any(word in f"{param} {hint}" for word in ("state", "status", "type", "kind", "mode")):
                findings.append(_finding(
                    name, "enum_candidate",
                    f"`{param}` looks like a fixed set but is a free string. An enum removes "
                    "a whole class of invalid call.",
                ))

    looks_like_list = any(
        word in name.lower() for word in ("list", "search", "find", "query", "all")
    )
    if looks_like_list and not (BOUNDING_PARAMS & set(properties)):
        findings.append(_finding(
            name, "unbounded_list_response",
            "List-shaped tool with no limit/page-size parameter. Fine on three records, "
            "drowns the context window on real data.",
        ))

    return findings


def review(tools: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Findings across the whole tool set."""
    findings: list[dict[str, str]] = []
    if len(tools) > CROWDED_TOOL_COUNT:
        findings.append(_finding(
            "<server>", "too_many_tools",
            f"{len(tools)} tools. Past roughly {CROWDED_TOOL_COUNT} the agent starts picking "
            "the wrong one. Collapse endpoints that are always called together onto intents.",
        ))
    for tool in tools:
        findings.extend(review_tool(tool))
    return findings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
    tools = payload["tools"] if isinstance(payload, dict) else payload
    findings = review(tools)
    if not findings:
        print(f"{len(tools)} tools reviewed, nothing flagged.")
        return 0
    for finding in findings:
        print(f"{finding['tool']}: {finding['rule']}\n    {finding['detail']}")
    print(f"\n{len(findings)} finding(s) across {len(tools)} tool(s). Advisory, not verdicts.")
    return 1


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Self-check: a deliberately bad tool must be flagged, a good one must not.
        bad = review_tool({
            "name": "get",
            "description": "Gets stuff.",
            "inputSchema": {"properties": {"state": {"type": "string"}}, "required": []},
        })
        assert {f["rule"] for f in bad} >= {
            "name_describes_transport", "description_too_thin", "enum_candidate",
        }, bad
        good = review_tool({
            "name": "search_issues",
            "description": (
                "Search Acme issues by full-text query. Use this to find issues by words in "
                "the title or body; to fetch an issue you already have the id for, use "
                "get_issue instead. Returns at most `limit` matches with id, title, and state."
            ),
            "inputSchema": {
                "properties": {
                    "query": {"type": "string", "description": "Words to match"},
                    "state": {"type": "string", "enum": ["open", "closed"], "description": "Filter"},
                    "limit": {"type": "integer", "description": "Max matches"},
                },
                "required": ["query"],
            },
        })
        assert good == [], good
        print("review_tools self-test passed")
        raise SystemExit(0)
    raise SystemExit(main(sys.argv))
