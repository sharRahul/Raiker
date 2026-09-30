"""Code: repository references and their read posture."""

from __future__ import annotations

import re
from dataclasses import dataclass

from raiker.contracts.views import View

# GitHub coordinate shapes. Validation is strict and local — a repository
# reference is stored only when it *could* name a real repository, and no
# network call is made to find out.
_GITHUB_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_])?")


_GITHUB_REF = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._/-]{0,98}[A-Za-z0-9_-])?")


@dataclass(frozen=True)
class CodeRepoView(View):
    """One repository a coding chat can be pointed at.

    A row is a *reference*, not an integration: it stores no credential, opens no
    network connection, and grants no capability. A ``local`` repository is a
    workspace-contained subpath — anything resolving outside the workspace is
    refused (fail closed) — and its files reach a turn as bounded, untrusted
    context through the same governed attachment path as any other workspace
    path. A ``github`` repository records the ``owner/repo`` coordinate only; the
    content is read through the brokered ``github_read`` tool, which stays
    subject to the ``connector_github_runtime`` gate and its decision mode, so
    a reference here never becomes read access on its own.
    """

    repo_id: str
    kind: str
    label: str
    selected: bool
    created_at: str
    local_subpath: str | None = None
    local_exists: bool = False
    github_owner: str | None = None
    github_repo: str | None = None
    branch: str | None = None


@dataclass(frozen=True)
class CodeReposView(View):
    """Every repository reference for one account, plus the honest read posture.

    ``github_gate_state``/``github_decision_mode`` report what the
    ``connector_github_runtime`` gate currently permits, so the interface can say
    whether a connected GitHub repository is actually readable instead of
    implying it is.
    """

    repos: tuple[CodeRepoView, ...]
    selected_repo_id: str | None
    github_gate_state: str
    github_decision_mode: str
    github_token_configured: bool
    note: str = (
        "References only. Connecting a repository grants no capability: a local folder "
        "stays workspace-contained, and every GitHub read still runs through the brokered "
        "github_read tool under the connector_github_runtime gate and its decision mode — "
        "a disabled gate fails closed no matter what is connected here."
    )
