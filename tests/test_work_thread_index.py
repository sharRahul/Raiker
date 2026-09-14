"""NEW-THREAD-01 — the work index, and the three things a browser could not do.

Threads derived its Project choices *and* its results from one unpaginated read
of a hundred rows. A project whose newest thread fell outside that page was not
offered as a filter at all, which on screen is indistinguishable from a project
with nothing in it; the window looked like the whole inventory; and typing a
query called an unscoped search and hid the filters, so narrowing something down
silently widened it.

The order is what these cover: **filter, then facet over everything that
matched, then page.**
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control import dashboard as dashboard_module
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore

# The owner these cases belong to. `sessions.user_id` is a foreign key, so the
# account has to exist before anything can be filed to it.
OWNER = ""


@pytest.fixture
def service(tmp_path: Path) -> DashboardService:
    global OWNER
    workspace = tmp_path / "ws"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    store = SQLiteStore(workspace)
    OWNER = str(store.list_users()[0]["user_id"])
    return DashboardService(workspace)


def _project(service: DashboardService, name: str) -> str:
    """One project row. Created through the store rather than the governed
    control path, because what these cases are about is the index reading them,
    not the approval that makes one."""
    project_id = f"proj_{name.replace(' ', '_').lower()}"
    service.store.create_project(
        project_id=project_id,
        name=name,
        root_subpath=f".raiker/projects/{project_id}",
        owner_user_id=OWNER,
    )
    return project_id


def _chat(
    service: DashboardService,
    title: str,
    *,
    when: str,
    project_id: str | None = None,
) -> str:
    """One conversation, filed where the caller says and touched when they say.

    `create_session` takes its project from the *active* project and its
    timestamp from the clock, which is right for the product and useless for a
    test about ordering and filtering. Both are set directly afterwards, so each
    case states the workspace it is about.
    """
    session_id = f"sess_{title.replace(' ', '_')}"
    service.store.create_session(session_id, str(service.workspace_root), title=title, user_id=OWNER)
    with service.store.connect() as connection:
        connection.execute(
            "UPDATE sessions SET updated_at = ?, project_id = ? WHERE session_id = ?",
            (when, project_id, session_id),
        )
    return session_id


class TestFacetsCoverEverythingThatMatched:
    def test_a_project_outside_the_first_page_is_still_offered(
        self, service: DashboardService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The finding. A facet computed over a page can only ever offer what is
        already on screen."""
        recent = _project(service, "Recent work")
        old = _project(service, "Last quarter")
        for index in range(8):
            _chat(service, f"recent {index}", when=f"2026-09-13T10:{index:02d}:00Z", project_id=recent)
        _chat(service, "the forgotten one", when="2026-01-01T00:00:00Z", project_id=old)

        page = service.work_thread_page(user_id=OWNER, limit=3)

        # Three rows, and both projects offered — including the one whose only
        # thread is nine rows down.
        assert len(page.threads) == 3
        assert {facet.value for facet in page.projects} == {recent, old}
        assert {facet.label for facet in page.projects} == {"Recent work", "Last quarter"}
        # And it can actually be selected.
        selected = service.work_thread_page(user_id=OWNER, project_id=old)
        assert [thread.title for thread in selected.threads] == ["the forgotten one"]

    def test_each_facet_lifts_its_own_filter(self, service: DashboardService) -> None:
        """A project facet that respected the project filter would offer exactly
        one project: the one already on."""
        alpha = _project(service, "Alpha")
        beta = _project(service, "Beta")
        _chat(service, "a one", when="2026-09-13T10:00:00Z", project_id=alpha)
        _chat(service, "b one", when="2026-09-13T09:00:00Z", project_id=beta)

        page = service.work_thread_page(user_id=OWNER, project_id=alpha)

        assert [thread.title for thread in page.threads] == ["a one"]
        assert {facet.value for facet in page.projects} == {alpha, beta}

    def test_a_facet_count_is_what_choosing_it_would_return(
        self, service: DashboardService
    ) -> None:
        alpha = _project(service, "Alpha")
        for index in range(4):
            _chat(service, f"a {index}", when=f"2026-09-13T10:0{index}:00Z", project_id=alpha)
        _chat(service, "loose", when="2026-09-13T11:00:00Z")

        page = service.work_thread_page(user_id=OWNER, limit=2)
        facet = next(entry for entry in page.projects if entry.value == alpha)

        assert facet.count == 4
        assert service.work_thread_page(user_id=OWNER, project_id=alpha).total == 4


class TestNarrowingDownDoesNotWiden:
    def test_a_query_keeps_the_selected_project(self, service: DashboardService) -> None:
        """Typing used to call an unscoped search and hide the filters."""
        alpha = _project(service, "Alpha")
        beta = _project(service, "Beta")
        _chat(service, "quarterly note", when="2026-09-13T10:00:00Z", project_id=alpha)
        _chat(service, "quarterly plan", when="2026-09-13T09:00:00Z", project_id=beta)

        page = service.work_thread_page(user_id=OWNER, project_id=alpha, query="quarterly")

        assert [thread.title for thread in page.threads] == ["quarterly note"]
        assert page.total == 1

    def test_a_blank_query_is_not_a_filter(self, service: DashboardService) -> None:
        _chat(service, "anything", when="2026-09-13T10:00:00Z")
        assert service.work_thread_page(user_id=OWNER, query="   ").total == 1

    def test_the_query_is_case_insensitive(self, service: DashboardService) -> None:
        _chat(service, "Quarterly Note", when="2026-09-13T10:00:00Z")
        assert service.work_thread_page(user_id=OWNER, query="QUARTERLY").total == 1


