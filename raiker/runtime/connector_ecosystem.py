from __future__ import annotations

import asyncio
import hashlib
import json
import weakref
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken

from raiker.auth.vault_key_file import effective_vault_key, ensure_vault_key
from raiker.contracts.ids import new_id, utc_now
from raiker.runtime.executors.sandbox import connector_egress_allowlist
from raiker.storage.sqlite import SQLiteStore

_METHODS = frozenset({"get", "post", "put", "patch", "delete"})

# ── The connector response-size contract (GCR-34) ────────────────────────────
#
# A connector answer is read into memory and handed to a model, so it needs a
# bound. The bound used to be applied as a slice of the bytes *before* parsing:
#
#     raw = response.content[:200_000]
#     try: result = json.loads(raw)
#     except ...: result = raw.decode(...)[:20_000]
#
# which meant a perfectly valid JSON answer one byte over the cap was cut in the
# middle of a token, failed to parse, and came back as a 20 000-character
# string. Nothing told the caller the body had been truncated, and nothing told
# it that a structured result had become an unstructured one — a model reading
# that string cannot tell it apart from a connector that answers in plain text.
#
# The bound is now a stated contract rather than a silent slice. A body over the
# cap is its own outcome, named, with the size that caused it; the stream is
# stopped at the cap rather than buffered whole and then discarded.

#: The most of one connector answer Raiker will hold and hand on.
CONNECTOR_RESPONSE_MAX_BYTES = 200_000
#: How much of a body that is text rather than JSON is carried as text, and how
#: much of an over-cap body is kept as a preview so the owner can see what
#: arrived.
CONNECTOR_TEXT_MAX_CHARS = 20_000
#: The stable code an over-cap answer carries in place of its value.
CONNECTOR_RESPONSE_TOO_LARGE = "response_too_large"


def _too_large_result(byte_count: int, content_type: str, head: bytes) -> dict[str, Any]:
    """The typed stand-in for an answer that does not fit the contract.

    A dict rather than a truncated string on purpose: the caller and the model
    both need to be able to tell "this connector answered with more than Raiker
    will carry" from "this connector answered with text".
    """
    return {
        "truncated": True,
        "reason_code": CONNECTOR_RESPONSE_TOO_LARGE,
        "byte_count": byte_count,
        "max_bytes": CONNECTOR_RESPONSE_MAX_BYTES,
        "content_type": content_type,
        "preview": head.decode("utf-8", errors="replace")[:CONNECTOR_TEXT_MAX_CHARS],
    }


def _decode_connector_body(body: bytes) -> Any:
    """A complete body within the cap: parsed as JSON, or carried as text.

    Reached only for a body that was *not* truncated, so a parse failure here
    means the connector really did answer with something that is not JSON.
    """
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace")[:CONNECTOR_TEXT_MAX_CHARS]


def _keep(chunks: list[bytes], kept: int, chunk: bytes, total: int) -> int:
    """Accumulate *chunk* while the contract still allows it. Returns bytes kept.

    Under the cap the whole chunk is kept, because it is the answer. Over it
    only enough for a preview is kept: the body is already known not to fit, and
    buffering the rest of a body that will be reported as too large is the copy
    this contract exists to avoid.
    """
    if total <= CONNECTOR_RESPONSE_MAX_BYTES:
        chunks.append(chunk)
        return kept + len(chunk)
    if kept < CONNECTOR_TEXT_MAX_CHARS:
        head = chunk[: CONNECTOR_TEXT_MAX_CHARS - kept]
        chunks.append(head)
        return kept + len(head)
    return kept


async def _aread_bounded(response: httpx.Response) -> tuple[bytes, int]:
    """The body as far as the contract allows, and the size the peer really sent."""
    chunks: list[bytes] = []
    kept = 0
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        kept = _keep(chunks, kept, chunk, total)
    return b"".join(chunks), total


def _read_bounded(response: httpx.Response) -> tuple[bytes, int]:
    chunks: list[bytes] = []
    kept = 0
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        kept = _keep(chunks, kept, chunk, total)
    return b"".join(chunks), total


def _connector_result(response: httpx.Response, body: bytes, total: int) -> Any:
    """One connector answer, honouring the response-size contract above."""
    if total > CONNECTOR_RESPONSE_MAX_BYTES:
        return _too_large_result(
            total, str(response.headers.get("content-type") or ""), body
        )
    return _decode_connector_body(body)


@dataclass(frozen=True)
class ConnectorDefinition:
    connector_id: str
    name: str
    category: str
    description: str
    auth_type: str
    host: str


