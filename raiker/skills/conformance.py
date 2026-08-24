"""Measuring an installed skill against the Agent Skills standard.

`SKILL.md` stopped being one product's convention. **Agent Skills**
(https://agentskills.io) is a published specification
(https://agentskills.io/specification) with a reference validator, implemented
by all seven of Raiker's reference platforms and roughly forty other products.
Raiker predates it and is close to it without being conformant.

**This module reports; it never refuses.** A skill that installs today keeps
installing. That is the whole design: the differences between Raiker's reader
and the standard are small, mostly in Raiker's favour (its `name` rule is a
*superset*, so every conformant name is accepted), and refusing a skill an owner
already relies on in order to enforce someone else's stricter rule would be
trading their working setup for a badge.

What an owner gets instead is the answer to the question that actually matters:
*will this skill work anywhere else?* A finding names the field, the rule, and
what to change.

**One field is read and deliberately not honoured.** `allowed-tools` is a skill
pre-approving the tools it may use — exactly the grant
`REFERENCE_PLATFORM_COMPATIBILITY.md` §3.5 ("a skill is instruction-only")
exists to prevent. Ignoring the field silently would leave an author believing it
did something. Raiker parses it and says out loud that it does not, which is the
stronger answer and the one difference here that is a deliberate divergence
rather than a gap.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

#: Where the rules below come from, quoted anywhere a finding is rendered.
SPEC_URL = "https://agentskills.io/specification"

#: The standard's name rule: lowercase alphanumerics in single-hyphen-separated
#: segments. No leading or trailing hyphen, no `--`, no `.` and no `_`. Raiker's
#: own rule (`^[a-z0-9][a-z0-9._-]{0,63}$`) admits all four.
STANDARD_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STANDARD_NAME_MAX = 64

#: The standard caps `description` at 1024 characters. Raiker truncates at 2000.
STANDARD_DESCRIPTION_MAX = 1024

#: Fields the standard defines at the top level of the frontmatter. Anything
#: else belongs under `metadata:`.
STANDARD_TOP_LEVEL_FIELDS = frozenset({
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
})

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
#: A field Raiker reads, understands, and declines to act on.
SEVERITY_REFUSED = "refused"


@dataclass(frozen=True)
class ConformanceFinding:
    """One way this skill differs from the standard, and what to do about it."""

    #: The frontmatter field the finding is about.
    field: str
    #: Stable machine code, safe to branch on and to render as a test assertion.
    code: str
    severity: str
    #: One sentence an owner can act on. No markup — a skill's frontmatter is
    #: author-supplied text and this string is rendered beside it.
    message: str


@dataclass(frozen=True)
class ConformanceReport:
    """What an owner is told about one skill's portability."""

    #: True when nothing would stop this skill validating elsewhere. A refused
    #: `allowed-tools` does **not** make a skill non-conformant: the document is
    #: valid, Raiker simply declines one of its requests.
    conformant: bool
    findings: tuple[ConformanceFinding, ...] = ()
    #: Parsed for display. Empty when the field is absent.
    license: str = ""
    compatibility: str = ""
    #: The standard's nested `metadata:` map, flattened to strings.
    metadata: Mapping[str, str] = field(default_factory=dict)
    #: The tools the skill asked to pre-approve. Recorded so the refusal can name
    #: them; never consulted by anything that grants.
    refused_allowed_tools: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "conformant": self.conformant,
            "spec_url": SPEC_URL,
            "findings": [
                {
                    "field": f.field,
                    "code": f.code,
                    "severity": f.severity,
                    "message": f.message,
                }
                for f in self.findings
            ],
            "license": self.license,
            "compatibility": self.compatibility,
            "metadata": dict(self.metadata),
            "refused_allowed_tools": list(self.refused_allowed_tools),
        }


def _split_list(raw: str) -> tuple[str, ...]:
    """Read a scalar list in either shape the format uses in practice.

    `allowed-tools: [Read, Grep]` and `allowed-tools: Read, Grep` both occur.
    The block-sequence shape does not, because the flat frontmatter reader never
    produces a value for it — which is itself reported, as an unparsed field.
    """
    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    parts = [p.strip().strip("\"'") for p in text.split(",")]
    return tuple(p for p in parts if p)


