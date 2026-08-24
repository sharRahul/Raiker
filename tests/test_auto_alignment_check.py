"""Auto mode's second check: deterministic, withholding-only, and explainable.

BUG-218 — Raiker's **Auto** approval mode meant "do not add a restriction of my
own", while the products an owner arrives from promise a safety review on exactly
that mode. Closing the gap with a classifier would have been worse than leaving
it: it would make Auto *feel* safer without being safer, and put a model in the
authority path.

So the check asks a question with a factual answer — *has this turn established
the file this action is about to change?* — and these tests hold it to the four
constraints the defect entry set: evidence on the decision, withholding only,
a stated reason naming what did not match, and failing closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.runtime.alignment import (
    ALIGNMENT_CHECKED_TOOLS,
    REASON_RECORD_UNAVAILABLE,
    REASON_UNESTABLISHED,
    action_targets,
    check_alignment,
)
from raiker.storage.sqlite import SQLiteStore

SESSION = "sess_align"


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path)
    store.create_session(SESSION, str(tmp_path))
    return store


def _turn(store: SQLiteStore, prompt: str) -> str:
    turn_id = new_id("turn_")
    store.insert_turn(SESSION, turn_id, prompt)
    return turn_id


def _record(
    store: SQLiteStore, turn_id: str, tool_name: str, arguments: dict[str, Any]
) -> None:
    """Record one completed tool call in the turn, as the broker does."""
    store.insert_tool_action(
        ToolAction(
            action_id=new_id("act_"),
            tool_name=tool_name,
            arguments=arguments,
            risk_level="medium",
            proposed_by="prin_agent",
            requires_approval=False,
        ),
        SESSION,
        turn_id,
        "success",
    )


def _check(store: SQLiteStore, turn_id: str, tool: str, **arguments: Any) -> Any:
    return check_alignment(
        store,
        tool_name=tool,
        arguments=arguments,
        session_id=SESSION,
        turn_id=turn_id,
    )


# ── The thing the defect reproduced ─────────────────────────────────────────


def test_a_write_to_a_file_the_turn_never_touched_is_withheld(store: SQLiteStore) -> None:
    """The exact reproduction in BUG-218: a change to an unrelated file ran."""
    turn_id = _turn(store, "Fix the retry timeout in the client.")
    verdict = _check(store, turn_id, "write_file", path="unrelated/secrets.env", text="x")
    assert verdict.aligned is False
    assert verdict.reason_code == REASON_UNESTABLISHED
    assert verdict.target == "unrelated/secrets.env"


def test_the_reason_names_the_path_rather_than_expressing_a_mood(store: SQLiteStore) -> None:
    """"State which part of the request the action did not match" — the entry's word."""
    turn_id = _turn(store, "Tidy the README.")
    verdict = _check(store, turn_id, "write_file", path="src/deploy.sh", text="x")
    assert "src/deploy.sh" in verdict.message
    assert "withheld" in verdict.message.lower()
    # It also says what to do about it, because the owner is now the decider.
    assert "approve" in verdict.message.lower()


# ── What establishes a target ───────────────────────────────────────────────


def test_the_owner_naming_the_file_establishes_it(store: SQLiteStore) -> None:
    turn_id = _turn(store, "Fix the timeout in src/client/retry.py please")
    assert _check(store, turn_id, "write_file", path="src/client/retry.py", text="x").aligned


def test_a_bare_filename_in_the_prompt_establishes_it_wherever_it_lives(
    store: SQLiteStore,
) -> None:
    """An owner who writes "fix retry.py" does not know or care where it is."""
    turn_id = _turn(store, "fix the bug in retry.py")
    assert _check(store, turn_id, "edit_file", path="deep/nested/dir/retry.py", text="x").aligned


def test_reading_a_file_earlier_in_the_turn_establishes_it(store: SQLiteStore) -> None:
    turn_id = _turn(store, "Make that function faster.")
    _record(store, turn_id, "read_file", {"path": "src/slow.py"})
    assert _check(store, turn_id, "write_file", path="src/slow.py", text="x").aligned


def test_listing_a_directory_covers_a_new_file_inside_it(store: SQLiteStore) -> None:
    """The turn demonstrably went there; refusing the write adds friction, not safety."""
    turn_id = _turn(store, "Add a test for the parser.")
    _record(store, turn_id, "list_directory", {"path": "tests"})
    assert _check(store, turn_id, "write_file", path="tests/test_parser.py", text="x").aligned


def test_reading_one_file_does_not_establish_its_sibling(store: SQLiteStore) -> None:
    """The line worth holding: a neighbour is not the same file."""
    turn_id = _turn(store, "Have a look at the parser.")
    _record(store, turn_id, "read_file", {"path": "src/a.py"})
    assert _check(store, turn_id, "write_file", path="src/b.py", text="x").aligned is False


