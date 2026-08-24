"""Owner-authoritative provider consent, and conversation history.

Two behaviour changes, both grounded in `docs/architecture/HANDOFF.md` → "Security posture":
Raiker is *owner-authoritative and monitored, not prevention-by-restriction*.

1. Configuring a provider **is** the owner's authorisation to use it. A separate
   capability gate and a separate environment allowlist, each of which had to be
   satisfied afterwards, were exactly the "wall in front of the owner's
   legitimate choices" that posture rejects. Explicit revocation still wins.
2. Prior turns of a conversation are replayed to the model. Without them the
   provider answered every follow-up as if it were the opening message.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.models.connections import list_model_connections, put_model_connection
from raiker.models.endpoint_policy import ProviderPolicyError, enforce_model_egress
from raiker.models.policy_state import (
    HOSTED_MODEL_GATE,
    gate_explicitly_disabled,
    provider_runtime_policy_from_gates,
)
from raiker.runtime.conversation_history import conversation_messages, history_char_budget
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    created = SQLiteStore(tmp_path)
    created.bootstrap()
    return created


class TestConsentByConfiguration:
    def test_a_fresh_account_with_no_provider_still_fails_closed(
        self, store: SQLiteStore
    ) -> None:
        policy = provider_runtime_policy_from_gates(store, "p1")
        assert policy.allow_hosted_provider is False

    def test_saving_a_connection_authorises_the_provider(self, store: SQLiteStore) -> None:
        put_model_connection(store, "p1", "anthropic-hosted", {"api_key": "sk-test"})
        policy = provider_runtime_policy_from_gates(store, "p1")
        assert policy.allow_hosted_provider is True
        assert policy.allow_policy_gated_provider is True

    def test_the_save_itself_counts_before_it_is_persisted(self, store: SQLiteStore) -> None:
        # The connection is validated before it is written, so without this the
        # act of configuring a provider would be refused for not having
        # configured it.
        policy = provider_runtime_policy_from_gates(
            store, "p1", configuring_profile_id="anthropic-hosted"
        )
        assert policy.allow_hosted_provider is True

    def test_consent_is_scoped_to_the_principal_who_configured(
        self, store: SQLiteStore
    ) -> None:
        put_model_connection(store, "p1", "anthropic-hosted", {"api_key": "sk-test"})
        assert provider_runtime_policy_from_gates(store, "p2").allow_hosted_provider is False

    def test_listing_connections_returns_ids_only(self, store: SQLiteStore) -> None:
        put_model_connection(store, "p1", "anthropic-hosted", {"api_key": "sk-secret"})
        listed = list_model_connections(store, "p1")
        assert listed == ["anthropic-hosted"]
        assert not any("sk-secret" in entry for entry in listed)


class TestRevocationStillWins:
    def test_an_untouched_gate_is_undecided_not_denied(self, store: SQLiteStore) -> None:
        assert gate_explicitly_disabled(store, HOSTED_MODEL_GATE, "p1") is False

    def test_an_explicitly_disabled_gate_overrides_configuration(
        self, store: SQLiteStore
    ) -> None:
        # Revocation has to work or the controls are theatre: a configured
        # provider the owner then turned off must stay off.
        put_model_connection(store, "p1", "anthropic-hosted", {"api_key": "sk-test"})
        # A principal with no account row resolves against the workspace gate
        # table, which is the path this store exercises.
        store.upsert_capability_gate_state(
            {
                "capability": HOSTED_MODEL_GATE,
                "state": "disabled",
                "runtime_mode": "local_single_user_runtime",
                "created_at": "2026-07-26T00:00:00Z",
                "updated_at": "2026-07-26T00:00:00Z",
            }
        )
        assert gate_explicitly_disabled(store, HOSTED_MODEL_GATE, "p1") is True
        assert provider_runtime_policy_from_gates(store, "p1").allow_hosted_provider is False


class TestEgressFollowsConfiguration:
    def test_an_unconfigured_host_still_fails_closed(self) -> None:
        with pytest.raises(ProviderPolicyError, match="no_allowlist"):
            enforce_model_egress("https://api.anthropic.com", kind="remote_hosted")

    def test_a_configured_endpoint_authorises_its_own_host(self) -> None:
        enforce_model_egress(
            "https://api.anthropic.com",
            kind="remote_hosted",
            configured_allowlist=frozenset({"api.anthropic.com"}),
        )

    def test_configuring_one_host_does_not_open_another(self) -> None:
        # Consent is for the provider the owner configured, not a blanket
        # opening of every off-machine destination.
        with pytest.raises(ProviderPolicyError, match="evil.example.com"):
            enforce_model_egress(
                "https://evil.example.com",
                kind="remote_hosted",
                configured_allowlist=frozenset({"api.anthropic.com"}),
            )

    def test_local_endpoints_are_never_subject_to_egress(self) -> None:
        enforce_model_egress("http://127.0.0.1:8080", kind="local_machine")


class TestConversationHistory:
    def _turn(self, store: SQLiteStore, session: str, turn: str, prompt: str, reply: str) -> None:
        store.insert_turn(session, turn, prompt)
        store.complete_turn(turn, "completed", reply)

    def test_prior_exchanges_are_replayed_in_order(self, store: SQLiteStore) -> None:
        store.create_session("sess_1", "cli")
        self._turn(store, "sess_1", "turn_1", "Remember MARIGOLD-42", "OK")
        self._turn(store, "sess_1", "turn_2", "What is 2+2?", "4")
        messages = conversation_messages(store, "sess_1")
        assert [(m.role, m.content) for m in messages] == [
            ("user", "Remember MARIGOLD-42"),
            ("assistant", "OK"),
            ("user", "What is 2+2?"),
            ("assistant", "4"),
        ]

    def test_the_current_turn_is_excluded(self, store: SQLiteStore) -> None:
        store.create_session("sess_1", "cli")
        self._turn(store, "sess_1", "turn_1", "first", "reply")
        store.insert_turn("sess_1", "turn_2", "the prompt being answered now")
        messages = conversation_messages(store, "sess_1", exclude_turn_id="turn_2")
        assert all("being answered now" not in m.content for m in messages)

    def test_an_unanswered_turn_is_skipped(self, store: SQLiteStore) -> None:
        # A prompt with no reply would read to the model as an unanswered
        # question and skew the next response.
        store.create_session("sess_1", "cli")
        store.insert_turn("sess_1", "turn_1", "never answered")
        assert conversation_messages(store, "sess_1") == []

    def test_a_failed_turn_with_an_error_summary_is_skipped(self, store: SQLiteStore) -> None:
        store.create_session("sess_1", "cli")
        store.insert_turn("sess_1", "turn_1", "request that failed")
        store.complete_turn("turn_1", "failed", "The provider was unavailable.")
        assert conversation_messages(store, "sess_1") == []

    def test_history_is_scoped_to_its_session(self, store: SQLiteStore) -> None:
        store.create_session("sess_1", "cli")
        store.create_session("sess_2", "cli")
        self._turn(store, "sess_1", "turn_1", "in session one", "reply one")
        messages = conversation_messages(store, "sess_2")
        assert messages == []

    def test_the_budget_drops_the_oldest_exchanges_first(self, store: SQLiteStore) -> None:
        store.create_session("sess_1", "cli")
        self._turn(store, "sess_1", "turn_1", "x" * 100, "y" * 100)
        self._turn(store, "sess_1", "turn_2", "recent prompt", "recent reply")
        messages = conversation_messages(store, "sess_1", char_budget=60)
        assert [m.content for m in messages] == ["recent prompt", "recent reply"]

    def test_a_known_capacity_produces_a_larger_budget_than_the_default(self) -> None:
        assert history_char_budget(1_000_000) > history_char_budget(None)
        assert history_char_budget(None) == history_char_budget(0)

    def test_a_missing_store_yields_no_history_rather_than_failing(self) -> None:
        assert conversation_messages(None, "sess_1") == []
