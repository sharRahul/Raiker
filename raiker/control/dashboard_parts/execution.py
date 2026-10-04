# mypy: disable-error-code="misc"
"""Execution environments: what exists, what is selected, and resetting one
(GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, cast

from raiker.contracts.ids import new_id, utc_now
from raiker.control.dtos import ControlResult
from raiker.control.views.execution import (
    BoundaryRefusal,
    ExecutionBoundaryView,
    ExecutionEnvironmentsView,
    ExecutionEnvironmentView,
)
from raiker.control.views.models import _DISABLED_STATES
from raiker.execution.profiles import (
    CONTAINER_PROFILE_TOOLS,
    DEFAULT_EXECUTION_PROFILES,
    ContainerRuntime,
    ExecutionProfile,
    RepositoryAccess,
    probe_execution_profile,
    validate_execution_profile,
)
from raiker.runtime.executors.containers import container_image_allowlist

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


class ExecutionService:

    def execution_boundary(
        self: DashboardService,
        owner_principal_id: str,
        *,
        project_id: str | None,
        user_id: str | None,
    ) -> ExecutionBoundaryView:
        """DEC-06 step 1 — Project → repository → environment → model, resolved here.

        ``project_id`` is the one input the client supplies, because Build's
        project travels with each turn rather than living in a server
        selection; it is resolved against this owner's own projects, and an id
        that names none is reported as no project, never trusted. Everything
        else is read from the stored selections a turn reads. The first link
        that would stop a turn is named, in order, with its one remedy.
        """
        from raiker.models.decision import ModelDecisionService
        from raiker.models.registry import ModelProfileRegistry

        project = (
            self.store.load_project(project_id, user_id) if project_id else None
        )
        repos = self.list_code_repos(owner_principal_id=owner_principal_id)
        repo = next(
            (item for item in repos.repos if item.repo_id == repos.selected_repo_id), None
        )
        environments = self.execution_environments(owner_principal_id)
        environment = next(
            (item for item in environments["environments"] if item["selected"]),
            next(iter(environments["environments"])),
        )
        decision = ModelDecisionService(self.store).decide(
            owner_principal_id, "build", project_id if project is not None else None
        )
        effective = decision.effective
        model_profile_id = effective.profile_id or None
        provider: str | None = None
        off_machine: bool | None = None
        if model_profile_id:
            try:
                profile = ModelProfileRegistry.load().resolve_profile_id(model_profile_id)
                provider = profile.provider
                off_machine = str(profile.raw.get("endpoint_kind", "")) in {
                    "remote_hosted",
                    "private_network",
                }
            except Exception:  # noqa: BLE001 — an unknown profile names no provider
                provider = None
        model = effective.model if effective.model and "<" not in effective.model else None

        refusal: BoundaryRefusal | None = None
        if project is None:
            refusal = {
                "step": "project",
                "reason_code": "build_project_required",
                "summary": "Build needs a project to run inside.",
                "remediation": "Choose or create a project for this work.",
                "action_href": "#/projects",
                "action_label": "Choose a project",
            }
        elif not environment["available"]:
            refusal = {
                "step": "environment",
                "reason_code": environment["availability_reason"] or "environment_unavailable",
                "summary": f"{environment['name']} is not available on this machine.",
                "remediation": "Set it up, or choose another place for commands to run.",
                "action_href": "#/settings?tab=runtime",
                "action_label": "Change where it runs",
            }
        elif model is None or not decision.ready:
            problem = decision.problem or {}
            refusal = {
                "step": "model",
                "reason_code": problem.get("reason_code", "no_model_selected"),
                "summary": problem.get("summary", "No model is selected."),
                "remediation": problem.get("remediation", "Choose a model on the Models page."),
                "action_href": "#/models",
                "action_label": "Open Models",
            }
        return {
            "project_id": project["project_id"] if project is not None else None,
            "project_name": project["name"] if project is not None else None,
            "repo_id": repo.repo_id if repo is not None else None,
            "repo_label": repo.label if repo is not None else None,
            "repo_kind": cast(Any, repo.kind) if repo is not None else None,
            "writable_root": (
                repo.local_subpath if repo is not None and repo.kind == "local" else None
            ),
            "environment_id": environment["profile_id"],
            "environment_name": environment["name"],
            "environment_available": bool(environment["available"]),
            "environment_boundary": environment.get("boundary"),
            "model_profile_id": model_profile_id,
            "model": model,
            "provider": provider,
            "model_source": effective.source or None,
            "model_ready": bool(decision.ready),
            "model_off_machine": off_machine,
            "ready": refusal is None,
            "refusal": refusal,
        }

    def execution_environments(
        self: DashboardService, owner_principal_id: str
    ) -> ExecutionEnvironmentsView:
        """List selectable execution targets without exposing credential values."""
        selected = self.store.selected_execution_environment(owner_principal_id)
        allowed_images = sorted(container_image_allowlist())
        gate = self.control.get_capability_gate("container_execution_cap", owner_principal_id)
        gate_enabled = gate is not None and gate.state not in _DISABLED_STATES
        default_image = allowed_images[0] if allowed_images else None
        default_profile = ExecutionProfile(
            "container_default",
            "container",
            name="Local container",
            runtime="docker",
            image=default_image,
            tools=("shell",),
            repository_access="read_only",
            writable_output=True,
        )
        default_probe = probe_execution_profile(default_profile)
        default_reason = (
            "container_gate_disabled"
            if not gate_enabled
            else (
                "container_image_required:container_default"
                if default_image is None
                else default_probe.reason_code
            )
        )
        local_profile = ExecutionProfile("local_native", "local")
        # The native boundary is measured, not declared: this probe runs the
        # real sandbox over the real workspace before the card can say anything
        # about it.
        native_profile = next(
            profile
            for profile in DEFAULT_EXECUTION_PROFILES
            if profile.profile_id == "native_sandbox"
        )
        native_probe = probe_execution_profile(
            native_profile, workspace_root=self.store.paths.workspace_root
        )
        environments: list[dict[str, Any]] = [
            {
                "profile_id": "local_native",
                "kind": "local",
                "name": "Local strict",
                "enabled": True,
                "configured": True,
                "available": True,
                "status": "ready",
                "selected": selected == "local_native",
                "credential_configured": True,
                "budget": None,
                "cost": None,
                "selected_for_commands": selected == "local_native",
                "assigned_tools": ["run_command"],
                "features": asdict(local_profile.features),
                "probe_checked_at": utc_now(),
                "availability_reason": None,
                "boundary": "host_reduced_isolation",
                "probe_observations": {},
            },
            {
                "profile_id": "native_sandbox",
                "kind": "native",
                "name": "Native OS sandbox",
                "enabled": True,
                "configured": True,
                "available": native_probe.available,
                "status": "ready" if native_probe.available else "unavailable",
                "selected": selected == "native_sandbox",
                "credential_configured": True,
                "budget": None,
                "cost": None,
                "selected_for_commands": selected == "native_sandbox",
                "assigned_tools": ["shell", "run_command"],
                "features": asdict(native_probe.features or native_profile.features),
                "probe_checked_at": native_probe.checked_at,
                "availability_reason": native_probe.reason_code,
                "boundary": native_probe.boundary,
                "probe_observations": dict(native_probe.observations),
                "runner_trust": native_probe.runner_trust,
            },
            {
                "profile_id": "container_default",
                "kind": "container",
                "name": "Local container",
                "enabled": True,
                "configured": default_image is not None,
                "available": default_reason is None,
                "status": "ready" if default_reason is None else "unavailable",
                "selected": selected == "container_default",
                "credential_configured": True,
                "budget": None,
                "cost": None,
                "runtime": "docker",
                "image": default_image,
                "repository_access": "read_only",
                "writable_output": True,
                "assigned_tool_count": 1,
                "availability_reason": default_reason,
                "selected_for_commands": selected == "container_default",
                "assigned_tools": ["shell"],
                "features": asdict(default_profile.features),
                "probe_checked_at": default_probe.checked_at,
            },
        ]
        for row in self.store.list_remote_execution_profiles(owner_principal_id=owner_principal_id):
            try:
                config = json.loads(row["config_json"])
            except (TypeError, ValueError):
                config = {}
            kind = "daytona" if row["profile_type"] == "cloud" else str(row["profile_type"])
            if kind == "container":
                raw_tools = config.get("tools", [])
                tools = (
                    tuple(str(tool) for tool in raw_tools if isinstance(tool, str))
                    if isinstance(raw_tools, list)
                    else ()
                )
                profile = ExecutionProfile(
                    str(row["profile_id"]),
                    "container",
                    name=str(row["name"]),
                    enabled=bool(row["enabled"]),
                    runtime=cast(ContainerRuntime | None, config.get("runtime")),
                    image=str(config.get("image") or "") or None,
                    tools=tools,
                    repository_access=cast(
                        RepositoryAccess, config.get("repository_access", "none")
                    ),
                    writable_output=bool(config.get("writable_output", False)),
                    config={**config, "owner_principal_id": owner_principal_id},
                )
                reason = validate_execution_profile(profile)
                if reason is None and profile.image not in container_image_allowlist():
                    reason = f"container_image_not_allowed:{profile.profile_id}"
                if reason is None and not gate_enabled:
                    reason = "container_gate_disabled"
                proof = probe_execution_profile(profile)
                if reason is None:
                    reason = proof.reason_code
                available = bool(profile.enabled and reason is None)
                environments.append(
                    {
                        "profile_id": profile.profile_id,
                        "kind": "container",
                        "name": profile.name,
                        "enabled": profile.enabled,
                        "configured": validate_execution_profile(profile) is None,
                        "available": available,
                        "status": "ready" if available else "unavailable",
                        "selected": selected == profile.profile_id,
                        "credential_configured": True,
                        "budget": None,
                        "cost": None,
                        "runtime": profile.runtime,
                        "image": profile.image,
                        "repository_access": profile.repository_access,
                        "writable_output": profile.writable_output,
                        "assigned_tool_count": len(profile.tools),
                        "selected_for_commands": selected == profile.profile_id,
                        "assigned_tools": list(profile.tools),
                        "features": asdict(profile.features),
                        "probe_checked_at": proof.checked_at,
                        "availability_reason": reason,
                        "config": {
                            "runtime": profile.runtime,
                            "image": profile.image,
                            "tools": list(profile.tools),
                            "repository_access": profile.repository_access,
                            "writable_output": profile.writable_output,
                            "egress_domains": list(config.get("egress_domains", [])),
                            "egress_ports": list(config.get("egress_ports", [])),
                            # Configuration is a request, not enforcement. This
                            # remains false until the real container bypass
                            # probe records a passing measurement.
                            "egress_enforcement": "not_proven",
                        },
                    }
                )
                continue
            credential_env = str(config.get("credential_env") or config.get("api_key_env") or "")
            credential_configured = bool(
                credential_env and os.environ.get(credential_env, "").strip()
            )
            configured = (
                bool(
                    config.get("host")
                    and config.get("user")
                    and config.get("host_public_key")
                    and config.get("host_key_sha256")
                    and credential_env
                )
                if kind == "ssh"
                else bool(config.get("sandbox_id") and credential_env)
            )
            remote_profile = ExecutionProfile(
                str(row["profile_id"]),
                cast(Any, kind),
                name=str(row["name"]),
                enabled=bool(row["enabled"]),
                tools=("shell",),
                config={**config, "owner_principal_id": owner_principal_id},
            )
            remote_proof = (
                probe_execution_profile(
                    remote_profile, workspace_root=self.store.paths.workspace_root
                )
                if configured and credential_configured
                else None
            )
            available = bool(
                row["enabled"]
                and configured
                and credential_configured
                and remote_proof is not None
                and remote_proof.available
            )
            budget = config.get("max_cost") if kind == "daytona" else None
            cost = (
                self.store.cloud_execution_cost_summary(
                    owner_principal_id, str(row["profile_id"]), max_cost=float(budget or 0)
                )
                if kind == "daytona"
                else None
            )
            environments.append(
                {
                    "profile_id": str(row["profile_id"]),
                    "kind": kind,
                    "name": str(row["name"]),
                    "enabled": bool(row["enabled"]),
                    "configured": configured,
                    "available": available,
                    "status": "ready"
                    if available
                    else (
                        "credential_required"
                        if configured and not credential_configured
                        else "unavailable"
                        if remote_proof is not None
                        else "configuration_required"
                    ),
                    "selected": selected == row["profile_id"],
                    "credential_configured": credential_configured,
                    "budget": budget,
                    "cost": cost,
                    "selected_for_commands": selected == row["profile_id"],
                    "assigned_tools": ["shell"],
                    "features": asdict(remote_profile.features),
                    "probe_checked_at": remote_proof.checked_at
                    if remote_proof is not None
                    else utc_now(),
                    "boundary": remote_proof.boundary
                    if remote_proof is not None
                    else "remote_recipient_tcb",
                    "probe_observations": dict(remote_proof.observations)
                    if remote_proof is not None
                    else {},
                    "availability_reason": None
                    if available
                    else (
                        remote_proof.reason_code
                        if remote_proof is not None
                        else (
                            "execution_environment_credential_required"
                            if configured and not credential_configured
                            else "execution_environment_configuration_required"
                        )
                    ),
                    "config": {
                        key: value
                        for key, value in config.items()
                        if key not in {"password", "token", "api_key", "secret"}
                    },
                }
            )
        if not any(item["selected"] for item in environments):
            environments[0]["selected"] = True
            selected = "local_native"
        return {
            "selected_profile_id": selected,
            "environments": cast(list[ExecutionEnvironmentView], environments),
            "container_options": {
                "runtimes": ["docker", "podman"],
                "images": allowed_images,
                "supported_tools": sorted(CONTAINER_PROFILE_TOOLS),
            },
        }

    def configure_execution_environment(
        self: DashboardService,
        *,
        profile_id: str | None,
        kind: str,
        name: str,
        config: dict[str, Any],
        enabled: bool,
        owner_principal_id: str,
    ) -> ControlResult:
        if kind not in {"ssh", "daytona", "container"}:
            return ControlResult(ok=False, reason_code="unsupported_execution_environment")
        forbidden = {"password", "token", "api_key", "secret", "private_key"}
        if any(key.casefold() in forbidden for key in config):
            return ControlResult(
                ok=False, reason_code="execution_credentials_must_use_environment_reference"
            )
        if kind == "container":
            raw_tools = config.get("tools")
            tools = (
                tuple(str(tool) for tool in raw_tools if isinstance(tool, str))
                if isinstance(raw_tools, list)
                else ()
            )
            profile = ExecutionProfile(
                profile_id or "container_pending",
                "container",
                name=name.strip() or "Local container",
                enabled=enabled,
                runtime=cast(ContainerRuntime | None, config.get("runtime")),
                image=str(config.get("image") or "") or None,
                tools=tools,
                repository_access=cast(RepositoryAccess, config.get("repository_access", "none")),
                writable_output=bool(config.get("writable_output", False)),
            )
            reason = validate_execution_profile(profile)
            if reason:
                return ControlResult(ok=False, reason_code=reason)
            if profile.image not in container_image_allowlist():
                return ControlResult(ok=False, reason_code="container_image_not_allowed")
            raw_domains = config.get("egress_domains", [])
            raw_ports = config.get("egress_ports", [])
            if raw_domains or raw_ports:
                try:
                    from raiker.execution.commands.egress_policy import EgressPolicy

                    policy = EgressPolicy(
                        tuple(str(value) for value in raw_domains),
                        tuple(int(value) for value in raw_ports),
                    )
                except (TypeError, ValueError):
                    return ControlResult(ok=False, reason_code="container_egress_policy_invalid")
                config = {
                    **config,
                    "egress_domains": list(policy.domains),
                    "egress_ports": list(policy.ports),
                }
        env_key = "credential_env" if kind == "ssh" else "api_key_env"
        credential_env = str(config.get(env_key, "")).strip()
        if (
            kind != "container"
            and credential_env
            and not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", credential_env)
        ):
            return ControlResult(ok=False, reason_code="invalid_execution_credential_reference")
        if kind == "ssh":
            host = str(config.get("host", "")).strip()
            user = str(config.get("user", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host) or not re.fullmatch(
                r"[A-Za-z0-9._-]{1,64}", user
            ):
                return ControlResult(ok=False, reason_code="invalid_ssh_profile")
            try:
                from raiker.execution.commands.known_hosts import host_key_fingerprint

                if (
                    host_key_fingerprint(str(config.get("host_public_key", "")))
                    != str(config.get("host_key_sha256", "")).strip()
                ):
                    return ControlResult(ok=False, reason_code="ssh_host_key_fingerprint_mismatch")
            except ValueError:
                return ControlResult(ok=False, reason_code="ssh_host_key_invalid")
        elif kind == "daytona" and not str(config.get("sandbox_id", "")).strip():
            return ControlResult(ok=False, reason_code="daytona_sandbox_required")
        elif kind == "daytona":
            try:
                if float(config.get("max_cost", 0) or 0) <= 0:
                    return ControlResult(ok=False, reason_code="daytona_budget_required")
            except (TypeError, ValueError):
                return ControlResult(ok=False, reason_code="daytona_budget_required")
        now = utc_now()
        existing = self.store.load_remote_execution_profile(
            profile_id or "", owner_principal_id=owner_principal_id
        )
        actual_id = str(existing["profile_id"]) if existing else new_id("rex_")
        from raiker.contracts.models import RemoteExecutionProfile

        self.store.insert_remote_execution_profile(
            RemoteExecutionProfile(
                actual_id,
                "ssh" if kind == "ssh" else ("cloud" if kind == "daytona" else "container"),
                name.strip()
                or (
                    "SSH host"
                    if kind == "ssh"
                    else ("Daytona sandbox" if kind == "daytona" else "Local container")
                ),
                json.dumps(config, sort_keys=True),
                enabled,
                owner_principal_id,
                str(existing["created_at"]) if existing else now,
                now,
            )
        )
        return ControlResult(ok=True, data={"profile_id": actual_id})

    def select_execution_environment(
        self: DashboardService, profile_id: str, owner_principal_id: str
    ) -> ControlResult:
        view = self.execution_environments(owner_principal_id)
        environment = next(
            (item for item in view["environments"] if item["profile_id"] == profile_id), None
        )
        if environment is None:
            return ControlResult(ok=False, reason_code="unknown_execution_environment")
        if not environment["available"]:
            return ControlResult(ok=False, reason_code="execution_environment_unavailable")
        self.store.select_execution_environment(owner_principal_id, profile_id)
        return ControlResult(ok=True, data={"selected_profile_id": profile_id})

    def reset_execution_environment(
        self: DashboardService, profile_id: str, session_id: str, *, recreate: bool, owner_principal_id: str
    ) -> ControlResult:
        """Take a session's persistent boundary away, on the owner's word (BUG-194).

        Only a boundary that *is* persistent can be reset, and the refusal says
        which it is: offering the control on a profile that rebuilds itself
        around every command would be offering an action with no effect.
        """
        view = self.execution_environments(owner_principal_id)
        environment = next(
            (item for item in view["environments"] if item["profile_id"] == profile_id), None
        )
        if environment is None:
            return ControlResult(ok=False, reason_code="unknown_execution_environment")
        if not environment.get("features", {}).get("persistent_environment"):
            return ControlResult(ok=False, reason_code="execution_environment_not_persistent")
        if not session_id.strip():
            return ControlResult(ok=False, reason_code="execution_environment_session_required")
        from raiker.execution.commands.service import CommandService

        service = CommandService.for_workspace(self.workspace_root)
        reset = service.reset_environment(
            owner_principal_id, session_id, profile_id, recreate=recreate
        )
        if not reset:
            return ControlResult(ok=False, reason_code="execution_environment_reset_unavailable")
        return ControlResult(
            ok=True,
            data={"profile_id": profile_id, "session_id": session_id, "recreated": recreate},
        )
