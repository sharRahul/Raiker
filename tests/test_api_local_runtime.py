"""The llama.cpp engine routes, end to end through the API with no network."""

from __future__ import annotations

import functools
import hashlib
import io
import tarfile
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

import raiker.api.routes_local_runtime as routes
from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models import local_presence
from raiker.models.llama_cpp import hardware, installer
from raiker.models.llama_cpp.hardware import GpuDevice, HardwareProfile
from raiker.models.llama_cpp.installer import DeviceReport, InstallError
from raiker.models.llama_cpp.planner import MemoryBudget, ModelShape, RuntimeSettings, plan_launch
from raiker.models.llama_cpp.releases import Release, ReleaseAsset
from raiker.models.llama_cpp.supervisor import LlamaSupervisor, SlotHealth
from raiker.storage.sqlite import SQLiteStore
from tests.fixtures.llama_cpp.gguf_writer import llama_metadata, write_gguf

GIB = 1024**3
OWNER = "principal_owner"
TAG = "b7000"


def _tar(name: str) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        data = b"#!/bin/sh\n"
        info = tarfile.TarInfo(f"llama-{TAG}/{installer.EXECUTABLE}")
        info.size, info.mode = len(data), 0o755
        bundle.addfile(info, io.BytesIO(data))
        marker = name.encode()
        info = tarfile.TarInfo(f"llama-{TAG}/BUILD")
        info.size = len(marker)
        bundle.addfile(info, io.BytesIO(marker))
    return buffer.getvalue()


def _profile() -> HardwareProfile:
    gpu = GpuDevice("nvidia", "Test GPU", 12 * GIB, 11 * GIB, True, cuda_version="12.8")
    return HardwareProfile(
        "linux", "x64", 8, 32 * GIB, 20 * GIB, (gpu,), True, False,
        ("cuda", "vulkan", "cpu"), "cuda", "Test GPU runs local models fastest through CUDA.",
    )


class World:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.workspace = tmp_path / "ws"
        self.workspace.mkdir()
        self.library = tmp_path / "models"
        self.library.mkdir()
        bootstrap_owner("owner", "Owner", workspace_root=self.workspace)
        token, _ = ApiSessionStore(self.workspace).create_session(OWNER)
        self.app = create_app(self.workspace)
        self.client = TestClient(self.app)
        self.h = {"Authorization": f"Bearer {token}"}
        names = {
            "cuda": f"llama-{TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz",
            "cudart": f"cudart-llama-{TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz",
            "vulkan": f"llama-{TAG}-bin-ubuntu-vulkan-x64.tar.gz",
            "cpu": f"llama-{TAG}-bin-ubuntu-x64.tar.gz",
        }
        self.blobs = {name: _tar(key) for key, name in names.items()}
        assets = tuple(
            ReleaseAsset(name, f"https://github.com/ggml-org/llama.cpp/releases/download/{TAG}/{name}", len(blob),
                         f"sha256:{hashlib.sha256(blob).hexdigest()}")
            for name, blob in self.blobs.items()
        )
        self.fetched: list[str | None] = []

        def fetch(tag: str | None = None) -> Release:
            self.fetched.append(tag)
            return Release(TAG, "2026-10-30T00:00:00Z", assets)

        monkeypatch.setattr(routes, "fetch_release", fetch)
        monkeypatch.setattr(hardware, "detect", lambda probe=None, force=False: _profile())
        self.no_device: set[str] = set()

        def verify(_executable: Path, backend: str) -> tuple[str, tuple[DeviceReport, ...]]:
            if backend in self.no_device:
                raise InstallError("llama_cpp_backend_no_device")
            devices = () if backend == "cpu" else (DeviceReport("GPU0", "Test GPU", 12 * GIB, 11 * GIB),)
            return "version: 7000 (test)", devices

        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=self.blobs[request.url.path.rsplit("/", 1)[-1]])
            )
        )
        monkeypatch.setattr(installer, "install", functools.partial(installer.install, client=client, verify=verify))
        monkeypatch.setattr(installer.shutil, "which", lambda _name: None)

    def model(self, name: str = "tiny.gguf") -> str:
        write_gguf(self.library / name, llama_metadata(layers=24, context=32768), pad_bytes=4096)
        self.client.post("/api/model-library/roots", headers=self.h, json={"path": str(self.library)})
        models = self.client.post("/api/model-library/rescan", headers=self.h).json()["models"]
        return str(next(item["model_id"] for item in models if item["name"] == "Test Llama"))

    def operation(self, operation_id: str) -> dict[str, Any]:
        items = self.client.get("/api/model-operations", headers=self.h).json()["items"]
        return next(item for item in items if item["operation_id"] == operation_id)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(tmp_path, monkeypatch)


