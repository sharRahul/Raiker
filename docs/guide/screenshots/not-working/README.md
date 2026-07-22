# Screenshots — Not Working

Real captures of the problems found during the end-to-end web-app test run. Each
maps to an entry in [`../../TO_BE_FIXED.md`](../../TO_BE_FIXED.md).

> **FIX-02, FIX-03, and TASK-01 (rows 2, 3, and 6 below) are now resolved in this branch** —
> these images are kept as "before" evidence. The working hosted-Anthropic flow
> is captured in [`../working/`](../working/) (`26`–`29`).

| File | Shows | Tracked as |
|------|-------|-----------|
| `01-firstrun-cta-confusion.png` | First-run panel: heading says "Create a User Account" but the primary button says "Unlock Raiker" | [FIX-01](../../TO_BE_FIXED.md#fix-01--first-run-primary-button-says-unlock-raiker-but-no-account-exists-yet) |
| `02-model-connect-redacted-error.png` | Anthropic connect fails with "Could not connect (403: `[REDACTED_SECRET]`)" | [FIX-02](../../TO_BE_FIXED.md#fix-02--connect-error-is-over-redacted-to-redacted_secret) |
| `03-hosted-model-enable-deadend.png` | Enabling "Hosted models": "Activation is blocked. Satisfy the activation requirement first." with no way to satisfy it | [FIX-03](../../TO_BE_FIXED.md#fix-03--hosted-model-activation-is-impossible-from-the-web-dashboard) |
| `04-vault-key-invalid-no-hint.png` | Vault key rejected: "connector_vault_key_invalid" with no format hint | [FIX-07](../../TO_BE_FIXED.md#fix-07--vault-key-field-requires-a-fernet-key-but-gives-no-format-hint) |
| `05-mcp-capability-disabled.png` | "Create server" clickable while MCP capability disabled → 403 | [FIX-04](../../TO_BE_FIXED.md#fix-04--mcp-create-server-button-is-clickable-while-the-capability-is-disabled) |
| `2026-07-22-task-title-only-422.png` | Before: the task form enabled title-only submission, then the server rejected it because instructions are required | [TASK-01](../../../plans/2026-07-22-web-app-user-verification-to-be-fixed.md#task-01--instructions-are-required-but-the-task-form-allows-an-empty-submission) |

> None of these are requests to weaken a security control. They are experience
> problems: unclear errors, a dead-end flow, and a missing format hint around
> Raiker's (correct) fail-closed behaviour.