def test_a_second_edit_to_a_file_the_turn_already_wrote_is_the_same_work(
    store: SQLiteStore,
) -> None:
    turn_id = _turn(store, "Create the module.")
    _record(store, turn_id, "write_file", {"path": "src/new.py"})
    assert _check(store, turn_id, "edit_file", path="src/new.py", text="x").aligned


def test_a_grep_establishes_what_it_searched(store: SQLiteStore) -> None:
    turn_id = _turn(store, "Where is the timeout set?")
    _record(store, turn_id, "grep", {"query": "timeout", "path": "src/config.py"})
    assert _check(store, turn_id, "edit_file", path="src/config.py", text="x").aligned


def test_establishment_does_not_carry_across_turns(store: SQLiteStore) -> None:
    """Otherwise a review quietly becomes a standing grant nobody issued."""
    first = _turn(store, "Read the config.")
    _record(store, first, "read_file", {"path": "src/config.py"})
    second = _turn(store, "Now do the other thing.")
    assert _check(store, second, "write_file", path="src/config.py", text="x").aligned is False


# ── Patches carry their paths in the diff ───────────────────────────────────


def test_a_patch_is_read_for_the_paths_it_names(store: SQLiteStore) -> None:
    patch = "--- a/src/mod.py\n+++ b/src/mod.py\n@@ -1 +1 @@\n-old\n+new\n"
    assert action_targets("apply_patch", {"patch": patch}) == ("src/mod.py",)

    turn_id = _turn(store, "Update the module.")
    assert _check(store, turn_id, "apply_patch", patch=patch).aligned is False
    _record(store, turn_id, "read_file", {"path": "src/mod.py"})
    assert _check(store, turn_id, "apply_patch", patch=patch).aligned


def test_a_patch_creating_a_file_ignores_the_dev_null_side(store: SQLiteStore) -> None:
    patch = "--- /dev/null\n+++ b/src/created.py\n@@ -0,0 +1 @@\n+new\n"
    assert action_targets("apply_patch", {"patch": patch}) == ("src/created.py",)


# ── The four constraints the defect entry set ───────────────────────────────


def test_it_can_only_withhold_never_widen(store: SQLiteStore) -> None:
    """Every possible verdict is either "run as you would have" or "ask".

    There is no code path in which the check makes an action *more* permitted
    than the gate and decision mode already made it, which is what keeps it out
    of the authority path.
    """
    turn_id = _turn(store, "anything")
    for tool in sorted(ALIGNMENT_CHECKED_TOOLS):
        verdict = _check(store, turn_id, tool, path="never/mentioned.txt", text="x")
        assert verdict.aligned in (True, False)
        # The only effect of `aligned=False` is a fallback to the approval queue.
        assert verdict.reason_code in ("", REASON_UNESTABLISHED, REASON_RECORD_UNAVAILABLE)


def test_it_fails_closed_when_the_record_cannot_be_read(store: SQLiteStore) -> None:
    """An unreachable reviewer means Auto behaves as Manual, not as Skip."""

    class Broken:
        def load_turn(self, turn_id: str) -> dict[str, Any]:
            raise RuntimeError("storage unavailable")

        def list_turn_tool_actions(self, session_id: str, turn_id: str | None) -> list[Any]:
            raise RuntimeError("storage unavailable")

    verdict = check_alignment(
        Broken(),  # type: ignore[arg-type]
        tool_name="write_file",
        arguments={"path": "src/x.py"},
        session_id=SESSION,
        turn_id="turn_1",
    )
    assert verdict.aligned is False
    assert verdict.reason_code == REASON_RECORD_UNAVAILABLE


def test_a_tool_outside_the_checked_set_is_untouched(store: SQLiteStore) -> None:
    """The check adds friction only where an unrequested action changes something."""
    turn_id = _turn(store, "anything")
    assert _check(store, turn_id, "memory_write", text="a fact").aligned
    assert _check(store, turn_id, "git_commit", message="wip").aligned
    assert _check(store, turn_id, "shell", command="ls").aligned


def test_an_action_naming_no_path_is_not_punished_for_being_unusual(
    store: SQLiteStore,
) -> None:
    turn_id = _turn(store, "anything")
    assert _check(store, turn_id, "write_file", text="no path given").aligned


def test_the_verdict_is_serialisable_evidence(store: SQLiteStore) -> None:
    """It is recorded on the decision, so it has to survive a JSON round trip."""
    turn_id = _turn(store, "Tidy up.")
    verdict = _check(store, turn_id, "write_file", path="a/b.txt", text="x")
    payload = json.loads(json.dumps(verdict.to_dict()))
    assert payload["aligned"] is False
    assert payload["target"] == "a/b.txt"
    assert payload["reason_code"] == REASON_UNESTABLISHED
    assert payload["message"]


# ── Path shapes ─────────────────────────────────────────────────────────────


