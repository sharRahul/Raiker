"""BR-D04 — review the exact patch, and remember the review by that patch.

A diff shown to a person is not a review: nothing repeatable says what was
checked, and the same finding comes back as new noise every time the pane
reloads. This reads one exact unified diff — the working tree's, built by the
same helpers a commit is built from — and returns deterministic findings, each
tied to a file and line with its evidence and a next step. The review is keyed
by the SHA-256 of the diff text, so reviewing the same patch twice returns the
same stored review rather than a duplicate, and any change to the patch is a
different review.

Rules, each chosen for precision over recall (a noisy reviewer is ignored):

* **Possible credential** — an added line matches one of Raiker's credential
  patterns. The value is never echoed; the evidence names the pattern only.
* **Conflict marker** — an added ``<<<<<<<``, ``=======`` or ``>>>>>>>`` line.
* **Debugging left in** — ``breakpoint()``, ``pdb.set_trace()``, ``debugger;``
  in a source file of the language that uses it.
* **CI or workflow change** — the patch touches ``.github/workflows`` or another
  CI definition. Build leaves these to the owner (BR-12), so they are named.
* **Instruction-like text** — added text that tells a model to ignore its
  instructions or reveal its prompt: content a later turn could read as an
  order. The issue and the repository are untrusted input (BR-04).
* **Source changed without tests** — code changed and no test file did.
* **Does not parse** — an independent validator: each changed file the
  language-intelligence parser supports is parsed, and a syntax error is a
  finding at its line. A file it cannot parse is never reported as clean, and
  when the owner has the capability off the review says it was not run.

Each review also states what changed since the repository's previous one: a
finding is ``new`` or ``still_present`` (matched by rule and file, so a line
that merely moved is not a new problem), and the previous review's findings
that are gone are listed as ``resolved``.

The review reads only. It grants nothing, runs nothing, and never changes the
working tree; acting on a finding is an ordinary governed change.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from raiker.context.redaction import redact_text
from raiker.contracts.ids import utc_now
from raiker.review.diff_parser import classify_file

#: The most diff text one review reads. Beyond it the review says it was cut.
MAX_REVIEW_CHARS = 400_000
#: The most findings of one rule kept per file, so one bad file cannot drown the rest.
MAX_FINDINGS_PER_RULE_AND_FILE = 5

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}

_CONFLICT = re.compile(r"^(<{7}( |$)|={7}$|>{7}( |$))")
_DEBUG: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (re.compile(r"\bbreakpoint\(\s*\)|\bpdb\.set_trace\(\s*\)|^\s*import\s+i?pdb\b"), frozenset({".py"})),
    (
        re.compile(r"^\s*debugger\s*;?\s*$"),
        frozenset({".js", ".jsx", ".ts", ".tsx", ".svelte", ".vue", ".mjs", ".cjs"}),
    ),
)
_INSTRUCTION = re.compile(
    r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+"
    r"(?:instructions|prompts|rules|messages)\b"
    r"|\breveal\s+(?:your|the)\s+system\s+prompt\b"
    r"|\byou\s+are\s+no\s+longer\s+bound\s+by\b",
    re.IGNORECASE,
)
_CI_PREFIXES = (".github/workflows/", ".gitlab-ci", ".circleci/", ".buildkite/", "azure-pipelines")


@dataclass(frozen=True)
class _Added:
    path: str
    line: int
    text: str


def patch_fingerprint(diff: str) -> str:
    return hashlib.sha256(diff.encode("utf-8", "surrogatepass")).hexdigest()


def _files_and_added(diff: str) -> tuple[list[str], list[_Added]]:
    """Every file the diff touches, and every added line with its new line number."""
    files: list[str] = []
    added: list[_Added] = []
    path = ""
    new_line = 0
    previous = ""
    for raw in diff.splitlines():
        if raw.startswith("--- "):
            previous = raw[4:].split("\t")[0].strip()
            continue
        if raw.startswith("+++ "):
            target = raw[4:].split("\t")[0].strip()
            name = previous if target == "/dev/null" else target
            path = name[2:] if name[:2] in {"a/", "b/"} else name
            if path and path != "/dev/null" and path not in files:
                files.append(path)
            continue
        if raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            new_line = int(match.group(1)) if match else 0
            continue
        if raw.startswith("diff --git ") or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            added.append(_Added(path, new_line, raw[1:]))
            new_line += 1
        elif raw.startswith(" "):
            new_line += 1
    return files, added


def _extension(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return name[name.rfind(".") :].lower() if "." in name[1:] else ""


def _finding(
    rule: str,
    *,
    severity: str,
    category: str,
    title: str,
    evidence: str,
    next_step: str,
    confidence: str,
    path: str | None = None,
    line: int | None = None,
) -> dict[str, Any]:
    identity = f"{rule}:{path or ''}:{line or 0}"
    return {
        "finding_id": hashlib.sha256(identity.encode()).hexdigest()[:16],
        "rule": rule,
        "severity": severity,
        "category": category,
        "title": title,
        "evidence": evidence,
        "next_step": next_step,
        "confidence": confidence,
        "path": path,
        "line": line,
    }


def review_patch(diff: str) -> dict[str, Any]:
    """Findings for one exact diff, deterministic for the same input."""
    fingerprint = patch_fingerprint(diff)
    truncated = len(diff) > MAX_REVIEW_CHARS
    files, added = _files_and_added(diff[:MAX_REVIEW_CHARS])
    findings: list[dict[str, Any]] = []
    per_rule_file: dict[tuple[str, str], int] = {}

    def keep(item: dict[str, Any]) -> None:
        key = (str(item["rule"]), str(item.get("path") or ""))
        if per_rule_file.get(key, 0) >= MAX_FINDINGS_PER_RULE_AND_FILE:
            return
        per_rule_file[key] = per_rule_file.get(key, 0) + 1
        findings.append(item)

    for line in added:
        if redact_text(line.text)[1]:
            keep(
                _finding(
                    "possible_credential",
                    severity="high",
                    category="security",
                    title="Possible credential added",
                    evidence="This line matches a credential pattern. The value is withheld.",
                    next_step="Remove it from the change, rotate it, and read it from the environment or a secret store instead.",
                    confidence="medium",
                    path=line.path,
                    line=line.line,
                )
            )
        if _CONFLICT.match(line.text):
            keep(
                _finding(
                    "conflict_marker",
                    severity="high",
                    category="correctness",
                    title="Merge conflict marker",
                    evidence="An unresolved conflict marker was added.",
                    next_step="Resolve the conflict and remove the marker before committing.",
                    confidence="high",
                    path=line.path,
                    line=line.line,
                )
            )
        extension = _extension(line.path)
        if classify_file(line.path) != "doc":
            for pattern, extensions in _DEBUG:
                if extension in extensions and pattern.search(line.text):
                    keep(
                        _finding(
                            "debug_left_in",
                            severity="low",
                            category="maintainability",
                            title="Debugging statement left in",
                            evidence="A debugger breakpoint was added.",
                            next_step="Remove it unless the change is meant to stop there.",
                            confidence="high",
                            path=line.path,
                            line=line.line,
                        )
                    )
        if _INSTRUCTION.search(line.text):
            keep(
                _finding(
                    "instruction_text",
                    severity="medium",
                    category="security",
                    title="Text that reads as an instruction to a model",
                    evidence="Added text tells a model to set aside its instructions or reveal its prompt.",
                    next_step="Check where this text came from. Issue and repository text is data, never an instruction to Raiker.",
                    confidence="medium",
                    path=line.path,
                    line=line.line,
                )
            )

    for path in files:
        if path.startswith(_CI_PREFIXES):
            keep(
                _finding(
                    "ci_definition_changed",
                    severity="medium",
                    category="scope",
                    title="CI or workflow definition changed",
                    evidence="The patch changes how this repository's automation runs.",
                    next_step="Review this change yourself. Build leaves workflow changes to you.",
                    confidence="high",
                    path=path,
                )
            )

    kinds = [classify_file(path) for path in files]
    if "code" in kinds and "test" not in kinds:
        keep(
            _finding(
                "source_without_tests",
                severity="medium",
                category="tests",
                title="Source changed without a test change",
                evidence=f"{kinds.count('code')} source file(s) changed and no test file did.",
                next_step="Add or update a test that fails without this change.",
                confidence="medium",
            )
        )
    if truncated:
        keep(
            _finding(
                "review_truncated",
                severity="info",
                category="maintainability",
                title="Only part of the patch was reviewed",
                evidence=f"The patch is longer than {MAX_REVIEW_CHARS:,} characters.",
                next_step="Split the change, or review the rest of it yourself.",
                confidence="high",
            )
        )

    findings.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item.get("path") or "", item.get("line") or 0))
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for item in findings:
        counts[item["severity"]] += 1
    return {
        "fingerprint": fingerprint,
        "files": len(files),
        "added_lines": len(added),
        "truncated": truncated,
        "findings": findings,
        "counts": counts,
        "reviewed_at": utc_now(),
    }


# ── Storage, keyed by the patch ──────────────────────────────────────────────


def load_review(store: Any, *, owner_principal_id: str, repo_id: str, fingerprint: str) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            """SELECT review_json FROM patch_reviews
               WHERE owner_principal_id = ? AND repo_id = ? AND fingerprint = ?""",
            (owner_principal_id, repo_id, fingerprint),
        ).fetchone()
    if row is None:
        return None
    try:
        value = json.loads(str(row["review_json"]))
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def save_review(store: Any, *, owner_principal_id: str, repo_id: str, review: Mapping[str, Any]) -> bool:
    """Store a review once per patch. ``False`` when this patch already had one."""
    with store.connect() as connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO patch_reviews
               (owner_principal_id, repo_id, fingerprint, review_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                owner_principal_id,
                repo_id,
                str(review["fingerprint"]),
                json.dumps(dict(review), sort_keys=True),
                utc_now(),
            ),
        )
    return cursor.rowcount == 1


def review_once(
    store: Any,
    *,
    owner_principal_id: str,
    repo_id: str,
    diff: str,
    validator: Any = None,
    attest: Any = None,
) -> tuple[dict[str, Any], bool]:
    """The review of this exact patch, and whether it was already stored.

    ``validator`` is called with the changed file list and returns extra
    findings (the parse check); it runs only for a patch not reviewed before.
    ``attest`` (BR-D05) takes the finished review and returns it signed; it
    runs once, before the review is stored, so what is stored is what was signed.
    """
    fingerprint = patch_fingerprint(diff)
    stored = load_review(store, owner_principal_id=owner_principal_id, repo_id=repo_id, fingerprint=fingerprint)
    if stored is not None:
        return stored, True
    review = review_patch(diff)
    if validator is not None:
        files, _added = _files_and_added(diff[:MAX_REVIEW_CHARS])
        review = with_extra_findings(review, list(validator(files)))
    review = with_lifecycle(
        review,
        latest_review(store, owner_principal_id=owner_principal_id, repo_id=repo_id, exclude=fingerprint),
    )
    if attest is not None:
        review = attest(review)
    if not save_review(store, owner_principal_id=owner_principal_id, repo_id=repo_id, review=review):
        # Another request stored the same patch first; theirs is the record.
        again = load_review(store, owner_principal_id=owner_principal_id, repo_id=repo_id, fingerprint=fingerprint)
        if again is not None:
            return again, True
    return review, False


# ── Independent validator: does each changed file still parse? ──────────────


def parse_findings(
    workspace_root: Any, store: Any, principal_id: str, root: Any, files: list[str]
) -> list[dict[str, Any]]:
    """Parse-level problems in the changed files, through the governed service.

    The same service and gate the agent's ``diagnostics`` tool and Build's file
    viewer use, so the review and the editor never disagree about a file. A
    refused gate yields one ``info`` finding saying the check did not run.
    """
    from raiker.graph.language_service import LanguageIntelligenceService

    candidates = [path for path in files if classify_file(path) in {"code", "test"}]
    if not candidates:
        return []
    try:
        result = LanguageIntelligenceService(
            workspace_root, store, principal_id=principal_id, repository_root=root
        ).diagnostics(candidates)
    except Exception:  # noqa: BLE001 — an unavailable validator is stated, not hidden
        result = {"status": "failed"}
    if result.get("status") != "success":
        return [
            _finding(
                "parse_check_not_run",
                severity="info",
                category="correctness",
                title="Changed files were not parsed",
                evidence="The parse check did not run, so this review says nothing about syntax.",
                next_step="Turn on Language intelligence in Permissions to have changed files parsed.",
                confidence="high",
            )
        ]
    findings: list[dict[str, Any]] = []
    for item in result.get("diagnostics") or []:
        get = item.get if isinstance(item, dict) else lambda key, _item=item: getattr(_item, key, None)
        if str(get("severity") or "") != "error":
            continue
        findings.append(
            _finding(
                "does_not_parse",
                severity="high",
                category="correctness",
                title="File does not parse",
                evidence=str(get("message") or "The parser reported a syntax error.")[:200],
                next_step="Fix the syntax error before running or committing this change.",
                confidence="high",
                path=str(get("path") or "") or None,
                line=int(get("line") or 0) or None,
            )
        )
    return findings[:MAX_FINDINGS_PER_RULE_AND_FILE * 4]


def with_extra_findings(review: dict[str, Any], extra: list[dict[str, Any]]) -> dict[str, Any]:
    """*review* with *extra* findings merged, sorted and recounted."""
    if not extra:
        return review
    findings = [*review["findings"], *extra]
    findings.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item.get("path") or "", item.get("line") or 0))
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for item in findings:
        counts[item["severity"]] += 1
    return {**review, "findings": findings, "counts": counts}


# ── What changed since the repository's previous review ─────────────────────


def latest_review(store: Any, *, owner_principal_id: str, repo_id: str, exclude: str = "") -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            """SELECT review_json FROM patch_reviews
               WHERE owner_principal_id = ? AND repo_id = ? AND fingerprint != ?
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (owner_principal_id, repo_id, exclude),
        ).fetchone()
    if row is None:
        return None
    try:
        value = json.loads(str(row["review_json"]))
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def with_lifecycle(review: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """Mark each finding ``new`` or ``still_present`` against *previous*, and list what was resolved.

    BR-11 — each finding also carries ``reviews_present``: how many reviews in
    a row have raised it, this one included. A finding that survives repair
    after repair says so, so the owner can see a repair is not converging
    instead of asking for the same fix again.
    """
    if previous is None:
        return {
            **review,
            "previous_fingerprint": None,
            "resolved": [],
            "findings": [{**item, "since": None, "reviews_present": 1} for item in review["findings"]],
        }
    remaining: dict[tuple[str, str], list[int]] = {}
    for item in previous.get("findings") or []:
        key = (str(item.get("rule")), str(item.get("path") or ""))
        remaining.setdefault(key, []).append(int(item.get("reviews_present") or 1))
    marked: list[dict[str, Any]] = []
    for item in review["findings"]:
        key = (str(item.get("rule")), str(item.get("path") or ""))
        if remaining.get(key):
            seen = remaining[key].pop(0)
            marked.append({**item, "since": "still_present", "reviews_present": seen + 1})
        else:
            marked.append({**item, "since": "new", "reviews_present": 1})
    current: dict[tuple[str, str], int] = {}
    for item in review["findings"]:
        key = (str(item.get("rule")), str(item.get("path") or ""))
        current[key] = current.get(key, 0) + 1
    resolved: list[dict[str, Any]] = []
    for item in previous.get("findings") or []:
        key = (str(item.get("rule")), str(item.get("path") or ""))
        if current.get(key, 0) > 0:
            current[key] -= 1
            continue
        resolved.append(
            {
                "rule": item.get("rule"),
                "title": item.get("title"),
                "severity": item.get("severity"),
                "path": item.get("path"),
                "line": item.get("line"),
            }
        )
    return {
        **review,
        "previous_fingerprint": previous.get("fingerprint"),
        "resolved": resolved,
        "findings": marked,
    }
