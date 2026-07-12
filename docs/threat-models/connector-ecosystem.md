# Manifest-Driven Connector Ecosystem Threat Model

## Scope

This surface installs principal-scoped connectors, stores encrypted API/OAuth
credentials, compiles OpenAPI or `ai-plugin.json` metadata, routes GET requests,
and stages POST/PUT/PATCH/DELETE requests behind action-bound approvals.

## Trust boundaries

- Catalog and manifests are metadata, not authority.
- Manifests are untrusted input and never execute code.
- Connector responses are untrusted external data.
- Credential plaintext exists only while encrypting or issuing an authenticated
  request. API responses, events, model context, and UI state never contain it.
- A catalog listing does not assert that a provider grants Raiker API access.

## Controls

- `RAIKER_CONNECTOR_VAULT_KEY` must contain an owner-provided Fernet key. Missing,
  invalid, or mismatched keys fail closed; there is no derived fallback key.
- Credentials are keyed by `(principal_id, connector_id)` and encrypted at rest.
- The authenticated API principal is bound into prompt execution server-side;
  models cannot select another principal or credential owner.
- Request URLs derive from the stored manifest. The scheme must be HTTPS, the
  operation path must be declared, path values are encoded, redirects are off,
  the API host must match the catalog, and the host must be owner-allowlisted.
- `connector_read` accepts only GET operations. `connector_write` accepts only
  POST/PUT/PATCH/DELETE operations and always yields `needs_approval`.
- Write intents contain the exact connector, operation, and arguments, are bound
  to the requesting principal and approval, and are atomically claimed once.
  Denied, failed, or executed intents cannot be replayed.
- OAuth refresh uses only the manifest-declared HTTPS token URL and encrypted
  refresh/client credentials. Its host must also be owner-allowlisted. Rotated
  credentials replace the encrypted record atomically.
- Manifest compilation is bounded to 500 operations. Responses are bounded to
  200 KB before parsing and text fallbacks to 20,000 characters.
- Invocation lifecycle stores metadata only: connector, operation, method,
  timestamps, and processing/completed/failed status.

## Residual risks

- Provider manifests can describe semantically dangerous operations even when
  technically valid. Human approval must judge the exact arguments and effect.
- API-key placement varies by provider; the generic runtime currently uses a
  bearer header. Provider adapters may override this only through reviewed code.
- OAuth authorization-code initiation depends on provider-issued client IDs,
  redirect URIs, and consent configuration. The current UI accepts encrypted
  OAuth token material; provider-specific popup initiation must not be fabricated
  for services that have not issued Raiker an OAuth client.
- Several catalog services expose partner/private APIs only. They remain
  discoverable and installable but cannot execute until the owner registers an
  authorized manifest and credentials for that service.

## Verification

- Catalog coverage, encrypted-at-rest storage, fail-closed key handling,
  principal isolation, install/auth/enable/uninstall lifecycle, manifest bounds,
  model tool exposure, session context, write approval, exactly-once execution,
  and sub-200 ms manifest compilation are covered by
  `tests/test_connector_ecosystem.py`.
