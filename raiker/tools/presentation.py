"""What a tool call may say about itself in a transcript (BUG-206 slice B).

The durable event log is the full record of a call: the tool, its redacted
arguments, its result metadata, and the policy decision behind it. The
transcript is the *summary* — one line per call, read while the turn is still
running — and this module is the only place that decides what that line says.

Three rules, and they are the reason this is server-side rather than assembled
in the client from raw arguments:

1. **The label is the owner's language, never the identifier.** ``read_file``
   is "Read file". A transcript that prints tool identifiers is a log, not a
   conversation.
2. **The action names the object, and comes only from arguments the durable
   event already keeps verbatim.** Where ``_event_safe_arguments`` drops a
   tool's argument *values* — the advisor's question, a projected MCP tool's
   input — the row carries no argument-derived phrase either. The transcript
   can never be the looser of the two surfaces.
3. **Two arguments are narrowed further than the event narrows them.** A URL is
   reduced to its host, because a query string carries session tokens in a
   position pattern-based redaction does not recognise; a command is reduced to
   its program name, because an argument can be a credential. Both are kept in
   full in the event, where they are governance evidence rather than something
   an over-the-shoulder reader sees.

Everything that does reach a phrase is passed through :func:`redact_text`
first, so the same secret shapes that never enter an event never enter a row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from raiker.context.redaction import redact_text
from raiker.tools.mcp_tools import parse_mcp_tool_name

# The icon families the client draws one glyph for. `tool` is the neutral
# fallback: an unrecognised tool renders as a tool rather than as nothing, which
# is the whole point of having a fallback at all.
FAMILY_FILE_READ = "file-read"
FAMILY_FILE_WRITE = "file-write"
FAMILY_SHELL = "shell"
FAMILY_WEB = "web"
FAMILY_REPOSITORY = "repository"
FAMILY_CONNECTOR = "connector"
FAMILY_MEMORY = "memory"
FAMILY_SUBAGENT = "subagent"
FAMILY_PLAN = "plan"
FAMILY_TOOL = "tool"

TOOL_FAMILIES: tuple[str, ...] = (
    FAMILY_FILE_READ,
    FAMILY_FILE_WRITE,
    FAMILY_SHELL,
    FAMILY_WEB,
    FAMILY_REPOSITORY,
    FAMILY_CONNECTOR,
    FAMILY_MEMORY,
    FAMILY_SUBAGENT,
    FAMILY_PLAN,
    FAMILY_TOOL,
)

_FAMILY_BY_TOOL: dict[str, str] = {
    # Reading the workspace.
    "read_file": FAMILY_FILE_READ,
    "list_directory": FAMILY_FILE_READ,
    "glob": FAMILY_FILE_READ,
    "grep": FAMILY_FILE_READ,
    "stat_path": FAMILY_FILE_READ,
    "diff_files": FAMILY_FILE_READ,
    "skill_load": FAMILY_FILE_READ,
    "vector_get": FAMILY_FILE_READ,
    # Changing the workspace.
    "write_file": FAMILY_FILE_WRITE,
    "edit_file": FAMILY_FILE_WRITE,
    "apply_patch": FAMILY_FILE_WRITE,
    "create_document": FAMILY_FILE_WRITE,
    # Running something.
    "shell": FAMILY_SHELL,
    "run_command": FAMILY_SHELL,
    "remote_execute": FAMILY_SHELL,
    "cloud_execute": FAMILY_SHELL,
    # Leaving the machine for the open web.
    "web_fetch": FAMILY_WEB,
    "web_search": FAMILY_WEB,
    # The repository and what Raiker knows about it.
    "git_status": FAMILY_REPOSITORY,
    "git_diff": FAMILY_REPOSITORY,
    "git_log": FAMILY_REPOSITORY,
    "git_branch": FAMILY_REPOSITORY,
    "git_commit": FAMILY_REPOSITORY,
    "git_push": FAMILY_REPOSITORY,
    "github_read": FAMILY_REPOSITORY,
    "github_write": FAMILY_REPOSITORY,
    "code_map_search": FAMILY_REPOSITORY,
    "code_map_references": FAMILY_REPOSITORY,
    # The owner's own accounts, reached through a governed connector.
    "gmail_read": FAMILY_CONNECTOR,
    "gcal_read": FAMILY_CONNECTOR,
    "slack_read": FAMILY_CONNECTOR,
    "connector_read": FAMILY_CONNECTOR,
    "connector_write": FAMILY_CONNECTOR,
    # What Raiker remembers.
    "memory_search": FAMILY_MEMORY,
    "memory_list": FAMILY_MEMORY,
    "memory_get": FAMILY_MEMORY,
    "memory_write": FAMILY_MEMORY,
    "memory_forget": FAMILY_MEMORY,
    "conversation_search": FAMILY_MEMORY,
    # Another model doing bounded work for this turn.
    "spawn_subagent": FAMILY_SUBAGENT,
    "consult_advisor": FAMILY_SUBAGENT,
    # The turn's own spine.
    "update_plan": FAMILY_PLAN,
    "create_task": FAMILY_PLAN,
    "assign_session_project": FAMILY_PLAN,
}

_LABEL_BY_TOOL: dict[str, str] = {
    "read_file": "Read file",
    "list_directory": "List folder",
    "glob": "Find files",
    "grep": "Search files",
    "stat_path": "Inspect path",
    "diff_files": "Compare files",
    "skill_load": "Load skill",
    "vector_get": "Open vector",
    "write_file": "Write file",
    "edit_file": "Edit file",
    "apply_patch": "Apply patch",
    "create_document": "Create document",
    "shell": "Run command",
    "run_command": "Run command",
    "remote_execute": "Run command on the remote host",
    "cloud_execute": "Run command in the cloud",
    "web_fetch": "Fetch page",
    "web_search": "Search the web",
    "git_status": "Check repository status",
    "git_diff": "Read repository changes",
    "git_log": "Read repository history",
    "git_branch": "Create branch",
    "git_commit": "Commit",
    "git_push": "Push",
    "github_read": "Read from GitHub",
    "github_write": "Write to GitHub",
    "code_map_search": "Search the code map",
    "code_map_references": "Find references",
    "gmail_read": "Read Gmail",
    "gcal_read": "Read Calendar",
    "slack_read": "Read Slack",
    "connector_read": "Read connector",
    "connector_write": "Write through connector",
    "memory_search": "Search memory",
    "memory_list": "List memory",
    "memory_get": "Open memory",
    "memory_write": "Save memory",
    "memory_forget": "Forget memory",
    "conversation_search": "Search past conversations",
    "spawn_subagent": "Delegate to a subagent",
    "consult_advisor": "Consult the advisor model",
    "update_plan": "Update the plan",
    "create_task": "Create task",
    "assign_session_project": "Assign to project",
}

# How long a phrase may be before it stops being a summary. A path is trimmed
# from the *left* so the filename survives; everything else from the right.
_MAX_PHRASE = 72


@dataclass(frozen=True)
class ToolRow:
    """One transcript line: the icon family, the name, and what it acted on."""

    tool_name: str
    family: str
    label: str
    action: str

    def to_payload(self) -> dict[str, str]:
        return {
            "tool_name": self.tool_name,
            "family": self.family,
            "label": self.label,
            "action": self.action,
        }


def _clean(value: Any, *, locator: bool = False, identifier: bool = False) -> str:
    """One argument as it may appear in a row: redacted, flattened, bounded.

    ``locator`` and ``identifier`` say what the caller already knows from the
    argument's name — that this is a path or URL, or a server-issued id. Each
    relaxes the high-entropy fallback for that one shape and nothing else, which
    is what keeps ``docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md`` from rendering
    as ``[REDACTED_SECRET]`` while a key embedded in a path still does.
    """
    if not isinstance(value, str):
        return ""
    redacted, _ = redact_text(value, locator_value=locator, identifier_value=identifier)
    return " ".join(redacted.split())


def _trim(text: str, *, from_left: bool = False) -> str:
    if len(text) <= _MAX_PHRASE:
        return text
    return ("…" + text[-(_MAX_PHRASE - 1) :]) if from_left else (text[: _MAX_PHRASE - 1] + "…")


def _path(arguments: dict[str, Any], key: str = "path") -> str:
    return _trim(_clean(arguments.get(key), locator=True).replace("\\", "/"), from_left=True)


def _quoted(arguments: dict[str, Any], key: str) -> str:
    text = _trim(_clean(arguments.get(key)))
    return f"“{text}”" if text else ""


def _host(url: str) -> str:
    """A URL reduced to the host it would reach — never its path or query.

    A signed URL carries its credential in the query string, in a shape that
    reads as ordinary base64 to pattern-based redaction. The host is the fact
    the row exists to state ("Raiker left the machine, and went here"), and it
    is the only part that cannot carry one.
    """
    remainder = url.split("://", 1)[-1]
    authority = remainder.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = authority.rpartition("@")[2]
    # An IPv6 literal keeps its brackets and loses its port; everything else
    # splits on the first colon.
    host = host.partition("]")[0] + "]" if host.startswith("[") else host.partition(":")[0]
    return _trim(_clean(host, locator=True).lower())


def _program(command: str) -> str:
    """A command reduced to the program it runs.

    The full command line reaches the approval card, the receipt and the event,
    where it is evidence the owner is deciding on. The row is read at a glance
    while the turn runs, so it names the program and stops: an argument can be a
    token, a password, or a path the owner would rather not have on a shared
    screen, and no amount of trimming makes "the rest of the command" safe.
    """
    first = command.strip().split()
    if not first:
        return ""
    program = first[0].replace("\\", "/").rpartition("/")[2]
    return _trim(_clean(program))


def _joined(*parts: str) -> str:
    return " · ".join(part for part in parts if part)


def tool_row(tool_name: str, arguments: dict[str, Any] | None = None) -> ToolRow:
    """The transcript row for one call, safe to stream to the client.

    Unknown tools are not an error: they get the neutral family, a humanised
    label, and no action phrase — a tool the owner can see ran, rather than a
    silence.
    """
    args = arguments if isinstance(arguments, dict) else {}
    mcp = parse_mcp_tool_name(tool_name)
    if mcp is not None:
        server, tool = mcp
        # A projected MCP tool's *arguments* are dropped from the durable event
        # (BUG-12): they are values the model composed for an outside program
        # and can carry anything the conversation contained. The row names the
        # owner-registered server and the advertised tool, both of which the
        # owner chose, and nothing the model wrote.
        return ToolRow(
            tool_name=tool_name,
            family=FAMILY_CONNECTOR,
            label=f"Call {_trim(_clean(server))}",
            action=_trim(_clean(tool)),
        )
    family = _FAMILY_BY_TOOL.get(tool_name, FAMILY_TOOL)
    label = _LABEL_BY_TOOL.get(tool_name, humanize_tool_name(tool_name))
    return ToolRow(
        tool_name=tool_name,
        family=family,
        label=label,
        action=_action_phrase(tool_name, args),
    )


def humanize_tool_name(tool_name: str) -> str:
    """A tool with no entry in the table, said as words rather than as an id."""
    words = tool_name.replace("__", " ").replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else "Tool"


def _action_phrase(tool_name: str, args: dict[str, Any]) -> str:  # noqa: PLR0911, PLR0912
    """What this call acted on, in one short phrase, or "" when nothing is safe."""
    # ── Paths ────────────────────────────────────────────────────────────────
    if tool_name in {"read_file", "stat_path", "write_file", "edit_file", "create_document"}:
        return _path(args)
    if tool_name == "list_directory":
        return _path(args) or "the workspace root"
    if tool_name == "apply_patch":
        return _path(args) or "the proposed hunks"
    if tool_name == "diff_files":
        return _path(args, "after_path")
    if tool_name == "glob":
        return _clean(args.get("pattern"), locator=True)[:_MAX_PHRASE]

    # ── Queries the model composed from the owner's own words ────────────────
    if tool_name in {
        "grep",
        "web_search",
        "memory_search",
        "code_map_search",
        "conversation_search",
    }:
        return _quoted(args, "query")
    if tool_name == "code_map_references":
        return _quoted(args, "name")
    if tool_name == "skill_load":
        return _clean(args.get("name"))[:_MAX_PHRASE]

    # ── Narrowed further than the event narrows them ─────────────────────────
    if tool_name == "web_fetch":
        return _host(str(args.get("url", "")))
    if tool_name in {"shell", "run_command", "remote_execute", "cloud_execute"}:
        return _program(str(args.get("command", "")))

    # ── Governance-relevant identifiers the event keeps verbatim ─────────────
    if tool_name == "git_branch":
        return _clean(args.get("name"))[:_MAX_PHRASE]
    if tool_name == "git_push":
        return _joined(_clean(args.get("remote")), _clean(args.get("branch")))[:_MAX_PHRASE]
    if tool_name in {"github_read", "github_write"}:
        return _joined(
            _clean(args.get("repo")),
            _clean(args.get("resource")) or _clean(args.get("operation")),
        )[:_MAX_PHRASE]
    if tool_name in {"gmail_read", "gcal_read", "slack_read"}:
        # The resource names *what kind* of record was read. The message id,
        # calendar id and channel stay in the event: a calendar id is usually an
        # address, and an address in a transcript is a disclosure the row does
        # not need to make to be useful.
        return _clean(args.get("resource"))[:_MAX_PHRASE]
    if tool_name in {"connector_read", "connector_write"}:
        return _joined(
            _clean(args.get("connector_id"), identifier=True),
            _clean(args.get("operation_id"), identifier=True),
        )[:_MAX_PHRASE]
    if tool_name in {"memory_get", "memory_forget"}:
        return _clean(args.get("memory_id"), identifier=True)[:_MAX_PHRASE]
    if tool_name == "memory_write":
        # Never the text. The owner reads the exact sentence on the approval
        # card, decides there, and does not need it repeated in the transcript.
        scope = _clean(args.get("scope")) or "project"
        return f"{scope} scope"
    if tool_name == "assign_session_project":
        return _clean(args.get("project_id"), identifier=True)[:_MAX_PHRASE]
    if tool_name == "create_task":
        return _quoted(args, "title")
    if tool_name == "spawn_subagent":
        return _clean(args.get("name"))[:_MAX_PHRASE]

    # ── Nothing an argument could add ────────────────────────────────────────
    # `consult_advisor` is metadata-only in the event, so it is metadata-only
    # here. `git_status`/`git_diff`/`git_log`, `memory_list` and `update_plan`
    # act on the whole of their subject and have nothing to name.
    return ""
