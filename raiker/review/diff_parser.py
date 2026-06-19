from __future__ import annotations

from dataclasses import dataclass, field

# File classification used by deterministic review rules. Kept small and stable.
_CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".rb",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".cs",
        ".kt",
        ".swift",
        ".scala",
        ".sh",
        ".php",
    }
)
_DOC_EXTENSIONS = frozenset({".md", ".rst", ".txt", ".adoc"})


@dataclass(frozen=True)
class ParsedDiff:
    files: list[str] = field(default_factory=list)
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)


def parse_unified_diff(diff_text: str) -> ParsedDiff:
    """Parse a unified git diff into changed file paths and added/removed content lines.

    Deterministic and total: it never raises on malformed input, it simply extracts what it
    can. File order follows first appearance in the diff.
    """

    files: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            path = _path_from_diff_header(line)
            if path and path not in files:
                files.append(path)
            continue
        if line.startswith("+++ b/"):
            path = line[len("+++ b/") :].strip()
            if path and path != "/dev/null" and path not in files:
                files.append(path)
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return ParsedDiff(files=files, added_lines=added, removed_lines=removed)


def _path_from_diff_header(line: str) -> str | None:
    marker = " b/"
    index = line.rfind(marker)
    if index == -1:
        return None
    path = line[index + len(marker) :].strip()
    return path or None


def _extension(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot > 0 else ""


def classify_file(path: str) -> str:
    """Return one of ``test``, ``doc``, ``code`` or ``other`` for ``path``."""

    parts = path.split("/")
    name = parts[-1]
    lowered = name.lower()
    stem = lowered.rsplit(".", 1)[0] if "." in lowered else lowered
    if (
        "tests" in parts
        or "test" in parts
        or lowered.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith(".test")
        or stem.endswith(".spec")
    ):
        return "test"
    extension = _extension(path)
    if "docs" in parts or extension in _DOC_EXTENSIONS:
        return "doc"
    if extension in _CODE_EXTENSIONS:
        return "code"
    return "other"
