"""RU-12 — Raiker remembers its own work.

After a project task, Raiker may propose a *lesson*: something its own work in
that project showed, such as "`npm test -- --runInBand` works here where
`npm test` failed". A lesson is a memory proposal like any other — deferred,
offered under the answer with **Keep** / **Not this**, and stored only when the
owner keeps it — and it is scoped to the one project it came from, so the Memory
Brief recalls it on the next task in that project and nowhere else.

Lessons are read from the turn's own command records, never written by the
model: a sentence a model wrote about its work may be invented (FIXED-1548),
while a command that failed and a later variant of it that passed is a fact the
runtime recorded. The rule is deliberately narrow — the same program, a shared
leading word, a non-zero exit followed by a zero one — so a lesson is rare and
worth reading.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.memory.candidates import MemoryCandidate
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.storage.sqlite import SQLiteStore

LESSON_ROLE = "raiker_lesson"
LESSON_MEMORY_TYPE = "lesson"
LESSON_EXTRACTOR_VERSION = "ru12-command-lesson-v1"
#: A lesson whose failing command is one of the project's declared checks. The
#: lesson alone would only tell the next task to work around a wrong check;
#: Keep fixes the check itself, so this is the one lesson that still asks — it
#: changes the project's settings.
CHECK_FIX_MEMORY_TYPE = "check_fix"
#: Every lesson ends with the commands it rests on, so a later task can find
#: it at the moment it is about to run one of them.
_TAIL = re.compile(r"[Rr]un `(?P<passed>[^`]+)` instead of `(?P<failed>[^`]+)`\.$")


def _declared_checks(store: SQLiteStore, project_id: str) -> set[str]:
    try:
        context = store.load_effective_project_context(project_id)
    except Exception:  # noqa: BLE001 — no readable checks means no check to fix
        return set()
    return {str(item).strip() for item in context.get("checks") or []}


def lesson_text(lesson: str, *, failed: str, passed: str, check: bool = False) -> str:
    tail = "Declared check: run" if check else ("Run" if lesson.strip() else "In this project, run")
    return f"{lesson.strip()} {tail} `{passed}` instead of `{failed}`.".strip()


def check_fix_text(lesson: str, *, failed: str, passed: str) -> str:
    return lesson_text(lesson, failed=failed, passed=passed, check=True)


def parse_lesson(text: str) -> tuple[str, str] | None:
    """``(failed, passed)`` a lesson rests on, or ``None``."""
    match = _TAIL.search(text.strip())
    return (match["failed"], match["passed"]) if match else None


parse_check_fix = parse_lesson


def apply_check_fix(store: SQLiteStore, project_id: str, *, failed: str, passed: str) -> bool:
    """Replace the declared check `failed` with `passed`; ``False`` if it is not declared."""
    context = store.load_project_context(project_id)
    checks = [str(item) for item in context.get("checks") or []]
    if failed not in checks:
        return False
    store.save_project_context(
        project_id,
        instructions=str(context.get("instructions") or ""),
        attachment_ids=list(context.get("attachment_ids") or []),
        memory_mode=str(context.get("memory_mode") or ("enabled" if context.get("memory_enabled") else "disabled")),
        checks=[passed if item == failed else item for item in checks],
    )
    return True
#: One lesson per task: the first thing its trial and error taught. A longer
#: list is a log, not a lesson (and the candidate table holds one proposal per
#: turn, role and extractor).
MAX_LESSONS_PER_TURN = 1
_COMMAND_LIMIT = 160
_REFUSED = frozenset({MemorySensitivity.CREDENTIAL_LIKE, MemorySensitivity.SECRET_LIKE})


@dataclass(frozen=True)
class LessonSummary:
    proposed: int = 0
    already_present: int = 0
    suppressed: int = 0


def _words(command: str) -> list[str]:
    return command.strip().split()


def _related(failed: str, passed: str) -> bool:
    """The passing command is a variant of the failing one, not another task."""
    a, b = _words(failed), _words(passed)
    if not a or not b or a == b or a[0] != b[0]:
        return False
    # `npm test` → `npm test -- --runInBand` shares two words; a lone program
    # (`pytest` → `pytest -p no:cacheprovider`) shares its one.
    shared = min(2, len(a), len(b))
    return a[:shared] == b[:shared]


def lessons_from_runs(
    runs: Iterable[Mapping[str, Any]], changes: Iterable[str] = ()
) -> list[str]:
    """Lesson sentences only; see :func:`lesson_pairs`."""
    return [text for text, _failed, _passed in lesson_pairs(runs, changes)]


def lesson_pairs(
    runs: Iterable[Mapping[str, Any]], changes: Iterable[str] = ()
) -> list[tuple[str, str, str]]:
    """Lesson sentences from one turn's command runs, oldest first.

    A run is ``{"command": str, "exit_code": int | None, "created_at": str}``;
    *changes* are the times this turn changed a file. A pass that follows a file
    change may be the change working, not the command — `pytest a.py` failing,
    a fix, then `pytest a.py -x` passing teaches nothing about `-x` — so a
    change between the two runs is no lesson.
    """
    edits = sorted(str(at) for at in changes)
    ordered = sorted(
        (run for run in runs if str(run.get("command") or "").strip()),
        key=lambda run: str(run.get("created_at") or ""),
    )
    lessons: list[tuple[str, str, str]] = []
    used: set[str] = set()
    for index, run in enumerate(ordered):
        failed = str(run["command"]).strip()
        exit_code = run.get("exit_code")
        if exit_code in (None, 0) or failed in used:
            continue
        for later in ordered[index + 1 :]:
            passed = str(later["command"]).strip()
            if later.get("exit_code") != 0 or not _related(failed, passed):
                continue
            start, end = str(run.get("created_at") or ""), str(later.get("created_at") or "")
            # Seconds-granular clocks: a tie counts as between, so a doubt is no lesson.
            if any(start <= at <= end for at in edits):
                break
            if len(failed) > _COMMAND_LIMIT or len(passed) > _COMMAND_LIMIT:
                break
            lessons.append((lesson_text("", failed=failed, passed=passed), failed, passed))
            used.update({failed, passed})
            break
        if len(lessons) >= MAX_LESSONS_PER_TURN:
            break
    return lessons


def propose_turn_lessons(
    store: SQLiteStore,
    *,
    owner_principal_id: str,
    project_id: str,
    session_id: str,
    turn_id: str,
    source_event_id: str,
    runs: Iterable[Mapping[str, Any]],
    changes: Iterable[str] = (),
) -> LessonSummary:
    """File each lesson this turn taught as a deferred, project-scoped proposal."""
    proposed = already = suppressed = 0
    checks = _declared_checks(store, project_id)
    for text, failed, passed in lesson_pairs(runs, changes):
        memory_type = LESSON_MEMORY_TYPE
        if failed in checks:
            text, memory_type = check_fix_text("", failed=failed, passed=passed), CHECK_FIX_MEMORY_TYPE
        sensitivity = classify_memory_sensitivity(text)
        if sensitivity in _REFUSED:
            suppressed += 1
            continue
        # A lesson the owner forgot is not proposed again on the next task.
        if store.memory_text_forgotten(text, owner_principal_id=owner_principal_id):
            suppressed += 1
            continue
        if store.memory_candidate_text_pending(text, owner_principal_id=owner_principal_id):
            already += 1
            continue
        material = f"{owner_principal_id}\0{turn_id}\0{text}\0{LESSON_EXTRACTOR_VERSION}"
        created = store.insert_memory_candidate(
            MemoryCandidate(
                candidate_id="memcand_" + hashlib.sha256(material.encode()).hexdigest()[:24],
                source_event_id=source_event_id,
                memory_type=memory_type,
                scope=f"project:{project_id}",
                text=text,
                sensitivity=sensitivity.value,
                confidence=0.8,
                decision="deferred",
                created_at=utc_now(),
                source_session_id=session_id,
                source_turn_id=turn_id,
                source_role=LESSON_ROLE,
                extractor_version=LESSON_EXTRACTOR_VERSION,
            ),
            owner_principal_id=owner_principal_id,
        )
        proposed += int(created)
        already += int(not created)
    return LessonSummary(proposed=proposed, already_present=already, suppressed=suppressed)


def turn_runs_and_changes(
    store: SQLiteStore, *, owner_principal_id: str, session_id: str, turn_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """This turn's command runs and the times it changed a file, from its own records."""
    from raiker.control.build_outcome import WRITE_TOOLS
    from raiker.execution.commands.store import CommandStore

    runs = [
        {"command": run.safe_display, "exit_code": run.exit_code, "created_at": run.created_at}
        for run in CommandStore(store).list_runs(owner_principal_id, session_id=session_id, limit=500)
        if run.turn_id == turn_id
    ]
    changes = [
        str(row.get("completed_at") or row.get("proposed_at") or "")
        for row in store.list_turn_tool_actions(session_id, turn_id)
        if str(row.get("tool_name") or "") in WRITE_TOOLS and row.get("status") == "success"
    ]
    return runs, changes