class ConnectorCatalog:
    def __init__(self) -> None:
        path = files("raiker.config").joinpath("connector-store.json")
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._items = tuple(
            ConnectorDefinition(
                connector_id=str(item["id"]),
                name=str(item["name"]),
                category=str(item["category"]),
                description=str(item["description"]),
                auth_type=str(item["auth"]),
                host=str(item["host"]),
            )
            for item in raw["connectors"]
        )
        if len(self._items) != len({item.connector_id for item in self._items}):
            raise ValueError("duplicate_connector_id")

    def list(self) -> tuple[ConnectorDefinition, ...]:
        return self._items

    def get(self, connector_id: str) -> ConnectorDefinition:
        for item in self._items:
            if item.connector_id == connector_id:
                return item
        raise ValueError("unknown_connector")


class ConnectorVault:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def configured(self) -> bool:
        value = effective_vault_key(self.store.paths.workspace_root)
        if not value:
            return False
        try:
            Fernet(value.encode("ascii"))
        except (ValueError, TypeError):
            return False
        return True

    def _fernet(self, *, provision: bool = False) -> Fernet:
        """The workspace's vault cipher.

        ``provision`` is set only on the write path. The vault key is a locally
        generated encryption key, not a passphrase the owner invents, so making
        them go and press "Generate key" before they may save a credential was
        friction with no security benefit — the resulting key is identical
        either way, and `connector_vault_key_unset` was the most common
        first-run dead end.

        Reads never provision. If the key is missing on a read, existing
        credentials genuinely cannot be decrypted, and saying so is the honest
        answer; minting a fresh key there would hide a real problem behind an
        empty result.
        """
        value = effective_vault_key(self.store.paths.workspace_root)
        if not value and provision:
            value = ensure_vault_key(self.store.paths.workspace_root)
        if not value:
            raise ValueError("connector_vault_key_unset")
        try:
            return Fernet(value.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise ValueError("connector_vault_key_invalid") from exc

    def put(
        self,
        principal_id: str,
        connector_id: str,
        payload: dict[str, str],
        expires_at: str | None = None,
    ) -> None:
        clean = {str(k): str(v) for k, v in payload.items() if str(v)}
        if not clean:
            raise ValueError("credential_empty")
        encrypted = self._fernet(provision=True).encrypt(
            json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        now = utc_now()
        with self.store.connect() as connection:
            connection.execute(
                """INSERT INTO connector_credentials
                   (principal_id, connector_id, encrypted_payload, expires_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(principal_id, connector_id) DO UPDATE SET
                   encrypted_payload=excluded.encrypted_payload,
                   expires_at=excluded.expires_at, updated_at=excluded.updated_at""",
                (principal_id, connector_id, encrypted, expires_at, now),
            )

    def get(self, principal_id: str, connector_id: str) -> dict[str, str] | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT encrypted_payload FROM connector_credentials WHERE principal_id=? AND connector_id=?",
                (principal_id, connector_id),
            ).fetchone()
        if row is None:
            return None
        try:
            raw = self._fernet().decrypt(bytes(row["encrypted_payload"]))
        except InvalidToken as exc:
            raise ValueError("connector_credential_decryption_failed") from exc
        parsed = json.loads(raw)
        return {str(k): str(v) for k, v in parsed.items()}

    def metadata(self, principal_id: str, connector_id: str) -> dict[str, str | None] | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT expires_at, updated_at FROM connector_credentials WHERE principal_id=? AND connector_id=?",
                (principal_id, connector_id),
            ).fetchone()
        return dict(row) if row else None


