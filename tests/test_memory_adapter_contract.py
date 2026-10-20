"""MEM-ADAPTER-04 — the external memory adapter contract, with no provider.

A fake adapter stands in for any future provider: the contract is what must
hold whichever one is integrated, so it is tested against a stub that can be
made to misbehave.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from raiker.memory.adapter import (
    ADAPTER_PAYLOAD_FIELDS,
    MemoryAdapter,
    MemoryAdapterError,
    MemoryAdapterPolicy,
    prepare_adapter_payload,
    query_with_local_fallback,
    reconcile_deletions,
)

OWNER = "usr_owner"


def _record(memory_id: str, text: str, **overrides: Any) -> dict[str, Any]:
    return {
        "memory_id": memory_id,
        "owner_principal_id": OWNER,
        "approval_state": "approved",
        "scope": "user",
        "text": text,
        "sensitivity": "public",
        "updated_at": "2026-10-20T00:00:00Z",
        "provenance_json": '{"source_type": "human_correction"}',
        **overrides,
    }


def _policy(**overrides: Any) -> MemoryAdapterPolicy:
    values: dict[str, Any] = {
        "adapter_id": "fake",
        "pinned_version": "1.2.3",
        "enabled": True,
        "allowed_scopes": frozenset({"user"}),
    }
    values.update(overrides)
    return MemoryAdapterPolicy(**values)


class FakeAdapter:
    adapter_id = "fake"

    def __init__(
        self,
        *,
        version: str = "1.2.3",
        answer: Sequence[dict[str, Any]] = (),
        receipts: Sequence[dict[str, Any]] | None = None,
        fail: bool = False,
    ) -> None:
        self._version = version
        self._answer = list(answer)
        self._receipts = receipts
        self._fail = fail
        self.sent: list[dict[str, str]] = []

    def version(self) -> str:
        return self._version

    def upsert(self, items: Sequence[dict[str, str]]) -> None:
        self.sent.extend(items)

    def query(self, *, owner_ref: str, scope: str, text: str, limit: int) -> Sequence[dict[str, Any]]:
        if self._fail:
            raise ConnectionError("down")
        return self._answer

    def delete(self, *, owner_ref: str, memory_ids: Sequence[str]) -> Sequence[dict[str, Any]]:
        if self._fail:
            raise ConnectionError("down")
        if self._receipts is not None:
            return self._receipts
        return [{"memory_id": memory_id, "deleted": True} for memory_id in memory_ids]


def test_the_fake_satisfies_the_protocol() -> None:
    assert isinstance(FakeAdapter(), MemoryAdapter)


def test_a_default_policy_is_disabled_and_refuses_before_reading() -> None:
    with pytest.raises(MemoryAdapterError, match="adapter_disabled"):
        prepare_adapter_payload([_record("m1", "Public docs live at the wiki.")],
                                owner_principal_id=OWNER, policy=MemoryAdapterPolicy())


def test_egress_is_denied_for_secrets_other_owners_scopes_and_inactive_records() -> None:
    records = [
        _record("ok", "Public docs live at the wiki."),
        _record("secret", "api_key = abcdefghijklmnopqrstuvwxyz0123", sensitivity="public"),
        _record("cred", "Shared note.", sensitivity="credential_like"),
        _record("theirs", "Public note.", owner_principal_id="usr_other"),
        _record("scope", "Public note.", scope="project:alpha"),
        _record("archived", "Public note.", archived_at="2026-01-01"),
        _record("proposal", "Public note.", approval_state="proposed"),
        _record("personal", "Write to me at alice@example.test."),
    ]

    payload = prepare_adapter_payload(
        records,
        owner_principal_id=OWNER,
        policy=_policy(allowed_sensitivity=frozenset({"public", "secret_like", "credential_like"})),
    )

    assert [item.memory_id for item in payload.items] == ["ok"]
    assert payload.audit.refused == {
        "never_egress": 2,
        "other_owner": 1,
        "scope_not_allowed": 1,
        "inactive": 1,
        "not_approved": 1,
        "sensitivity_not_allowed": 1,
    }


def test_only_contract_fields_leave_and_text_is_redacted() -> None:
    payload = prepare_adapter_payload(
        [_record("m1", "Send the weekly digest to alice@example.test.", sensitivity="personal")],
        owner_principal_id=OWNER,
        policy=_policy(allowed_sensitivity=frozenset({"personal"})),
    )

    (item,) = payload.items
    wire = item.wire()
    assert tuple(wire) == ADAPTER_PAYLOAD_FIELDS
    assert "provenance_json" not in wire
    assert "alice@example.test" not in wire["text"]
    assert item.redacted is True


def test_a_credential_in_a_url_never_leaves_even_when_labelled_public() -> None:
    payload = prepare_adapter_payload(
        [_record("m1", "Docs at https://user:hunter2pass@example.test/wiki.", sensitivity="public")],
        owner_principal_id=OWNER,
        policy=_policy(),
    )
    assert payload.items == ()
    assert payload.audit.refused == {"never_egress": 1}


def test_the_audit_never_holds_memory_text() -> None:
    payload = prepare_adapter_payload(
        [_record("m1", "Public docs live at the wiki.")], owner_principal_id=OWNER, policy=_policy()
    )
    assert "wiki" not in repr(payload.audit)
    assert payload.audit.sent_ids == ("m1",)


def test_an_outage_degrades_to_local_recall() -> None:
    result = query_with_local_fallback(
        FakeAdapter(fail=True), policy=_policy(), owner_principal_id=OWNER, scope="user",
        text="wiki", local_ids=["local_1", "local_2"], known_ids=["m1"],
    )
    assert result.source == "degraded"
    assert result.memory_ids == ("local_1", "local_2")
    assert result.audit.outcome == "adapter_unavailable"


def test_an_unpinned_version_degrades_rather_than_answering() -> None:
    result = query_with_local_fallback(
        FakeAdapter(version="9.9.9", answer=[{"memory_id": "m1"}]), policy=_policy(),
        owner_principal_id=OWNER, scope="user", text="wiki", local_ids=["local"], known_ids=["m1"],
    )
    assert result.source == "degraded"
    assert result.audit.outcome == "adapter_version_not_pinned"


def test_an_adapter_cannot_introduce_a_memory_raiker_does_not_hold() -> None:
    result = query_with_local_fallback(
        FakeAdapter(answer=[{"memory_id": "m1"}, {"memory_id": "invented"}, "junk"]),  # type: ignore[list-item]
        policy=_policy(), owner_principal_id=OWNER, scope="user", text="wiki",
        local_ids=[], known_ids=["m1"],
    )
    assert result.source == "adapter"
    assert result.memory_ids == ("m1",)


def test_a_disallowed_scope_never_reaches_the_adapter() -> None:
    adapter = FakeAdapter(answer=[{"memory_id": "m1"}])
    result = query_with_local_fallback(
        adapter, policy=_policy(), owner_principal_id=OWNER, scope="project:alpha",
        text="wiki", local_ids=["local"], known_ids=["m1"],
    )
    assert result.source == "degraded"
    assert result.audit.outcome == "scope_not_allowed"


def test_deletion_is_confirmed_only_by_an_explicit_receipt() -> None:
    reconciled = reconcile_deletions(
        FakeAdapter(receipts=[{"memory_id": "m1", "deleted": True}, {"memory_id": "m2", "deleted": "yes"},
                              {"memory_id": "never_asked", "deleted": True}]),
        policy=_policy(), owner_principal_id=OWNER, memory_ids=["m1", "m2", "m3"],
    )
    assert reconciled.confirmed == ("m1",)
    assert reconciled.pending == ("m2", "m3")
    assert reconciled.audit.outcome == "deletion_pending"


def test_an_outage_during_deletion_leaves_every_id_pending() -> None:
    reconciled = reconcile_deletions(
        FakeAdapter(fail=True), policy=_policy(), owner_principal_id=OWNER, memory_ids=["m1", "m1", "m2"],
    )
    assert reconciled.confirmed == ()
    assert reconciled.pending == ("m1", "m2")
    assert reconciled.audit.outcome == "adapter_unavailable"
