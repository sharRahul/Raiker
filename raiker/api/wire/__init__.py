# SPDX-License-Identifier: Apache-2.0
"""What a route answers with, where the route itself assembles the answer.

OPT-01/OPT-02 Stage B. A read model's view already describes its route's
response; a route that builds its body in place had nothing that did, so the
OpenAPI document could not name a field of it and the browser kept its own copy.
Each view here is that body, built by the route through ``serialize_dto`` — so
the wire is the view's fields by construction, ``mypy`` checks every value put
in it, and ``scripts/api_contract.py`` can describe it.

A view here is a projection the route sends, never a stored record.
"""

from __future__ import annotations

from dataclasses import dataclass

from raiker.contracts.views import View

__all__ = ["Ok"]


@dataclass(frozen=True)
class Ok(View):
    """The acknowledgement a route gives when the change it was asked for is done."""

    ok: bool = True
