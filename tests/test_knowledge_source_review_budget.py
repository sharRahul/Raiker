"""NEW-MAP-03 — what one source review is allowed to cost.

The review walked ``path.rglob("*")`` and stopped when a counter reached 5,000,
but the counter only advanced on entries it **accepted**. Everything it skipped
was free: every directory, every hidden path, every name under ``node_modules``,
every file it could not stat. So the cap bounded the answer and not the work,
and a folder with a large dependency tree beside it was walked in full to report
the six files the owner cared about.

This is a resource-bound weakness in an authenticated, owner-scoped path rather
than a demonstrated denial of service, and these tests are written to that
claim: they measure what the walk *touches*, not what an attacker could do with
it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.control import dashboard as dashboard_module
from raiker.control.dashboard import DashboardService
from raiker.control.knowledge_scope import (
    REVIEW_ACCEPTED_FILE_BUDGET,
    REVIEW_DEPTH_BUDGET,
    REVIEW_TRUNCATION_REASONS,
    REVIEW_VISITED_ENTRY_BUDGET,
    grant_root_id,
)

OWNER = "principal_owner"


def _service(tmp_path: Path) -> DashboardService:
    service = DashboardService(tmp_path)
    (tmp_path / ".raiker" / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".raiker" / "memory").mkdir(parents=True, exist_ok=True)
    return service


def _granted(service: DashboardService, folder: Path) -> str:
    """Grant *folder* and return the root id the review is addressed by."""
    service.grant_brain_source_folder(str(folder), owner_principal_id=OWNER)
    return grant_root_id(folder.resolve())


class TestThePrunedWalk:
    def test_an_excluded_tree_is_not_entered_at_all(self, tmp_path: Path) -> None:
        """The finding itself. ``node_modules`` used to be walked in full and
        its entries discarded one at a time, so the folder below cost four
        thousand visits to report one file."""
        folder = tmp_path / "project"
        (folder / "node_modules" / "pkg" / "deep").mkdir(parents=True)
        for index in range(400):
            (folder / "node_modules" / "pkg" / "deep" / f"m{index}.js").write_text("x")
        (folder / ".git" / "objects").mkdir(parents=True)
        for index in range(200):
            (folder / ".git" / "objects" / f"o{index}").write_text("x")
        (folder / "notes.md").write_text("the one file that matters\n", encoding="utf-8")

        service = _service(tmp_path)
        review = service.review_brain_source(_granted(service, folder), owner_principal_id=OWNER)

        assert review["supported_files"] == 1
        # The point of the change: the 600 entries inside the pruned trees are
        # never looked at. Before, every one of them was produced and dropped.
        assert review["visited_entries"] <= 5
        assert review["truncated"] is False

    def test_every_entry_visited_is_counted_even_when_it_is_skipped(
        self, tmp_path: Path
    ) -> None:
        """The counter's actual defect: a skipped file cost nothing, so the
        stated budget measured the answer rather than the work."""
        folder = tmp_path / "mixed"
        folder.mkdir()
        (folder / "keep.md").write_text("x", encoding="utf-8")
        for index in range(50):
            # Unsupported extensions: counted, and previously they at least
            # advanced the counter — hidden files and directories did not.
            (folder / f"image{index}.bin").write_bytes(b"x")
        (folder / ".hidden").mkdir()
        (folder / ".hidden" / "secret.md").write_text("x", encoding="utf-8")

        service = _service(tmp_path)
        review = service.review_brain_source(_granted(service, folder), owner_principal_id=OWNER)

        assert review["supported_files"] == 1
        assert review["unsupported_files"] == 50
        # 51 files, and the hidden directory that was pruned before descent.
        assert review["visited_entries"] >= 51
        # The hidden file inside it is not in the answer.
        assert review["supported_files"] + review["unsupported_files"] == 51


class TestTheBudgetsBind:
    def test_a_wide_tree_stops_on_the_visit_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The budget the old cap was mistaken for. Lowered here rather than
        building fifty thousand files: what is under test is that the walk
        stops when it binds and says which budget stopped it."""
        monkeypatch.setattr(dashboard_module, "REVIEW_VISITED_ENTRY_BUDGET", 40)
        folder = tmp_path / "wide"
        folder.mkdir()
        for index in range(200):
            (folder / f"note{index}.md").write_text("x", encoding="utf-8")

        service = _service(tmp_path)
        review = service.review_brain_source(_granted(service, folder), owner_principal_id=OWNER)

        assert review["truncated"] is True
        assert review["truncated_reason"] == "visited_entry_cap"
        assert review["visited_entries"] <= 41
        # A partial answer that says so. The reason names what the owner can do
        # about it, which is why there are four reasons and not one.
        assert REVIEW_TRUNCATION_REASONS["visited_entry_cap"] in review["warnings"]

    def test_a_deep_tree_stops_on_the_depth_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pathological tree is deep rather than wide, and no counter of
        entries notices depth on its own."""
        monkeypatch.setattr(dashboard_module, "REVIEW_DEPTH_BUDGET", 3)
        folder = tmp_path / "deep"
        here = folder
        for level in range(8):
            here = here / f"level{level}"
            here.mkdir(parents=True)
            (here / "note.md").write_text("x", encoding="utf-8")

        service = _service(tmp_path)
        review = service.review_brain_source(_granted(service, folder), owner_principal_id=OWNER)

        assert review["truncated_reason"] == "depth_cap"
        # Everything above the cap is still counted and reported.
        assert 0 < review["supported_files"] < 8

    def test_the_file_budget_still_bounds_the_answer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The budget that was already there keeps meaning what the card says
        it means — how many files the review will describe."""
        monkeypatch.setattr(dashboard_module, "REVIEW_ACCEPTED_FILE_BUDGET", 10)
        folder = tmp_path / "many"
        folder.mkdir()
        for index in range(40):
            (folder / f"note{index}.md").write_text("x", encoding="utf-8")

        service = _service(tmp_path)
        review = service.review_brain_source(_granted(service, folder), owner_principal_id=OWNER)

        assert review["truncated_reason"] == "accepted_file_cap"
        assert review["supported_files"] + review["unsupported_files"] == 10

    def test_a_slow_walk_stops_on_the_time_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The backstop for work that is slow rather than large — a network
        mount, a sleeping disk — which none of the counters catch."""
        folder = tmp_path / "slow"
        folder.mkdir()
        for index in range(20):
            (folder / f"note{index}.md").write_text("x", encoding="utf-8")

        ticks = iter([0.0] + [float(step) for step in range(1, 400)])
        monkeypatch.setattr(dashboard_module.time, "monotonic", lambda: next(ticks))

        service = _service(tmp_path)
        review = service.review_brain_source(_granted(service, folder), owner_principal_id=OWNER)

        assert review["truncated_reason"] == "time_cap"
        assert review["supported_files"] < 20


class TestTheAnswerIsUnchangedWhereItWasRight:
    def test_a_single_file_is_reviewed_as_itself(self, tmp_path: Path) -> None:
        folder = tmp_path / "one"
        folder.mkdir()
        (folder / "research.md").write_text("hello\n", encoding="utf-8")

        service = _service(tmp_path)
        root_id = _granted(service, folder)
        review = service.review_brain_source(f"{root_id}/research.md", owner_principal_id=OWNER)

        assert review["kind"] == "file"
        assert review["supported_files"] == 1
        assert review["total_bytes"] == len("hello\n")
        assert review["truncated"] is False
        assert review["visited_entries"] == 1

    def test_the_cap_the_card_reports_is_the_file_budget(self, tmp_path: Path) -> None:
        folder = tmp_path / "plain"
        folder.mkdir()
        (folder / "a.md").write_text("x", encoding="utf-8")

        service = _service(tmp_path)
        review = service.review_brain_source(_granted(service, folder), owner_principal_id=OWNER)

        assert review["review_cap"] == REVIEW_ACCEPTED_FILE_BUDGET
        assert review["visited_entries"] >= 1
        assert REVIEW_VISITED_ENTRY_BUDGET > REVIEW_ACCEPTED_FILE_BUDGET
        assert REVIEW_DEPTH_BUDGET > 0

    def test_examples_still_name_files_inside_the_granted_root(self, tmp_path: Path) -> None:
        folder = tmp_path / "examples"
        (folder / "sub").mkdir(parents=True)
        (folder / "sub" / "paper.md").write_text("x", encoding="utf-8")

        service = _service(tmp_path)
        root_id = _granted(service, folder)
        review = service.review_brain_source(root_id, owner_principal_id=OWNER)

        assert review["examples"] == [f"{root_id}/sub/paper.md"]
