"""BR-D04 — a selected model's review of the exact patch.

* What reaches the model is the patch, credential-redacted and framed as data.
* The answer is read strictly: findings outside the patch are dropped, an
  unverified "high" is shown as medium at most, and unreadable JSON is said.
* The reading is stored by patch fingerprint and model, so the same model is
  never asked twice about the same patch; it is audited without content.
* A model's finding never keeps a turn from being, or makes it, verified.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.build_outcome import classify_build_turn
from raiker.models.contracts import ModelResponse
from raiker.review.model_review import parse_answer, review_messages
from raiker.storage.sqlite import SQLiteStore

#: What Build's composer sends: a connected profile and a concrete model.
CHOICE = {"model_profile": "anthropic-hosted", "model": "claude-haiku-5-5"}

DIFF = (
    "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
    "@@ -1,2 +1,3 @@\n def ping():\n-    return 1\n+    token = 'ghp_" + "a" * 36 + "'\n+    return 1 / 0\n"
)


def test_the_patch_sent_to_the_model_is_redacted_and_framed_as_data() -> None:
    messages, truncated = review_messages(DIFF)
    assert not truncated
    assert messages[0]["role"] == "system" and "untrusted data" in messages[0]["content"]
    user = messages[1]["content"]
    assert "<<<PATCH" in user and "PATCH>>>" in user
    assert "ghp_" + "a" * 36 not in user
    assert "return 1 / 0" in user


def test_the_answer_is_kept_to_the_patch_and_never_claims_high() -> None:
    answer = json.dumps(
        {
            "findings": [
                {"path": "b/service.py", "line": 4, "severity": "high", "confidence": "high",
                 "title": "Division by zero", "evidence": "returns 1 / 0", "next_step": "Return 1."},
                {"path": "other.py", "line": 1, "severity": "low", "title": "Not in this patch"},
                {"path": "service.py", "severity": "bogus", "title": "Odd severity"},
                {"title": ""},
            ]
        }
    )
    findings = parse_answer(f"Here you go:\n```json\n{answer}\n```", ["service.py"])
    assert [item["title"] for item in findings] == ["Division by zero", "Odd severity"]
    assert findings[0]["severity"] == "medium" and findings[0]["path"] == "service.py"
    assert findings[1]["severity"] == "low" and findings[1]["confidence"] == "low"
    assert all(item["source"] == "model" and item["rule"] == "model_review" for item in findings)


def test_an_unreadable_answer_is_said_not_shown_as_clean() -> None:
    with pytest.raises(ValueError, match="model_review_unreadable"):
        parse_answer("Looks fine to me!", ["service.py"])
    with pytest.raises(ValueError, match="model_review_unreadable"):
        parse_answer('{"verdict": "ok"}', ["service.py"])


def test_a_model_finding_never_decides_verification() -> None:
    write = {"tool_name": "write_file", "status": "success", "completed_at": "2026-10-19T10:00:05Z",
             "arguments_json": json.dumps({"path": "a.py", "text": "x\n"})}
    run = {"run_id": "c", "safe_display": "pytest -q", "started_at": "2026-10-19T10:00:10Z",
           "state": "succeeded", "exit_code": 0}
    review = {"fingerprint": "f", "counts": {"high": 0, "medium": 1}, "findings": [
        {"rule": "model_review", "severity": "medium", "source": "model"}]}
    outcome = classify_build_turn(tool_actions=[write], command_runs=[run], checks=["pytest -q"], review=review)
    assert outcome["outcome"] == "completed_verified"


@pytest.fixture
def api(tmp_path: Path) -> tuple[TestClient, dict[str, str], Path]:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, tmp_path


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
        check=True, capture_output=True,
    )


def _connect(client: TestClient, headers: dict[str, str], ws: Path) -> str:
    root = ws / "app"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "service.py").write_text("def ping():\n    return 1\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    resp = client.post("/api/code/repos", json={"kind": "local", "path": "app"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["repo_id"])


def test_the_model_reads_a_patch_once_and_the_reading_is_audited_without_content(
    api: tuple[TestClient, dict[str, str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.models.router import ModelRouter

    client, headers, ws = api
    repo_id = _connect(client, headers, ws)
    calls: list[list[Any]] = []

    async def achat(self: Any, provider: str, model: str, messages: Any, tools: Any = None, **_: Any) -> ModelResponse:
        calls.append(list(messages))
        return ModelResponse(text=json.dumps({"findings": [
            {"path": "service.py", "line": 2, "severity": "medium", "confidence": "medium",
             "title": "Division by zero", "evidence": "1 / 0 always raises", "next_step": "Return 1."}]}))

    monkeypatch.setattr(ModelRouter, "achat", achat)

    # Nothing to read: no call is made.
    empty = client.post(f"/api/code/repos/{repo_id}/review/model", json=CHOICE, headers=headers).json()
    assert empty["has_changes"] is False and empty["reason_code"] == "no_changes" and calls == []

    (ws / "app" / "service.py").write_text("def ping():\n    return 1 / 0\n")
    first = client.post(f"/api/code/repos/{repo_id}/review/model", json=CHOICE, headers=headers)
    assert first.status_code == 200, first.text
    reading = first.json()["model_review"]
    assert first.json()["reused"] is False
    assert reading["findings"][0]["title"] == "Division by zero"
    assert reading["findings"][0]["source"] == "model"
    assert reading["provider"] == "anthropic" and reading["model"] == "claude-haiku-5-5"

    # The same patch and the same model: the stored reading, and no second call.
    again = client.post(f"/api/code/repos/{repo_id}/review/model", json=CHOICE, headers=headers).json()
    assert again["reused"] is True and len(calls) == 1
    assert again["model_review"]["fingerprint"] == reading["fingerprint"]

    # The deterministic review's read carries the latest model reading of this patch.
    read = client.get(f"/api/code/repos/{repo_id}/review", headers=headers).json()
    assert read["model_review"]["fingerprint"] == reading["fingerprint"]

    # A changed patch has no reading until one is asked for.
    (ws / "app" / "service.py").write_text("def ping():\n    return 2 / 0\n")
    assert client.get(f"/api/code/repos/{repo_id}/review", headers=headers).json()["model_review"] is None

    store = SQLiteStore(ws)
    with store.connect() as connection:
        paths = {
            str(row[0])
            for row in connection.execute(
                "SELECT jsonl_path FROM events_index WHERE event_type = 'patch_model_review_completed'"
            ).fetchall()
        }
    payloads = [
        json.loads(line)["payload"]
        for path in paths
        for line in Path(path if Path(path).is_absolute() else ws / path).read_text(encoding="utf-8").splitlines()
        if "patch_model_review_completed" in line
    ]
    assert [payload["reused"] for payload in payloads] == [False, True]
    assert all("Division" not in json.dumps(payload) and "1 / 0" not in json.dumps(payload) for payload in payloads)


def test_an_unknown_profile_is_refused_not_replaced(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, headers, ws = api
    repo_id = _connect(client, headers, ws)
    (ws / "app" / "service.py").write_text("def ping():\n    return 3\n")
    resp = client.post(
        f"/api/code/repos/{repo_id}/review/model", json={"model_profile": "no-such-profile"}, headers=headers
    )
    assert resp.status_code == 422
    assert "model_review_profile_unknown" in resp.text


def test_an_unreadable_answer_is_a_refusal(
    api: tuple[TestClient, dict[str, str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.models.router import ModelRouter

    client, headers, ws = api
    repo_id = _connect(client, headers, ws)

    async def achat(self: Any, *args: Any, **kwargs: Any) -> ModelResponse:
        return ModelResponse(text="It all looks fine.")

    monkeypatch.setattr(ModelRouter, "achat", achat)
    (ws / "app" / "service.py").write_text("def ping():\n    return 4\n")
    resp = client.post(f"/api/code/repos/{repo_id}/review/model", json=CHOICE, headers=headers)
    assert resp.status_code == 502 and "model_review_unreadable" in resp.text
    assert client.get(f"/api/code/repos/{repo_id}/review", headers=headers).json()["model_review"] is None


# ── BR-D05 — signed review evidence and commit signature read-back ──────────


def test_a_stored_review_is_signed_and_a_changed_one_reads_invalid(
    api: tuple[TestClient, dict[str, str], Path],
) -> None:
    client, headers, ws = api
    repo_id = _connect(client, headers, ws)
    (ws / "app" / "service.py").write_text("def ping():\n    breakpoint()\n    return 1\n")
    taken = client.post(f"/api/code/repos/{repo_id}/review", headers=headers).json()
    assert taken["attestation"]["state"] == "verified"
    assert taken["attestation"]["key_id"]
    # The signature bytes are never part of what the owner is sent.
    assert "attestation" not in taken["review"]
    assert client.get(f"/api/code/repos/{repo_id}/review", headers=headers).json()["attestation"]["state"] == "verified"

    # Something rewrites the stored review: dropping a finding breaks the signature.
    store = SQLiteStore(ws)
    with store.connect() as connection:
        row = connection.execute("SELECT review_json FROM patch_reviews WHERE repo_id = ?", (repo_id,)).fetchone()
        stored = json.loads(str(row["review_json"]))
        stored["findings"] = []
        connection.execute(
            "UPDATE patch_reviews SET review_json = ? WHERE repo_id = ?", (json.dumps(stored), repo_id)
        )
    read = client.get(f"/api/code/repos/{repo_id}/review", headers=headers).json()
    assert read["attestation"]["state"] == "invalid"


def test_a_model_reading_is_signed_too(
    api: tuple[TestClient, dict[str, str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.models.router import ModelRouter

    client, headers, ws = api
    repo_id = _connect(client, headers, ws)

    async def achat(self: Any, *args: Any, **kwargs: Any) -> ModelResponse:
        return ModelResponse(text='{"findings": []}')

    monkeypatch.setattr(ModelRouter, "achat", achat)
    (ws / "app" / "service.py").write_text("def ping():\n    return 5\n")
    answer = client.post(f"/api/code/repos/{repo_id}/review/model", json=CHOICE, headers=headers).json()
    assert answer["model_attestation"]["state"] == "verified"
    assert "attestation" not in answer["model_review"]


def test_an_unsigned_review_says_so_rather_than_verified() -> None:
    from raiker.review.review_attestation import verify_review

    assert verify_review(None, owner_principal_id="o", repo_id="r", review={"fingerprint": "f"}) == "unsigned"


def test_commit_signatures_are_read_back_in_words(tmp_path: Path) -> None:
    from raiker.control.build_provenance import read_provenance

    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "a.txt").write_text("a\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "plain")
    rows = read_provenance(None, root, user_id=None)
    assert rows[0]["signature"] == "none"


def test_a_placeholder_default_is_refused_as_no_model_chosen(
    api: tuple[TestClient, dict[str, str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Found live: with nothing chosen, the owner default was `ollama/<model>` and the review 502'd."""
    import raiker.models.owner_runtime as owner_runtime
    from raiker.models.router import ModelRouter

    client, headers, ws = api
    repo_id = _connect(client, headers, ws)
    calls: list[str] = []

    async def achat(self: Any, provider: str, model: str, *args: Any, **kwargs: Any) -> ModelResponse:
        calls.append(model)
        return ModelResponse(text='{"findings": []}')

    real = owner_runtime.owner_model_runtime

    def placeholder(store: Any, owner: str, writer: Any) -> Any:
        router, _selected = real(store, owner, writer)
        return router, ("ollama", "<model>")

    monkeypatch.setattr(ModelRouter, "achat", achat)
    monkeypatch.setattr(owner_runtime, "owner_model_runtime", placeholder)
    (ws / "app" / "service.py").write_text("def ping():\n    return 6\n")
    resp = client.post(f"/api/code/repos/{repo_id}/review/model", json={}, headers=headers)
    assert resp.status_code == 422 and "model_review_model_required" in resp.text
    assert calls == []
