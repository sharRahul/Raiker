"""The agent's language intelligence over its repository (GAP-BUILD B10).

Three read tools, all governed inside
:class:`~raiker.graph.language_service.LanguageIntelligenceService`: the
``language_intelligence`` capability gate (off ⇒ fail closed with the reason),
the decision mode (``deny`` refuses), and the same workspace containment the git
and code-map tools use to decide which repository "this repository" means.

B10's fourth item, ``find_references``, already ships as ``code_map_references``
(B9 / FIXED-113). It is not duplicated here: two names for one behaviour is a
choice the model has to make for no reason.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


def _service(
    workspace_root: str | Path, store: SQLiteStore | None, principal_id: str | None
) -> Any:
    from raiker.graph.language_service import LanguageIntelligenceService
    from raiker.storage.sqlite import SQLiteStore as Store

    return LanguageIntelligenceService(
        workspace_root, store or Store(workspace_root), principal_id=principal_id
    )


def document_symbols(
    workspace_root: str | Path,
    path: str,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """The outline of one file — every declaration, with its line range.

    Parsed from the file on disk, not read from the stored code map, so it is
    right the instant after the agent's own edit rather than after the next
    index refresh. What comes back is names, signatures and docstrings copied
    out of a repository file, so it is labelled untrusted data exactly like a
    fetched page.
    """
    return _service(workspace_root, store, principal_id).document_symbols(str(path))


def find_definition(
    workspace_root: str | Path,
    name: str,
    from_path: Any = None,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Where exactly *name* is declared, best candidate first.

    Differs from ``code_map_search`` in the way that matters at a call site:
    that ranks a fuzzy query and will happily return ``ConfigLoader`` for
    ``Config``; this matches the exact name and orders the real candidates by
    proximity to ``from_path`` — the declaring file first, then a file it
    imports, then the rest.
    """
    origin = str(from_path).strip() if from_path else None
    return _service(workspace_root, store, principal_id).find_definition(
        str(name), from_path=origin or None
    )


def diagnostics(
    workspace_root: str | Path,
    paths: Any,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Parse the named files and report what a parser can see.

    The edit → verify loop, without a command approval and without a subprocess.
    Its honesty contract is the reason it is worth having: a file in a language
    this runtime cannot parse comes back under ``unsupported`` and is explicitly
    **not** claimed to be clean.
    """
    requested = (
        [str(item) for item in paths]
        if isinstance(paths, (list, tuple))
        else ([str(paths)] if paths else [])
    )
    return _service(workspace_root, store, principal_id).diagnostics(requested)
