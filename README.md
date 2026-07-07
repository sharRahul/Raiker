# Raiker

Raiker is a governed local project.

## Features

- The launchable local UIs are the plain local terminal client and the local web dashboard.
- Old UI planning documents were removed as cleanup.
- No replacement UI or UX plan is added in this cleanup PR.

## Architecture & Tech Stack

Architecture lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Current implementation truth lives in [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).

## Quick Start & Installation

Use `raiker --help` after installing the project.

## Project Status

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

- Phase 8 deferred clients remain deferred.
- Approval resolution is metadata-only.
- Durable memory mutation is broker-governed.
- Capabilities without real executors remain disabled/deferred and fail closed.
- Local single-user hardening includes owner bootstrap, persisted owner principal, acting-principal resolution, runtime_gate_manager authorization, and recovery flow.
- Deferred dangerous capabilities stay fail-closed unless their real executor, policy, storage, audit, and tests exist.
- Approval execution relay is a separate governed capability; approval resolution itself remains metadata-only.

## Contributing & Workflow

See [`docs/LOCAL_VALIDATION_GATE.md`](docs/LOCAL_VALIDATION_GATE.md).

## License

Released under the MIT License. See [`LICENSE`](LICENSE).
