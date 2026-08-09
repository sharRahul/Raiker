"""Web-app task 3 (uploaded-images slice) — governed image attachments.

Uploaded bytes are untrusted data behind fail-closed validation: media-type
allowlist, hard size cap, and a magic-byte sniff that the bytes really are the
declared type. Stored images reach a model only as an image block when the
turn's bound profile declares vision support (``supports_vision``); every other
path withholds honestly (metadata-only events — image bytes never enter event
payloads or text context).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    ClientMetadata,
    ModelProfile,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import (
    ModelCapabilities,
    ModelImage,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolSpec,
)
from raiker.models.factory import capabilities_from_profile
from raiker.models.providers.anthropic_messages import AsyncAnthropicMessagesProvider
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.attachments import (
    MAX_IMAGE_BYTES,
    AttachmentValidationError,
    load_image,
    store_image,
    validate_image,
)
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker

# A real 1x1 transparent PNG.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


# ── validation ──────────────────────────────────────────────────────────────


class TestImageValidation:
    def test_valid_png_passes(self) -> None:
        validate_image("image/png", PNG_BYTES)

    def test_unsupported_media_type_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError) as err:
            validate_image("application/pdf", PNG_BYTES)
        assert err.value.reason.startswith("unsupported_media_type")

    def test_oversize_fails_closed(self) -> None:
        data = PNG_BYTES + b"\x00" * MAX_IMAGE_BYTES
        with pytest.raises(AttachmentValidationError) as err:
            validate_image("image/png", data)
        assert err.value.reason.startswith("attachment_too_large")

    def test_magic_byte_mismatch_fails_closed(self) -> None:
        # Declared PNG, but the bytes are JPEG magic — reject.
        with pytest.raises(AttachmentValidationError) as err:
            validate_image("image/png", b"\xff\xd8\xff\xe0 not a png")
        assert err.value.reason == "content_does_not_match_media_type"

    def test_empty_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError):
            validate_image("image/png", b"")

    def test_webp_requires_webp_tag(self) -> None:
        with pytest.raises(AttachmentValidationError):
            validate_image("image/webp", b"RIFF\x00\x00\x00\x00NOPE")


# ── store round-trip ────────────────────────────────────────────────────────


class TestAttachmentStore:
    def test_store_and_load_roundtrip(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_image(store, filename="shot.png", media_type="image/png", data=PNG_BYTES)
        assert stored.attachment_id.startswith("att_")
        assert stored.byte_size == len(PNG_BYTES)
        record = load_image(store, stored.attachment_id)
        assert record is not None
        assert record["data"] == PNG_BYTES
        assert record["media_type"] == "image/png"

    def test_metadata_load_never_carries_bytes(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_image(store, filename="shot.png", media_type="image/png", data=PNG_BYTES)
        metadata = store.load_attachment_metadata(stored.attachment_id)
        assert metadata is not None
        assert "data" not in metadata
        assert metadata["sha256"] == stored.sha256

    def test_unknown_attachment_loads_none(self, tmp_path: Path) -> None:
        assert load_image(SQLiteStore(tmp_path), "att_missing") is None

    def test_invalid_upload_never_stored(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        with pytest.raises(AttachmentValidationError):
            store_image(store, filename="x.png", media_type="image/png", data=b"nope")


# ── capabilities ────────────────────────────────────────────────────────────


def _profile(raw: dict[str, object]) -> ModelProfile:
    return ModelProfile(
        profile_id="p",
        provider="anthropic",
        model="m",
        build_phase="phase4",
        default_state="enabled",
        tui_launch_action="none",
        local_only=False,
        requires_network=True,
        raw=dict(raw),
    )


class TestVisionCapability:
    def test_supports_vision_parsed_from_profile(self) -> None:
        assert capabilities_from_profile(_profile({"supports_vision": True})).supports_vision

    def test_supports_vision_defaults_false(self) -> None:
        assert not capabilities_from_profile(_profile({})).supports_vision


# ── provider serialization ─────────────────────────────────────────────────


def _request(images: tuple[ModelImage, ...]) -> ModelRequest:
    return ModelRequest(
        profile_id="p",
        provider="x",
        model="m",
        messages=[
            ModelMessage(role="system", content="sys"),
            ModelMessage(role="user", content="what is in this image?", images=images),
        ],
    )


IMAGE = ModelImage(media_type="image/png", base64_data=base64.b64encode(PNG_BYTES).decode())


class TestProviderImageSerialization:
    def test_anthropic_sends_image_block_when_vision(self) -> None:
        provider = AsyncAnthropicMessagesProvider(
            profile_id="p",
            provider="anthropic",
            model="m",
            endpoint="http://127.0.0.1:1",
            capabilities=ModelCapabilities(supports_vision=True),
        )
        payload = provider._payload(_request((IMAGE,)), stream=False)
        blocks = payload["messages"][0]["content"]
        assert blocks[0]["type"] == "image"
        assert blocks[0]["source"]["media_type"] == "image/png"
        assert blocks[1]["type"] == "text"

    def test_anthropic_drops_images_without_vision(self) -> None:
        provider = AsyncAnthropicMessagesProvider(
            profile_id="p",
            provider="anthropic",
            model="m",
            endpoint="http://127.0.0.1:1",
            capabilities=ModelCapabilities(supports_vision=False),
        )
        payload = provider._payload(_request((IMAGE,)), stream=False)
        assert all(
            block["type"] != "image"
            for message in payload["messages"]
            for block in message["content"]
        )

    def test_openai_sends_data_url_when_vision(self) -> None:
        provider = AsyncOpenAICompatibleProvider(
            profile_id="p",
            provider="openai",
            model="m",
            endpoint="http://127.0.0.1:1",
            capabilities=ModelCapabilities(supports_vision=True),
        )
        payload = provider._payload(_request((IMAGE,)), stream=False)
        content = payload["messages"][1]["content"]
        assert content[0]["type"] == "image_url"
        assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
        assert content[1] == {"type": "text", "text": "what is in this image?"}

    def test_openai_keeps_plain_text_without_vision(self) -> None:
        provider = AsyncOpenAICompatibleProvider(
            profile_id="p",
            provider="llama.cpp",
            model="m",
            endpoint="http://127.0.0.1:1",
            capabilities=ModelCapabilities(supports_vision=False),
        )
        payload = provider._payload(_request((IMAGE,)), stream=False)
        assert payload["messages"][1]["content"] == "what is in this image?"


# ── context gathering (metadata only) ───────────────────────────────────────


class TestImageAttachmentGathering:
    def test_uploaded_image_becomes_metadata_item(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_image(store, filename="shot.png", media_type="image/png", data=PNG_BYTES)
        bundle = ContextGatherer().gather(
            workspace_root=tmp_path,
            session_id="s",
            turn_id="t",
            prompt_text="hi",
            attachments=[{"type": "image", "attachment_id": stored.attachment_id}],
        )
        items = [i for i in bundle.items if i.source.source_type == "attachment"]
        assert len(items) == 1
        item = items[0]
        assert item.source.trust_level == "untrusted_external"
        assert item.metadata["attachment_status"] == "image_uploaded"
        assert "image/png" in item.content
        # Metadata only: the base64/bytes must never enter text context.
        assert IMAGE.base64_data not in item.content

    def test_unknown_image_reported_honestly(self, tmp_path: Path) -> None:
        bundle = ContextGatherer().gather(
            workspace_root=tmp_path,
            session_id="s",
            turn_id="t",
            prompt_text="hi",
            attachments=[{"type": "image", "attachment_id": "att_missing"}],
        )
        item = [i for i in bundle.items if i.source.source_type == "attachment"][0]
        assert item.metadata["attachment_status"] == "not_found"

    def test_missing_attachment_id_reported_honestly(self, tmp_path: Path) -> None:
        bundle = ContextGatherer().gather(
            workspace_root=tmp_path,
            session_id="s",
            turn_id="t",
            prompt_text="hi",
            attachments=[{"type": "image"}],
        )
        item = [i for i in bundle.items if i.source.source_type == "attachment"][0]
        assert item.metadata["attachment_status"] == "missing_attachment_id"


# ── orchestrator delivery / withholding ─────────────────────────────────────


class VisionFakeRouter:
    """Scripted router that records the messages it was sent."""

    def __init__(self, *, vision: bool) -> None:
        self.vision = vision
        self.seen_messages: list[Sequence[ModelMessage]] = []

    def supports_vision(self, provider: str, model: str) -> bool:
        return self.vision

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        self.seen_messages.append(messages)
        return ModelResponse(text="ok", finish_reason="stop")

    def chat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        self.seen_messages.append(messages)
        return ModelResponse(text="ok", finish_reason="stop")


def _orchestrator(tmp_path: Path, router: VisionFakeRouter) -> RuntimeOrchestrator:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=writer,
    )
    return RuntimeOrchestrator(
        workspace_root=tmp_path,
        writer=writer,
        tool_broker=broker,
        model_router=router,  # type: ignore[arg-type]
    )


def _envelope(attachments: list[dict[str, object]]) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text="describe the image", attachments=list(attachments)),
        options=PromptOptions(),
    )


def _events(orchestrator: RuntimeOrchestrator, session_id: str) -> list[dict[str, Any]]:
    path = orchestrator.writer.path_for_session(session_id)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class TestOrchestratorImageDelivery:
    def test_image_delivered_to_vision_model(self, tmp_path: Path) -> None:
        stored = store_image(
            SQLiteStore(tmp_path), filename="a.png", media_type="image/png", data=PNG_BYTES
        )
        router = VisionFakeRouter(vision=True)
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope([{"type": "image", "attachment_id": stored.attachment_id}])
        orchestrator.handle(envelope)
        user_messages = [m for m in router.seen_messages[0] if m.role == "user" and m.images]
        assert len(user_messages) == 1
        assert user_messages[0].images[0].media_type == "image/png"
        events = _events(orchestrator, envelope.session_id)
        included = [e for e in events if e["event_type"] == "attachment_image_included"]
        assert len(included) == 1
        payload = included[0]["payload"]
        assert payload["attachment_id"] == stored.attachment_id
        # Metadata-only audit: image bytes/base64 never enter event payloads.
        assert base64.b64encode(PNG_BYTES).decode() not in json.dumps(events)

    def test_image_withheld_from_non_vision_model(self, tmp_path: Path) -> None:
        stored = store_image(
            SQLiteStore(tmp_path), filename="a.png", media_type="image/png", data=PNG_BYTES
        )
        router = VisionFakeRouter(vision=False)
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope([{"type": "image", "attachment_id": stored.attachment_id}])
        orchestrator.handle(envelope)
        assert all(not m.images for m in router.seen_messages[0])
        events = _events(orchestrator, envelope.session_id)
        withheld = [e for e in events if e["event_type"] == "attachment_image_withheld"]
        assert len(withheld) == 1
        assert withheld[0]["payload"]["reason"] == "model_profile_lacks_vision_support"

    def test_missing_attachment_withheld_honestly(self, tmp_path: Path) -> None:
        router = VisionFakeRouter(vision=True)
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope([{"type": "image", "attachment_id": "att_missing"}])
        orchestrator.handle(envelope)
        assert all(not m.images for m in router.seen_messages[0])
        events = _events(orchestrator, envelope.session_id)
        withheld = [e for e in events if e["event_type"] == "attachment_image_withheld"]
        assert withheld[0]["payload"]["reason"] == "attachment_not_found"

    def test_router_without_vision_support_fails_closed(self, tmp_path: Path) -> None:
        stored = store_image(
            SQLiteStore(tmp_path), filename="a.png", media_type="image/png", data=PNG_BYTES
        )
        router = VisionFakeRouter(vision=True)
        # A router that exposes no supports_vision hook must mean "no vision".
        del VisionFakeRouter.supports_vision
        try:
            orchestrator = _orchestrator(tmp_path, router)
            envelope = _envelope([{"type": "image", "attachment_id": stored.attachment_id}])
            orchestrator.handle(envelope)
            assert all(not m.images for m in router.seen_messages[0])
        finally:
            VisionFakeRouter.supports_vision = (  # type: ignore[method-assign]
                lambda self, provider, model: self.vision
            )


# ── upload API ──────────────────────────────────────────────────────────────


class TestUploadApi:
    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        ws = tmp_path / "ws"
        ws.mkdir()
        return ws

    @pytest.fixture
    def client(self, workspace: Path) -> TestClient:
        bootstrap_owner("owner", "Owner", workspace_root=workspace)
        app: FastAPI = create_app(workspace)
        return TestClient(app)

    @pytest.fixture
    def owner_token(self, workspace: Path) -> str:
        raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
        return raw

    def _upload(self, client: TestClient, token: str, **overrides: str) -> Any:
        body = {
            "filename": "shot.png",
            "media_type": "image/png",
            "data_base64": base64.b64encode(PNG_BYTES).decode(),
            **overrides,
        }
        return client.post(
            "/api/attachments", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    def test_upload_stores_and_returns_metadata_only(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        resp = self._upload(client, owner_token)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["attachment_id"].startswith("att_")
        assert "data" not in body and "data_base64" not in body
        assert load_image(SQLiteStore(workspace), body["attachment_id"]) is not None

    def test_upload_requires_auth(self, client: TestClient) -> None:
        resp = client.post(
            "/api/attachments",
            json={"filename": "a.png", "media_type": "image/png", "data_base64": "aGk="},
        )
        assert resp.status_code in {401, 403}

    def test_upload_rejects_bad_media_type(self, client: TestClient, owner_token: str) -> None:
        resp = self._upload(client, owner_token, media_type="application/x-msdownload")
        assert resp.status_code == 400
        assert "unsupported_media_type" in json.dumps(resp.json())

    def test_upload_rejects_type_content_mismatch(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = self._upload(
            client,
            owner_token,
            data_base64=base64.b64encode(b"\xff\xd8\xffJPEG").decode(),
        )
        assert resp.status_code == 400
        assert "content_does_not_match_media_type" in json.dumps(resp.json())

    def test_upload_rejects_invalid_base64(self, client: TestClient, owner_token: str) -> None:
        resp = self._upload(client, owner_token, data_base64="!!not-base64!!")
        assert resp.status_code == 400

    def test_prompt_accepts_image_attachment_reference(
        self,
        client: TestClient,
        owner_token: str,
        workspace: Path,
        mark_model_ready: Callable[..., None],
    ) -> None:
        mark_model_ready(workspace)
        upload = self._upload(client, owner_token)
        attachment_id = upload.json()["attachment_id"]
        resp = client.post(
            "/api/prompts",
            json={
                "text": "hi",
                "attachments": [{"type": "image", "attachment_id": attachment_id}],
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 200
        assert "Invalid prompt" not in resp.json().get("message", "")