def evidence_holds(
    runs: Iterable[Mapping[str, Any]], changes: Iterable[str], *, failed: str, passed: str
) -> bool:
    """`failed` exited non-zero, and later in the turn `passed` exited zero, no file changed between."""
    failed, passed = failed.strip(), passed.strip()
    if not failed or not passed or failed == passed:
        return False
    ordered = sorted(runs, key=lambda run: str(run.get("created_at") or ""))
    edits = [str(at) for at in changes]
    for index, run in enumerate(ordered):
        if str(run.get("command") or "").strip() != failed or run.get("exit_code") in (None, 0):
            continue
        start = str(run.get("created_at") or "")
        for later in ordered[index + 1 :]:
            if str(later.get("command") or "").strip() != passed or later.get("exit_code") != 0:
                continue
            end = str(later.get("created_at") or "")
            if not any(start <= at <= end for at in edits):
                return True
    return False


#: A lesson is a sentence, not a report.
LESSON_TEXT_LIMIT = 240
#: How many lessons one turn may record in its own words.
MAX_RECORDED_LESSONS = 3


def record_lesson(
    store: SQLiteStore,
    *,
    owner_principal_id: str,
    project_id: str,
    session_id: str,
    turn_id: str,
    source_event_id: str,
    text: str,
    failed_command: str,
    passed_command: str,
) -> str:
    """The model's lesson, filed only when the turn's records back it. Returns a status code."""
    text = " ".join(text.split())
    if not text or len(text) > LESSON_TEXT_LIMIT:
        return "lesson_text_invalid"
    if classify_memory_sensitivity(text) in _REFUSED:
        return "lesson_secret_like"
    runs, changes = turn_runs_and_changes(
        store, owner_principal_id=owner_principal_id, session_id=session_id, turn_id=turn_id
    )
    if not evidence_holds(runs, changes, failed=failed_command, passed=passed_command):
        return "lesson_not_backed_by_this_task"
    memory_type = LESSON_MEMORY_TYPE
    is_check = failed_command.strip() in _declared_checks(store, project_id)
    text = lesson_text(text, failed=failed_command.strip(), passed=passed_command.strip(), check=is_check)
    if is_check:
        memory_type = CHECK_FIX_MEMORY_TYPE
    if store.memory_text_forgotten(text, owner_principal_id=owner_principal_id):
        return "lesson_forgotten_before"
    if store.memory_candidate_text_pending(text, owner_principal_id=owner_principal_id):
        return "lesson_already_recorded"
    recorded = [
        row for row in store.list_memory_candidates(owner_principal_id=owner_principal_id)
        if row.get("source_turn_id") == turn_id and row.get("source_role") == LESSON_ROLE
    ]
    if len(recorded) >= MAX_RECORDED_LESSONS:
        return "lesson_limit_reached"
    # The candidate table holds one row per turn, role and extractor; the
    # ordinal keeps a second lesson from the same task distinct.
    version = f"{LESSON_EXTRACTOR_VERSION}-recorded#{len(recorded) + 1}"
    material = f"{owner_principal_id}\0{turn_id}\0{text}\0{version}"
    store.insert_memory_candidate(
        MemoryCandidate(
            candidate_id="memcand_" + hashlib.sha256(material.encode()).hexdigest()[:24],
            source_event_id=source_event_id,
            memory_type=memory_type,
            scope=f"project:{project_id}",
            text=text,
            sensitivity=classify_memory_sensitivity(text).value,
            confidence=0.85,
            decision="deferred",
            created_at=utc_now(),
            source_session_id=session_id,
            source_turn_id=turn_id,
            source_role=LESSON_ROLE,
            extractor_version=version,
        ),
        owner_principal_id=owner_principal_id,
    )
    return "recorded"


