# Raiker user guide

This guide explains how to install, configure, use, and safely operate Raiker.
It is written for people using the web dashboard or terminal client; you do not
need to understand Raiker's internal architecture first.

The same task-oriented guide is available in a running Raiker under
**Utilities → Guide**.

## Start here

If this is your first time using Raiker, read these pages in order:

1. [Getting started](getting-started.md) — requirements, installation, first
   launch, and the local owner account.
2. [Connecting a model](connecting-a-model.md) — connect a local, home-lab, or
   hosted model and confirm it is ready.
3. [Permissions and the runtime](permissions-and-runtime-modes.md) — decide
   what Raiker may do and when it must ask.
4. [Dashboard and observability](dashboard-and-observability.md) — understand
   every main area and see what Raiker is doing.

## Use Raiker

| Goal | Guide |
|---|---|
| Have conversations, attach files, use memory, and review approvals | [Working in Chat](working-in-chat.md) |
| Plan and change code, run commands, commit, and push | [Working in Build](working-in-build.md) |
| Run work now, later, repeatedly, or in the background | [Tasks and projects](tasks-and-projects.md) |
| Add connectors, MCP servers, skills, hooks, plugins, or channels | [Extensions and MCP](extensions-and-mcp.md) |
| Start Raiker at sign-in, pause it, update it, or remove it | [Managing the Raiker host](managing-the-host.md) |
| Understand accounts, credentials, audit records, and privacy choices | [Security and privacy](security-and-privacy.md) |
| Check what is unavailable or deliberately restricted | [Known limits](known-limits.md) |
| Resolve a refusal, reason code, blank page, or connection problem | [Troubleshooting](troubleshooting.md) |

## The two ideas that prevent most confusion

### A model must be ready

Selecting a model records a preference. Raiker enables model-backed work only
after the exact provider endpoint and model pass a readiness check. Open
**Models**, connect a provider, choose a model, and run **Check again**. The
[model guide](connecting-a-model.md) explains local and hosted setups.

### Permission has layers

Raiker is owner-authoritative and monitored. Connecting a provider authorizes
that provider's endpoint, but actions such as writing a file or running a
command still pass through a capability gate, a decision mode, the current
turn's posture, and—when required—an approval. The agent cannot increase its
own authority. See [Permissions and the runtime](permissions-and-runtime-modes.md).

## Where data lives

Raiker is local-first. The owner account, conversations, configuration, audit
records, and encrypted credentials belong to the Raiker instance on your
machine. `raiker-app` uses the normal application-data directory for your
platform; `raiker-app --workspace PATH` instead keeps instance data in
`PATH/.raiker/`. Run `raiker-app --print-paths` to see the exact paths before
making backups or uninstalling.

## Technical and project documentation

The user guide describes supported workflows. For implementation details,
contracts, security boundaries, verification evidence, and development plans,
use the [complete documentation index](../README.md). If a user guide and a
technical status document disagree, the
[implementation status](../architecture/IMPLEMENTATION_STATUS.md) is the source
of truth for what the current build implements.
