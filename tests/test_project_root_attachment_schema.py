"""Schema for a project whose root is a folder the owner already has.

A project's root used to be one thing: a subpath under the workspace. It is now
one of two, and the columns here are what tell them apart. The invariants worth
protecting in the schema rather than in a service are the ones a second writer
could otherwise violate — which is why one project per attached root is a unique
index and not a check in Python.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_user(User("user_owner", "Owner", None, True, now, now))
    store.insert_principal(OWNER, "human", "Owner", delegated_by_user_id="user_owner")
    return store


@pytest.fixture()
def owner_grant(store: SQLiteStore) -> str:
    store.add_brain_source_grant(OWNER, "granted-abc123", "C:/repo", "repo")
    return "granted-abc123"


def test_existing_projects_default_to_managed(store: SQLiteStore) -> None:
    store.create_project("proj_a", "Alpha", ".raiker/projects/alpha")

    row = store.load_project("proj_a")

    assert row is not None
    assert row["root_kind"] == "managed"
    assert row["root_grant_id"] is None


def test_one_project_per_attached_root(store: SQLiteStore, owner_grant: str) -> None:
    store.create_project("proj_a", "Alpha", "")
    store.create_project("proj_b", "Beta", "")
    assert store.attach_project_root("proj_a", owner_grant) is True

    with pytest.raises(sqlite3.IntegrityError):
        store.attach_project_root("proj_b", owner_grant)


def test_attaching_records_the_grant_and_clears_the_subpath(
    store: SQLiteStore, owner_grant: str
) -> None:
    store.create_project("proj_a", "Alpha", ".raiker/projects/alpha")

    assert store.attach_project_root("proj_a", owner_grant) is True

    row = store.load_project("proj_a")
    assert row is not None
    assert row["root_kind"] == "attached"
    assert row["root_grant_id"] == owner_grant
    assert row["root_subpath"] == ""


def test_detaching_leaves_the_project_rootless_not_managed(
    store: SQLiteStore, owner_grant: str
) -> None:
    store.create_project("proj_a", "Alpha", "")
    store.attach_project_root("proj_a", owner_grant)

    assert store.detach_project_root("proj_a") is True

    row = store.load_project("proj_a")
    assert row is not None
    # Turning it back into a managed project would invent a root the owner
    # never asked for, so it stays attached-with-no-grant.
    assert row["root_kind"] == "attached"
    assert row["root_grant_id"] is None


def test_attach_and_detach_refuse_an_unknown_project(store: SQLiteStore, owner_grant: str) -> None:
    assert store.attach_project_root("proj_absent", owner_grant) is False
    assert store.detach_project_root("proj_absent") is False


def test_grants_are_read_only_until_write_is_enabled(store: SQLiteStore) -> None:
    store.add_brain_source_grant(OWNER, "granted-abc", "C:/repo", "repo")
    assert store.list_brain_source_grants(OWNER)[0]["write_enabled"] == 0

    assert store.set_grant_write_enabled(OWNER, "granted-abc", True) is True

    assert store.list_brain_source_grants(OWNER)[0]["write_enabled"] == 1


def test_enabling_write_on_an_unknown_grant_reports_failure(store: SQLiteStore) -> None:
    assert store.set_grant_write_enabled(OWNER, "granted-absent", True) is False


def test_project_for_grant_finds_the_attached_project(
    store: SQLiteStore, owner_grant: str
) -> None:
    store.create_project("proj_a", "Alpha", "")
    store.attach_project_root("proj_a", owner_grant)

    found = store.project_for_grant(OWNER, owner_grant)

    assert found is not None
    assert found["project_id"] == "proj_a"
    assert store.project_for_grant(OWNER, "granted-nothing") is None


def test_managed_files_carry_a_discovered_mtime_column(store: SQLiteStore) -> None:
    with store.connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(managed_files)")}

    assert "source_mtime_ns" in columns
