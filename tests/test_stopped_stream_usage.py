"""DEC-24 step 2 — a call the owner stopped is still billed, so it is still counted.

"Account for cancelled calls that a provider still bills." A streamed turn the
owner stopped mid-answer left the usage ledger untouched: the input had been
sent and billed, part of the answer generated and billed, and every spending
limit read the turn as free. Anthropic says what the input cost as the stream
opens; that is now passed on at once, and a stopped (or failed) stream records
whatever the provider had counted. A provider that reports nothing until the
end has said nothing yet, so its stopped call is recorded as an *estimate* —
marked as one, counted by every limit, never shown as settled (BUG-333).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

import raiker.runtime.orchestrator as orchestrator_module
from raiker.models.contracts import ModelMessage, ModelStreamEvent
from raiker.runtime.model_usage import ModelUsageLedger
from raiker.storage.sqlite import SQLiteStore
from tests.test_turn_resume_after_approval import (
    ScriptedRouter,
    _envelope,
    _identity_for,
    _orchestrator,
)


class _StoppedMidStream(ScriptedRouter):
    """Streams an answer; the owner presses Stop after the second chunk."""

    def __init__(self, store: SQLiteStore, envelope: object, *, early_usage: bool) -> None:
        super().__init__([])
        self._store = store
        self._envelope = envelope
        self._early_usage = early_usage

    async def astream(  # type: ignore[no-untyped-def]
        self, provider: str, model: str, messages: Sequence[ModelMessage], tools=None, **_kw
    ) -> AsyncIterator[ModelStreamEvent]:
        self.calls += 1
        if self._early_usage:
            yield ModelStreamEvent(
                event_type="usage",
                metadata={"usage": {"input_tokens": 1200, "cache_read_input_tokens": 300, "output_tokens": 1}},
            )
        for index, chunk in enumerate(["Half ", "of an ", "answer ", "that never ends"]):
            if index == 2:
                env = self._envelope
                self._store.request_turn_stop(
                    env.session_id, env.user.id, reason="user stopped this turn"  # type: ignore[attr-defined]
                )
            yield ModelStreamEvent(event_type="text_delta", text_delta=chunk)
            await asyncio.sleep(0)


def _stream(workspace: Path, *, early_usage: bool, monkeypatch: pytest.MonkeyPatch) -> tuple[str, list[object]]:
    monkeypatch.setattr(orchestrator_module, "_STOP_POLL_SECONDS", 0.0)
    envelope = _envelope("write something long")
    store = SQLiteStore(workspace)
    router = _StoppedMidStream(store, envelope, early_usage=early_usage)
    orchestrator = _orchestrator(workspace, router)

    async def go() -> list[object]:
        identity = _identity_for(workspace, orchestrator, envelope)
        return [
            event
            async for event in orchestrator._aturn_events(envelope, stream=True, identity=identity)
        ]

    return envelope.session_id, asyncio.run(go())


def test_a_stopped_stream_records_what_the_provider_had_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, events = _stream(tmp_path, early_usage=True, monkeypatch=monkeypatch)

    final = events[-1].response  # type: ignore[attr-defined]
    assert final is not None and final.status == "stopped"
    rows = ModelUsageLedger(SQLiteStore(tmp_path)).session_usage("principal_owner", session_id)
    assert len(rows) == 1
    totals = rows[0].totals
    assert totals.input_tokens == 1200 and totals.cache_read_tokens == 300


def test_a_provider_that_said_nothing_yet_is_recorded_as_an_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # BUG-333 — OpenAI-compatible streams count usage only in their last chunk.
    # The prompt was sent and billed, so the stop records an estimate from the
    # request and the text already shown — marked as one, never a zero row.
    session_id, events = _stream(tmp_path, early_usage=False, monkeypatch=monkeypatch)

    final = events[-1].response  # type: ignore[attr-defined]
    assert final is not None and final.status == "stopped"
    rows = ModelUsageLedger(SQLiteStore(tmp_path)).session_usage("principal_owner", session_id)
    assert len(rows) == 1
    totals = rows[0].totals
    assert totals.estimated_requests == 1 and totals.requests == 1
    assert totals.input_tokens > 0 and totals.output_tokens > 0
    assert totals.cache_read_tokens == 0


def test_a_providers_own_count_is_not_marked_as_an_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, _events = _stream(tmp_path, early_usage=True, monkeypatch=monkeypatch)
    rows = ModelUsageLedger(SQLiteStore(tmp_path)).session_usage("principal_owner", session_id)
    assert rows[0].totals.estimated_requests == 0
