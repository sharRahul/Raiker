# Threat Model — Local Container Execution (Phase 4, slice 3)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capability is now
> integrated and governed/default-ask; it was historically disabled/deferred
> before its executor landed. Approval resolution is metadata-only.

Per-capability threat model required by
[`docs/RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) before
`container_execution_cap` may join `REAL_EXECUTOR_CAPABILITIES`. This covers
**local** Docker only; SSH/Daytona use separate owner-profile-gated executors,
and other remote/cloud providers stay fail-closed.

## What the executor does

`raiker/runtime/executors/containers.py::ContainerExecutionExecutor` runs an
owner-allowlisted image via `docker run` with a hardened, sandboxed-first flag
set, and returns metadata only.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Owner image allowlist | `RAIKER_CONTAINER_IMAGE_ALLOWLIST` (comma-separated). Empty ⇒ everything denied (`image_not_allowed`). |
| No network | `--network none`. |
| No host filesystem | No bind mounts / volumes are ever added. |
| Least privilege | `--cap-drop ALL`, `--security-opt no-new-privileges`, `--read-only` rootfs. |
| Resource bounds | `--memory 512m`, `--cpus 1`, `--pids-limit 256`, `--rm`, capped timeout. |
| Daemon absence | `command_not_found:docker` ⇒ `docker_unavailable` (fail closed, never fake success). |
| No data leakage | Artifacts carry exit code + byte counts only — never stdout/stderr content. |
| Only `docker` | The container runner's command allowlist is exactly `{docker}`; the shell executor cannot launch docker. |
| AI principals | Capability gate + `route_action` block non-human principals from running or enabling the gate. |

## Activation requirements

Default gate state is **DISABLED**. Enabling requires a HUMAN
`runtime_gate_manager`, the `local_single_user_runtime` mode (this is local
Docker, not networked execution), the registered executor, a
`threat_model_acks` row referencing this document, and a human confirmation
token. AI principals can never flip the gate.

## Residual risks & non-goals

- Container escape is the principal residual risk; the flag set
  (no network, no mounts, dropped caps, read-only, no-new-privileges, pid/mem/cpu
  limits) minimises it, and the **image allowlist is the trust boundary** — only
  images the owner vets can run. A live-daemon successful run is verified
  manually (CI exercises governance + fail-closed paths via an injected runner).
- Out of scope: host bind mounts, networked containers, GPU/privileged mode,
  Kubernetes, and arbitrary remote/cloud providers. Those remain gated and fail
  closed; the separately modeled SSH/Daytona executors are out of scope here.
