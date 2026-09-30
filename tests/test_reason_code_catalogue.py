"""OPT-18 — the authority router's refusals are one catalogue, and the web copy follows it."""

from __future__ import annotations

import re
from pathlib import Path

from raiker.runtime.authority import router
from raiker.runtime.authority.reason_codes import SCOPED_REASONS, AuthorityReason, scoped

ROOT = Path(__file__).resolve().parents[1]
COPY = ROOT / "web" / "src" / "lib" / "reasonCodes.ts"


def _copy_tables() -> tuple[set[str], set[str]]:
    """The keys of ``REASON_CODES`` and ``PREFIX_CODES`` in the web client."""
    source = COPY.read_text(encoding="utf-8")
    tables = {}
    for name in ("REASON_CODES", "PREFIX_CODES"):
        body = re.search(rf"const {name}: Record<string, ReasonCopy> = \{{(.*?)\n\}};", source, re.S)
        assert body, name
        tables[name] = set(re.findall(r'^\s{2}"?([a-z_:]+)"?: \{', body.group(1), re.M))
    return tables["REASON_CODES"], tables["PREFIX_CODES"]


def _backend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "raiker").rglob("*.py")
    )


def test_every_catalogue_reason_has_owner_facing_copy() -> None:
    exact, prefix = _copy_tables()
    for reason in AuthorityReason:
        table = prefix if reason in SCOPED_REASONS else exact
        assert reason.value in table, f"reasonCodes.ts has no copy for {reason.value}"


def test_every_copy_key_names_a_code_the_backend_sends() -> None:
    """Copy for a code nothing emits is how the table drifted before."""
    exact, prefix = _copy_tables()
    catalogue = {reason.value for reason in AuthorityReason}
    source = _backend_source()
    stale = [
        key
        for key in exact | prefix
        if key not in catalogue and f'"{key}' not in source and f"'{key}" not in source
    ]
    assert not stale, f"copy for codes the backend never sends: {sorted(stale)}"


def test_the_router_spells_no_catalogue_reason_as_a_literal() -> None:
    source = Path(router.__file__).read_text(encoding="utf-8")
    for reason in AuthorityReason:
        assert f'return "{reason.value}"' not in source, reason.value
        assert f'return f"{reason.value}:' not in source, reason.value


def test_a_scoped_reason_is_its_code_then_its_subject() -> None:
    assert scoped(AuthorityReason.UNKNOWN_CAPABILITY, "shell_execute") == (
        "unknown_capability:shell_execute"
    )
    # A member is its wire string: comparisons, JSON and storage read the value.
    assert AuthorityReason.PRINCIPAL_EXPIRED == "principal_expired"
