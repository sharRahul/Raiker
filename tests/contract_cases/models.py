"""Models: readiness, decisions, operations, the library, Hugging Face, pricing,
capacity, usage, connections, setup, speech, images and language."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.models.huggingface import HfDownloadPreview, HfSearchResult, HfVariant
from raiker.models.local_operations import ModelOperationRequest, ModelOperationService
from raiker.storage.sqlite import SQLiteStore
from tests.contract_cases.base import Call, Cases, Seed, patched, plain

OWNER = "principal_owner"
OLLAMA = "ollama-local-openai-compatible"
REVISION = "0123456789abcdef0123456789abcdef01234567"


def _library(ws: Path, client: TestClient, h: dict[str, str]) -> Path:
    """An approved, empty model-library root."""
    root = ws.parent / "models"
    root.mkdir(parents=True, exist_ok=True)
    added = client.post("/api/model-library/roots", json={"path": str(root)}, headers=h)
    assert added.status_code == 200, added.text
    return root


def _operation(ws: Path, kind: str = "pull", state: str | None = None) -> str:
    service = ModelOperationService(SQLiteStore(ws))
    operation = service.start(
        OWNER, ModelOperationRequest(kind=kind, target="llama3", confirmed=True), payload={"model": "llama3"}
    )
    if state == "failed":
        service.fail(OWNER, operation.operation_id, code="contract_failure")
    return operation.operation_id


def _on_operation(suffix: str, state: str | None = None, method_suffix: str = "") -> Seed:
    def seed(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
        return f"/api/model-operations/{_operation(ws, state=state)}{suffix}{method_suffix}"

    return seed


def _folder(ws: Path, name: str = "library") -> Path:
    folder = ws.parent / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _operations(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _operation(ws)
    return "/api/model-operations"


def _after_library(path: str) -> Seed:
    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        _library(ws, client, h)
        return path

    return seed


def _add_root(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    return "/api/model-library/roots", {"path": str(_folder(ws))}


def _remove_root(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/model-library/roots", {"path": str(_library(ws, client, h))}


def _backup(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    return "/api/setup/backup/create", {"target": str(_folder(ws, "backups"))}


# A minimal GGUF v3: no tensors, and the two metadata keys a scan identifies it by.
_GGUF = (
    b"GGUF" + (3).to_bytes(4, "little") + (0).to_bytes(8, "little") + (2).to_bytes(8, "little")
    + (12).to_bytes(8, "little") + b"general.name" + (8).to_bytes(4, "little")
    + (4).to_bytes(8, "little") + b"Tiny"
    + (20).to_bytes(8, "little") + b"general.architecture" + (8).to_bytes(4, "little")
    + (5).to_bytes(8, "little") + b"llama"
)


def _deploy(name: str, suffix: str) -> Seed:
    """A complete GGUF file or MLX folder in an approved root, and its deploy path."""

    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        root = _library(ws, client, h)
        if name.endswith(".gguf"):
            (root / name).write_bytes(_GGUF)
        else:
            (root / name).mkdir()
            (root / name / "config.json").write_text(
                json.dumps({"model_type": "qwen2", "quantization": {"bits": 4}}), encoding="utf-8"
            )
            (root / name / "model.safetensors").write_bytes(b"weights")
        models = client.post("/api/model-library/rescan", headers=h).json()["models"]
        return f"/api/model-library/{models[0]['model_id']}{suffix}"

    return seed


def _quiet(worker: str) -> Callable[[Any], None]:
    """Replace the background worker a route queues: the case is about its answer."""

    def patch(monkeypatch: Any) -> None:
        import raiker.api.routes_models as routes

        monkeypatch.setattr(routes, worker, lambda *args: None)

    return patch


def _conversion(path: str) -> Seed:
    """A safetensors checkpoint of a supported architecture, beside an output folder."""

    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        root = _library(ws, client, h)
        source, output = root / "source", root / "converted"
        source.mkdir()
        output.mkdir()
        (source / "config.json").write_text(
            json.dumps({"architectures": ["LlamaForCausalLM"]}), encoding="utf-8"
        )
        (source / "model.safetensors").write_bytes(b"weights")
        return path, {
            "source": str(source), "output": str(output), "revision": REVISION,
            "quantization": "Q4_K_M", "confirmed": True,
        }

    return seed


_SELECTION = {"repo_id": "acme/tiny", "revision": REVISION, "files": ["tiny.Q4_K_M.gguf"]}


class _FakeHub:
    """The Hub's answers, so no case reaches huggingface.co."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None: ...

    def search(self, query: str, *, token: str | None = None, limit: int = 20) -> list[HfSearchResult]:
        return [HfSearchResult("acme/tiny", 10, 1, False)]

    def trending(self, *, token: str | None = None, limit: int = 12) -> list[HfSearchResult]:
        return self.search("")

    def variants(self, repo_id: str, *, revision: str | None, token: str | None) -> list[HfVariant]:
        return [HfVariant(repo_id, REVISION, ("tiny.Q4_K_M.gguf",), "gguf", "Q4_K_M", 1, 0, False, None, True)]

    def dry_run(self, repo_id: str, variant: HfVariant, *, token: str | None) -> HfDownloadPreview:
        return HfDownloadPreview(repo_id, variant.revision, variant.files, 1, 0, 1)


