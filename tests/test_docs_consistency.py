from __future__ import annotations

import re
from pathlib import Path

REQUIRED_DOCS = [
    Path("README.md"),
    Path("docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md"),
    Path("docs/architecture/IMPLEMENTATION_STATUS.md"),
    Path("docs/architecture/EVENT_CATALOG.md"),
    Path("docs/architecture/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md"),
    # docs/UI_UX_DESIGN_SPEC.md was deliberately removed (superseded by apps/web/README.md).
    Path("apps/web/README.md"),
    Path("docs/architecture/API_AND_CONTRACT_SCHEMAS.md"),
    Path("docs/architecture/SECURITY_AND_POLICY.md"),
    Path("docs/architecture/RUNTIME_ORCHESTRATION_SPEC.md"),
    Path("docs/architecture/TOOLS_AND_PERMISSIONS_SPEC.md"),
    Path("docs/architecture/VERIFICATION_PLAN.md"),
]

STALE_CLAIMS = [
    "zero runtime dependencies",
    "zero_runtime_dependencies",
    "http.client",
    "LlamaCppServerProvider",
    "provider_not_wired",
    "mock fallback",
    "Ollama is intentionally not supported",
    "other providers raise",
    "default fallback when no server is reachable",
    "falls back to the deterministic",
    "binds to it automatically when",
    # 2026-08-23 — `MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` listed a fourth `mock`
    # adapter for "deterministic offline testing". No such adapter exists, and
    # `AsyncProviderFactory.create` refuses `mock`/`test` providers with
    # `test_provider_not_available`. A provider that answers without a real model
    # would let every readiness gate pass over an endpoint that proves nothing,
    # so the claim is worth asserting against rather than merely deleting.
    "Deterministic offline testing",
    "Four adapters ship",
]


def test_required_docs_do_not_contain_stale_model_runtime_claims() -> None:
    offenders: list[str] = []
    for path in REQUIRED_DOCS:
        text = path.read_text(encoding="utf-8")
        for claim in STALE_CLAIMS:
            if claim in text:
                offenders.append(f"{path}:{claim}")
    assert offenders == []


# ── Documentation validation: the docs cannot drift ahead of the code ─────────
#
# Three invariants, each of which had actually broken before it was asserted:
#
#   1. every capability with a real executor is reachable from the threat-models
#      index — the step-up asks the owner to acknowledge a threat model, and an
#      acknowledgement with nothing behind it is weaker than one with a page;
#   2. every relative Markdown link resolves, including its heading anchor;
#   3. `EXECUTABLE_ON_APPROVAL`'s size is stated correctly wherever a document
#      commits to a number.

THREAT_MODEL_INDEX = Path("docs/threat-models/README.md")

DOC_ROOTS = [
    Path("README.md"),
    Path("CONTRIBUTING.md"),
    Path("SECURITY.md"),
    Path("apps/web/README.md"),
]


def _markdown_files() -> list[Path]:
    return [p for p in DOC_ROOTS if p.exists()] + sorted(Path("docs").rglob("*.md"))


def _slugify(title: str) -> str:
    """GitHub's heading-anchor algorithm, closely enough for a link check."""
    text = title.strip().replace("`", "").replace("*", "")
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [text](url) -> text
    text = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return text.replace(" ", "-")


def _anchors(text: str) -> set[str]:
    found: set[str] = set()
    seen: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading is None:
            continue
        base = _slugify(heading.group(2))
        index = seen.get(base, 0)
        seen[base] = index + 1
        found.add(base if index == 0 else f"{base}-{index}")
    return found


def test_every_real_executor_capability_has_a_threat_model() -> None:
    """The owner acknowledges a document; there has to be one to acknowledge."""
    from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

    index = THREAT_MODEL_INDEX.read_text(encoding="utf-8")
    missing = sorted(cap for cap in REAL_EXECUTOR_CAPABILITIES if cap not in index)
    assert missing == [], (
        "capabilities with a real executor and no entry in the threat-models "
        f"index: {missing}"
    )


def test_documentation_links_and_anchors_resolve() -> None:
    link = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
    anchors_by_file: dict[Path, set[str]] = {}
    broken: list[str] = []

    for source in _markdown_files():
        for match in link.finditer(source.read_text(encoding="utf-8")):
            raw = match.group(1)
            if raw.startswith(("http://", "https://", "mailto:")):
                continue
            target, _, fragment = raw.partition("#")
            resolved = (source.parent / target).resolve() if target else source.resolve()
            if target and not resolved.exists():
                broken.append(f"{source} -> {raw} (no such file)")
                continue
            if not fragment or resolved.suffix != ".md":
                continue
            if resolved not in anchors_by_file:
                anchors_by_file[resolved] = _anchors(resolved.read_text(encoding="utf-8"))
            if fragment not in anchors_by_file[resolved]:
                broken.append(f"{source} -> {raw} (no such heading)")

    assert broken == [], "broken documentation links:\n" + "\n".join(broken)


def test_relayed_capability_count_is_stated_correctly() -> None:
    """The technical threat model commits to the executor count."""
    from raiker.approvals.execution import EXECUTABLE_ON_APPROVAL

    assert len(EXECUTABLE_ON_APPROVAL) == 13, (
        "EXECUTABLE_ON_APPROVAL changed size; update "
        "docs/architecture/THREAT_MODEL.md, which names it"
    )
    threat_model = Path("docs/architecture/THREAT_MODEL.md").read_text(encoding="utf-8")
    assert "explicit **thirteen**-member frozenset" in threat_model


def _first_id_table(text: str) -> str:
    match = re.search(
        r"^\| ID \|.*\n^\|---\|.*\n(?P<rows>(?:^\|.*\|\n)+)",
        text,
        re.MULTILINE,
    )
    assert match is not None
    return match.group("rows")


def test_plan_tracker_indexes_cover_and_link_their_authoritative_headings() -> None:
    trackers = {
        Path("docs/plans/FIXED_ITEMS.md"): r"FIXED-\d+",
        Path("docs/plans/TO_BE_ADDED.md"): r"ADD-\d+",
        Path("docs/plans/MEMORY_RELIABILITY_PLAN.md"): r"MEM-\d+",
        Path("docs/plans/GAP_BUILD_CHAT.md"): r"[BC]\d+",
    }
    failures: list[str] = []

    for path, id_pattern in trackers.items():
        text = path.read_text(encoding="utf-8")
        headings = {
            match.group(1): _slugify(f"{match.group(1)} — {match.group(2)}")
            for match in re.finditer(
                rf"^#{{2,4}} ({id_pattern})\s+—\s+(.+)$", text, re.MULTILINE
            )
        }
        rows = _first_id_table(text)
        row_links = {
            match.group(1): match.group(2)
            for match in re.finditer(
                rf"^\| \[({id_pattern})\]\(([^)]+)\)", rows, re.MULTILINE
            )
        }
        missing = sorted(set(headings) - set(row_links))
        if missing:
            failures.append(f"{path}: headings missing from index: {missing}")
        for item_id, anchor in headings.items():
            target = row_links.get(item_id)
            expected = f"#{anchor}"
            if target is not None and target != expected:
                failures.append(f"{path}: {item_id} links to {target}, expected {expected}")

    assert failures == [], "plan tracker index drift:\n" + "\n".join(failures)