class TestPagingIsAPositionInOneAnswer:
    def test_a_cursor_walks_every_row_exactly_once(self, service: DashboardService) -> None:
        for index in range(11):
            _chat(service, f"thread {index:02d}", when=f"2026-09-13T10:{index:02d}:00Z")

        seen: list[str] = []
        cursor: str | None = None
        for _page in range(6):
            page = service.work_thread_page(user_id=OWNER, limit=4, cursor=cursor)
            seen.extend(thread.session_id for thread in page.threads)
            cursor = page.next_cursor
            if cursor is None:
                break

        assert len(seen) == 11
        assert len(set(seen)) == 11, "a row was repeated across pages"
        assert cursor is None

    def test_the_last_page_offers_no_cursor(self, service: DashboardService) -> None:
        for index in range(3):
            _chat(service, f"t{index}", when=f"2026-09-13T10:0{index}:00Z")
        page = service.work_thread_page(user_id=OWNER, limit=10)
        assert len(page.threads) == 3
        assert page.next_cursor is None

    def test_threads_touched_in_the_same_second_keep_their_order(
        self, service: DashboardService
    ) -> None:
        """Without a tie-breaker a cursor skips one row and repeats another."""
        for index in range(6):
            _chat(service, f"same {index}", when="2026-09-13T10:00:00Z")

        first = service.work_thread_page(user_id=OWNER, limit=3)
        second = service.work_thread_page(user_id=OWNER, limit=3, cursor=first.next_cursor)
        ids = [thread.session_id for thread in [*first.threads, *second.threads]]

        assert len(set(ids)) == 6

    def test_a_cursor_from_another_question_is_refused(
        self, service: DashboardService
    ) -> None:
        """A position in one ordered answer means nothing in another, so a
        cursor carries the scope it was issued for and restarts rather than
        paging through a different question."""
        alpha = _project(service, "Alpha")
        for index in range(6):
            _chat(service, f"a {index}", when=f"2026-09-13T10:0{index}:00Z", project_id=alpha)

        unfiltered = service.work_thread_page(user_id=OWNER, limit=3)
        assert unfiltered.next_cursor is not None

        # The same cursor, a different question.
        replayed = service.work_thread_page(
            user_id=OWNER, project_id=alpha, limit=3, cursor=unfiltered.next_cursor
        )
        assert [thread.title for thread in replayed.threads] == ["a 5", "a 4", "a 3"]

    def test_a_corrupt_cursor_restarts_rather_than_failing(
        self, service: DashboardService
    ) -> None:
        _chat(service, "only one", when="2026-09-13T10:00:00Z")
        page = service.work_thread_page(user_id=OWNER, cursor="not-a-cursor")
        assert page.total == 1


class TestTheAnswerStatesItsOwnBounds:
    def test_a_complete_answer_says_it_is_complete(self, service: DashboardService) -> None:
        _chat(service, "one", when="2026-09-13T10:00:00Z")
        assert service.work_thread_page(user_id=OWNER).scan_truncated is False

    def test_a_bounded_scan_says_so(
        self, service: DashboardService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An index that reads everything is the defect with a larger number."""
        monkeypatch.setattr(dashboard_module, "WORK_THREAD_SCAN_LIMIT", 3)
        for index in range(5):
            _chat(service, f"t{index}", when=f"2026-09-13T10:0{index}:00Z")

        page = service.work_thread_page(user_id=OWNER)

        assert page.scan_truncated is True
        assert page.total == 3

    def test_the_page_size_is_bounded(self, service: DashboardService) -> None:
        _chat(service, "one", when="2026-09-13T10:00:00Z")
        page = service.work_thread_page(user_id=OWNER, limit=100_000)
        assert page.total == 1  # and no error: the size was clamped, not refused


class TestTheUnfilteredListingIsUnchanged:
    def test_home_still_gets_its_newest_few(self, service: DashboardService) -> None:
        """`list_work_threads` is what Home reads: the newest few threads to
        offer as somewhere to continue, with no filters to apply."""
        for index in range(6):
            _chat(service, f"t{index}", when=f"2026-09-13T10:0{index}:00Z")

        threads = service.list_work_threads(user_id=OWNER, limit=4)

        assert [thread.title for thread in threads] == ["t5", "t4", "t3", "t2"]

    def test_another_account_sees_none_of_it(self, service: DashboardService) -> None:
        _chat(service, "private", when="2026-09-13T10:00:00Z")
        assert service.work_thread_page(user_id="user_someone_else").total == 0
