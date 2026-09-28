"""Measure Raiker's handwritten source, so simplification is reported, not guessed.

Wave 0 of the codebase optimisation review: before any refactor claims to have
removed lines, there has to be a baseline taken the same way every time. This
script is that baseline. It reads only files git tracks, so a build output, a
virtualenv or ``node_modules`` can never inflate a number, and it writes one
machine-readable JSON report that CI keeps as an artifact on every run.

What it separates, because the review's rules (OR-01, OR-03) depend on it:

* **production** and **test** code, per language — a line moved from one
  handwritten file to another scores nothing, and a test is not product;
* **comment and docstring** lines within those, so compressing history out of
  executable files (OPT-15) can be measured on its own;
* **generated** files, counted apart and never as handwritten;
* the **largest files**, and Python functions over a length threshold as a
  plain complexity signal that needs no extra dependency;
* the **frontend bundle** size, when a build is present.

Documentation, screenshots, lockfiles and data are not source and are skipped.

Usage::

    python scripts/measure_loc.py                    # human summary
    python scripts/measure_loc.py --json out.json    # also write the report
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import subprocess
import sys
import tokenize
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Suffix → language. Anything else tracked in the tree is not counted as code.
LANGUAGES = {
    ".py": "python",
    ".ts": "typescript",
    ".svelte": "svelte",
    ".rs": "rust",
    ".css": "css",
    ".sh": "shell",
    ".yml": "yaml",
}

#: Files a tool writes. Counted apart so a generator replacing handwritten code
#: shows as a reduction rather than a move (OR-01).
GENERATED_PREFIXES: tuple[str, ...] = ()

#: A function longer than this is reported. A signal to look at, not a gate.
LONG_FUNCTION_LINES = 150

LARGEST_FILES = 30


@dataclass
class FileCount:
    path: str
    language: str
    kind: str  # production | test | generated | workflow
    lines: int
    blank: int
    comment: int

    @property
    def code(self) -> int:
        return self.lines - self.blank - self.comment


@dataclass
class Totals:
    files: int = 0
    lines: int = 0
    code: int = 0
    comment: int = 0
    blank: int = 0

    def add(self, count: FileCount) -> None:
        self.files += 1
        self.lines += count.lines
        self.code += count.code
        self.comment += count.comment
        self.blank += count.blank


@dataclass
class Report:
    files: list[FileCount] = field(default_factory=list)
    long_functions: list[dict[str, object]] = field(default_factory=list)
    bundle_bytes: int | None = None


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout.decode()
    return [root / name for name in output.split("\0") if name]


def classify(relative: str) -> str | None:
    """Which bucket a tracked path belongs to, or ``None`` when it is not code."""
    if relative.startswith(("docs/", "node_modules/")) or "/node_modules/" in relative:
        return None
    if relative.startswith(GENERATED_PREFIXES) and GENERATED_PREFIXES:
        return "generated"
    if relative.startswith(".github/"):
        return "workflow"
    name = relative.rsplit("/", 1)[-1]
    if (
        relative.startswith(("tests/", "web/e2e/"))
        or ".test." in name
        or ".spec." in name
        or name.startswith("test_")
        or name in {"test-setup.ts", "test-helpers.ts"}
    ):
        return "test"
    return "production"


def python_comment_lines(source: str) -> set[int]:
    """Lines that are only a comment, or part of a docstring, found by tokenizer and AST."""
    lines: set[int] = set()
    code_lines: set[int] = set()
    layout = {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                lines.add(token.start[0])
            elif token.type not in layout:
                code_lines.update(range(token.start[0], token.end[0] + 1))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return lines
    # A trailing comment shares its line with code, and that line is code.
    lines -= code_lines
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return lines
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                end = body[0].end_lineno or body[0].lineno
                lines.update(range(body[0].lineno, end + 1))
    return lines


def c_like_comment_lines(text: str, *, hash_comments: bool = False) -> set[int]:
    """Lines that are only ``//``, ``/* */`` (or ``#``) comment. Strings are not parsed.

    Good enough for a trend line; a comment marker inside a string literal on
    its own line is rare and would only move the split, never the total.
    """
    lines: set[int] = set()
    in_block = False
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if in_block:
            lines.add(number)
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith(("/*", "<!--")):
            lines.add(number)
            in_block = "*/" not in stripped and "-->" not in stripped
            continue
        if stripped.startswith("//") or (hash_comments and stripped.startswith("#")):
            lines.add(number)
    return lines


def count_file(path: Path, relative: str, language: str, kind: str) -> FileCount | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    all_lines = text.splitlines()
    blank = sum(1 for line in all_lines if not line.strip())
    if language == "python":
        comments = python_comment_lines(text)
    else:
        comments = c_like_comment_lines(text, hash_comments=language in {"shell", "yaml"})
    comment = sum(1 for number in comments if 0 < number <= len(all_lines) and all_lines[number - 1].strip())
    return FileCount(relative, language, kind, len(all_lines), blank, comment)


def long_python_functions(path: Path, relative: str) -> list[dict[str, object]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > LONG_FUNCTION_LINES:
                found.append({"path": relative, "function": node.name, "lines": length})
    return found


def bundle_size(root: Path) -> int | None:
    dist = root / "raiker" / "web" / "dist"
    if not dist.is_dir():
        dist = root / "web" / "dist"
    if not dist.is_dir():
        return None
    return sum(item.stat().st_size for item in dist.rglob("*") if item.is_file())


def measure(root: Path = ROOT) -> Report:
    report = Report()
    for path in tracked_files(root):
        relative = path.relative_to(root).as_posix()
        language = LANGUAGES.get(path.suffix)
        kind = classify(relative)
        if language is None or kind is None or not path.is_file():
            continue
        count = count_file(path, relative, language, kind)
        if count is None:
            continue
        report.files.append(count)
        if language == "python" and kind == "production":
            report.long_functions.extend(long_python_functions(path, relative))
    report.long_functions.sort(key=lambda item: -int(str(item["lines"])))
    report.bundle_bytes = bundle_size(root)
    return report


def summarise(report: Report) -> dict[str, object]:
    by_kind: dict[str, Totals] = defaultdict(Totals)
    by_language: dict[str, dict[str, Totals]] = defaultdict(lambda: defaultdict(Totals))
    for count in report.files:
        by_kind[count.kind].add(count)
        by_language[count.kind][count.language].add(count)
    largest = sorted(
        (count for count in report.files if count.kind in {"production", "test"}),
        key=lambda count: -count.lines,
    )[:LARGEST_FILES]
    return {
        "schema": "raiker-loc/1",
        "totals": {kind: vars(totals) for kind, totals in sorted(by_kind.items())},
        "by_language": {
            kind: {language: vars(totals) for language, totals in sorted(languages.items())}
            for kind, languages in sorted(by_language.items())
        },
        "largest_files": [
            {"path": count.path, "kind": count.kind, "lines": count.lines, "code": count.code}
            for count in largest
        ],
        "long_python_functions": {
            "threshold_lines": LONG_FUNCTION_LINES,
            "count": len(report.long_functions),
            "longest": report.long_functions[:LARGEST_FILES],
        },
        "frontend_bundle_bytes": report.bundle_bytes,
    }


def render(summary: dict[str, object]) -> str:
    out = ["Raiker handwritten source (git-tracked, docs excluded)", ""]
    totals = summary["totals"]
    assert isinstance(totals, dict)
    out.append(f"{'kind':<12}{'files':>8}{'lines':>10}{'code':>10}{'comment':>10}")
    for kind, row in totals.items():
        out.append(
            f"{kind:<12}{row['files']:>8}{row['lines']:>10}{row['code']:>10}{row['comment']:>10}"
        )
    out.append("")
    out.append("Largest files:")
    largest = summary["largest_files"]
    assert isinstance(largest, list)
    for row in largest[:10]:
        out.append(f"  {row['lines']:>7}  {row['path']}")
    long_functions = summary["long_python_functions"]
    assert isinstance(long_functions, dict)
    out.append("")
    out.append(
        f"Python functions over {long_functions['threshold_lines']} lines: {long_functions['count']}"
    )
    bundle = summary["frontend_bundle_bytes"]
    out.append(f"Frontend bundle: {bundle if bundle is not None else 'not built'} bytes")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="write the machine-readable report here")
    args = parser.parse_args(argv)
    summary = summarise(measure())
    if args.json is not None:
        args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(render(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
