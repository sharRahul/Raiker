# Extensions and MCP

**Extensions** has four tabs: Connectors, MCP servers, Plugins, Channels.

## Connectors

A connector is a governed link to an outside service. Raiker keeps four facts
about each one **separate** and confirms all of them server-side before it will
call anything:

| Fact | Meaning |
|---|---|
| Installed | Present in the workspace |
| Connected | An account credential is stored (its value is never shown) |
| Enabled | Switched on for this session |
| Usable | Every condition confirmed by the server |

A connector appearing in the catalogue means nothing on its own. The readiness
counters at the top read `0 usable` on a fresh workspace, which is correct.

Reference connectors with real, governed read paths: **GitHub**, **Gmail**,
**Google Calendar**, **Slack**. Each needs, at minimum:

1. its capability gate on (`connector_github_runtime`, etc.);
2. a decision mode above the default `ask`;
3. an owner credential in the server environment (`RAIKER_GITHUB_TOKEN`, …);
4. its host on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`.

Miss any one and the read fails closed with a named reason —
`connector_gate_disabled`, `connector_withheld_ask`, `connector_not_configured`,
`connector_egress_denied`. Fetched content is always framed as **untrusted
data**, never as instructions.

**Import manifest** adds a manifest-driven connector.

## MCP servers

Raiker can build, connect to, and monitor Model Context Protocol servers.

**Prerequisites:** both `mcp_builder_runtime` and `mcp_connector_runtime` must
be at a **runtime** state, which means a runtime-enablement mode must be active
first (see [Permissions and runtime modes](permissions-and-runtime-modes.md)).
Until then the form is disabled.

To create one:

1. Enter a server name.
2. Pick a template — *Sample echo server (safe starter)* ships with Raiker.
3. **Create server**. The generated file lands at
   `.raiker/mcp/servers/<name>.py`; writing it goes through the normal file-write
   approval path.
4. **Test** connects and discovers tools. The echo template exposes `echo` and
   `workspace_ping`.

Each server card shows its command, template, last connection, discovered tools,
and recent monitored sessions. Controls: **Test**, **Stop** / **Resume**,
**Rename**, **Delete**. Stop is an instant containment switch — it refuses all
sessions for that connection and is revocable.

**Current limit (BUG-12):** a connected server's tools are **not** offered to
the model in Chat. MCP works today as a management and monitoring surface, not
yet as an agent capability. See [To be fixed](../plans/TO_BE_FIXED.md).

## Plugins and Channels

Both tabs are intentionally empty and say so:

> A plugin cannot render its own page here until Raiker has an accepted route,
> permission, and accessibility contract for it. Listing them early would
> suggest an authority the runtime does not enforce, so this tab stays empty on
> purpose.

> Inbound and outbound delivery needs an accepted contract and threat model
> before Raiker offers controls for it. This tab exists so the gap is visible
> rather than silently missing.

No plugin code runs in your browser.
