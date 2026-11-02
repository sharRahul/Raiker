"""The managed llama.cpp engine: status, install, update check, slots, settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.models.llama_cpp.planner import MemoryBudget, ModelShape, RuntimeSettings, plan_launch
from raiker.models.llama_cpp.releases import Release
from raiker.models.llama_cpp.supervisor import SlotHealth
from tests.contract_cases.base import Call, Cases, Seed, patched, plain
from tests.contract_cases.models import _GGUF, _library

ROOT = "/api/local-runtime/llama-cpp"
SLOT = "raiker-local-llama-cpp"


def _health() -> SlotHealth:
    plan = plan_launch(
        ModelShape("llama", 32, 8192, 4096, 32 * 2048, 4 * 1024**3),
        MemoryBudget("cuda", 8 * 1024**3, False, 16 * 1024**3, 32 * 1024**3),
        RuntimeSettings(),
    )
    return SlotHealth(SLOT, "mdl_x", "/models/x.gguf", "ready", "http://127.0.0.1:8080/v1", 42, 0,
                      None, "cuda", plan, "/logs/x.log")


def _with_slot(monkeypatch: Any) -> None:
    from raiker.models.llama_cpp.supervisor import LlamaSupervisor

    monkeypatch.setattr(LlamaSupervisor, "slots", lambda self, owner=None: [_health()])
    monkeypatch.setattr(LlamaSupervisor, "restart_slot", lambda self, slot: _health())


def _quiet_install(monkeypatch: Any) -> None:
    import raiker.api.routes_local_runtime as routes

    monkeypatch.setattr(routes, "run_llama_cpp_install", lambda *args: None)


def _latest(monkeypatch: Any) -> None:
    import raiker.api.routes_local_runtime as routes

    monkeypatch.setattr(routes, "fetch_release", lambda tag=None: Release("b7000", "2026-10-30T00:00:00Z", ()))


def _model(suffix: str, body: Any = None) -> Seed:
    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        root = _library(ws, client, h)
        (root / "tiny.gguf").write_bytes(_GGUF)
        models = client.post("/api/model-library/rescan", headers=h).json()["models"]
        path = f"{ROOT}/models/{models[0]['model_id']}{suffix}"
        return path if body is None else (path, body)

    return seed


_SETTINGS = {"gpu_layers": 10, "context_size": 4096, "flash_attention": "auto", "kv_cache_type": "f16"}

CASES: Cases = {
    ("GET", ROOT): patched(plain(ROOT), _with_slot),
    ("POST", f"{ROOT}/install"): patched(plain(f"{ROOT}/install", {"backend": "auto"}), _quiet_install),
    ("POST", f"{ROOT}/update-check"): patched(plain(f"{ROOT}/update-check"), _latest),
    ("DELETE", f"{ROOT}/installation"): plain(f"{ROOT}/installation"),
    ("POST", f"{ROOT}/slots/{{profile_id}}/stop"): plain(f"{ROOT}/slots/{SLOT}/stop"),
    ("POST", f"{ROOT}/slots/{{profile_id}}/restart"): patched(plain(f"{ROOT}/slots/{SLOT}/restart"), _with_slot),
    ("GET", f"{ROOT}/models/{{model_id}}/settings"): _model("/settings"),
    ("PUT", f"{ROOT}/models/{{model_id}}/settings"): _model("/settings", _SETTINGS),
    ("POST", f"{ROOT}/models/{{model_id}}/plan"): _model("/plan", _SETTINGS),
}
