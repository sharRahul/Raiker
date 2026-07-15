from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken

from raiker.auth.vault_key_file import effective_vault_key
from raiker.contracts.ids import new_id, utc_now
from raiker.runtime.executors.sandbox import connector_egress_allowlist
from raiker.storage.sqlite import SQLiteStore

_METHODS = frozenset({"get", "post", "put", "patch", "delete"})


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

    def _fernet(self) -> Fernet:
        value = effective_vault_key(self.store.paths.workspace_root)
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
        encrypted = self._fernet().encrypt(
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
            operations.append(
                {
                    "operation_id": operation_id,
                    "method": str(method).upper(),
                    "path": path,
                    "description": str(operation.get("description") or operation.get("summary") or "")[:1000],
                    "requires_confirmation": str(method).lower() != "get",
                }
            )
            if len(operations) > 500:
                raise ValueError("manifest_operation_limit_exceeded")
    if not operations:
        raise ValueError("manifest_operations_missing")
    return {"kind": "openapi", "version": version, "operations": operations}


def credential_status(expires_at: str | None) -> str:
    if not expires_at:
        return "connected"
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return "reauth_required"
    return "reauth_required" if expiry <= datetime.now(UTC) else "connected"


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
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
                response = await client.request(
                    operation["method"],
                    url,
                    headers=headers,
                    json=body if body is not None else None,
                )
        except Exception:
            self._finish_invocation(invocation_id, "failed")
            raise
        if response.status_code >= 400:
            self._finish_invocation(invocation_id, "failed")
            raise ValueError(f"connector_upstream_error:{response.status_code}")
        raw = response.content[:200_000]
        try:
            result: Any = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            result = raw.decode("utf-8", errors="replace")[:20_000]
        self._finish_invocation(invocation_id, "completed")
        return {
            "invocation_id": invocation_id,
            "connector_id": connector_id,
            "operation_id": operation_id,
            "method": operation["method"],
            "status_code": response.status_code,
            "data": result,
        }

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
        try:
            with httpx.Client(timeout=20.0, follow_redirects=False) as client:
                response = client.get(url, headers=headers)
        except Exception:
            self._finish_invocation(invocation_id, "failed")
            raise
        if response.status_code >= 400:
            self._finish_invocation(invocation_id, "failed")
            raise ValueError(f"connector_upstream_error:{response.status_code}")
        raw = response.content[:200_000]
        try:
            data: Any = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = raw.decode("utf-8", errors="replace")[:20_000]
        self._finish_invocation(invocation_id, "completed")
        return {
            "invocation_id": invocation_id,
            "connector_id": connector_id,
            "operation_id": operation_id,
            "method": "GET",
            "status_code": response.status_code,
            "data": data,
        }

    async def _refresh_oauth(
        self,
        vault: ConnectorVault,
        principal_id: str,
        connector_id: str,
        credential: dict[str, str],
    ) -> dict[str, str]:
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
            from datetime import timedelta

            expires_at = (
                datetime.now(UTC) + timedelta(seconds=max(0, int(payload["expires_in"])))
            ).isoformat()
        vault.put(principal_id, connector_id, rotated, expires_at)
        return rotated
