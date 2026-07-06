# Command Reference

> Use Raiker › Command Reference. Back to [Use Raiker](use-raiker.md).

The full catalog is in [`RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](../RAIKER_TOOL_AND_PLUGIN_CATALOG.md).
The runtime-governance commands:

| Command | What it does |
|---|---|
| `/bootstrap-owner` | Create the owner principal (first run) |
| `/runtime-mode status\|activate\|disable` | View or set the runtime mode |
| `/capability-gates` | List all capability gates and their state |
| `/capability-gate <cap>` | Show one capability's gate detail |
| `/capability-gate enable <cap> --state <state> --confirm <token>` | Enable a capability (human gate manager only) |
| `/capability-gate disable <cap>` | Disable a capability |
| `/capability-mode <cap> [ask\|deny\|always_allow\|auto]` | View or set a capability's decision mode |
| `/runtime-readiness` | Summarize runtime mode, owner, gates |
| `/model use --provider <p> --model <m>` | Select the active model backend |
| `/approve`, `/deny` | Resolve an approval (metadata-only) |
