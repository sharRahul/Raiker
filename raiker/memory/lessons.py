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
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.memory.candidates import MemoryCandidate
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.storage.sqlite import SQLiteStore

LESSON_ROLE = "raiker_lesson"
LESSON_MEMORY_TYPE = "lesson"
LESSON_EXTRACTOR_VERSION = "ru12-command-lesson-v1"
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


def lessons_from_runs(runs: Iterable[Mapping[str, Any]]) -> list[str]:
    """Lesson sentences from one turn's command runs, oldest first.

    A run is ``{"command": str, "exit_code": int | None, "created_at": str}``.
    """
    ordered = sorted(
        (run for run in runs if str(run.get("command") or "").strip()),
        key=lambda run: str(run.get("created_at") or ""),
    )
    lessons: list[str] = []
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
            if len(failed) > _COMMAND_LIMIT or len(passed) > _COMMAND_LIMIT:
                break
            lessons.append(f"In this project, `{passed}` works where `{failed}` failed.")
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
) -> LessonSummary:
    """File each lesson this turn taught as a deferred, project-scoped proposal."""
    proposed = already = suppressed = 0
    for text in lessons_from_runs(runs):
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
                memory_type=LESSON_MEMORY_TYPE,
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
