# Commands and interactive mode

The `raiker` terminal is a governed client. Slash commands inspect or request
actions through the same policy and runtime-authority path as the local web API.
Unknown commands and unsupported state transitions fail safely.

Use `/help` for interactive help, `/status` for local posture, and
`/runtime-readiness` for governance blockers. The complete command list is
maintained in [RAIKER_TOOL_AND_PLUGIN_CATALOG.md](RAIKER_TOOL_AND_PLUGIN_CATALOG.md).
