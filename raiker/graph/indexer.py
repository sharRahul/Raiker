from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class SymbolInfo:
    def __init__(self, name: str, kind: str, file_path: str, line_number: int, module: str, parent: str | None = None, doc: str | None = None) -> None:
        self.name = name
        self.kind = kind
        self.file_path = file_path
        self.line_number = line_number
        self.module = module
        self.parent = parent
        self.doc = doc

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "module": self.module,
            "parent": self.parent,
            "doc_preview": (self.doc[:200] + "...") if self.doc and len(self.doc) > 200 else self.doc,
        }


class DependencyInfo:
    def __init__(self, source: str, target: str, dep_type: str, file_path: str, line_number: int) -> None:
        self.source = source
        self.target = target
        self.dep_type = dep_type
        self.file_path = file_path
        self.line_number = line_number

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "dep_type": self.dep_type,
            "file_path": self.file_path,
            "line_number": self.line_number,
        }


class GraphIndexer:
    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.symbols: list[SymbolInfo] = []
        self.dependencies: list[DependencyInfo] = []

    def index_python_file(self, file_path: str | Path) -> None:
        path = Path(file_path)
        if not path.exists() or path.suffix != ".py":
            return
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            return
        rel_path = str(path.relative_to(self.workspace_root).as_posix())
        module = rel_path.replace("/", ".").replace(".py", "")
        self._extract_symbols(tree, module, rel_path)
        self._extract_imports(tree, module, rel_path)

    def index_python_directory(self, dir_path: str | Path | None = None) -> None:
        root = Path(dir_path) if dir_path else self.workspace_root
        for py_file in sorted(root.rglob("*.py")):
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            self.index_python_file(py_file)

    def _extract_symbols(self, tree: ast.Module, module: str, file_path: str, parent: str | None = None) -> None:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                doc = ast.get_docstring(node)
                self.symbols.append(SymbolInfo(node.name, kind, file_path, node.lineno or 0, module, parent, doc))
                if node.body:
                    self._extract_nested(node, f"{module}.{node.name}", file_path)
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                self.symbols.append(SymbolInfo(node.name, "class", file_path, node.lineno or 0, module, parent, doc))
                self._extract_symbols(node, f"{module}.{node.name}", file_path, parent=node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.symbols.append(SymbolInfo(target.id, "variable", file_path, node.lineno or 0, module, parent))
            elif isinstance(node, (ast.AsyncFunctionDef,)):  # already handled
                pass

    def _extract_nested(self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, module: str, file_path: str) -> None:
        for node in ast.iter_child_nodes(func_node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                self.symbols.append(SymbolInfo(node.name, kind, file_path, node.lineno or 0, module, func_node.name, doc))
                if node.body:
                    self._extract_nested(node, f"{module}.{node.name}", file_path)
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                self.symbols.append(SymbolInfo(node.name, "class", file_path, node.lineno or 0, module, func_node.name, doc))

    def _extract_imports(self, tree: ast.Module, module: str, file_path: str) -> None:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.dependencies.append(DependencyInfo(module, alias.name or alias.asname or "", "import", file_path, node.lineno or 0))
            elif isinstance(node, ast.ImportFrom):
                source = node.module or ""
                for alias in node.names:
                    self.dependencies.append(DependencyInfo(module, f"{source}.{alias.name}", "import_from", file_path, node.lineno or 0))

    def summary(self) -> dict[str, Any]:
        kinds: dict[str, int] = {}
        for s in self.symbols:
            kinds[s.kind] = kinds.get(s.kind, 0) + 1
        return {
            "symbol_count": len(self.symbols),
            "dependency_count": len(self.dependencies),
            "symbol_kinds": kinds,
        }