def compile_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    """Compile OpenAPI 2/3 or ai-plugin metadata into a bounded operation index."""
    if "api" in raw and isinstance(raw.get("api"), dict):
        url = raw["api"].get("url")
        if not isinstance(url, str) or not url:
            raise ValueError("manifest_api_url_missing")
        return {"kind": "ai_plugin", "api_url": url, "operations": []}
    version = raw.get("openapi") or raw.get("swagger")
    if not isinstance(version, str):
        raise ValueError("manifest_version_missing")
    paths = raw.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("manifest_paths_missing")
    operations: list[dict[str, Any]] = []
    for path, item in paths.items():
        if not isinstance(path, str) or not path.startswith("/") or not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if str(method).lower() not in _METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id.strip():
                operation_id = f"{str(method).lower()}_{hashlib.sha256(path.encode()).hexdigest()[:12]}"
            compiled_operation: dict[str, Any] = {
                    "operation_id": operation_id,
                    "method": str(method).upper(),
                    "path": path,
                    "description": str(operation.get("description") or operation.get("summary") or "")[:1000],
                    "requires_confirmation": str(method).lower() != "get",
                }
            compensation = operation.get("x-raiker-compensation")
            if compensation is not None:
                if not isinstance(compensation, dict):
                    raise ValueError("manifest_compensation_invalid")
                compensation_operation = compensation.get("operationId")
                argument_map = compensation.get("argumentMap", {})
                deadline_seconds = compensation.get("deadlineSeconds")
                if (
                    not isinstance(compensation_operation, str)
                    or not compensation_operation.strip()
                    or not isinstance(argument_map, dict)
                    or len(argument_map) > 50
                    or not all(isinstance(k, str) and isinstance(v, str) for k, v in argument_map.items())
                    or not isinstance(deadline_seconds, int)
                    or isinstance(deadline_seconds, bool)
                    or not 1 <= deadline_seconds <= 2_592_000
                ):
                    raise ValueError("manifest_compensation_invalid")
                compiled_operation["compensation"] = {
                    "operation_id": compensation_operation,
                    "argument_map": dict(sorted(argument_map.items())),
                    "deadline_seconds": deadline_seconds,
                }
            operations.append(compiled_operation)
            if len(operations) > 500:
                raise ValueError("manifest_operation_limit_exceeded")
    if not operations:
        raise ValueError("manifest_operations_missing")
    operation_ids = {item["operation_id"] for item in operations}
    for operation in operations:
        compensation = operation.get("compensation")
        if compensation and compensation["operation_id"] not in operation_ids:
            raise ValueError("manifest_compensation_operation_unknown")
    return {"kind": "openapi", "version": version, "operations": operations}


def credential_status(expires_at: str | None) -> str:
    if not expires_at:
        return "connected"
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return "reauth_required"
    return "reauth_required" if expiry <= datetime.now(UTC) else "connected"


# GCR-33 — one refresh at a time per (owner, connector).
#
# A credential that has expired is noticed by every invocation that reaches it,
# and each one used to call the refresh independently. All of them read the same
# stored refresh token R0. For a provider that rotates refresh tokens, the first
# exchange invalidates R0 and stores R1; the second then presents a token the
# provider has already retired, and depending on what that provider does with a
# retired token the owner is either handed a spurious failure or left with a
# credential row that no longer matches anything upstream.
#
# `ConnectorInvoker` is built per request, so the lease cannot live on the
# instance. It is keyed by the running loop as well as the credential: an
# `asyncio.Lock` binds to the loop that first awaits it, and a host that has
# torn a loop down and built another (the test client does exactly this) must
# not be handed a lock belonging to the dead one. The outer map is weak, so a
# loop that goes away takes its locks with it.
_REFRESH_LEASES: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, dict[tuple[str, str], asyncio.Lock]
] = weakref.WeakKeyDictionary()


def _refresh_lease(principal_id: str, connector_id: str) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    per_loop = _REFRESH_LEASES.get(loop)
    if per_loop is None:
        per_loop = _REFRESH_LEASES[loop] = {}
    key = (principal_id, connector_id)
    lock = per_loop.get(key)
    if lock is None:
        lock = per_loop[key] = asyncio.Lock()
    return lock


