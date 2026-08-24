"""Auto mode's second check: does this action match what the turn is about?

**The gap this closes (BUG-218).** Raiker's **Auto** approval mode meant "do not
add a restriction of my own": the turn ran under the owner's standing
permissions and nothing looked at whether a particular action was what the owner
actually asked for. The reference set promises more —
`Claude Code's auto <https://code.claude.com/docs/en/permissions>`_
"auto-approves tool calls with background safety checks that verify actions align
with your request", and Cowork's Auto "reviews each action for safety". An owner
arriving from either reads Raiker's Auto as the same promise.

**And the obvious implementation is worse than nothing.** A classifier that
quietly approves makes Auto *feel* safer without being safer, and it puts a model
in the authority path — the one place Raiker has refused to put one everywhere
else. So this check is not a classifier. It asks one question with a factual
answer:

    **Has this turn established the thing this action is about to touch?**

A target is *established* when the turn's own durable record shows it: the
owner's prompt named it, an earlier step in the same turn read, listed, searched
or inspected it, or an earlier step already wrote it. That is set membership over
`tool_actions` rows and one prompt string — deterministic, replayable from the
audit trail, and explainable in a sentence that names the path.

**What it can and cannot do.**

* It can only **withhold**: an unestablished target falls back to the ordinary
  approval queue, where the owner decides. It never widens a gate, never skips
  one, and never approves anything that was not already permitted.
* It **fails closed**. An unreadable record means "not established", so Auto
  behaves as Manual rather than as Skip.
* It applies to **Auto only**, not to Skip. Skip's label says no approval is
  raised at all; attaching a silent second check to it would redefine a mode
  whose entire point is not to interrupt. Auto is the mode that promises a
  review, so Auto is the mode that gets one.

**Scoped to the turn, never the session.** Reading a file in one turn must not
silently authorise writing it unprompted in the next: that is how a review
becomes a standing grant nobody issued.

**And scoped to files that already exist.** Creating a new file is not the risk
this check is about — an owner who asks for "the report" and gets `report.md`
got what they asked for, and nothing of theirs was lost. The harm the defect
reproduced is an *existing* file being changed without the turn ever having
looked at it. Checking creates too would make Auto obstructive in the ordinary
case while adding nothing, and an obstructive Auto is one an owner turns off.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: Tools whose target this check examines. Each one changes something outside the
#: conversation, which is what makes "was this asked for?" worth answering. A
#: tool not named here is unaffected — the check adds friction only where an
#: unrequested action would be a real change to the owner's workspace.
ALIGNMENT_CHECKED_TOOLS = frozenset({
    "write_file",
    "edit_file",
    "apply_patch",
    "create_document",
})

#: Tools whose use *establishes* their target: after any of these, the turn has
#: demonstrably looked at the path, so acting on it is continuous with the work.
ESTABLISHING_TOOLS = frozenset({
    "read_file",
    "list_directory",
    "glob",
    "grep",
    "stat_path",
    "diff_files",
    "git_status",
    "git_diff",
    "git_log",
    "code_map_search",
    "code_map_references",
    # A write already made in this turn establishes its own target: a second
    # edit to a file the turn just created is the same work continuing.
    "write_file",
    "edit_file",
    "apply_patch",
    "create_document",
})

#: Argument names that carry a path, across the tools above.
_PATH_ARGUMENT_NAMES = ("path", "before_path", "after_path", "target_path", "file_path")

#: A path-ish token in prompt text: at least one separator or a file extension,
#: so ordinary prose words are not read as filenames.
_PROMPT_PATH_RE = re.compile(r"[\w./\\-]*[\w-]+(?:/[\w.-]+)+|[\w-]+\.[A-Za-z0-9]{1,8}")

REASON_UNESTABLISHED = "auto_alignment_target_not_established"
REASON_RECORD_UNAVAILABLE = "auto_alignment_record_unavailable"


@dataclass(frozen=True)
class AlignmentVerdict:
    """The check's answer, recorded as evidence rather than applied silently."""

    #: True when the action may run unprompted under Auto.
    aligned: bool
    #: Stable machine code when it may not. Empty when aligned.
    reason_code: str = ""
    #: The path the check was about, when there was one.
    target: str = ""
    #: One sentence naming what did not match, for the approval the owner sees.
    #: Never a mood — it says which path, and that the turn never established it.
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "aligned": self.aligned,
            "reason_code": self.reason_code,
            "target": self.target,
            "message": self.message,
        }