def _fake_hub(monkeypatch: Any) -> None:
    import raiker.api.routes_models as routes

    monkeypatch.setattr(routes, "_hugging_face_service", lambda request: _FakeHub())


def _fake_download(monkeypatch: Any) -> None:
    _fake_hub(monkeypatch)
    _quiet("_dispatch_operation")(monkeypatch)


def _download(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    root = _library(ws, client, h)
    return "/api/hugging-face/download", {**_SELECTION, "confirmed": True, "destination": str(root)}


def _budget(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    from raiker.models.connections import put_model_connection

    put_model_connection(SQLiteStore(ws), OWNER, "anthropic-hosted", {"connection_kind": "api_key"})
    return "/api/models/anthropic-hosted/weekly-budget", {"token_budget": 100000}


class _FakeCodex:
    """A local Codex client already signed in to a ChatGPT subscription."""

    async def status(self, _principal_id: str) -> Any:
        from raiker.models.codex_app_server import CodexAccountStatus

        return CodexAccountStatus(signed_in=True, plan_type="plus")

    async def start_login(self, _principal_id: str) -> Any:
        from raiker.models.codex_app_server import CodexLogin

        return CodexLogin(login_id="login_contract")

    async def disconnect(self, _principal_id: str) -> None: ...


def _fake_codex(monkeypatch: Any) -> None:
    import raiker.api.routes_dashboard as routes

    codex = _FakeCodex()
    monkeypatch.setattr(routes, "_codex_sessions", lambda request: codex)


# The smallest thing that is genuinely a PNG.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _image(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    """Image generation enabled the way an owner enables it, then one prompt."""
    from raiker.contracts.ids import utc_now
    from raiker.control.service import RuntimeControlService

    control = RuntimeControlService(ws)
    control.activate_runtime_mode("local_single_user_runtime", None, "test")
    with SQLiteStore(ws).connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) "
            "VALUES (?, ?, ?, ?)",
            ("image_generation", OWNER, utc_now(), "docs/threat-models/models.md"),
        )
    enabled = control.set_capability_state(
        "image_generation", "enabled_runtime", None, "test", confirmation_token="confirm"
    )
    assert enabled.ok, enabled.reason_code
    return "/api/images", {"profile_id": "openai-hosted", "prompt": "a cat", "size": "1024x1024"}


def _fake_image_provider(monkeypatch: Any) -> None:
    from raiker.runtime.executors import tier2_image

    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-contract")
    monkeypatch.setattr(
        tier2_image, "post_json",
        lambda *args, **kwargs: {"data": [{"b64_json": base64.b64encode(_PNG).decode()}]},
    )