def test_status_before_install_names_the_recommended_backend(world: World) -> None:
    body = world.client.get("/api/local-runtime/llama-cpp", headers=world.h).json()
    assert body["installation"] is None
    assert body["executable"]["source"] == "none"
    assert body["hardware"]["recommended_backend"] == "cuda"
    assert body["slots"] == []
    assert world.fetched == []  # reading the page never reaches GitHub


def test_automatic_install_picks_cuda_with_its_runtime(world: World) -> None:
    started = world.client.post("/api/local-runtime/llama-cpp/install", headers=world.h, json={"backend": "auto"})
    assert started.status_code == 200
    op = world.operation(started.json()["operation_id"])
    assert op["state"] == "complete" and op["kind"] == "install"
    body = world.client.get("/api/local-runtime/llama-cpp", headers=world.h).json()
    assert body["installation"]["backend"] == "cuda"
    assert body["installation"]["assets"][1].startswith("cudart-")
    assert body["installation"]["devices"][0]["name"] == "Test GPU"
    assert body["executable"]["source"] == "managed"
    # Readiness and first-run setup now see the engine, though it is not on PATH.
    presence = local_presence.cached(SQLiteStore(world.workspace))["llama.cpp"]
    assert presence.present and Path(str(presence.executable)).name == installer.EXECUTABLE


def test_automatic_install_falls_through_to_a_backend_that_works(world: World) -> None:
    world.no_device.update({"cuda", "vulkan"})
    started = world.client.post("/api/local-runtime/llama-cpp/install", headers=world.h, json={})
    assert world.operation(started.json()["operation_id"])["state"] == "complete"
    body = world.client.get("/api/local-runtime/llama-cpp", headers=world.h).json()
    assert body["installation"]["backend"] == "cpu"


def test_an_explicit_backend_that_fails_is_reported_not_substituted(world: World) -> None:
    world.no_device.add("vulkan")
    started = world.client.post("/api/local-runtime/llama-cpp/install", headers=world.h, json={"backend": "vulkan"})
    op = world.operation(started.json()["operation_id"])
    assert op["state"] == "failed"
    assert op["error_code"] == "llama_cpp_install_failed"
    assert op["error_detail"] == "llama_cpp_backend_no_device"
    assert op["retryable"] is True
    world.no_device.clear()
    retried = world.client.post(f"/api/model-operations/{op['operation_id']}/retry", headers=world.h)
    assert retried.status_code == 200, retried.text
    assert world.operation(op["operation_id"])["state"] == "complete"


def test_install_request_is_validated(world: World) -> None:
    refused = world.client.post("/api/local-runtime/llama-cpp/install", headers=world.h, json={"backend": "rocm"})
    assert refused.status_code == 422


def test_update_check_compares_tags(world: World) -> None:
    body = world.client.post("/api/local-runtime/llama-cpp/update-check", headers=world.h).json()
    assert body == {"installed_tag": None, "latest_tag": TAG, "update_available": True, "published_at": "2026-10-30T00:00:00Z"}
    world.client.post("/api/local-runtime/llama-cpp/install", headers=world.h, json={})
    body = world.client.post("/api/local-runtime/llama-cpp/update-check", headers=world.h).json()
    assert body["installed_tag"] == TAG and body["update_available"] is False


