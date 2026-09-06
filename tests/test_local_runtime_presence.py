"""BUG-270 — a fresh install must not name a model nobody has.

`ollama-local-openai-compatible` ships `gemma4:31b-cloud` and is the only
`is_native_default`, so a brand-new workspace selected it and printed that model
in the setup meter, the Global model control and both composer chips on a host
with no `ollama` binary. The profile has always declared
`disabled_until_provider_detected`; these are the tests for the detector that
finally makes the declaration mean something.

Two properties matter as much as the outcome:

* **Detection never opens a connection.** It is a PATH lookup, and a status read
  reads the row it wrote (FIXED-357).
* **"Not looked yet" is not "absent".** An unknown answer about someone else's
  machine must not become a claim in either direction.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models import local_presence
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def bare_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """A host with none of the local runtimes installed.

    Several tests below assert what Raiker says when nothing is on the machine.
    They used to get that by *assuming* the machine had nothing, so they passed
    on CI and failed on any developer laptop with Ollama installed — tests about
    a workspace were reading a fact about the computer running them. The absence
    is stated here instead, and `test_a_present_runtime_records_the_executable`
    states the presence the same way.
    """
    monkeypatch.setattr(local_presence.shutil, "which", lambda _name: None)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "local_runtime_presence"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def owner_token(workspace: Path) -> str:
    token, _session = ApiSessionStore(workspace).create_session("principal_owner")
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestDetection:
    def test_an_absent_runtime_is_recorded_as_absent(
        self, workspace: Path, bare_host: None
    ) -> None:
        store = SQLiteStore(workspace)
        results = local_presence.detect(store, runtimes=("ollama",))
        assert results["ollama"].present is False
        assert results["ollama"].executable is None
        assert local_presence.presence(store, "ollama") is False

    def test_a_present_runtime_records_the_executable_it_found(
        self, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        found = tmp_path / "ollama"
        monkeypatch.setattr(
            local_presence.shutil, "which", lambda name: str(found) if name == "ollama" else None
        )
        store = SQLiteStore(workspace)
        results = local_presence.detect(store, runtimes=("ollama",), force=True)
        assert results["ollama"].present is True
        assert results["ollama"].executable == str(found)
        assert local_presence.presence(store, "ollama") is True

    def test_a_runtime_nobody_has_looked_for_is_unknown_not_absent(
        self, workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        assert local_presence.presence(store, "ollama") is None
        # A provider with no detector is unknown for a different reason and gets
        # the same answer, because in both cases Raiker does not know.
        assert local_presence.presence(store, "anthropic") is None

    def test_a_fresh_row_is_not_reprobed(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = SQLiteStore(workspace)
        store.save_local_runtime_presence("ollama", present=True, executable="/usr/bin/ollama")
        calls: list[str] = []

        def counted(name: str) -> str | None:
            calls.append(name)
            return None

        monkeypatch.setattr(local_presence.shutil, "which", counted)
        assert local_presence.detect(store, runtimes=("ollama",))["ollama"].present is True
        assert calls == []

    def test_a_stale_row_is_looked_at_again(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An install or an uninstall is rare, but it does happen."""
        store = SQLiteStore(workspace)
        store.save_local_runtime_presence("ollama", present=True, executable="/usr/bin/ollama")
        stale = (
            datetime.now(UTC) - timedelta(seconds=local_presence.DETECTION_TTL_SECONDS + 60)
        ).isoformat()
        with store.connect() as connection:
            connection.execute(
                "UPDATE local_runtime_presence SET detected_at = ? WHERE runtime = ?",
                (stale, "ollama"),
            )
        monkeypatch.setattr(local_presence.shutil, "which", lambda _name: None)
        assert local_presence.detect(store, runtimes=("ollama",))["ollama"].present is False


class TestRoutes:
    def test_the_read_route_reports_what_was_detected(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        SQLiteStore(workspace).save_local_runtime_presence(
            "ollama", present=True, executable="/usr/local/bin/ollama"
        )
        body = client.get("/api/local-runtimes", headers=_auth(owner_token)).json()
        row = next(item for item in body["runtimes"] if item["runtime"] == "ollama")
        assert row["present"] is True
        assert row["executable"] == "/usr/local/bin/ollama"

    def test_detect_looks_again_for_an_owner_who_just_installed_one(
        self, client: TestClient, owner_token: str, workspace: Path, bare_host: None
    ) -> None:
        SQLiteStore(workspace).save_local_runtime_presence(
            "ollama", present=True, executable="/usr/local/bin/ollama"
        )
        body = client.post("/api/local-runtimes/detect", headers=_auth(owner_token)).json()
        row = next(item for item in body["runtimes"] if item["runtime"] == "ollama")
        # Nothing is installed on this host (`bare_host`), so a forced look
        # corrects the row rather than trusting the cache it was told to bypass.
        assert row["present"] is False

    def test_both_routes_require_auth(self, client: TestClient) -> None:
        assert client.get("/api/local-runtimes").status_code == 401
        assert client.post("/api/local-runtimes/detect").status_code == 401


class TestTheCountThatWasWrong:
    def test_empty_local_slots_are_not_counted_as_models_set_up(
        self, client: TestClient, owner_token: str, bare_host: None
    ) -> None:
        """The other half of "5 models set up" on a machine with none.

        Four llama.cpp slots carry `local-gguf`…`local-gguf-4` — aliases Raiker
        itself invents when it deploys into a slot, not models anyone has — and
        the old predicate counted every one of them because they are not the
        `<model>` placeholder.
        """
        body = client.get("/api/models", headers=_auth(owner_token)).json()
        assert body["usable_provider_count"] == 0
        slots = [
            profile
            for profile in body["profiles"]
            if profile["profile_id"].startswith("raiker-local-llama-cpp")
        ]
        assert slots, "the shipped llama.cpp slots should still be listed for setup"
        assert all(profile["configured"] is False for profile in slots)

    def test_a_deployed_slot_counts(
        self, client: TestClient, owner_token: str, workspace: Path, bare_host: None
    ) -> None:
        """Deploying a GGUF writes a configured model; that is the owner's own evidence."""
        SQLiteStore(workspace).save_configured_model(
            "principal_owner", "raiker-local-llama-cpp", "local-gguf"
        )
        body = client.get("/api/models", headers=_auth(owner_token)).json()
        slot = next(
            profile
            for profile in body["profiles"]
            if profile["profile_id"] == "raiker-local-llama-cpp"
        )
        assert slot["configured"] is True
        assert body["usable_provider_count"] == 1
