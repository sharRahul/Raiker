"""Every literal refusal an API route sends has owner-facing copy (beta plan UX-4).

`tests/test_reason_code_catalogue.py` covers the authority router's catalogue.
This covers the rest: each ``refusal(status, "code")`` written in
``raiker/api`` must have words in the web client, either in
``reasonCodes.ts`` (which ``failure()`` and ``explainReasonCode`` read) or
beside the control that meets it (a view's own label table). A new route code
without either fails here, so the owner never reads only a machine code.

Codes passed through from an exception (``refusal(status, exc.reason_code)``)
are not literals and are covered where they are raised.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "raiker" / "api"
WEB = ROOT / "web" / "src"
LITERAL = re.compile(r'refusal\(\s*[^,()]+,\s*"([a-z0-9_]+)"')


def _route_codes() -> dict[str, str]:
    codes: dict[str, str] = {}
    for path in sorted(API.rglob("*.py")):
        for code in LITERAL.findall(path.read_text(encoding="utf-8")):
            codes.setdefault(code, path.relative_to(ROOT).as_posix())
    return codes


def _web_source() -> str:
    parts = []
    for path in WEB.rglob("*"):
        if path.suffix not in {".ts", ".svelte"} or ".test." in path.name:
            continue
        if "generated" in path.parts:
            continue
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_the_scan_finds_the_route_refusals() -> None:
    # A regex that silently matched nothing would make the next test vacuous.
    assert len(_route_codes()) > 100


def test_every_route_refusal_has_copy_in_the_web_client() -> None:
    source = _web_source()
    missing = sorted(
        f"{code} ({where})"
        for code, where in _route_codes().items()
        if not re.search(rf'["\s{{,]{code}["]?\s*:', source) and f'"{code}"' not in source
    )
    assert missing == [], (
        "route refusals with no owner-facing copy; add them to web/src/lib/reasonCodes.ts: "
        + ", ".join(missing)
    )
