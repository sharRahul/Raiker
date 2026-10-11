"""DEC-13 step 3 — review priority from named reasons, not one opaque score.

Memory said which records were expiring or stale, one policy at a time; nothing
ordered the set by what most needed the owner's look, or said why. Each factor
the decision names — retention, sensitivity, use, verification, conflict,
provenance and pin — is a named reason with a fixed weight, and the priority is
their sum.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.memory.review_priority import REVIEW_WEIGHTS, review_reasons
from raiker.memory.store import MemoryGovernance, write_memory

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def _iso(delta: timedelta) -> str:
    return (NOW + delta).isoformat().replace("+00:00", "Z")


def _memory(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "archived_at": None, "expires_at": None, "sensitivity": "project", "source": "user",
        "created_at": _iso(-timedelta(days=1)), "updated_at": _iso(-timedelta(days=1)),
        "confidence": 0.9, "supersedes_memory_id": None, "last_used_at": _iso(-timedelta(hours=1)),
        "recall_turn_count": 3, "pinned": False,
    }
    base.update(fields)
    return base


def test_a_record_with_nothing_to_review_has_no_reasons() -> None:
    assert review_reasons(_memory(), now=NOW) == (0, ())


def test_each_factor_is_a_named_reason_and_the_priority_is_their_sum() -> None:
    priority, reasons = review_reasons(
        _memory(
            expires_at=_iso(timedelta(days=3)), sensitivity="personal", source="agent",
            confidence=0.4, supersedes_memory_id="mem_old",
        ),
        now=NOW,
    )
    assert reasons == (
        "expires_soon", "personal", "written_by_agent", "low_confidence", "replaces_another",
    )
    assert priority == sum(REVIEW_WEIGHTS[reason] for reason in reasons)


def test_age_raises_priority_and_an_owner_edit_counts_as_verification() -> None:
    old = timedelta(days=200)
    _, stale = review_reasons(
        _memory(created_at=_iso(-old), updated_at=_iso(-old), last_used_at=None, source="agent"),
        now=NOW,
    )
    assert stale == ("written_by_agent", "stale")
    _, edited = review_reasons(
        _memory(created_at=_iso(-old), updated_at=_iso(-timedelta(days=2)), source="agent"),
        now=NOW,
    )
    assert "written_by_agent" not in edited


def test_a_pin_lowers_priority_but_is_not_an_exemption() -> None:
    expiring = _memory(expires_at=_iso(timedelta(days=2)))
    unpinned, reasons = review_reasons(expiring, now=NOW)
    pinned, pinned_reasons = review_reasons({**expiring, "pinned": True}, now=NOW)
    assert pinned == unpinned - 1 and pinned_reasons == reasons == ("expires_soon",)


def test_an_archived_record_is_not_up_for_review() -> None:
    assert review_reasons(_memory(archived_at=_iso(-timedelta(days=1)), expires_at=_iso(-timedelta(days=1))), now=NOW) == (0, ())


def test_the_memory_list_carries_each_records_reasons(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    service = DashboardService(tmp_path)
    write_memory(
        "Rahul's home address is 1 Example Lane",
        workspace_root=tmp_path,
        scope="project",
        governance=MemoryGovernance(
            source_event_id="evt", source_session_id="sess", source_turn_id="turn",
            source_type="agent", confidence=0.5, trust_score=0.5, retention="until_forget",
            approval_state="approved", created_by="test",
        ),
        store=service.store,
        owner_principal_id="principal_owner",
    )
    (view,) = service.list_memories(acting_principal_id="principal_owner")
    assert "written_by_agent" in view.review_reasons and "low_confidence" in view.review_reasons
    assert view.review_priority >= REVIEW_WEIGHTS["written_by_agent"] + REVIEW_WEIGHTS["low_confidence"]
