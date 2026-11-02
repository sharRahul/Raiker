"""Live end to end: the real llama.cpp release and a real model, through the API.

Skipped unless ``RAIKER_LIVE_LLAMA_CPP=1``, because it downloads the official
llama.cpp build for this machine from GitHub (tens to hundreds of MB) and a
tiny GGUF model from Hugging Face. CI runs it on Windows, macOS and Linux
(``.github/workflows/llama-cpp.yml``). It is the owner's path, step by step:

1. install the engine (automatic backend choice, digest-verified);
2. add a model folder, download a model into it, rescan;
3. serve it — planned, started, health-checked — and answer a chat request;
4. serve it in a second slot at once, then switch the first slot's settings
   and restart it;
5. stop a slot, and shut down with nothing left running.

Environment:

* ``RAIKER_LIVE_LLAMA_CPP=1`` — run at all.
* ``RAIKER_LLAMA_CPP_RELEASE`` — a tag such as ``b7000``; latest when unset.
* ``RAIKER_LLAMA_CPP_BACKEND`` — ``auto`` (default) or a backend to force.
* ``RAIKER_LIVE_GGUF_URL`` — the model to fetch; llama.cpp's own
  ``stories260K`` test model by default.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.app.launcher import port_is_free
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.contracts import ModelMessage
from raiker.models.llama_cpp import hardware, installer
from raiker.models.local_runtime import LOCAL_SLOTS
from raiker.models.providers.llama_cpp_server import LlamaCppServerProvider

pytestmark = pytest.mark.skipif(
    os.environ.get("RAIKER_LIVE_LLAMA_CPP") != "1",
    reason="downloads llama.cpp and a model; set RAIKER_LIVE_LLAMA_CPP=1",
)

DEFAULT_MODEL = "https://huggingface.co/ggml-org/models/resolve/main/tinyllamas/stories260K.gguf"
OWNER = "principal_owner"


def _op(client: TestClient, h: dict[str, str], operation_id: str) -> dict[str, Any]:
    items = client.get("/api/model-operations", headers=h).json()["items"]
    return next(item for item in items if item["operation_id"] == operation_id)


def _chat(endpoint: str, alias: str) -> str:
    provider = LlamaCppServerProvider(model=alias, endpoint=endpoint.removesuffix("/v1"), max_tokens=16, timeout=120)
    return provider.chat([ModelMessage(role="user", content="Once upon a time")]).text


def test_install_serve_infer_switch_and_stop_with_the_real_engine(tmp_path: Path) -> None:
    for slot in LOCAL_SLOTS[:2]:
        if not port_is_free(slot.port):
            pytest.skip(f"port {slot.port} is in use on this machine")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    library = tmp_path / "models"
    library.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session(OWNER)
    app = create_app(workspace)
    client = TestClient(app)
    h = {"Authorization": f"Bearer {token}"}
    try:
        profile = hardware.detect(force=True)
        print(f"hardware: {profile.os}/{profile.arch} backends={profile.backends} -> {profile.recommended_backend}")

        # 1. Install the engine.
        backend = os.environ.get("RAIKER_LLAMA_CPP_BACKEND", "auto")
        body: dict[str, Any] = {"backend": backend}
        if os.environ.get("RAIKER_LLAMA_CPP_RELEASE"):
            body["release"] = os.environ["RAIKER_LLAMA_CPP_RELEASE"]
        started = client.post("/api/local-runtime/llama-cpp/install", headers=h, json=body)
        assert started.status_code == 200, started.text
        install = _op(client, h, started.json()["operation_id"])
        assert install["state"] == "complete", install
        overview = client.get("/api/local-runtime/llama-cpp", headers=h).json()
        installed = overview["installation"]
        print(f"installed llama.cpp {installed['tag']} ({installed['backend']}): {installed['version_text']}")
        assert overview["executable"]["source"] == "managed"
        # API responses pass through the secret redactor. A temporary directory
        # segment can look credential-shaped, so prove the managed executable
        # from the installation record instead of treating a presentation field
        # as a filesystem locator.
        managed = installer.current(workspace)
        assert managed is not None and Path(managed.executable).is_file()

        # 2. A model in an approved folder.
        url = os.environ.get("RAIKER_LIVE_GGUF_URL", DEFAULT_MODEL)
        target = library / url.rsplit("/", 1)[-1]
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_bytes(1 << 20):
                    handle.write(chunk)
        assert client.post("/api/model-library/roots", headers=h, json={"path": str(library)}).status_code == 200
        models = client.post("/api/model-library/rescan", headers=h).json()["models"]
        model_id = models[0]["model_id"]
        plan = client.get(f"/api/local-runtime/llama-cpp/models/{model_id}/settings", headers=h).json()["plan"]
        print(f"plan: {plan['gpu_layers']}/{plan['total_layers']} layers, ctx {plan['context_size']}, {plan['verdict']}")
        assert plan["allowed"]

        # 3. Serve and infer.
        first = LOCAL_SLOTS[0]
        deployed = client.post(f"/api/model-library/{model_id}/deploy", headers=h, json={"profile_id": first.profile_id})
        assert _op(client, h, deployed.json()["operation_id"])["state"] == "complete"
        slots = {slot["slot_profile_id"]: slot for slot in client.get("/api/local-runtime/llama-cpp", headers=h).json()["slots"]}
        assert slots[first.profile_id]["state"] == "ready"
        text = _chat(slots[first.profile_id]["endpoint"], first.alias)
        print(f"slot 1 answered: {text!r}")
        assert text.strip()

        # 4. A second slot at once; then new settings and a restart of the first.
        second = LOCAL_SLOTS[1]
        deployed = client.post(f"/api/model-library/{model_id}/deploy", headers=h, json={"profile_id": second.profile_id})
        assert _op(client, h, deployed.json()["operation_id"])["state"] == "complete"
        slots = {slot["slot_profile_id"]: slot for slot in client.get("/api/local-runtime/llama-cpp", headers=h).json()["slots"]}
        assert _chat(slots[second.profile_id]["endpoint"], second.alias).strip()
        saved = client.put(
            f"/api/local-runtime/llama-cpp/models/{model_id}/settings", headers=h,
            json={"context_size": 512, "gpu_layers": 0},
        )
        assert saved.status_code == 200
        # Restart re-plans from the slot's own settings; a new deploy picks up saved ones.
        redeployed = client.post(f"/api/model-library/{model_id}/deploy", headers=h, json={"profile_id": first.profile_id})
        assert _op(client, h, redeployed.json()["operation_id"])["state"] == "complete"
        slot = next(s for s in client.get("/api/local-runtime/llama-cpp", headers=h).json()["slots"] if s["slot_profile_id"] == first.profile_id)
        assert slot["plan"]["context_size"] == 512 and slot["plan"]["gpu_layers"] == 0
        assert _chat(slot["endpoint"], first.alias).strip()
        restarted = client.post(f"/api/local-runtime/llama-cpp/slots/{first.profile_id}/restart", headers=h)
        assert restarted.status_code == 200
        deadline = time.monotonic() + 120
        supervisor = app.state.llama_supervisor
        while supervisor.health(first.profile_id).state != "ready" and time.monotonic() < deadline:
            supervisor.tick()
            time.sleep(0.5)
        assert supervisor.health(first.profile_id).state == "ready"

        # 5. Stop one; shut down; nothing left listening.
        stopped = client.post(f"/api/local-runtime/llama-cpp/slots/{second.profile_id}/stop", headers=h).json()
        assert [s["slot_profile_id"] for s in stopped["slots"]] == [first.profile_id]
    finally:
        app.state.llama_supervisor.shutdown()
    deadline = time.monotonic() + 15
    while not all(port_is_free(slot.port) for slot in LOCAL_SLOTS[:2]) and time.monotonic() < deadline:
        time.sleep(0.5)
    assert all(port_is_free(slot.port) for slot in LOCAL_SLOTS[:2])
