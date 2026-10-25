"""TOOL-70 — a turn searches the owner's skills by what they do."""

from __future__ import annotations

from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.tool_call_validation import risk_for_tool
from raiker.skills.service import SkillsService
from raiker.tools.skill_tools import skill_search

OWNER = "principal_owner"


def test_search_ranks_by_name_description_and_body_and_lists_all(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    SkillsService(tmp_path).seed_builtins(OWNER)
    found = skill_search(tmp_path, "security review", owner_principal_id=OWNER)
    assert found["status"] == "success"
    assert found["skills"][0]["name"] == "security-review"
    every = skill_search(tmp_path, "", owner_principal_id=OWNER)
    assert {"code-review", "skill-creator"} <= {skill["name"] for skill in every["skills"]}
    assert skill_search(tmp_path, "zzqx qqxz", owner_principal_id=OWNER)["skills"] == []
    assert skill_search(tmp_path, "x")["error"]["type"] == "not_found"
    assert risk_for_tool("skill_search") == "low"
