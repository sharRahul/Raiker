# Containerised Tool Execution Design

## Scope

Complete ADD-01 by extending Raiker's existing command sandbox into a governed,
per-tool container boundary. The delivered feature supports Docker and Podman,
mounts the selected repository read-only with one isolated writable output
directory, exposes real readiness instead of fixed false flags, and tells the
owner which execution profile will be used or why it is unavailable.

This work does not move an entire agent turn, Raiker's database, provider
credentials, connectors, or network-backed tools into a container. Those tools
retain explicit host or remote profiles. A tool assigned to an unavailable or
unsupported container profile fails closed; it never falls back to the host.

## Existing Foundation

- `raiker/runtime/executors/containers.py` already provides bounded Docker
  execution for the `container_execution_cap` executor and for owner-granted
  shell commands.
- `raiker/execution/profiles.py` currently exposes four static, coarse profiles
  without tool assignments or runtime availability.
- `raiker/tools/broker.py` is the common governed tool boundary and therefore
  remains responsible for policy, approvals, audit records, and result
  redaction.
- `raiker/remote/readiness.py`, `raiker/storage/lifecycle_evidence.py`, and
  `raiker/workspace/views.py` still report container execution as a constant
  `False`.
- The web application already presents execution environments in Settings and
  on work composers, but it cannot show a per-tool container choice or a
  concrete unavailability reason.

## Architecture

### Execution profiles

`raiker/execution/profiles.py` will own immutable profile definitions and their
validation. A tool execution profile contains:

- a stable profile id and owner-facing name;
- an execution kind: `host`, `container`, `ssh`, or `daytona`;
- for a container profile, the runtime choice `docker` or `podman` and an
  owner-allowlisted image;
- the exact tool names that may use the profile;
- repository access (`none` or `read_only`);
- whether a writable output directory is exposed;
- resource ceilings and approval metadata.

The shipped default preserves current behaviour with explicit host profiles.
The existing command sandbox becomes a container profile rather than a separate
special case. Operator configuration may assign supported local tools to an
enabled container profile. Unknown tools, duplicate assignments, unsupported
container tools, invalid images, and unrecognised runtime names invalidate that
profile with a machine-readable reason.

Profile resolution always returns an explicit result: the selected profile or
a refusal. It never converts a failed container choice into host execution.

### Runtime abstraction

`raiker/runtime/executors/containers.py` will expose a runtime-neutral request
and a small container runtime interface. Docker and Podman implementations will
produce equivalent invocations for:

- an ephemeral `--rm` container;
- no network;
- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- bounded memory, CPU, process count, output, and wall-clock duration;
- non-root execution where the host exposes uid/gid;
- the selected repository mounted read-only at `/repository` when requested;
- one action-scoped host directory mounted read/write at `/workspace-output`.

The runtime executable is selected as an argument from the validated profile,
not interpolated from model input. Only `docker` and `podman` enter the process
allowlist. A missing executable, unavailable daemon, rejected image, malformed
runner response, timeout, or non-zero exit returns a specific governed failure.

### Generic tool bridge

Container-capable tools use a bounded JSON bridge implemented as a module that
can run inside an approved Raiker tool image. The broker sends one request on
standard input containing the tool name, redacted execution context, arguments,
repository path `/repository`, and writable path `/workspace-output`. The
bridge invokes only a static registry of container-safe tool handlers and emits
one JSON result on standard output.

The request is not written to disk or included in the command line. Existing
tool-specific audit redaction rules remain authoritative. The host broker
parses and validates the response before creating the normal `ToolResult`.

Initial container-safe coverage includes local repository inspection/search and
bounded command execution. Tools that require the Raiker database, vault,
provider credentials, connectors, MCP, egress, host lifecycle control, or an
approval transaction remain explicitly host/remote-only. Assigning one of
those tools to a container profile produces
`container_profile_tool_unsupported` before execution.

Mutation tools do not write directly through the read-only repository mount.
They may produce candidates in `/workspace-output`; the existing host-side
preview, approval, checkpoint, stale-state validation, and atomic application
remain the only route by which a candidate reaches the repository.

### Broker routing and governance

The existing `ToolBroker.execute` flow continues to authenticate, evaluate
policy, obtain or validate approval, and emit the started event before choosing
an executor. Immediately before the existing handler call, the broker resolves
the tool's execution profile:

