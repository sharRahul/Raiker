from __future__ import annotations

from raiker.build_identity import build_identity

__all__ = ["__version__"]

#: GCR-16 — resolved rather than declared, so this, the API, the prompt client
#: metadata and the web client all report the one identity the release build
#: wrote into the artifact. A source checkout still answers ``0.0.0``, which is
#: the honest answer for a tree that has never been released.
__version__ = build_identity().version