CASES: Cases = {
    ("GET", "/api/model-readiness"): plain("/api/model-readiness"),
    ("POST", "/api/model-readiness/check"): plain(
        "/api/model-readiness/check", {"profile_id": OLLAMA, "model": "llama3"}
    ),
    ("GET", "/api/surface-models"): plain("/api/surface-models"),
    ("PUT", "/api/surface-models"): plain(
        "/api/surface-models", {"surface": "chat", "profile_id": OLLAMA, "model": "llama3"}
    ),
    ("GET", "/api/model-decision"): plain("/api/model-decision?surface=chat"),
    ("GET", "/api/model-decisions"): plain("/api/model-decisions"),
    ("GET", "/api/model-setup"): plain("/api/model-setup"),
    ("PUT", "/api/model-setup"): plain(
        "/api/model-setup", {"status": "in_progress", "step": "provider", "path": "ollama"}
    ),
    ("GET", "/api/local-runtimes"): plain("/api/local-runtimes"),
    ("POST", "/api/local-runtimes/detect"): plain("/api/local-runtimes/detect"),
    ("POST", "/api/model-operations/preview"): plain(
        "/api/model-operations/preview", {"kind": "install", "target": "ollama"}
    ),
    ("GET", "/api/model-operations"): _operations,
    ("POST", "/api/model-operations"): plain(
        "/api/model-operations", {"kind": "install", "target": "ollama", "confirmed": True}
    ),
    ("POST", "/api/model-operations/{operation_id}/cancel"): _on_operation("/cancel"),
    ("POST", "/api/model-operations/{operation_id}/retry"): _on_operation("/retry", state="failed"),
    ("GET", "/api/model-operations/{operation_id}/partial-files"): _on_operation("/partial-files"),
    ("POST", "/api/model-operations/{operation_id}/delete-partial-files"): _on_operation(
        "/delete-partial-files", method_suffix="?confirmed=true"
    ),
    ("DELETE", "/api/model-operations/{operation_id}"): _on_operation("", state="failed"),
    ("GET", "/api/model-library"): _after_library("/api/model-library"),
    ("POST", "/api/model-library/roots"): _add_root,
    ("DELETE", "/api/model-library/roots"): _remove_root,
    ("POST", "/api/model-library/rescan"): _after_library("/api/model-library/rescan"),
    ("POST", "/api/model-library/{model_id:path}/deploy"): patched(
        _deploy("tiny.gguf", "/deploy"), _quiet("_run_local_deployment")
    ),
    ("POST", "/api/model-library/{model_id:path}/deploy-mlx"): patched(
        _deploy("Qwen-MLX-4bit", "/deploy-mlx"), _quiet("_run_mlx_deployment")
    ),
    ("POST", "/api/model-conversion/preview"): _conversion("/api/model-conversion/preview"),
    ("POST", "/api/model-conversion"): patched(
        _conversion("/api/model-conversion"), _quiet("_run_model_conversion")
    ),
    ("POST", "/api/ollama/pull"): patched(
        plain("/api/ollama/pull", {"model": "llama3", "confirmed": True}), _quiet("_pull_ollama_model")
    ),
    ("GET", "/api/hugging-face/search"): patched(plain("/api/hugging-face/search?query=tiny"), _fake_hub),
    ("GET", "/api/hugging-face/trending"): patched(plain("/api/hugging-face/trending"), _fake_hub),
    ("GET", "/api/hugging-face/{owner}/{repository}/variants"): patched(
        plain("/api/hugging-face/acme/tiny/variants"), _fake_hub
    ),
    ("POST", "/api/hugging-face/download/preview"): patched(
        plain("/api/hugging-face/download/preview", _SELECTION), _fake_hub
    ),
    ("POST", "/api/hugging-face/download"): patched(_download, _fake_download),
    ("PUT", "/api/hugging-face/credential"): plain("/api/hugging-face/credential", {"token": "hf_contract"}),
    ("GET", "/api/models"): plain("/api/models"),
    ("GET", "/api/models/weekly-usage"): plain("/api/models/weekly-usage"),
    ("PUT", "/api/models/{profile_id}/weekly-budget"): _budget,
    ("GET", "/api/models/chatgpt-codex/status"): patched(plain("/api/models/chatgpt-codex/status"), _fake_codex),
    ("POST", "/api/models/chatgpt-codex/connection"): patched(
        plain("/api/models/chatgpt-codex/connection"), _fake_codex
    ),
    ("POST", "/api/models/chatgpt-codex/login"): patched(plain("/api/models/chatgpt-codex/login"), _fake_codex),
    ("DELETE", "/api/models/chatgpt-codex/connection"): patched(
        plain("/api/models/chatgpt-codex/connection"), _fake_codex
    ),
    ("GET", "/api/models/pricing"): plain("/api/models/pricing"),
    ("POST", "/api/models/pricing/refresh"): plain("/api/models/pricing/refresh"),
    ("GET", "/api/models/capacities"): plain("/api/models/capacities"),
    ("POST", "/api/models/capacities/refresh"): plain("/api/models/capacities/refresh"),
    ("PUT", "/api/models/{profile_id}/capacity"): plain(
        f"/api/models/{OLLAMA}/capacity", {"model": "llama3", "tokens": 8192, "reason": "contract"}
    ),
    ("PUT", "/api/models/{profile_id}/price"): plain(
        "/api/models/anthropic-hosted/price",
        {"model": "claude-haiku-4-5-20251001", "input_per_mtok": "1", "output_per_mtok": "5", "reason": "contract"},
    ),
    ("PUT", "/api/models/{profile_id}/available-models"): plain(
        f"/api/models/{OLLAMA}/available-models", {"models": ["llama3"]}
    ),
    ("GET", "/api/models/{profile_id}/provider-models"): plain(f"/api/models/{OLLAMA}/provider-models"),
    ("PUT", "/api/model-selection"): plain("/api/model-selection", {"profile_id": OLLAMA, "model": "llama3"}),
    ("PUT", "/api/model-advisor"): plain("/api/model-advisor", {"profile_id": None}),
    ("PUT", "/api/model-fallback"): plain("/api/model-fallback", {"profile_ids": []}),
    ("PUT", "/api/models/{profile_id}/connection"): plain(
        f"/api/models/{OLLAMA}/connection", {"endpoint": "http://127.0.0.1:11434/v1"}
    ),
    ("POST", "/api/models/catalogues/refresh"): plain("/api/models/catalogues/refresh", {"profile_ids": []}),
    ("GET", "/api/setup"): plain("/api/setup"),
    ("PUT", "/api/setup"): plain("/api/setup", {"status": "in_progress", "stage": "model"}),
    ("POST", "/api/setup/backup/create"): _backup,
    ("GET", "/api/speech/runtime"): plain("/api/speech/runtime"),
    ("PUT", "/api/speech/runtime"): plain(
        "/api/speech/runtime", {"endpoint": "http://127.0.0.1:9", "model": "whisper"}
    ),
    ("POST", "/api/speech/runtime/probe"): plain(
        "/api/speech/runtime/probe", {"endpoint": "http://127.0.0.1:9", "model": "whisper"}
    ),
    ("GET", "/api/images"): plain("/api/images"),
    ("POST", "/api/images"): patched(_image, _fake_image_provider),
    ("POST", "/api/language/check"): plain("/api/language/check", {"text": "This are wrong.", "language": "en-US"}),
}