1. Host/remote profiles continue through their current executor.
2. A valid, available container profile invokes the generic bridge.
3. An invalid, unavailable, or unsupported container profile returns a normal
   failed `ToolResult` and a named audit reason.

The result then passes through the current result-scrubbing, durable event, and
session-transcript paths. Container routing grants no new capability and does
not weaken any approval requirement.

### Writable workspace lifecycle

Each container call receives a unique directory below
`.raiker/container-workspaces/<action-id>`. Only that directory is mounted
writable. Its resolved path must remain inside the selected repository's
`.raiker/container-workspaces` root.

Ordinary scratch data is removed after the result is validated. Candidate
artifacts that must survive for approval or download are moved through the
existing governed artifact/checkpoint service before cleanup. Cleanup failure
is recorded as a finding and must not turn an execution failure into success.

### Readiness and API presentation

Container readiness becomes derived state. `container_execution_enabled` and
`ready_for_container_execution` are true only when:

- the owner capability gate is enabled;
- at least one enabled container profile is structurally valid;
- its runtime executable is available;
- its image is present in the owner image allowlist; and
- its tool bridge is available.

The readiness response lists blockers such as `container_gate_disabled`,
`container_profile_missing`, `container_runtime_unavailable:podman`,
`container_image_not_allowed:<profile-id>`, and
`container_tool_bridge_unavailable:<profile-id>`. Remote and cloud readiness
remain independent and keep their existing semantics.

The execution-environment API adds the profile's runtime, assigned tool count,
availability, and reason. It never exposes host paths, image registry
credentials, command arguments, or tool payloads.

### Owner interface

Settings -> Runtime presents container profiles alongside the existing host,
SSH, and Daytona choices. Each profile shows Docker or Podman, its approved
image, repository access, writable-output policy, assigned-tool count, and one
availability label. Unavailable profiles remain visible and name the corrective
action.

Composer environment badges and execution previews name the effective profile.
If a requested profile cannot run, the transcript shows the same plain-language
reason returned by the API. No UI control can select an image outside the
operator allowlist or make an unsupported tool silently use the host.

## Error Handling

All boundary failures are fail-closed and machine-readable. Expected refusal
families include invalid profile configuration, missing runtime, unavailable
daemon, disallowed image, unsupported tool, unsafe workspace path, bridge
protocol error, timeout, resource failure, and container exit status.

User-facing messages state the failed profile, the tool, and the next owner or
operator action. Audit events retain identifiers and counts but not request or
response content beyond the existing tool-specific rules.

## Testing

Implementation follows red-green-refactor cycles.

- Unit tests cover profile validation/resolution, Docker and Podman command
  parity, Windows and POSIX path handling, read-only and writable mounts,
  executable allowlists, response parsing, cleanup, and every fail-closed path.
- Broker tests prove that a container assignment reaches the bridge, a host
  assignment reaches the existing handler, and an unavailable container never
  falls back to the host.
- Readiness and API tests replace fixed-false expectations with derived-state
  cases while proving remote/cloud flags are unchanged.
- Web component tests cover profile details, badges, unavailable reasons, and
  selection constraints.
- Live Playwright verification configures the feature through the UI, exercises
  an available profile and an unavailable profile, and captures screenshots of
  the selector, execution evidence, and refusal state.
- The completed application is smoke-tested through Anthropic, OpenRouter, and
  the requested Ollama model. Credentials are entered only through the UI and
  are never committed or printed.

## Documentation and Delivery

Update `docs/plans/TO_BE_ADDED.md` in its existing format to mark ADD-01 shipped
and cite the implementation and evidence. Record any newly discovered defect in
`docs/plans/TO_BE_FIXED.md` unless it is fixed in the same run. Update operator,
security, runtime, and live-test documentation wherever the old constant-false
or Docker-only description appears.

Before delivery, run the focused tests, full Python quality gate, web tests,
production build, and live Playwright scenarios. Review screenshots, commit all
intentional changes, push `main`, and monitor every GitHub Actions workflow for
the pushed commit until green. Any workflow regression is fixed and re-verified
under the same evidence requirements.

## Explicit Non-Goals

- Containerising the complete Raiker service or model loop.
- Giving network access to the default container profile.
- Copying provider credentials or the encrypted workspace database into a
  container.
- Replacing existing approval, checkpoint, policy, or audit mechanisms.
- Building micro-VM isolation, which remains ADD-12.
- Treating Docker and Podman as interchangeable when a configured profile names
  one explicitly.
