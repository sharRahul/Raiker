"""The read side of installed skills, as a governed tool.

Only the skill *index* — one line per active skill — is placed in a turn's
system context. ``skill_load`` fetches the full document for one named skill
when the model decides it applies, and can then fetch one bundled file from that
skill's archive. That three-level shape is deliberate: ten installed skills cost
ten lines, a triggered skill costs its body, and a reference file costs only on
the turns that actually need that variant.

The lookup is owner-scoped and refuses a deactivated skill, because turning a
skill off has to withhold it rather than merely hide it from a list. A bundled
file is read from the stored archive with the archive's own path checks, so a
model-supplied name can never reach outside the bundle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.skills.package import SkillValidationError, read_bundle_member
from raiker.storage.sqlite import SQLiteStore


def _failed(kind: str, message: str) -> dict[str, Any]:
    return {"status": "failed", "error": {"type": kind, "message": message}}


def skill_load(
    workspace_root: str | Path,
    name: str,
    *,
    file: str | None = None,
    owner_principal_id: str | None = None,
) -> dict[str, Any]:
    """Return one active skill's instructions, or one file bundled with it."""
    handle = (name or "").strip().lower()
    if not handle:
        return _failed("invalid_argument", "A skill name is required.")
    if not owner_principal_id:
        return _failed("not_found", "No owner scope for this turn.")
    row = SQLiteStore(workspace_root).get_skill_by_name(owner_principal_id, handle)
    if row is None:
        return _failed("not_found", f"Skill '{handle}' is not installed.")
    if not row.get("active"):
        return _failed(
            "not_found",
            f"Skill '{handle}' is deactivated, so its instructions are withheld.",
        )
    files = [str(entry) for entry in row.get("files", [])]
    if file:
        bundle = row.get("bundle")
        if not bundle:
            return _failed(
                "not_found", f"Skill '{handle}' is a single document — it bundles no files."
            )
        try:
            content = read_bundle_member(bundle, file)
        except SkillValidationError as exc:
            return _failed(
                "not_found",
                f"'{file}' is not in this skill's bundle. It contains: {', '.join(files)}."
                if exc.reason == "skill_member_not_found"
                else f"'{file}' could not be read ({exc.reason}).",
            )
        return {"status": "success", "name": str(row["name"]), "file": file, "content": content}
    return {
        "status": "success",
        "name": str(row["name"]),
        "description": str(row.get("description", "")),
        "version": row.get("version"),
        "files": files,
        "instructions": str(row.get("skill_md", "")),
    }
