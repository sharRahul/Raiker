"""QUI-F21 — a project's own permission limits.

A project can say what work filed in it may reach, in three kinds:

* ``repositories`` — the only repositories a push or a GitHub write may go to,
  as ``owner/name`` ("may push to this one repository only");
* ``web_domains`` — the only sites a page may be read from (a domain also
  covers its subdomains);
* ``connections`` — the only connections its conversations may use.

Limits **only narrow**. They are checked after the owner's permissions have
decided, and can turn an allow or an ask into a refusal, never the reverse; an
empty list means that kind is not limited. A conversation is under a project's
limits while it is filed in that project, so choosing the project in the
composer sets them, and moving the conversation out lifts them.

When a limit cannot be checked — a push whose remote cannot be read, a page
address that is not a URL — the action is refused rather than allowed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from typing_extensions import TypedDict

from raiker.contracts.ids import utc_now

KINDS: tuple[str, ...] = ("repositories", "web_domains", "connections")
MAX_ENTRIES = 20

#: Tools a connection limit applies to, and the connection each one uses.
_CONNECTION_TOOLS = {
    "gmail_read": "gmail",
    "gcal_read": "gcal",
    "slack_read": "slack",
    "github_read": "github",
    "github_write": "github",
}
_WEB_TOOLS = frozenset({"web_fetch", "web_extract"})
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_DOMAIN = re.compile(r"^(?=.{1,253}$)([a-z0-9-]+\.)+[a-z]{2,63}$")
_CONNECTION = re.compile(r"^[a-z0-9_-]{1,64}$")


class ProjectLimits(TypedDict):
    repositories: list[str]
    web_domains: list[str]
    connections: list[str]


class LimitError(ValueError):
    pass


def empty() -> ProjectLimits:
    return {"repositories": [], "web_domains": [], "connections": []}


def clean(raw: dict[str, Any]) -> ProjectLimits:
    """Validate what the owner typed; refuse rather than drop an entry that is not usable."""
    limits = empty()
    for kind in KINDS:
        values = raw.get(kind) or []
        if not isinstance(values, list) or len(values) > MAX_ENTRIES:
            raise LimitError(f"project_limit_{kind}_invalid")
        seen: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if kind == "repositories":
                text = re.sub(r"^(https?://)?(www\.)?github\.com/", "", text, flags=re.I).removesuffix(".git").strip("/")
                if not _REPO.match(text):
                    raise LimitError("project_limit_repository_invalid")
                text = text.lower()
            elif kind == "web_domains":
                text = text.lower().removeprefix("https://").removeprefix("http://").split("/")[0].removeprefix("*.")
                if not _DOMAIN.match(text):
                    raise LimitError("project_limit_domain_invalid")
            elif not _CONNECTION.match(text.lower()):
                raise LimitError("project_limit_connection_invalid")
            else:
                text = text.lower()
            if text and text not in seen:
                seen.append(text)
        limits[kind] = seen  # type: ignore[literal-required]
    return limits


def load(store: Any, project_id: str | None) -> ProjectLimits:
    if not project_id:
        return empty()
    row = store._row("SELECT limits_json FROM project_limits WHERE project_id = ?", (project_id,))
    if row is None:
        return empty()
    try:
        return clean(json.loads(str(row["limits_json"])))
    except (ValueError, TypeError):
        # A stored value this build cannot read is treated as the strictest
        # reading of what it could have been: nothing reachable of any kind it
        # named would be wrong too, so an unreadable row refuses everything
        # limitable rather than nothing.
        return {"repositories": ["-/-"], "web_domains": ["invalid.invalid"], "connections": ["-"]}


def save(store: Any, project_id: str, limits: ProjectLimits) -> None:
    store._execute(
        "INSERT INTO project_limits (project_id, limits_json, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(project_id) DO UPDATE SET limits_json = excluded.limits_json, updated_at = excluded.updated_at",
        (project_id, json.dumps(limits, sort_keys=True), utc_now()),
    )


def describe(limits: ProjectLimits) -> list[str]:
    """The limits in words, for the composer and the project page."""
    lines: list[str] = []
    if limits["repositories"]:
        lines.append("Pushes only to " + ", ".join(limits["repositories"]))
    if limits["web_domains"]:
        lines.append("Reads web pages only from " + ", ".join(limits["web_domains"]))
    if limits["connections"]:
        lines.append("Uses only " + ", ".join(limits["connections"]))
    return lines


def _session_project(store: Any, session_id: str) -> str | None:
    row = store._row("SELECT project_id FROM sessions WHERE session_id = ?", (session_id,))
    return str(row["project_id"]) if row is not None and row["project_id"] else None


def _push_repository(workspace_root: str | Path, store: Any, owner: str | None, remote: str | None) -> str:
    from raiker.runtime.git_credential import repository_key
    from raiker.tools.git import (
        _remote_names,
        _remote_url,
        _upstream_remote,
        current_branch,
        resolve_repository_root,
        selected_repository_subpath,
    )

    root = resolve_repository_root(workspace_root, selected_repository_subpath(store, owner))
    names = _remote_names(root)
    name = remote or ""
    if not name:
        branch = current_branch(root)
        upstream = _upstream_remote(root, branch) if branch else ""
        name = upstream if upstream in names else ("origin" if "origin" in names else (names[0] if len(names) == 1 else ""))
    url = _remote_url(root, name) if name else ""
    key = repository_key(url) if url else ""
    return key.removeprefix("github.com/") if key else ""


def refusal(
    store: Any,
    *,
    workspace_root: str | Path,
    session_id: str,
    owner_principal_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
) -> str | None:
    """The reason a project limit refuses this action, or ``None`` when none does."""
    project_id = _session_project(store, session_id)
    if project_id is None:
        return None
    limits = load(store, project_id)
    if tool_name in {"git_push", "github_write"} and limits["repositories"]:
        if tool_name == "github_write":
            repo = str(arguments.get("repo") or "").strip().lower()
        else:
            try:
                repo = _push_repository(workspace_root, store, owner_principal_id, str(arguments.get("remote") or "") or None)
            except Exception:  # noqa: BLE001 — a remote that cannot be read is refused, not allowed
                repo = ""
        if repo not in limits["repositories"]:
            return "project_limit_repository"
    if tool_name in _WEB_TOOLS and limits["web_domains"]:
        host = (urlsplit(str(arguments.get("url") or "")).hostname or "").lower()
        if not host or not any(host == domain or host.endswith("." + domain) for domain in limits["web_domains"]):
            return "project_limit_web_domain"
    if limits["connections"]:
        connection = (
            str(arguments.get("connector_id") or "").lower()
            if tool_name in {"connector_read", "connector_write"}
            else _CONNECTION_TOOLS.get(tool_name, "")
        )
        if connection and connection not in limits["connections"]:
            return "project_limit_connection"
    return None
