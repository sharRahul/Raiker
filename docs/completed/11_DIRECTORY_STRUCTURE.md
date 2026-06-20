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
