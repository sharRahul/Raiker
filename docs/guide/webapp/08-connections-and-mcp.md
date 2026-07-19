# 8. Connections & MCP

## Connections (the Connector Store)

**Connections** is a store of governed service connectors — GitHub, Gmail, Google
Calendar, Slack, Hugging Face, NVIDIA, Vercel, Wolfram, Google Drive, YouTube,
Signal, Booking.com, and more — filterable by category (Development,
Productivity, Communication, Media, Travel, On-demand).

![The Connector Store](../screenshots/working/12-connections-store.png)

### Before you connect anything: set the vault key

Every card sits under a banner: **"Configure `RAIKER_CONNECTOR_VAULT_KEY` before
linking accounts. Credentials fail closed without it."** Set a valid vault key
first (see [page 9](09-security-vault-and-settings.md)) — otherwise saving a
credential fails closed.

### Installing a connector

1. Set a valid vault key (once).
2. On a connector card, click **Install**.
3. The card flips to an installed state showing **Authentication required**, with
   **Connect via MCP** and **Manage** actions.

![GitHub installed, awaiting auth](../screenshots/working/13-connector-installed.png)

You can also **Import manifest** to add a connector from a manifest file, and
search connectors by name.

> ✅ **Verified:** with a valid vault key set, **Install** works and moves the
> connector to "Authentication required". Without a valid vault key, credential
> storage fails closed — as intended.

## MCP Servers

**MCP Servers** lets you build, connect, and monitor governed local or remote
Model Context Protocol servers for this workspace.

![The MCP Servers view](../screenshots/working/17-mcp-servers.png)

The view offers a **Server name** field, a **Template** picker (e.g. "Sample echo
server (safe starter)"), and a **Create server** button.

> ⚠️ **Gated by default.** The MCP builder/connector capabilities are **disabled**
> on a fresh workspace, and the page tells you so: *"The MCP builder and connector
> capabilities are disabled. Enable them in Capabilities to create or test
> servers."* Clicking **Create server** while disabled returns a governed
> **403** with a clear message rather than doing anything.
>
> To use MCP you must enable `mcp_builder_runtime` / `mcp_connector_runtime` in
> **Capabilities**. These are **Tier-2** gates: turning them on requires a
> **confirmation token** and a threat-model acknowledgement in the step-up dialog
> (the same operator/CLI-issued token used for shell/network capabilities).
> Minor UX issue: the **Create server** button is clickable even while the
> capability is off — see
> [FIX-04](../TO_BE_FIXED.md#fix-04--mcp-create-server-button-is-clickable-while-the-capability-is-disabled).

Next: [Security, vault & settings →](09-security-vault-and-settings.md)
