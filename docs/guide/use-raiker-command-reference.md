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
| `/capability-mode <cap> [ask\|deny\|allow\|auto]` | View or set a capability's standing decision mode (`ask` is the default; `always_allow` accepted as a legacy alias for `allow`) |
| `/runtime-readiness` | Summarize runtime mode, owner, gates |
| `/model use --provider <p> --model <m>` | Select the active model backend |
| `/approve <id>`, `/deny <id>` | Resolve one pending approval by id (metadata-only). Distinct from the per-capability decision modes above: this approves/rejects a single queued action, `/capability-mode` sets the standing policy |
