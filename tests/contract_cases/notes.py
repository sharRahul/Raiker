"""Contract cases for Raiker Notes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.contract_cases.base import Call, Cases


def _seed(ws: Path) -> None:
    root = ws / "Notes"
    (root / "Projects").mkdir(parents=True, exist_ok=True)
    (root / "Projects" / "Raiker.md").write_text("---\ntags:\n  - app\n---\n# Raiker\n", encoding="utf-8")
    (root / "Ideas.md").write_text("Raiker notes. [[Raiker]] #idea\n- [ ] link it\n", encoding="utf-8")


def _seeded(call: Call) -> object:
    def seed(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
        _seed(ws)
        return call

    return seed


def _save(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _seed(ws)
    note = client.get("/api/notes/note?path=Ideas.md", headers=h).json()
    return "/api/notes/note", {"path": "Ideas.md", "content": "edited\n", "expected_mtime": note["mtime"]}


CASES: Cases = {
    ("GET", "/api/notes"): _seeded("/api/notes"),  # type: ignore[dict-item]
    ("GET", "/api/notes/note"): _seeded("/api/notes/note?path=Ideas.md"),  # type: ignore[dict-item]
    ("PUT", "/api/notes/note"): _save,
    ("POST", "/api/notes/note"): _seeded(("/api/notes/note", {"path": "New.md", "content": "# New\n"})),  # type: ignore[dict-item]
    ("DELETE", "/api/notes/note"): _seeded("/api/notes/note?path=Ideas.md"),  # type: ignore[dict-item]
    ("POST", "/api/notes/rename"): _seeded(("/api/notes/rename", {"from": "Projects/Raiker.md", "to": "Projects/App.md"})),  # type: ignore[dict-item]
    ("GET", "/api/notes/backlinks"): _seeded("/api/notes/backlinks?path=Projects/Raiker.md"),  # type: ignore[dict-item]
    ("POST", "/api/notes/link-mention"): _seeded(("/api/notes/link-mention", {"source": "Ideas.md", "line": 0, "target": "Projects/Raiker.md"})),  # type: ignore[dict-item]
    ("GET", "/api/notes/graph"): _seeded("/api/notes/graph"),  # type: ignore[dict-item]
    ("GET", "/api/notes/search"): _seeded("/api/notes/search?q=raiker"),  # type: ignore[dict-item]
    ("POST", "/api/notes/daily"): _seeded("/api/notes/daily"),  # type: ignore[dict-item]
    ("GET", "/api/notes/resolve"): _seeded("/api/notes/resolve?target=raiker"),  # type: ignore[dict-item]
}
