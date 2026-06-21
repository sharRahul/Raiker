> **Foundation document.** This is a living design-foundation doc (moved from `docs/completed/` during the 2026-06-21 documentation alignment). For current implementation status see the canonical ledger `docs/IMPLEMENTATION_STATUS.md`; for outstanding work see `docs/GAP_AND_TODO_ANALYSIS.md`. As of that date: Phases 1–9 foundations are in place (no Phase 8), the launchable UI is a local terminal client (native Textual Rich TUI + plain fallback), and all runtime execution remains disabled.

# 11 Directory Structure

The implementation must start with this scaffold.

```text
/core
  /contracts
  /agent_gateway
  /session_manager
  /agent_runtime
  /model_router
  /tool_broker
  /policy_engine
  /memory_service
  /event_log
  /checkpoint_service
  /plugin_manager
  /hook_engine
  /channel_manager
  /security
  /deployment_adapters
    /local
    /docker
    /ssh
    /daytona
    /modal
    /external_hosting
/apps
  /cli
  /tui
  /desktop
  /web
  /ide
/clients
  /slack
  /signal
  /teams
  /discord
  /email
  /voice
  /hotkeys
  /rest
  /webhooks
/plugins
/skills
/agents
/docs
/tests
/security_tests
/examples
```

Rules:
- Do not create alternative top-level directories without ADR.
- Future-phase directories may contain README stubs.
- Phase 1 code should live primarily in `/core` and `/apps/cli`.
