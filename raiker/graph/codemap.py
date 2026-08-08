"""The repository code map (GAP-BUILD B9).

Every turn used to start cold. The agent could `grep`, but it could not answer
"where is this defined" without guessing a pattern first, so on a repository of
any size it searched blind. This module is the scan that ends that: a bounded,
deterministic, local walk of one repository that records **what each file is and
what it defines**, so the runtime can rank a prompt against real symbols instead
of hoping a substring matches.

Three properties are deliberate.

**It is derived, never authoritative.** A code map is a projection of files the
agent may already read. It grants nothing: `code_map_search` returns coordinates,
and reading the file at those coordinates still goes through `read_file`, the
workspace containment check, and the policy engine. Nothing here can widen what a
turn may touch.

**It is bounded before it is useful.** A scan that walks an unbounded tree on the
owner's machine is a denial-of-service against the owner. Every limit in
:class:`CodeMapLimits` is enforced during the walk rather than checked afterwards,
and a scan that hits one records *which* limit it hit
(:attr:`CodeMapScan.limits_hit`) rather than silently returning a partial map that
reads as complete.

**Its text is untrusted.** Names and docstrings come out of repository files, so
they are exactly the place a prompt-injection string would sit. Everything this
module extracts is labelled untrusted where it is consumed — in the turn bundle
and in the tool result — and is never treated as instruction.

Python is parsed with :mod:`ast`, which is exact. Every other language is matched
with bounded regular expressions, which is not: a regex extractor finds most
declarations and misses unusual ones. That trade is stated rather than hidden —
:attr:`CodeMapFile.extractor` records which one produced a file's symbols, so a
caller can tell an exact result from an approximate one.
"""
from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "1.0"

# Directory names never walked. Dot-directories are skipped wholesale (`.git`,
# `.raiker`, `.venv`, `.svelte-kit`, every cache), and these are the ones that
# carry no leading dot but are just as certainly not the owner's source.
_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        "__pycache__",
        "venv",
        "site-packages",
        "dist",
        "build",
        "target",
        "coverage",
        "htmlcov",
        "vendor",
        "bower_components",
        "Pods",
    }
)

# Suffix → the language a file is recorded as. A suffix absent here is not
# indexed at all: an unrecognised extension is more likely to be data, a binary,
# or a lockfile than something whose symbols are worth a row.
_LANGUAGE_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".svelte": "svelte",
    ".vue": "vue",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".md": "markdown",
    ".rst": "markdown",
}

# Languages whose symbols come from a regex table rather than a real parser.
# Markdown is in neither: a document has no declarations, and its path and title
# are the whole of what a code map should claim about it.
_REGEX_LANGUAGES: frozenset[str] = frozenset(
    {
        "typescript",
        "javascript",
        "svelte",
        "vue",
        "go",
        "rust",
        "java",
        "kotlin",
        "swift",
        "ruby",
        "php",
        "csharp",
        "c",
        "cpp",
        "shell",
    }
)

_IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"

