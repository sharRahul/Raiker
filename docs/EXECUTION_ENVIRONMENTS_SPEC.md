# Execution Environments Specification

Raiker can execute work locally or, in future phases, in isolated or remote environments. Execution environments are high-risk because they can mutate files, consume resources, leak data, or run untrusted code.

Phase 1 supports local native execution only through policy-gated tools.

---

## Execution Goals

Raiker execution environments must support:

1. local native tool execution;
2. shell/PowerShell approval gates;
3. Docker sandboxing in future phases;
4. Git worktree isolation;
5. SSH remote hosts;
6. cloud/serverless/GPU jobs;
7. resource limits;
8. network egress policy;
9. artifact capture;
10. cancellation and cleanup;
11. event logging.

---

## Environment Types

| Environment | Phase | Default policy |
|---|---:|---|
| `local_native` | Phase 1 | tools policy-gated |
| `git_worktree` | Phase 2 | needs approval |
| `docker` | Phase 3 | deny until configured |
| `ssh` | Future | deny until configured |
| `vps` | Future | deny until configured |
| `kubernetes` | Future | deny until configured |
| `modal` | Future | deny until configured |
| `daytona` | Future | deny until configured |
| `managed_cloud` | Future | deny until configured |

---

## Execution Profile Schema

```json
{
  "schema_version": "1.0",
  "execution_profile_id": "local-safe",
  "environment_type": "local_native",
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

Future worktree execution creates a separate working tree for risky edits.

Rules:

- worktree creation requires approval;
- branch/worktree name must be deterministic and safe;
- cleanup must be explicit;
- checkpoints must link to worktree;
- diff/merge plan must be shown before applying to main workspace.

---

## Docker Execution

Future Docker execution must define:

- image source;
- image digest/checksum;
- network mode;
- mounted paths;
- user ID;
- resource limits;
- secrets policy;
- artifact paths;
- cleanup policy.

No unpinned image execution by default.

---

## SSH And Remote Execution

Remote execution requires:

- host allowlist;
- credential reference, not raw secret;
- command policy;
- environment profile;
- data egress review;
- artifact retrieval policy;
- audit log.

Remote execution cannot use approval inherited from local shell.

---

## Cloud/Batch/GPU Execution

Cloud execution requires:

- provider policy;
- cost budget;
- data sensitivity review;
- region policy;
- artifact retention;
- cancellation support;
- billing event logs;
- no silent fallback from local to cloud.

---

## Artifact Handling

Execution artifacts must include:

- artifact ID;
- source task/action;
- path or storage URI;
- size;
- checksum;
- sensitivity;
- retention;
- export policy.

---

## Events

Required events:

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

---

## Testing Requirements

Tests must prove:

- shell cannot run outside broker;
- timeout cancels command;
- output is truncated and logged;
- network commands denied by default;
- Docker/SSH/cloud profiles denied until configured;
- artifact metadata includes checksum;
- cancellation emits events.
