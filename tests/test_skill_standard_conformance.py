"""A skill is measured against the Agent Skills standard, and never refused for it.

`SKILL.md` is an open standard now (https://agentskills.io/specification),
implemented by all seven reference platforms and roughly forty other products.
Raiker predates it and is close to it. The rule these tests encode is that
closing the distance must not cost an owner a skill they already rely on: the
validator **reports**, and everything that installed before still installs.

The one deliberate divergence is `allowed-tools`. A skill pre-approving its own
tools is exactly the grant `REFERENCE_PLATFORM_COMPATIBILITY.md` §3.5 exists to
prevent, so Raiker parses the field and says out loud that it is not honoured.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.skills.conformance import (
    SEVERITY_ERROR,
    SEVERITY_REFUSED,
    SEVERITY_WARNING,
    STANDARD_DESCRIPTION_MAX,
    report_for_document,
)
from raiker.skills.package import SkillValidationError, parse_metadata_block, read_skill_md

BUILTIN_ROOT = Path("raiker/skills/builtin")


def _document(frontmatter: str, body: str = "Body text.") -> str:
    return f"---\n{frontmatter}\n---\n\n{body}\n"


def _codes(text: str) -> list[str]:
    return [f.code for f in report_for_document(text).findings]


# ── The standard's rules, one at a time ─────────────────────────────────────


def test_a_conformant_skill_reports_clean() -> None:
    report = report_for_document(
        _document("name: my-skill\ndescription: Does exactly one thing well.")
    )
    assert report.conformant is True
    assert report.findings == ()


@pytest.mark.parametrize(
    "name",
    [
        "my.skill",     # a dot
        "my_skill",     # an underscore
        "my--skill",    # a doubled hyphen
        "my-skill-",    # a trailing hyphen
    ],
)
def test_names_raiker_accepts_and_the_standard_does_not_are_reported(name: str) -> None:
    """Raiker's name rule is a *superset*, so each of these installs and travels badly."""
    text = _document(f"name: {name}\ndescription: A skill.")
    assert "name_not_standard" in _codes(text)
    assert report_for_document(text).conformant is False
    # And it still installs, which is the point.
    assert read_skill_md(text).name == name


def test_an_over_long_description_is_reported_and_still_installs() -> None:
    description = "x" * (STANDARD_DESCRIPTION_MAX + 1)
    text = _document(f"name: my-skill\ndescription: {description}")
    assert "description_too_long" in _codes(text)
    assert read_skill_md(text).description.startswith("xxx")


def test_a_top_level_version_is_reported_as_belonging_under_metadata() -> None:
    text = _document("name: my-skill\ndescription: A skill.\nversion: 1.0.0")
    findings = {f.code: f for f in report_for_document(text).findings}
    assert "version_not_top_level" in findings
    # A warning, not an error: the document is portable, a strict reader just
    # drops the key.
    assert findings["version_not_top_level"].severity == SEVERITY_WARNING
    assert report_for_document(text).conformant is True


def test_an_unknown_top_level_field_is_named_rather_than_ignored() -> None:
    text = _document("name: my-skill\ndescription: A skill.\nauthor: someone")
    findings = {f.field: f for f in report_for_document(text).findings}
    assert "author" in findings
    assert findings["author"].code == "unknown_top_level_field"
    assert findings["author"].severity == SEVERITY_WARNING


def test_license_and_compatibility_are_parsed_for_display() -> None:
    text = _document(
        "name: my-skill\ndescription: A skill.\n"
        "license: Apache-2.0\ncompatibility: claude-code >=1.0"
    )
    report = report_for_document(text)
    assert report.license == "Apache-2.0"
    assert report.compatibility == "claude-code >=1.0"
    assert report.conformant is True


# ── The nested `metadata:` block ────────────────────────────────────────────


def test_the_metadata_block_is_read_one_level_deep() -> None:
    text = _document(
        "name: my-skill\ndescription: A skill.\nmetadata:\n  version: 2.1.0\n  author: someone"
    )
    assert parse_metadata_block(text) == {"version": "2.1.0", "author": "someone"}
    # Reading it is what lets a standard-written skill show its version.
    assert read_skill_md(text).version == "2.1.0"
    assert report_for_document(text).conformant is True


def test_the_metadata_reader_stops_at_the_next_top_level_key() -> None:
    """It is not a YAML parser, deliberately, and must not act like a greedy one."""
    text = _document(
        "name: my-skill\nmetadata:\n  version: 2.1.0\ndescription: A skill.\nlicense: MIT"
    )
    assert parse_metadata_block(text) == {"version": "2.1.0"}
    assert report_for_document(text).license == "MIT"


def test_a_document_with_no_metadata_block_reads_as_empty() -> None:
    assert parse_metadata_block(_document("name: my-skill\ndescription: A skill.")) == {}
    assert parse_metadata_block("no frontmatter at all") == {}