# Declaration patterns per language. Each entry is (kind, compiled pattern) and
# every pattern captures the declared name in group 1. They run line by line with
# a per-line length cap, so a minified bundle costs a bounded scan rather than a
# catastrophic backtrack.
_DECLARATION_PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "typescript": (
        ("class", re.compile(rf"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+({_IDENT})")),
        ("interface", re.compile(rf"^\s*(?:export\s+)?interface\s+({_IDENT})")),
        ("type", re.compile(rf"^\s*(?:export\s+)?type\s+({_IDENT})\s*[=<]")),
        ("enum", re.compile(rf"^\s*(?:export\s+)?(?:const\s+)?enum\s+({_IDENT})")),
        ("function", re.compile(rf"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*({_IDENT})")),
        ("function", re.compile(rf"^\s*(?:export\s+)?(?:const|let)\s+({_IDENT})\s*(?::[^=]+)?=\s*(?:async\s*)?\(")),
        ("const", re.compile(rf"^\s*export\s+(?:const|let)\s+({_IDENT})\s*[:=]")),
    ),
    "go": (
        ("function", re.compile(rf"^func\s+({_IDENT})\s*\(")),
        ("method", re.compile(rf"^func\s+\([^)]*\)\s+({_IDENT})\s*\(")),
        ("type", re.compile(rf"^type\s+({_IDENT})\s+")),
    ),
    "rust": (
        ("function", re.compile(rf"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+({_IDENT})")),
        ("struct", re.compile(rf"^\s*(?:pub(?:\([^)]*\))?\s+)?struct\s+({_IDENT})")),
        ("enum", re.compile(rf"^\s*(?:pub(?:\([^)]*\))?\s+)?enum\s+({_IDENT})")),
        ("trait", re.compile(rf"^\s*(?:pub(?:\([^)]*\))?\s+)?trait\s+({_IDENT})")),
        ("impl", re.compile(rf"^\s*impl(?:<[^>]*>)?\s+(?:{_IDENT}(?:<[^>]*>)?\s+for\s+)?({_IDENT})")),
    ),
    "java": (
        ("class", re.compile(rf"^\s*(?:public\s+|private\s+|protected\s+|final\s+|abstract\s+|static\s+)*class\s+({_IDENT})")),
        ("interface", re.compile(rf"^\s*(?:public\s+|private\s+|protected\s+)*interface\s+({_IDENT})")),
        ("enum", re.compile(rf"^\s*(?:public\s+|private\s+|protected\s+)*enum\s+({_IDENT})")),
    ),
    "kotlin": (
        ("class", re.compile(rf"^\s*(?:public\s+|internal\s+|private\s+|open\s+|data\s+|sealed\s+|abstract\s+)*class\s+({_IDENT})")),
        ("interface", re.compile(rf"^\s*(?:public\s+|internal\s+|private\s+)*interface\s+({_IDENT})")),
        ("function", re.compile(rf"^\s*(?:public\s+|internal\s+|private\s+|suspend\s+|override\s+)*fun\s+({_IDENT})")),
    ),
    "swift": (
        ("class", re.compile(rf"^\s*(?:public\s+|private\s+|internal\s+|final\s+|open\s+)*class\s+({_IDENT})")),
        ("struct", re.compile(rf"^\s*(?:public\s+|private\s+|internal\s+)*struct\s+({_IDENT})")),
        ("protocol", re.compile(rf"^\s*(?:public\s+|private\s+|internal\s+)*protocol\s+({_IDENT})")),
        ("function", re.compile(rf"^\s*(?:public\s+|private\s+|internal\s+|static\s+|override\s+)*func\s+({_IDENT})")),
    ),
    "ruby": (
        ("class", re.compile(rf"^\s*class\s+({_IDENT})")),
        ("module", re.compile(rf"^\s*module\s+({_IDENT})")),
        ("function", re.compile(rf"^\s*def\s+({_IDENT})")),
    ),
    "php": (
        ("class", re.compile(rf"^\s*(?:final\s+|abstract\s+)?class\s+({_IDENT})")),
        ("interface", re.compile(rf"^\s*interface\s+({_IDENT})")),
        ("function", re.compile(rf"^\s*(?:public\s+|private\s+|protected\s+|static\s+)*function\s+({_IDENT})")),
    ),
    "csharp": (
        ("class", re.compile(rf"^\s*(?:public\s+|private\s+|protected\s+|internal\s+|sealed\s+|static\s+|abstract\s+|partial\s+)*class\s+({_IDENT})")),
        ("interface", re.compile(rf"^\s*(?:public\s+|private\s+|protected\s+|internal\s+)*interface\s+({_IDENT})")),
        ("struct", re.compile(rf"^\s*(?:public\s+|private\s+|protected\s+|internal\s+)*struct\s+({_IDENT})")),
        ("enum", re.compile(rf"^\s*(?:public\s+|private\s+|protected\s+|internal\s+)*enum\s+({_IDENT})")),
    ),
    "c": (
        ("struct", re.compile(rf"^\s*(?:typedef\s+)?struct\s+({_IDENT})")),
        ("function", re.compile(rf"^[A-Za-z_][A-Za-z0-9_ \t*]*\s+\*?({_IDENT})\s*\([^;]*\)\s*\{{\s*$")),
    ),
    "cpp": (
        ("class", re.compile(rf"^\s*class\s+({_IDENT})")),
        ("struct", re.compile(rf"^\s*(?:typedef\s+)?struct\s+({_IDENT})")),
        ("function", re.compile(rf"^[A-Za-z_][A-Za-z0-9_:<> \t*&]*\s+\*?({_IDENT})\s*\([^;]*\)\s*\{{\s*$")),
    ),
    "shell": (
        ("function", re.compile(rf"^\s*(?:function\s+)?({_IDENT})\s*\(\)\s*\{{")),
    ),
}