def test_settings_round_trip_and_preview_and_validation(world: World) -> None:
    world.client.post("/api/local-runtime/llama-cpp/install", headers=world.h, json={})
    model_id = world.model()
    url = f"/api/local-runtime/llama-cpp/models/{model_id}/settings"
    first = world.client.get(url, headers=world.h).json()
    assert first["settings"]["gpu_layers"] is None
    assert first["plan"]["total_layers"] == 24 and first["plan"]["trained_context"] == 32768
    saved = world.client.put(url, headers=world.h, json={"gpu_layers": 10, "context_size": 4096})
    assert saved.status_code == 200
    assert saved.json()["plan"]["gpu_layers"] == 10 and saved.json()["plan"]["context_size"] == 4096
    assert world.client.get(url, headers=world.h).json()["settings"]["context_size"] == 4096
    preview = world.client.post(
        f"/api/local-runtime/llama-cpp/models/{model_id}/plan", headers=world.h, json={"context_size": 16384}
    ).json()
    assert preview["plan"]["context_size"] == 16384
    assert world.client.get(url, headers=world.h).json()["settings"]["context_size"] == 4096  # preview saved nothing
    bad = world.client.put(url, headers=world.h, json={"context_size": 10})
    assert bad.status_code == 422 and bad.json()["detail"]["reason_code"] == "runtime_settings_invalid_context_size"
    mismatched = world.client.put(url, headers=world.h, json={"kv_cache_type": "q4_0", "flash_attention": "off"})
    assert mismatched.json()["detail"]["reason_code"] == "runtime_settings_kv_cache_needs_flash_attention"
    missing = world.client.get("/api/local-runtime/llama-cpp/models/mdl_nope/settings", headers=world.h)
    assert missing.status_code == 404


def _fake_launch(calls: list[dict[str, Any]]) -> Any:
    def launch(self: LlamaSupervisor, **kwargs: Any) -> SlotHealth:
        calls.append(kwargs)
        plan = plan_launch(
            ModelShape("llama", 24, 32768, 4096, 24 * 2048, GIB),
            MemoryBudget("cuda", 8 * GIB, False, 16 * GIB, 32 * GIB),
            kwargs["settings"],
        )
        return SlotHealth(kwargs.get("profile_id") or "raiker-local-llama-cpp", kwargs["model_id"],
                          str(kwargs["model_path"]), "ready", None, None, 0, None, "cuda", plan, None)

    return launch


def test_deploy_without_engine_and_without_consent_says_so(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(LlamaSupervisor, "launch", _fake_launch(calls))
    model_id = world.model()
    started = world.client.post(f"/api/model-library/{model_id}/deploy", headers=world.h)
    op = world.operation(started.json()["operation_id"])
    assert op["state"] == "failed" and op["error_detail"] == "llama_server_missing"
    assert calls == []


def test_deploy_with_consent_installs_then_serves_with_saved_settings(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(LlamaSupervisor, "launch", _fake_launch(calls))
    model_id = world.model()
    world.client.put(
        f"/api/local-runtime/llama-cpp/models/{model_id}/settings", headers=world.h, json={"context_size": 4096}
    )
    started = world.client.post(
        f"/api/model-library/{model_id}/deploy", headers=world.h, json={"install_if_missing": True}
    )
    op = world.operation(started.json()["operation_id"])
    assert op["state"] == "complete", op
    assert installer.current(world.workspace) is not None
    assert calls[0]["model_id"] == model_id
    assert calls[0]["settings"] == RuntimeSettings(context_size=4096)
    assert SQLiteStore(world.workspace).is_configured_model(OWNER, "raiker-local-llama-cpp", "local-gguf")


def test_slot_controls(world: World) -> None:
    unknown = world.client.post("/api/local-runtime/llama-cpp/slots/nope/stop", headers=world.h)
    assert unknown.status_code == 404
    idle = world.client.post("/api/local-runtime/llama-cpp/slots/raiker-local-llama-cpp/restart", headers=world.h)
    assert idle.status_code == 409 and idle.json()["detail"]["reason_code"] == "local_runtime_slot_not_deployed"
    stopped = world.client.post("/api/local-runtime/llama-cpp/slots/raiker-local-llama-cpp/stop", headers=world.h)
    assert stopped.status_code == 200 and stopped.json()["slots"] == []


def test_uninstall_is_refused_while_serving(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    world.client.post("/api/local-runtime/llama-cpp/install", headers=world.h, json={})
    monkeypatch.setattr(LlamaSupervisor, "slots", lambda self, owner=None: ["busy"])
    refused = world.client.delete("/api/local-runtime/llama-cpp/installation", headers=world.h)
    assert refused.status_code == 409 and refused.json()["detail"]["reason_code"] == "local_runtime_in_use"
    monkeypatch.setattr(LlamaSupervisor, "slots", lambda self, owner=None: [])
    removed = world.client.delete("/api/local-runtime/llama-cpp/installation", headers=world.h)
    assert removed.status_code == 200 and removed.json()["installation"] is None
    assert not installer.runtime_root(world.workspace).exists()