def lesson_for_command(
    store: SQLiteStore,
    *,
    workspace_root: str | Path,
    owner_principal_id: str,
    project_id: str,
    command: str,
    exit_code: int | None,
) -> str | None:
    """Recall at the moment it matters, and retire a lesson the project outgrew.

    * The command just **failed** and a kept lesson says what works instead:
      the note goes back with the result, so the model's next call is the one
      that works — instead of hoping the lesson was among the brief's few items.
    * The command a lesson recommends just **failed**: the lesson is stale, so
      it is archived (restorable from Memory) and the note says so.
    """
    from raiker.memory.store import set_memory_archived

    if exit_code in (None, 0) or not command.strip() or not project_id:
        return None
    command = command.strip()
    rows = store.list_approved_memory(
        limit=500, include_search_disabled=True, scope=f"project:{project_id}",
        owner_principal_id=owner_principal_id,
    )
    note: str | None = None
    for row in rows:
        if str(row.get("memory_type") or "") not in {LESSON_MEMORY_TYPE, CHECK_FIX_MEMORY_TYPE}:
            continue
        pair = parse_lesson(str(row.get("text") or ""))
        if pair is None:
            continue
        failed, passed = pair
        if command == passed:
            set_memory_archived(
                str(row["memory_id"]), archived=True, workspace_root=workspace_root,
                store=store, owner_principal_id=owner_principal_id,
            )
            store.record_memory_lifecycle_event(
                str(row["memory_id"]), "archive", owner_principal_id,
                {"auto": True, "reason": "lesson_stale", "command": command},
            )
            note = (
                f"A kept lesson recommended `{passed}`, which just failed; Raiker archived that "
                "lesson as out of date."
            )
        elif command == failed and note is None:
            note = f"A kept lesson for this project says `{passed}` works where `{failed}` fails."
    return note