# `import x from "spec"`, `import "spec"`, `require("spec")`, `from "spec"`.
_JS_IMPORT = re.compile(r"""(?:from|import|require)\s*\(?\s*["']([^"'\n]{1,200})["']""")
_GO_IMPORT = re.compile(rf"""^\s*(?:import\s+)?(?:{_IDENT}\s+)?"([^"\n]{{1,200}})"$""")
_RUST_USE = re.compile(r"^\s*(?:pub\s+)?use\s+([A-Za-z0-9_:{}, *]{1,200});")
_JVM_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([A-Za-z0-9_.*]{1,200})")
_MARKDOWN_TITLE = re.compile(r"^#\s+(.{1,160})")

_MAX_LINE_LEN = 2_000
_MAX_DOC_CHARS = 240
_MAX_SIGNATURE_CHARS = 200


@dataclass(frozen=True)
class CodeMapLimits:
    """Every bound the scan enforces, in one place the caller can read back.

    Held together as a value rather than as constants because the executor, the
    tool, and the tests all need to state the same numbers, and a limit named in
    three places drifts in two of them.
    """

    max_files: int = 20_000
    max_file_bytes: int = 512_000
    max_symbols: int = 200_000
    max_edges: int = 200_000
    max_depth: int = 24


@dataclass(frozen=True)
class CodeMapSymbol:
    """One declaration: what it is, what it is called, and where it lives."""

    path: str
    kind: str
    name: str
    qualified_name: str
    line_start: int
    line_end: int
    parent: str = ""
    signature: str = ""
    doc: str = ""


@dataclass(frozen=True)
class CodeMapFile:
    """One indexed file. ``sha256`` is what makes a refresh incremental."""

    path: str
    language: str
    sha256: str
    size_bytes: int
    line_count: int
    symbol_count: int
    title: str = ""
    extractor: str = "none"


@dataclass(frozen=True)
class CodeMapEdge:
    """One relationship, in the spec's vocabulary (``imports`` today)."""

    from_path: str
    relationship: str
    target: str
    line: int = 0


@dataclass
class CodeMapScan:
    """The result of one walk: rows to persist, plus what the walk refused.

    ``skipped`` and ``limits_hit`` exist so a partial map can never present
    itself as a complete one. A caller that renders "412 files indexed" without
    reading them is reporting a number the scan did not promise.
    """

    files: list[CodeMapFile] = field(default_factory=list)
    symbols: list[CodeMapSymbol] = field(default_factory=list)
    edges: list[CodeMapEdge] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)
    limits_hit: list[str] = field(default_factory=list)

    def note_skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def note_limit(self, name: str) -> None:
        if name not in self.limits_hit:
            self.limits_hit.append(name)

    @property
    def complete(self) -> bool:
        return not self.limits_hit


def language_for(path: Path) -> str | None:
    """The language a file is recorded as, or ``None`` when it is not indexed."""
    return _LANGUAGE_BY_SUFFIX.get(path.suffix.lower())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _doc_preview(text: str | None) -> str:
    if not text:
        return ""
    first = text.strip().splitlines()[0].strip() if text.strip() else ""
    return first[:_MAX_DOC_CHARS]


