from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class ProjectGraphExtractor:
    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)

    def extract_module_map(self) -> dict[str, dict[str, Any]]:
        modules: dict[str, dict[str, Any]] = {}
        for py_file in sorted(self.workspace_root.rglob("*.py")):
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            rel = py_file.relative_to(self.workspace_root).as_posix()
            module = rel.replace("/", ".").replace(".py", "")
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            imports: list[str] = []
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name or alias.asname or "")
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ""
                    for alias in node.names:
                        imports.append(f"{base}.{alias.name}" if base else alias.name)
            modules[module] = {
                "file_path": rel,
                "imports": sorted(set(imports)),
                "import_count": len(set(imports)),
            }
        return modules

    def build_dependency_graph(self) -> dict[str, Any]:
        modules = self.extract_module_map()
        local_modules = {m for m in modules}
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for module, info in modules.items():
            nodes.append({"module": module, "file_path": info["file_path"], "import_count": info["import_count"]})
            for imp in info["imports"]:
                base = imp.split(".")[0]
                if base in local_modules:
                    edges.append({"source": module, "target": imp, "type": "local_dependency"})
        return {
            "module_count": len(nodes),
            "dependency_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    def suggest_skill_candidates(self, min_dependencies: int = 3, max_candidates: int = 5) -> list[dict[str, Any]]:
        modules = self.extract_module_map()
        candidates: list[dict[str, Any]] = []
        for module, info in sorted(modules.items(), key=lambda x: x[1]["import_count"], reverse=True):
            if info["import_count"] >= min_dependencies:
                candidates.append({
                    "name": f"analyze_{module.split('.')[-1]}",
                    "description": f"Workflow for analyzing the {module} module ({info['import_count']} dependencies)",
                    "module": module,
                    "import_count": info["import_count"],
                    "confidence": min(1.0, info["import_count"] / 10),
                })
                if len(candidates) >= max_candidates:
                    break
        return candidates