class ConnectorInvoker:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def _operation(self, connector_id: str, operation_id: str) -> tuple[dict[str, Any], str]:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT manifest_json FROM connector_manifests WHERE connector_id=?",
                (connector_id,),
            ).fetchone()
        if row is None:
            raise ValueError("connector_manifest_missing")
        manifest = json.loads(row["manifest_json"])
        compiled = compile_manifest(manifest)
        operation = next(
            (item for item in compiled["operations"] if item["operation_id"] == operation_id), None
        )
        if operation is None:
            raise ValueError("connector_operation_unknown")
        servers = manifest.get("servers")
        if isinstance(servers, list) and servers and isinstance(servers[0], dict):
            base_url = servers[0].get("url")
        elif isinstance(manifest.get("host"), str):
            scheme = "https" if manifest.get("schemes", ["https"])[0] == "https" else "http"
            base_url = f"{scheme}://{manifest['host']}{manifest.get('basePath', '')}"
        else:
            raise ValueError("connector_server_missing")
        if not isinstance(base_url, str):
            raise ValueError("connector_server_invalid")
        return operation, base_url.rstrip("/")

    def _require_enabled(self, principal_id: str, connector_id: str) -> None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT enabled FROM connector_installations WHERE principal_id=? AND connector_id=?",
                (principal_id, connector_id),
            ).fetchone()
        if row is None or not bool(row["enabled"]):
            raise ValueError("connector_not_enabled")

    async def invoke(
        self,
        principal_id: str,
        connector_id: str,
        operation_id: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_enabled(principal_id, connector_id)
        definition = ConnectorCatalog().get(connector_id)
        operation, base_url = self._operation(connector_id, operation_id)
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname != definition.host:
            raise ValueError("connector_manifest_host_denied")
        if definition.host not in connector_egress_allowlist():
            raise ValueError("connector_egress_denied")
        vault = ConnectorVault(self.store)
        credential = vault.get(principal_id, connector_id)
        if credential is None:
            raise ValueError("connector_auth_required")
        meta = vault.metadata(principal_id, connector_id)
        if meta and credential_status(meta.get("expires_at")) == "reauth_required":
            credential = await self._refresh_oauth(
                vault, principal_id, connector_id, credential
            )
        path = operation["path"]
        path_values = arguments.get("path", {})
        if not isinstance(path_values, dict):
            raise ValueError("connector_path_arguments_invalid")
        for name, value in path_values.items():
            path = path.replace("{" + str(name) + "}", quote(str(value), safe=""))
        if "{" in path or "}" in path:
            raise ValueError("connector_path_argument_missing")
        query = arguments.get("query", {})
        body = arguments.get("body")
        if not isinstance(query, dict):
            raise ValueError("connector_query_arguments_invalid")
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{urlencode({str(k): str(v) for k, v in query.items()})}"
        headers = {"Accept": "application/json"}
        token = credential.get("access_token") or credential.get("api_key")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        invocation_id = new_id("cinv_")
        with self.store.connect() as connection:
            connection.execute(
                """INSERT INTO connector_invocations
                   (invocation_id, principal_id, connector_id, operation_id, method, status, started_at)
                   VALUES (?, ?, ?, ?, ?, 'processing', ?)""",
                (
                    invocation_id,
                    principal_id,
                    connector_id,
                    operation_id,
                    operation["method"],
                    utc_now(),
                ),
            )
        data: Any = None
        status_code = 0
        try:
            # Streamed rather than buffered so the response-size contract is
            # enforced while the body arrives, instead of after the whole of it
            # is already in memory.
            async with (
                httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client,
                client.stream(
                    operation["method"],
                    url,
                    headers=headers,
                    json=body if body is not None else None,
                ) as response,
            ):
                status_code = response.status_code
                if status_code < 400:
                    raw, byte_count = await _aread_bounded(response)
                    data = _connector_result(response, raw, byte_count)
        except Exception:
            self._finish_invocation(invocation_id, "failed")
            raise
        if status_code >= 400:
            self._finish_invocation(invocation_id, "failed")
            raise ValueError(f"connector_upstream_error:{status_code}")
        self._finish_invocation(invocation_id, "completed")
        result: dict[str, Any] = {
            "invocation_id": invocation_id,
            "connector_id": connector_id,
            "operation_id": operation_id,
            "method": operation["method"],
            "status_code": status_code,
            "data": data,
        }
        compensation = operation.get("compensation")
        if isinstance(compensation, dict):
            result["compensation"] = {
                **compensation,
                "available_until": (
                    datetime.now(UTC)
                    + timedelta(seconds=int(compensation["deadline_seconds"]))
                ).isoformat(),
                "source_invocation_id": invocation_id,
            }
        return result

    def _finish_invocation(self, invocation_id: str, status: str) -> None:
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE connector_invocations SET status=?, completed_at=? WHERE invocation_id=?",
                (status, utc_now(), invocation_id),
            )

    def invoke_read_sync(
        self,
        principal_id: str,
        connector_id: str,
        operation_id: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Synchronous GET-only path used by the model's brokered read tool."""
        self._require_enabled(principal_id, connector_id)
        definition = ConnectorCatalog().get(connector_id)
        operation, base_url = self._operation(connector_id, operation_id)
        if operation["method"] != "GET":
            raise ValueError("connector_read_requires_get")
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname != definition.host:
            raise ValueError("connector_manifest_host_denied")
        if definition.host not in connector_egress_allowlist():
            raise ValueError("connector_egress_denied")
        vault = ConnectorVault(self.store)
        credential = vault.get(principal_id, connector_id)
        meta = vault.metadata(principal_id, connector_id)
        if credential is None:
            raise ValueError("connector_auth_required")
        if meta and credential_status(meta.get("expires_at")) == "reauth_required":
            raise ValueError("connector_reauth_required")
        path = operation["path"]
        path_values = arguments.get("path", {})
        query = arguments.get("query", {})
        if not isinstance(path_values, dict) or not isinstance(query, dict):
            raise ValueError("connector_arguments_invalid")
        for name, value in path_values.items():
            path = path.replace("{" + str(name) + "}", quote(str(value), safe=""))
        if "{" in path or "}" in path:
            raise ValueError("connector_path_argument_missing")
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{urlencode({str(k): str(v) for k, v in query.items()})}"
        token = credential.get("access_token") or credential.get("api_key")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        invocation_id = new_id("cinv_")
        with self.store.connect() as connection:
            connection.execute(
                """INSERT INTO connector_invocations
                   (invocation_id, principal_id, connector_id, operation_id, method, status, started_at)
                   VALUES (?, ?, ?, ?, 'GET', 'processing', ?)""",
                (invocation_id, principal_id, connector_id, operation_id, utc_now()),
            )
        data: Any = None
        status_code = 0
        try:
            # The same response-size contract as the async path, enforced the
            # same way: while the body arrives, not once it is all in memory.
            with (
                httpx.Client(timeout=20.0, follow_redirects=False) as client,
                client.stream("GET", url, headers=headers) as response,
            ):
                status_code = response.status_code
                if status_code < 400:
                    raw, byte_count = _read_bounded(response)
                    data = _connector_result(response, raw, byte_count)
        except Exception:
            self._finish_invocation(invocation_id, "failed")
            raise
        if status_code >= 400:
            self._finish_invocation(invocation_id, "failed")
            raise ValueError(f"connector_upstream_error:{status_code}")
        self._finish_invocation(invocation_id, "completed")
        return {
            "invocation_id": invocation_id,
            "connector_id": connector_id,
            "operation_id": operation_id,
            "method": "GET",
            "status_code": status_code,
            "data": data,
        }

    async def _refresh_oauth(
        self,
        vault: ConnectorVault,
        principal_id: str,
        connector_id: str,
        credential: dict[str, str],
    ) -> dict[str, str]:
        async with _refresh_lease(principal_id, connector_id):
            return await self._refresh_oauth_locked(
                vault, principal_id, connector_id, credential
            )

    async def _refresh_oauth_locked(
        self,
        vault: ConnectorVault,
        principal_id: str,
        connector_id: str,
        credential: dict[str, str],
    ) -> dict[str, str]:
        """The exchange itself, with the lease held.

        The credential is re-read here rather than trusted from the caller: a
        request that queued behind another refresh was holding the token as it
        stood *before* that refresh, and exchanging it a second time is the
        rotation race this lease exists to close. If the waiter's turn arrives
        and the credential is already valid again, the refresh it was waiting
        for did the work and there is nothing left to do.
        """
        current = vault.get(principal_id, connector_id)
        if current is not None:
            meta = vault.metadata(principal_id, connector_id)
            if meta is None or credential_status(meta.get("expires_at")) == "connected":
                return current
            credential = current
        required = ("refresh_token", "client_id", "client_secret")
        if any(not credential.get(key) for key in required):
            raise ValueError("connector_reauth_required")
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT manifest_json FROM connector_manifests WHERE connector_id=?",
                (connector_id,),
            ).fetchone()
        manifest = json.loads(row["manifest_json"]) if row else {}
        schemes = manifest.get("components", {}).get("securitySchemes", {})
        token_url: str | None = None
        if isinstance(schemes, dict):
            for scheme in schemes.values():
                if not isinstance(scheme, dict) or scheme.get("type") != "oauth2":
                    continue
                flows = scheme.get("flows", {})
                if isinstance(flows, dict):
                    for flow in flows.values():
                        if isinstance(flow, dict) and isinstance(flow.get("tokenUrl"), str):
                            token_url = flow["tokenUrl"]
                            break
        if token_url is None:
            raise ValueError("connector_oauth_token_url_missing")
        parsed = urlparse(token_url)
        if parsed.scheme != "https" or parsed.hostname not in connector_egress_allowlist():
            raise ValueError("connector_oauth_egress_denied")
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": credential["refresh_token"],
                    "client_id": credential["client_id"],
                    "client_secret": credential["client_secret"],
                },
            )
        if response.status_code >= 400:
            raise ValueError("connector_oauth_refresh_failed")
        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("connector_oauth_refresh_invalid")
        rotated = dict(credential)
        rotated["access_token"] = access_token
        if isinstance(payload.get("refresh_token"), str):
            rotated["refresh_token"] = payload["refresh_token"]
        expires_at: str | None = None
        if isinstance(payload.get("expires_in"), (int, float)):
            expires_at = (
                datetime.now(UTC) + timedelta(seconds=max(0, int(payload["expires_in"])))
            ).isoformat()
        vault.put(principal_id, connector_id, rotated, expires_at)
        return rotated
