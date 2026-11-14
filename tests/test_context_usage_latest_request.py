"""Context size and cost read from the request that actually ran.

The window holds what the *last* request carried, cache reads included, and a
conversation is priced at the profile that served it rather than at whatever
is selected globally today.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.control.dashboard import DashboardService
from raiker.runtime.model_usage import ModelUsageLedger, UsageTotals
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    created = SQLiteStore(tmp_path)
    created.bootstrap()
    return created


def _record(ledger: ModelUsageLedger, at: str, usage: dict[str, int], model: str = "claude-haiku-4-5-20251001") -> None:
    ledger.record(
        owner_principal_id="owner",
        session_id="s1",
        provider="anthropic",
        model=model,
        usage=usage,
        recorded_at=at,
    )


def test_latest_request_is_the_newest_row_not_the_aggregate(store: SQLiteStore) -> None:
    ledger = ModelUsageLedger(store)
    _record(ledger, "2026-11-14T10:00:00Z", {"input_tokens": 1000, "output_tokens": 100})
    _record(ledger, "2026-11-14T10:01:00Z", {"input_tokens": 50, "output_tokens": 40, "cache_read_tokens": 1100})
    latest = ledger.latest_request("owner", "s1")
    assert latest is not None
    # 50 uncached + 1,100 cached + 40 written back, not 1,050 summed input.
    assert latest.totals.context_tokens == 1190
    aggregate = ledger.session_usage("owner", "s1")
    assert aggregate[-1].totals.input_tokens == 1050


def test_latest_request_ignores_compaction_and_other_sessions(store: SQLiteStore) -> None:
    ledger = ModelUsageLedger(store)
    _record(ledger, "2026-11-14T10:00:00Z", {"input_tokens": 300, "output_tokens": 20})
    ledger.record(
        owner_principal_id="owner",
        session_id="s1",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        usage={"input_tokens": 9000, "output_tokens": 500},
        request_kind="compaction",
        recorded_at="2026-11-14T10:05:00Z",
    )
    ledger.record(
        owner_principal_id="owner",
        session_id="other",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        usage={"input_tokens": 7, "output_tokens": 1},
        recorded_at="2026-11-14T10:09:00Z",
    )
    latest = ledger.latest_request("owner", "s1")
    assert latest is not None and latest.totals.context_tokens == 320
    assert ledger.latest_request("owner", "missing") is None


def test_context_tokens_counts_every_part_of_the_prompt() -> None:
    totals = UsageTotals(input_tokens=10, output_tokens=5, cache_read_tokens=100, cache_write_tokens=20)
    assert totals.context_tokens == 135


def test_context_usage_reads_the_serving_model_without_a_global_choice(store: SQLiteStore, tmp_path: Path) -> None:
    service = DashboardService(tmp_path)
    ledger = ModelUsageLedger(service.store)
    ledger.record(
        owner_principal_id="owner",
        session_id="s1",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        usage={"input_tokens": 120, "output_tokens": 30, "cache_read_tokens": 2000},
        recorded_at="2026-11-14T10:00:00Z",
    )
    view = service.get_context_usage("s1", "owner")
    assert view.usage_source == "provider"
    assert view.used_tokens == 2150
    assert view.model == "claude-haiku-4-5-20251001"
    assert view.provider == "anthropic"
