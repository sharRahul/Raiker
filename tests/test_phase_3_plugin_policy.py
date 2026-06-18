from __future__ import annotations

import sys

from raiker.plugins.policy import plan_plugin_registration
from raiker.plugins.registry import PluginPlanRegistry


def test_safe_read_only_plugin_manifest_plans_without_execution() -> None:
    plan = plan_plugin_registration({"plugin_id": "com.example.safe", "name": "Safe", "version": "1.0.0", "trust_level": "local_dev", "entrypoints": {"commands": ["commands/x.md"]}, "permissions": ["tool:read_file", "event:read"]})
    assert plan.status == "planned"
    assert plan.execution_enabled is False
    assert plan.entrypoints == {"commands": ["commands/x.md"]}
    assert [event["event_type"] for event in plan.events] == ["phase3.plugin.manifest.validated", "phase3.plugin.registration.planned"]


def test_unsafe_and_unknown_manifest_fields_are_denied_or_approval_required() -> None:
    assert plan_plugin_registration({"plugin_id": "bad", "name": "Bad", "version": "1", "permissions": ["subprocess:popen"]}).status == "denied"
    assert plan_plugin_registration({"plugin_id": "bad", "name": "Bad", "version": "1", "trust_level": "root", "permissions": ["tool:read_file"]}).status == "denied"
    assert plan_plugin_registration({"plugin_id": "write", "name": "Write", "version": "1", "permissions": ["tool:write_file"]}).status == "pending_approval"
    assert plan_plugin_registration({"plugin_id": "shell", "name": "Shell", "version": "1", "permissions": ["tool:shell"]}).status == "pending_approval"


def test_missing_fields_and_malicious_strings_never_import_or_execute() -> None:
    before = set(sys.modules)
    plan = plan_plugin_registration({"plugin_id": "../evil", "name": "Evil", "version": "1", "entrypoints": {"commands": ["../../evil.py"]}, "permissions": ["tool:read_file", "eval:__import__('os').system('echo nope')"]})
    after = set(sys.modules)
    assert plan.status == "denied"
    assert plan.execution_enabled is False
    assert "evil" not in after - before
    missing = plan_plugin_registration({"plugin_id": "missing"})
    assert missing.status == "denied"
    assert any(reason.startswith("missing_fields") for reason in missing.reasons)


def test_plugin_registry_inspection_is_read_only() -> None:
    registry = PluginPlanRegistry()
    plan = plan_plugin_registration({"plugin_id": "com.example.safe", "name": "Safe", "version": "1", "permissions": ["tool:read_file"]}).to_dict()
    registry.add_plan(plan)
    listed = registry.list_plans()
    listed[0]["status"] = "mutated"
    assert registry.list_plans()[0]["status"] == "planned"