def check_conformance(
    fields: Mapping[str, str],
    *,
    metadata: Mapping[str, str] | None = None,
) -> ConformanceReport:
    """Measure one skill's frontmatter against the standard.

    *fields* is the flat frontmatter map, and *metadata* the nested `metadata:`
    block if the reader captured one. Nothing here raises: an unreadable field
    becomes a finding, because a validator that refuses is a validator an owner
    routes around.
    """
    findings: list[ConformanceFinding] = []
    metadata = dict(metadata or {})

    name = (fields.get("name") or "").strip()
    if name and not STANDARD_NAME_RE.match(name):
        findings.append(ConformanceFinding(
            field="name",
            code="name_not_standard",
            severity=SEVERITY_ERROR,
            message=(
                "The standard allows lowercase letters and digits in "
                "hyphen-separated segments only — no dots, underscores, "
                "doubled hyphens or a trailing hyphen. This skill installs here "
                "and may be refused elsewhere."
            ),
        ))
    if len(name) > STANDARD_NAME_MAX:
        findings.append(ConformanceFinding(
            field="name",
            code="name_too_long",
            severity=SEVERITY_ERROR,
            message=f"The standard caps a name at {STANDARD_NAME_MAX} characters.",
        ))

    description = (fields.get("description") or "").strip()
    if len(description) > STANDARD_DESCRIPTION_MAX:
        findings.append(ConformanceFinding(
            field="description",
            code="description_too_long",
            severity=SEVERITY_ERROR,
            message=(
                f"The standard caps a description at {STANDARD_DESCRIPTION_MAX} "
                f"characters; this one is {len(description)}. Raiker keeps up to "
                "2000, so the skill works here and would be truncated or refused "
                "elsewhere."
            ),
        ))

    # `version` is Raiker's own history: the built-ins carried it at the top
    # level before the standard existed, and the standard puts it under
    # `metadata`. Reported as a warning because it is inert either way.
    if "version" in fields and "version" not in metadata:
        findings.append(ConformanceFinding(
            field="version",
            code="version_not_top_level",
            severity=SEVERITY_WARNING,
            message=(
                "The standard has no top-level `version` field; it belongs under "
                "`metadata:`. Readers that validate strictly will reject the "
                "extra key."
            ),
        ))

    for key in sorted(fields):
        if key in STANDARD_TOP_LEVEL_FIELDS or key == "version":
            continue
        findings.append(ConformanceFinding(
            field=key,
            code="unknown_top_level_field",
            severity=SEVERITY_WARNING,
            message=(
                f"`{key}` is not a field the standard defines at the top level. "
                "Move it under `metadata:` so a strict reader keeps it."
            ),
        ))

    refused_tools: tuple[str, ...] = ()
    if "allowed-tools" in fields:
        refused_tools = _split_list(fields["allowed-tools"])
        findings.append(ConformanceFinding(
            field="allowed-tools",
            code="allowed_tools_not_honoured",
            severity=SEVERITY_REFUSED,
            message=(
                "Read and deliberately not honoured. A skill is instruction text "
                "in Raiker; it cannot pre-approve the tools it uses. Every tool "
                "call a turn makes while following this skill is governed "
                "exactly as it would be otherwise — by its capability gate, its "
                "decision mode, and an approval where one is required."
            ),
        ))

    return ConformanceReport(
        # Only `error` findings mean "this would not validate elsewhere". A
        # warning is portable-but-untidy; a refusal is Raiker's own choice, and
        # calling the document non-conformant for it would blame the author.
        conformant=not any(f.severity == SEVERITY_ERROR for f in findings),
        findings=tuple(findings),
        license=(fields.get("license") or "").strip(),
        compatibility=(fields.get("compatibility") or "").strip(),
        metadata=metadata,
        refused_allowed_tools=refused_tools,
    )


def report_for_document(text: str) -> ConformanceReport:
    """Measure a stored ``SKILL.md`` without re-validating or re-storing it.

    Derived at read time rather than persisted, so tightening a rule re-measures
    every installed skill instead of leaving old rows reporting an old answer.
    """
    from raiker.skills.package import parse_frontmatter, parse_metadata_block

    return check_conformance(parse_frontmatter(text), metadata=parse_metadata_block(text))
