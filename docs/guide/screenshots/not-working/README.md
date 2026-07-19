# Screenshots — Not Working

Real captures of the problems found during the end-to-end web-app test run. Each
maps to an entry in [`../../TO_BE_FIXED.md`](../../TO_BE_FIXED.md).

| File | Shows | Tracked as |
|------|-------|-----------|
| `01-firstrun-cta-confusion.png` | First-run panel: heading says "Create a User Account" but the primary button says "Unlock Raiker" | [FIX-01](../../TO_BE_FIXED.md#fix-01--first-run-primary-button-says-unlock-raiker-but-no-account-exists-yet) |
| `02-model-connect-redacted-error.png` | Anthropic connect fails with "Could not connect (403: `[REDACTED_SECRET]`)" | [FIX-02](../../TO_BE_FIXED.md#fix-02--connect-error-is-over-redacted-to-redacted_secret) |
| `03-hosted-model-enable-deadend.png` | Enabling "Hosted models": "Activation is blocked. Satisfy the activation requirement first." with no way to satisfy it | [FIX-03](../../TO_BE_FIXED.md#fix-03--hosted-model-activation-is-impossible-from-the-web-dashboard) |
| `04-vault-key-invalid-no-hint.png` | Vault key rejected: "connector_vault_key_invalid" with no format hint | [FIX-07](../../TO_BE_FIXED.md#fix-07--vault-key-field-requires-a-fernet-key-but-gives-no-format-hint) |
| `05-mcp-capability-disabled.png` | "Create server" clickable while MCP capability disabled → 403 | [FIX-04](../../TO_BE_FIXED.md#fix-04--mcp-create-server-button-is-clickable-while-the-capability-is-disabled) |

> None of these are requests to weaken a security control. They are experience
> problems: unclear errors, a dead-end flow, and a missing format hint around
> Raiker's (correct) fail-closed behaviour.
