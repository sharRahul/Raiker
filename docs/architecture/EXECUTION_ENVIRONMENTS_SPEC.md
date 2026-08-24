# Execution Environments Specification

Raiker can execute work locally or in isolated, remote, containerised, or cloud environments according to phase-scheduled execution profiles. Execution environments are high-risk because they can mutate files, consume resources, leak data, or run untrusted code.

Local native and contained container execution remain available through
policy-gated tools. Owner-configured SSH and existing Daytona sandboxes now have
real, approval-required executors. Other profile types remain documented and
fail closed until they receive an executor and the controls below.

## Current implemented slice

- Settings stores only owner-scoped profile metadata and environment-variable
  credential references; raw keys and private-key contents are rejected.
- SSH uses `BatchMode=yes`, strict host-key checking, an explicit identity-file
  reference, bounded output, and a 300-second hard timeout.
- Daytona targets an existing sandbox, injects its API key only into the child
  CLI process, atomically reserves against cumulative profile exposure, and
  returns bounded result metadata. An append-only ledger retains estimate,
  release, provider snapshot, reconciliation, and unavailable events.
- Chat, Build, and Schedule display the same selected profile and capacity
  facts. Selection grants no authority: the capability gate, decision mode,
  policy review, approval, and owner/profile match are rechecked at execution.
- No surface silently falls back from local/container to SSH or cloud.

The provider-spend interface accepts cumulative billing snapshots. When a
deployment cannot supply them, the Runtime UI says `provider unavailable` and
the estimate remains reserved. Daytona's documented organization-usage endpoint
reports quota consumption rather than billed dollars, so Raiker deliberately
does not treat that response as cost.

---

## Execution Goals

Raiker execution environments must support:

1. local native tool execution;
2. command approval gates;
3. container sandboxing;
4. Git worktree isolation;
5. SSH remote hosts;
6. VPS and persistent sandbox profiles;
7. Kubernetes and managed cloud profiles;
8. cloud/serverless/GPU jobs;
9. resource limits;
10. network egress policy;
11. artifact capture;
12. cancellation and cleanup;
13. event logging.

---

## Environment Types

| Environment | Build phase | Default policy | Profile state |
|---|---:|---|---|
| `local_native` | Phase 1 | tools policy-gated | enabled |
| `git_worktree` | Phase 2 | needs approval | disabled until configured |
| `container` | Phase 4 | disabled until configured | profile available |
| `ssh` | Phase 4 | disabled until configured | profile available |
| `vps` | Phase 4 | disabled until configured | profile available |
| `kubernetes` | Phase 5 | disabled until configured | profile available |
| `modal` | Phase 5 | disabled until budget configured | profile available |
| `daytona` | Phase 4 | disabled until configured | profile available |
| `managed_cloud` | Phase 5 | disabled until managed policy configured | profile available |

---

## Execution Profile Schema

```json
{
  "schema_version": "1.0",
  "execution_profile_id": "local-safe",
  "environment_type": "local_native",
  "build_phase": "phase_1",
  "default_state": "enabled",
  "workspace_root": "/workspace/project",
  "network": {
    "egress_allowed": false,
    "allowed_hosts": []
  },
  "resources": {
    "max_runtime_seconds": 300,
    "max_stdout_bytes": 200000,
    "max_stderr_bytes": 200000,
    "max_parallel_processes": 2
  },
  "filesystem": {
    "workspace_only": true,
    "allow_writes": false,
    "ignored_paths": [".git", "node_modules", ".venv"]
  },
  "secrets": {
    "inject_env": false,
    "allowed_secret_refs": []
  },
  "artifacts": {
    "capture_stdout": true,
    "capture_stderr": true,
    "retention": "task_lifetime"
  }
}
```

---

## Local Native Execution

Local native execution is allowed only through tool broker actions.

Requirements:

- cwd must be explicit;
- command must be policy-reviewed;
- timeout required;
- stdout/stderr bounded;
- environment redacted;
- cancellation supported;
- no silent background process unless task manager owns it;
- command result event-logged.

---

## Git Worktree Isolation

Git worktree execution creates a separate working tree for risky edits.

Rules:

- worktree creation requires approval;
- branch/worktree name must be deterministic and safe;
- cleanup must be explicit;
- checkpoints must link to worktree;
- diff/merge plan must be shown before applying to main workspace;
- worktree state appears in TUI/Desktop/Web dashboard.

---

## Container Execution

Container execution must define:

- image source;
- image digest/checksum;
- network mode;
- mounted paths;
- user ID;
- resource limits;
- secret reference policy;
- artifact paths;
- cleanup policy.

No unpinned image execution by default.

---

## SSH, VPS, And Persistent Sandbox Execution

Remote or persistent sandbox execution requires:

- host/profile allowlist;
- credential reference, not raw secret;
- command policy;
- environment profile;
- data egress review;
- artifact retrieval policy;
- audit log;
- explicit cleanup or persistence policy;
- no inherited approval from local command execution.

---

## Kubernetes And Managed Cloud Execution

Managed remote execution requires:

- provider policy;
- cost budget;
- data sensitivity review;
- region policy;
- artifact retention;
- cancellation support;
- billing event logs;
- managed policy if multi-user or enterprise;
- no silent fallback from local to cloud.

---

## Artifact Handling

Execution artifacts must include artifact ID, source task/action, path or storage URI, size, checksum, sensitivity, retention, export policy, and linked execution profile.

---

## Events

Required events:

- `execution_profile_available`
- `execution_profile_loaded`
- `execution_environment_prepared`
- `execution_started`
- `execution_stdout_chunk`
- `execution_stderr_chunk`
- `execution_completed`
- `execution_failed`
- `execution_cancelled`
- `execution_cleanup_started`
- `execution_cleanup_completed`
- `artifact_created`
- `artifact_exported`

The implemented Daytona cost ledger is a separate append-only record with
`reserved`, `released`, `provider_snapshot`, `reconciled`, and
`provider_unavailable` event types. Budget admission is serialized with an
immediate database transaction and fails closed if committed exposure plus the
new estimate exceeds the owner limit.

---

## Testing Requirements

Tests must prove:

- local command execution cannot run outside broker;
- timeout cancels command;
- output is truncated and logged;
- network commands denied by default;
- SSH and Daytona remain unavailable until an owner configures and selects a
  valid profile; VPS, Kubernetes, Modal, and managed-cloud profiles remain
  disabled until an executor is implemented;
- artifact metadata includes checksum;
- cancellation emits events;
- dashboard can list configured and unconfigured execution profiles.