ALIGNED = AlignmentVerdict(aligned=True)


def _normalise(raw: object) -> str:
    """A comparable form of a path: posix separators, no leading `./`."""
    if not isinstance(raw, str):
        return ""
    text = raw.strip().replace("\\", "/")
    if not text:
        return ""
    parts = [p for p in text.split("/") if p not in ("", ".")]
    return "/".join(parts)


def action_targets(tool_name: str, arguments: Mapping[str, Any]) -> tuple[str, ...]:
    """Every path an action names, normalised. Empty when it names none."""
    found: list[str] = []
    for key in _PATH_ARGUMENT_NAMES:
        normalised = _normalise(arguments.get(key))
        if normalised:
            found.append(normalised)
    if tool_name == "apply_patch" and not found:
        # A patch may carry its paths only in the diff header.
        found.extend(_paths_in_patch(str(arguments.get("patch", ""))))
    return tuple(dict.fromkeys(found))


_PATCH_PATH_RE = re.compile(r"^(?:\+\+\+|---)\s+(?:[ab]/)?(\S+)", re.M)


def _paths_in_patch(patch: str) -> list[str]:
    out: list[str] = []
    for match in _PATCH_PATH_RE.finditer(patch):
        candidate = match.group(1)
        if candidate in ("/dev/null",):
            continue
        normalised = _normalise(candidate)
        if normalised:
            out.append(normalised)
    return out


def _established_from_prompt(prompt_text: str) -> set[str]:
    """Path-shaped tokens the owner wrote. Their basenames count too.

    An owner who writes "fix the timeout in retry.py" has established `retry.py`
    without knowing where it lives, so the match is on the basename as well as on
    the full token.
    """
    established: set[str] = set()
    for match in _PROMPT_PATH_RE.finditer(prompt_text or ""):
        normalised = _normalise(match.group(0))
        if not normalised:
            continue
        established.add(normalised)
        established.add(PurePosixPath(normalised).name)
    return established


#: The only status that establishes anything. A `proposed` row is an action that
#: has not run — including, at the moment this check executes, **the action being
#: checked**, which the broker records before the decision. Letting a proposal
#: establish its own target would make the check unconditionally pass, which is
#: exactly what it did on the first run.
_ESTABLISHING_STATUSES = frozenset({"success"})


def _established_from_actions(
    rows: Iterable[Mapping[str, Any]], *, exclude_action_id: str = ""
) -> set[str]:
    """Paths this turn has already read, listed, searched or written.

    Only *completed* calls count. A call that was proposed and not yet run has
    demonstrated nothing about the workspace.
    """
    established: set[str] = set()
    for row in rows:
        if exclude_action_id and str(row.get("action_id", "")) == exclude_action_id:
            continue
        if str(row.get("status", "")) not in _ESTABLISHING_STATUSES:
            continue
        tool_name = str(row.get("tool_name", ""))
        if tool_name not in ESTABLISHING_TOOLS:
            continue
        try:
            arguments = json.loads(str(row.get("arguments_json") or "{}"))
        except (TypeError, ValueError):
            continue
        if not isinstance(arguments, dict):
            continue
        for key in (*_PATH_ARGUMENT_NAMES, "pattern", "include"):
            normalised = _normalise(arguments.get(key))
            if normalised:
                # The full path only. The bare-basename shortcut belongs to the
                # *prompt*, where an owner writing "fix retry.py" genuinely may
                # not know where it lives; a tool call always names a location,
                # so accepting its basename would let reading `src/a.py`
                # establish `elsewhere/a.py` — looser than the check needs to be
                # and looser than it claims to be.
                established.add(normalised)
    return established


