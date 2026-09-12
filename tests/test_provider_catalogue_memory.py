"""The catalogue a provider published, remembered between listings.

GLOBAL-MODEL-01 and GLOBAL-MODEL-08. A provider's catalogue was probed on
demand and never written down, so it existed exactly as long as the HTTP
response that carried it. Two consequences followed, and both were read by
owners as Raiker losing their models:

* a model reached a composer only by being "kept available", which made
  curation a prerequisite for visibility rather than the convenience the plan
  describes;
* a provider that was briefly unreachable emptied every picker, because the one
  copy of its catalogue was the one in flight.

These tests are about the second, and about the honesty constraint on fixing
it: remembering must never turn a failure into a success, and must never
project a catalogue for a provider the gate is currently refusing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
PROFILE = "anthropic-hosted"


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    root = tmp_path / "catalogue"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return SQLiteStore(root)


def test_it_records_what_the_provider_published_in_the_order_given(store: SQLiteStore) -> None:
    saved = store.save_provider_catalogue(OWNER, PROFILE, ["opus", "sonnet", "haiku"])

    assert saved == ["opus", "sonnet", "haiku"]
    # The provider's own order, not sorted: a catalogue's first entry is usually
    # the one the provider considers current, and re-sorting loses that.
    assert store.list_provider_catalogue(OWNER, PROFILE) == ["opus", "sonnet", "haiku"]
    assert store.provider_catalogue_listed_at(OWNER, PROFILE) is not None


def test_a_second_listing_replaces_the_first_rather_than_accumulating(
    store: SQLiteStore,
) -> None:
    store.save_provider_catalogue(OWNER, PROFILE, ["opus", "retired-model"])
    store.save_provider_catalogue(OWNER, PROFILE, ["opus", "sonnet"])

    # A model the provider has withdrawn must not survive in the picker because
    # Raiker once saw it. This is the provider's current answer, not a union of
    # every answer it has given.
    assert store.list_provider_catalogue(OWNER, PROFILE) == ["opus", "sonnet"]


def test_an_empty_listing_never_erases_a_known_catalogue(store: SQLiteStore) -> None:
    store.save_provider_catalogue(OWNER, PROFILE, ["opus", "sonnet"])

    # A provider returning nothing is indistinguishable from one that failed in
    # a way the caller did not classify, and replacing a known catalogue with
    # emptiness is the disappearance this store exists to prevent.
    assert store.save_provider_catalogue(OWNER, PROFILE, []) == ["opus", "sonnet"]
    assert store.list_provider_catalogue(OWNER, PROFILE) == ["opus", "sonnet"]


def test_one_owners_catalogue_is_not_anothers(store: SQLiteStore) -> None:
    store.save_provider_catalogue(OWNER, PROFILE, ["opus"])
    store.save_provider_catalogue("principal_other", PROFILE, ["gpt-5"])

    assert store.list_provider_catalogue(OWNER, PROFILE) == ["opus"]
    assert store.list_provider_catalogue("principal_other", PROFILE) == ["gpt-5"]


def test_an_unknown_profile_has_no_catalogue_rather_than_someone_elses(
    store: SQLiteStore,
) -> None:
    store.save_provider_catalogue(OWNER, PROFILE, ["opus"])

    assert store.list_provider_catalogue(OWNER, "openai-hosted") == []
    assert store.provider_catalogue_listed_at(OWNER, "openai-hosted") is None


def test_blank_and_duplicate_names_are_dropped_before_they_reach_a_picker(
    store: SQLiteStore,
) -> None:
    saved = store.save_provider_catalogue(OWNER, PROFILE, ["opus", " opus ", "  ", "sonnet"])

    assert saved == ["opus", "sonnet"]


# ── Disconnecting is not an outage ───────────────────────────────────────────


def test_disconnecting_a_provider_forgets_what_it_published(tmp_path: Path) -> None:
    """The other direction of the disappearance defect.

    Remembering a catalogue is right for a provider that is briefly unreachable
    and wrong for one the owner has disconnected: leaving the rows behind offers
    every picker a list of models Raiker can no longer reach, drawn exactly like
    one it can.
    """
    from raiker.models.connections import clear_model_connection

    root = tmp_path / "disconnect"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    store = SQLiteStore(root)
    store.save_provider_catalogue(OWNER, PROFILE, ["claude-opus-5", "claude-sonnet-5"])
    assert store.list_provider_catalogue(OWNER, PROFILE) == [
        "claude-opus-5",
        "claude-sonnet-5",
    ]

    clear_model_connection(store, OWNER, PROFILE)

    assert store.list_provider_catalogue(OWNER, PROFILE) == []
    assert store.provider_catalogue_listed_at(OWNER, PROFILE) is None


def test_disconnecting_one_provider_leaves_another_alone(tmp_path: Path) -> None:
    from raiker.models.connections import clear_model_connection

    root = tmp_path / "disconnect-scoped"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    store = SQLiteStore(root)
    store.save_provider_catalogue(OWNER, PROFILE, ["claude-opus-5"])
    store.save_provider_catalogue(OWNER, "openai-hosted", ["gpt-5"])

    clear_model_connection(store, OWNER, PROFILE)

    assert store.list_provider_catalogue(OWNER, PROFILE) == []
    assert store.list_provider_catalogue(OWNER, "openai-hosted") == ["gpt-5"]


def test_forgetting_a_catalogue_that_is_not_there_is_not_an_error(tmp_path: Path) -> None:
    root = tmp_path / "disconnect-empty"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    store = SQLiteStore(root)

    assert store.forget_provider_catalogue(OWNER, PROFILE) == 0