def test_a_top_level_version_wins_over_a_metadata_one() -> None:
    """Raiker's own history first, so moving a built-in's version never loses it."""
    text = _document(
        "name: my-skill\ndescription: A skill.\nversion: 9.9.9\nmetadata:\n  version: 1.0.0"
    )
    assert read_skill_md(text).version == "9.9.9"


# ── The one field read and refused ──────────────────────────────────────────


def test_allowed_tools_is_parsed_and_explicitly_not_honoured() -> None:
    text = _document(
        'name: my-skill\ndescription: A skill.\nallowed-tools: [read_file, shell]'
    )
    report = report_for_document(text)
    refused = [f for f in report.findings if f.severity == SEVERITY_REFUSED]
    assert len(refused) == 1
    assert refused[0].field == "allowed-tools"
    assert report.refused_allowed_tools == ("read_file", "shell")
    # It names what it will not do, in words an owner can act on.
    assert "not honoured" in refused[0].message


def test_allowed_tools_is_read_in_either_scalar_shape() -> None:
    inline = _document("name: a-skill\ndescription: A skill.\nallowed-tools: read_file, grep")
    bracketed = _document('name: a-skill\ndescription: A skill.\nallowed-tools: ["read_file", "grep"]')
    assert report_for_document(inline).refused_allowed_tools == ("read_file", "grep")
    assert report_for_document(bracketed).refused_allowed_tools == ("read_file", "grep")


def test_a_refused_field_does_not_make_the_document_non_conformant() -> None:
    """The document is valid; Raiker declines one of its requests.

    Marking the skill non-conformant would blame the author for Raiker's own
    governance choice, and would tell them something untrue about portability —
    a skill with `allowed-tools` installs perfectly well elsewhere.
    """
    text = _document("name: my-skill\ndescription: A skill.\nallowed-tools: read_file")
    assert report_for_document(text).conformant is True


def test_declaring_allowed_tools_grants_nothing() -> None:
    """The refusal has to be structural, not a message beside a working grant."""
    text = _document("name: my-skill\ndescription: A skill.\nallowed-tools: shell, write_file")
    package = read_skill_md(text)
    # The stored package carries no notion of a pre-approved tool at all — there
    # is no field for one, which is the strongest form this refusal can take.
    assert not hasattr(package, "allowed_tools")
    assert "shell" not in package.description


# ── Nothing that installed before stops installing ──────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        _document("name: my.legacy_skill--\ndescription: A skill Raiker already stored."),
        _document(f"name: long-desc\ndescription: {'y' * 1500}"),
        _document("name: has-version\ndescription: A skill.\nversion: 3.0.0"),
        _document("name: odd-fields\ndescription: A skill.\nauthor: x\nhomepage: y"),
    ],
)
def test_a_non_conformant_skill_still_installs(text: str) -> None:
    """The validator reports. It is never a second gate on an owner's own file."""
    package = read_skill_md(text)
    assert package.name
    assert package.description


def test_a_genuinely_invalid_document_is_still_refused() -> None:
    """Reporting is not the same as accepting anything: the old rules still hold."""
    with pytest.raises(SkillValidationError):
        read_skill_md(_document("name: My Skill With Spaces\ndescription: A skill."))
    with pytest.raises(SkillValidationError):
        read_skill_md(_document("name: no-description"))


# ── Raiker's own skills ─────────────────────────────────────────────────────


def test_every_built_in_skill_conforms_to_the_standard() -> None:
    """Raiker should not ship the thing it is measuring other skills against.

    This is what moved the built-ins' `version:` under `metadata:` and trimmed
    one description that had drifted 24 characters over the standard's cap.
    """
    offenders: dict[str, list[str]] = {}
    for path in sorted(BUILTIN_ROOT.glob("*/SKILL.md")):
        report = report_for_document(path.read_text(encoding="utf-8"))
        bad = [f.code for f in report.findings if f.severity == SEVERITY_ERROR]
        if bad:
            offenders[path.parent.name] = bad
    assert offenders == {}, (
        "A built-in skill does not conform to the Agent Skills standard: "
        f"{offenders}. See https://agentskills.io/specification"
    )


def test_every_built_in_skill_still_carries_a_version() -> None:
    """Moving it must not lose it — the Skills tab shows it."""
    for path in sorted(BUILTIN_ROOT.glob("*/SKILL.md")):
        package = read_skill_md(path.read_text(encoding="utf-8"))
        assert package.version, path.parent.name


def test_no_built_in_skill_tries_to_pre_approve_tools() -> None:
    for path in sorted(BUILTIN_ROOT.glob("*/SKILL.md")):
        report = report_for_document(path.read_text(encoding="utf-8"))
        assert report.refused_allowed_tools == (), path.parent.name