def _covers(established: Sequence[str] | set[str], target: str) -> bool:
    """True when something the turn established accounts for *target*.

    A directory the turn listed covers the files inside it: `list_directory
    src/` then writing `src/new.py` is the same work continuing, and refusing it
    would make the check obstructive without making it safer — the owner already
    saw the turn go there. A *sibling* is not covered: reading `src/a.py` does
    not establish `src/b.py`.
    """
    if not target:
        return True
    if target in established:
        return True
    basename = PurePosixPath(target).name
    if basename and basename in established:
        return True
    parent = str(PurePosixPath(target).parent)
    return parent not in ("", ".") and parent in established


def _existing_targets(
    workspace_root: str | Path | None, targets: Sequence[str]
) -> tuple[str, ...]:
    """The subset of *targets* that already exist inside the workspace.

    A path that resolves outside the workspace is left in: containment is not
    this check's job, and dropping it here would quietly exempt the one shape
    most worth asking about.
    """
    if workspace_root is None:
        return tuple(targets)
    root = Path(workspace_root).resolve()
    existing: list[str] = []
    for target in targets:
        try:
            candidate = (root / target).resolve()
        except (OSError, ValueError):
            existing.append(target)
            continue
        outside = root not in candidate.parents and candidate != root
        if outside or candidate.exists():
            existing.append(target)
    return tuple(existing)


def check_alignment(
    store: SQLiteStore,
    *,
    tool_name: str,
    arguments: Mapping[str, Any],
    session_id: str,
    turn_id: str | None,
    workspace_root: str | Path | None = None,
    action_id: str = "",
) -> AlignmentVerdict:
    """Decide whether *this* action may run unprompted under Auto.

    Returns :data:`ALIGNED` for anything the check does not cover, so a tool
    outside :data:`ALIGNMENT_CHECKED_TOOLS` behaves exactly as it did before.
    """
    if tool_name not in ALIGNMENT_CHECKED_TOOLS:
        return ALIGNED
    targets = action_targets(tool_name, arguments)
    if not targets:
        # Nothing to compare. Adding friction here would punish an action for
        # being unusual rather than for being unrequested.
        return ALIGNED
    targets = _existing_targets(workspace_root, targets)
    if not targets:
        # Every target is a file that does not exist yet, so nothing of the
        # owner's is being changed without their knowledge.
        return ALIGNED

    try:
        turn = store.load_turn(turn_id) if turn_id else None
        rows = store.list_turn_tool_actions(session_id, turn_id)
    except Exception:  # noqa: BLE001 — an unreadable record is not an alignment
        return AlignmentVerdict(
            aligned=False,
            reason_code=REASON_RECORD_UNAVAILABLE,
            target=targets[0],
            message=(
                "Automatic approval was withheld because this turn's own record "
                "could not be read, so there was no way to check that the action "
                "matches what you asked for. Decide it here instead."
            ),
        )

    if turn is None:
        # The turn's prompt is half the record this check reads, and every
        # surface reaches the orchestrator through `AgentGateway`, which records
        # the turn before dispatching. A missing row therefore means the record
        # is unavailable, not that the owner asked for nothing — and reading it
        # as the latter would withhold every action with an unexplained reason.
        return AlignmentVerdict(
            aligned=False,
            reason_code=REASON_RECORD_UNAVAILABLE,
            target=targets[0],
            message=(
                "Automatic approval was withheld because this turn's prompt "
                "could not be read, so there was no way to check that the action "
                "matches what you asked for. Decide it here instead."
            ),
        )

    established = _established_from_prompt(str(turn.get("prompt_text") or ""))
    established |= _established_from_actions(rows, exclude_action_id=action_id)

    for target in targets:
        if not _covers(established, target):
            return AlignmentVerdict(
                aligned=False,
                reason_code=REASON_UNESTABLISHED,
                target=target,
                message=(
                    f"Automatic approval was withheld: {target} already exists "
                    "and this turn has not read, listed or been asked about it, "
                    "so changing it is outside what you asked for. Approve it "
                    "here if that is what you meant."
                ),
            )
    return ALIGNED