class CodeMapBuilder:
    """Walk one repository root and produce a :class:`CodeMapScan`.

    ``repo_root`` must already have been resolved and contained by the caller —
    this class does no containment checking of its own, because doing it in two
    places is how the two rules drift apart. :class:`CodeMapService` resolves the
    root through the same workspace check every other path read uses.
    """

    def __init__(self, repo_root: str | Path, *, limits: CodeMapLimits | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.limits = limits or CodeMapLimits()

    # ── the walk ─────────────────────────────────────────────────────────────

    def scan(self) -> CodeMapScan:
        """Index every eligible file under the root."""
        scan = CodeMapScan()
        for path in self._walk(scan):
            if len(scan.files) >= self.limits.max_files:
                scan.note_limit("max_files")
                break
            self.index_file(path, scan)
        return scan

    def scan_paths(self, relative_paths: list[str]) -> CodeMapScan:
        """Index exactly the named workspace-relative paths, and nothing else.

        This is the incremental half. A path that no longer exists produces no
        file row, which is what tells the caller to drop the stale one rather
        than keep a row for a file that was deleted.
        """
        scan = CodeMapScan()
        for relative in relative_paths:
            candidate = (self.repo_root / relative).resolve()
            try:
                candidate.relative_to(self.repo_root)
            except ValueError:
                scan.note_skip("outside_repository")
                continue
            if not candidate.is_file():
                scan.note_skip("missing")
                continue
            self.index_file(candidate, scan)
        return scan

    def _walk(self, scan: CodeMapScan) -> list[Path]:
        found: list[Path] = []
        stack: list[tuple[Path, int]] = [(self.repo_root, 0)]
        while stack:
            directory, depth = stack.pop()
            if depth > self.limits.max_depth:
                scan.note_limit("max_depth")
                continue
            try:
                entries = sorted(directory.iterdir(), key=lambda item: item.name)
            except (OSError, PermissionError):
                scan.note_skip("unreadable_directory")
                continue
            for entry in entries:
                if entry.is_symlink():
                    # A symlink can point anywhere, including out of the
                    # workspace. Following one would make containment a property
                    # of the filesystem rather than of this code.
                    scan.note_skip("symlink")
                    continue
                if entry.is_dir():
                    if entry.name.startswith(".") or entry.name in _IGNORED_DIRS:
                        continue
                    stack.append((entry, depth + 1))
                    continue
                if not entry.is_file():
                    continue
                if language_for(entry) is None:
                    continue
                found.append(entry)
        return sorted(found)

    # ── one file ─────────────────────────────────────────────────────────────

    def index_file(self, path: Path, scan: CodeMapScan) -> None:
        """Read one file and append its file/symbol/import rows to *scan*."""
        language = language_for(path)
        if language is None:
            scan.note_skip("unsupported_language")
            return
        try:
            size = path.stat().st_size
        except OSError:
            scan.note_skip("unreadable_file")
            return
        if size > self.limits.max_file_bytes:
            scan.note_skip("too_large")
            return
        try:
            data = path.read_bytes()
        except (OSError, PermissionError):
            scan.note_skip("unreadable_file")
            return
        if b"\x00" in data:
            scan.note_skip("binary")
            return
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            scan.note_skip("undecodable")
            return

        relative = path.relative_to(self.repo_root).as_posix()
        symbols: list[CodeMapSymbol] = []
        edges: list[CodeMapEdge] = []
        extractor = "none"
        title = ""
        if language == "python":
            extractor = "python_ast"
            symbols, edges, title, ok = self._python(relative, text)
            if not ok:
                # A file that does not parse is still a file. Recording it with
                # no symbols is honest; dropping it would hide it from search.
                extractor = "python_ast_unparsed"
                scan.note_skip("python_syntax_error")
        elif language in _REGEX_LANGUAGES:
            extractor = "regex"
            symbols, edges = self._regex(relative, language, text)
        elif language == "markdown":
            title = self._markdown_title(text)

        remaining_symbols = max(0, self.limits.max_symbols - len(scan.symbols))
        if len(symbols) > remaining_symbols:
            symbols = symbols[:remaining_symbols]
            scan.note_limit("max_symbols")
        remaining_edges = max(0, self.limits.max_edges - len(scan.edges))
        if len(edges) > remaining_edges:
            edges = edges[:remaining_edges]
            scan.note_limit("max_edges")

        scan.files.append(
            CodeMapFile(
                path=relative,
                language=language,
                sha256=_sha256(data),
                size_bytes=size,
                line_count=text.count("\n") + 1 if text else 0,
                symbol_count=len(symbols),
                title=title,
                extractor=extractor,
            )
        )
        scan.symbols.extend(symbols)
        scan.edges.extend(edges)

    @staticmethod
    def _markdown_title(text: str) -> str:
        """A document's own first heading, when it has one."""
        for line in text.splitlines()[:40]:
            match = _MARKDOWN_TITLE.match(line)
            if match:
                return match.group(1).strip()[:_MAX_DOC_CHARS]
        return ""

    # ── python: exact ────────────────────────────────────────────────────────

    def _python(
        self, relative: str, text: str
    ) -> tuple[list[CodeMapSymbol], list[CodeMapEdge], str, bool]:
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            return [], [], "", False
        module = relative.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
        symbols: list[CodeMapSymbol] = []
        edges: list[CodeMapEdge] = []
        self._python_body(tree.body, relative, module, "", symbols)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    edges.append(
                        CodeMapEdge(relative, "imports", alias.name[:200], node.lineno)
                    )
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                for alias in node.names:
                    target = f"{base}.{alias.name}" if base else alias.name
                    edges.append(CodeMapEdge(relative, "imports", target[:200], node.lineno))
        return symbols, edges, _doc_preview(ast.get_docstring(tree)), True

    def _python_body(
        self,
        body: list[ast.stmt],
        relative: str,
        module: str,
        parent: str,
        out: list[CodeMapSymbol],
    ) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                qualified = f"{module}.{node.name}" if not parent else f"{parent}.{node.name}"
                out.append(
                    CodeMapSymbol(
                        path=relative,
                        kind="class",
                        name=node.name,
                        qualified_name=qualified,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        parent=parent,
                        signature=self._class_signature(node),
                        doc=_doc_preview(ast.get_docstring(node)),
                    )
                )
                self._python_body(node.body, relative, module, qualified, out)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = f"{module}.{node.name}" if not parent else f"{parent}.{node.name}"
                out.append(
                    CodeMapSymbol(
                        path=relative,
                        kind="method" if parent else "function",
                        name=node.name,
                        qualified_name=qualified,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        parent=parent,
                        signature=self._function_signature(node),
                        doc=_doc_preview(ast.get_docstring(node)),
                    )
                )

    @staticmethod
    def _class_signature(node: ast.ClassDef) -> str:
        bases = [ast.unparse(base) for base in node.bases]
        rendered = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
        return rendered[:_MAX_SIGNATURE_CHARS]

    @staticmethod
    def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        try:
            args = ast.unparse(node.args)
        except Exception:  # noqa: BLE001 — a signature is a convenience, not the row
            args = ""
        return f"{prefix} {node.name}({args})"[:_MAX_SIGNATURE_CHARS]

    # ── everything else: approximate, and says so ────────────────────────────

    def _regex(
        self, relative: str, language: str, text: str
    ) -> tuple[list[CodeMapSymbol], list[CodeMapEdge]]:
        patterns = _DECLARATION_PATTERNS.get(language, ())
        if language in ("svelte", "vue"):
            patterns = _DECLARATION_PATTERNS["typescript"]
        symbols: list[CodeMapSymbol] = []
        edges: list[CodeMapEdge] = []
        seen: set[tuple[str, int]] = set()
        module = relative.rsplit("/", 1)[-1]
        for number, raw in enumerate(text.splitlines(), start=1):
            line = raw[:_MAX_LINE_LEN]
            for kind, pattern in patterns:
                match = pattern.match(line)
                if match is None:
                    continue
                name = match.group(1)
                if (name, number) in seen:
                    continue
                seen.add((name, number))
                symbols.append(
                    CodeMapSymbol(
                        path=relative,
                        kind=kind,
                        name=name,
                        qualified_name=f"{module}.{name}",
                        line_start=number,
                        line_end=number,
                        signature=line.strip()[:_MAX_SIGNATURE_CHARS],
                    )
                )
                break
            for target in self._imports(language, line):
                edges.append(CodeMapEdge(relative, "imports", target[:200], number))
        if language in ("svelte", "vue"):
            # The file *is* a component, and that is the name a person searches
            # for. Nothing in the file's text declares it, so it is added here.
            stem = relative.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            symbols.insert(
                0,
                CodeMapSymbol(
                    path=relative,
                    kind="component",
                    name=stem,
                    qualified_name=stem,
                    line_start=1,
                    line_end=max(1, text.count("\n") + 1),
                    signature=f"<{stem} />",
                ),
            )
        return symbols, edges

    @staticmethod
    def _imports(language: str, line: str) -> list[str]:
        if language in ("typescript", "javascript", "svelte", "vue"):
            return [match.group(1) for match in _JS_IMPORT.finditer(line)]
        if language == "go":
            match = _GO_IMPORT.match(line)
            return [match.group(1)] if match else []
        if language == "rust":
            match = _RUST_USE.match(line)
            return [match.group(1).strip()] if match else []
        if language in ("java", "kotlin"):
            match = _JVM_IMPORT.match(line)
            return [match.group(1)] if match else []
        return []