def test_windows_separators_and_dot_prefixes_compare_equal(store: SQLiteStore) -> None:
    turn_id = _turn(store, "Look at the module.")
    _record(store, turn_id, "read_file", {"path": "./src/mod.py"})
    assert _check(store, turn_id, "write_file", path="src\\mod.py", text="x").aligned


# ── Creating a file is not the risk this check is about ─────────────────────


def test_creating_a_new_file_runs_unprompted(store: SQLiteStore, tmp_path: Path) -> None:
    """"Write the report" producing `report.md` is the requested work.

    Withholding a *create* would make Auto obstructive in the ordinary case
    while protecting nothing: nothing of the owner's is lost, and an obstructive
    Auto is one an owner turns off — which is a worse outcome than the defect.
    """
    turn_id = _turn(store, "write the report")
    verdict = check_alignment(
        store,
        tool_name="write_file",
        arguments={"path": "report.md", "text": "# Report"},
        session_id=SESSION,
        turn_id=turn_id,
        workspace_root=tmp_path,
    )
    assert verdict.aligned is True


def test_overwriting_an_existing_unrelated_file_is_still_withheld(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """The harm the defect reproduced: an existing file changed unnoticed."""
    (tmp_path / "deploy.sh").write_text("#!/bin/sh\nreal deployment\n", encoding="utf-8")
    turn_id = _turn(store, "write the report")
    verdict = check_alignment(
        store,
        tool_name="write_file",
        arguments={"path": "deploy.sh", "text": "rm -rf /"},
        session_id=SESSION,
        turn_id=turn_id,
        workspace_root=tmp_path,
    )
    assert verdict.aligned is False
    assert verdict.reason_code == REASON_UNESTABLISHED
    assert "already exists" in verdict.message


def test_a_target_outside_the_workspace_is_never_waved_through_as_a_create(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """Containment is not this check's job, and exempting the escape would be worse."""
    turn_id = _turn(store, "tidy up")
    verdict = check_alignment(
        store,
        tool_name="write_file",
        arguments={"path": "../../etc/hosts", "text": "x"},
        session_id=SESSION,
        turn_id=turn_id,
        workspace_root=tmp_path,
    )
    assert verdict.aligned is False


def test_a_missing_turn_row_withholds_rather_than_reading_it_as_an_empty_prompt(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """Every surface records the turn before dispatching, so a missing row is a
    broken record — not an owner who asked for nothing. Reading it as the latter
    would withhold every action with an unexplained reason."""
    (tmp_path / "a.txt").write_text("existing", encoding="utf-8")
    verdict = check_alignment(
        store,
        tool_name="write_file",
        arguments={"path": "a.txt", "text": "x"},
        session_id=SESSION,
        turn_id="turn_never_recorded",
        workspace_root=tmp_path,
    )
    assert verdict.aligned is False
    assert verdict.reason_code == REASON_RECORD_UNAVAILABLE


def test_a_proposed_but_unrun_action_establishes_nothing(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """Including, at the moment the check runs, the action being checked.

    The broker records an action as `proposed` before the decision. Letting a
    proposal establish its own target made the check pass unconditionally on its
    first run — the failure mode a "safety check" must never have.
    """
    (tmp_path / "deploy.sh").write_text("real", encoding="utf-8")
    turn_id = _turn(store, "write the report")
    store.insert_tool_action(
        ToolAction(
            action_id="act_self",
            tool_name="write_file",
            arguments={"path": "deploy.sh", "text": "x"},
            risk_level="high",
            proposed_by="prin_agent",
            requires_approval=True,
        ),
        SESSION,
        turn_id,
        "proposed",
    )
    verdict = check_alignment(
        store,
        tool_name="write_file",
        arguments={"path": "deploy.sh", "text": "x"},
        session_id=SESSION,
        turn_id=turn_id,
        workspace_root=tmp_path,
        action_id="act_self",
    )
    assert verdict.aligned is False
    assert verdict.reason_code == REASON_UNESTABLISHED


def test_reading_a_file_does_not_establish_a_same_named_file_elsewhere(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """A tool call always names a location, so its basename is not a wildcard.

    The prompt keeps the bare-name shortcut — an owner writing "fix retry.py"
    genuinely may not know where it lives — but accepting a *tool's* basename
    would let reading `src/a.py` establish `vendor/a.py`, which is looser than
    the check claims to be.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "config.py").write_text("theirs", encoding="utf-8")
    turn_id = _turn(store, "have a look at the config")
    _record(store, turn_id, "read_file", {"path": "src/config.py"})
    verdict = check_alignment(
        store,
        tool_name="write_file",
        arguments={"path": "vendor/config.py", "text": "x"},
        session_id=SESSION,
        turn_id=turn_id,
        workspace_root=tmp_path,
    )
    assert verdict.aligned is False
