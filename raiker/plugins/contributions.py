"""What an installed plugin is allowed to actually contribute (BUG-221).

Installing a plugin used to validate its manifest, check its supply chain,
resolve its signature and write a record — and then nothing happened. The
blocking question was never packaging; it was *what a plugin's code is allowed to
be*. Every other extension surface answers it: a skill is instructions and runs
nothing, a connector is a brokered tool behind a capability gate, a hook is argv
resolved inside the workspace under a bounded timeout.

This module answers it the same way, by refusing to invent an answer. A plugin
does not get an execution surface of its own. It contributes **through a surface
that already governs the thing it contributes**, and the first of those is hooks:

* A hook already has an execution model, a timeout, an audit trail and a scope.
* ``plugin`` sits below ``managed``, ``user``, ``project`` and ``local`` in
  :data:`~raiker.hooks.contracts.HOOK_SCOPES`, so a plugin rule can make an
  action stricter and can never override a deny the owner or their organisation
  set — the property that makes this safe is structural, not a check.
* The owner's global hooks off switch reaches it, because it is a hook.

Three refusals, all fail-closed and all named:

1. **No declared permission, no contribution.** A manifest must ask for
   ``event:hook``. That permission is not in ``SAFE_READ_ONLY``, so a plugin
   asking for it lands on ``pending_approval`` and the owner reads it in the
   permission diff *before* installing — which is the point of asking.
2. **A malformed contribution is refused at plan time,** not written and
   discovered later by a hooks file that silently loads nothing.
3. **The contribution is a file the owner can read and delete.** Revoking the
   plugin removes it, so "what does this plugin do" never depends on trusting the
   manifest that described it.

The second contribution kind is **skills**, and it is held to the same bar:

* A skill is instruction text. Raiker executes nothing a skill ships, so the
  surface that already governs it is :mod:`raiker.skills` — the same validator an
  uploaded ``SKILL.md`` goes through decides whether a contributed one is a skill
  at all, before a byte is written.
* The document lands in ``.raiker/plugins/<plugin_id>/skills/<name>/SKILL.md``,
  inside the directory revocation already deletes, so a revoked plugin's skills
  disappear for the same structural reason its hooks do.
* It arrives **inactive**. Instructions injected into the owner's turns are not
  harmless just because they run nothing, so the manifest asks for
  ``skill:contribute`` — outside ``SAFE_READ_ONLY``, therefore read in the
  permission diff — and the owner still has to switch the skill on afterwards.
  Two consents, neither of them implied by the install.
* Existence lives on disk; the owner's on/off choice lives in the skills store,
  which is what the runtime reads. :meth:`raiker.skills.service.SkillsService.
  sync_plugin_skills` reconciles the two in one direction only: disk decides what
  exists, the store keeps the choice the owner made about it.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from raiker.hooks.contracts import HookConfigError
from raiker.hooks.registry import PLUGIN_HOOKS_DIR, PLUGIN_HOOKS_FILE, HooksRegistry
from raiker.skills.package import SkillPackage, SkillValidationError, read_skill_md

#: The permission a manifest must declare before any hook rule of its is written.
HOOK_CONTRIBUTION_PERMISSION = "event:hook"

#: The permission a manifest must declare before any skill of its is written.
SKILL_CONTRIBUTION_PERMISSION = "skill:contribute"

#: Sub-directory of a plugin's contribution folder holding its skills, one
#: folder per skill so a contributed skill can carry references beside its
#: document exactly as an uploaded bundle does.
PLUGIN_SKILLS_DIR = "skills"

#: More than this many skills from one manifest is refused rather than
#: truncated: a plugin that wants to fill the owner's skill list is a plugin
#: the owner should be told about, not one quietly cut short.
MAX_CONTRIBUTED_SKILLS = 20

#: The permission a manifest must declare before it may *offer* an MCP server.
MCP_CONTRIBUTION_PERMISSION = "mcp:server"

#: Where a plugin's offered servers are recorded. They are proposals, never
#: server profiles: nothing here is connected, stored as a server, or reachable
#: until the owner adds it through the ordinary governed create path.
PLUGIN_MCP_FILE = "mcp-servers.json"

MAX_CONTRIBUTED_MCP_SERVERS = 10

#: A plugin id becomes a directory name, so it is held to a directory-safe shape
#: rather than sanitised into one. Sanitising invites two ids collapsing onto the
#: same folder; refusing does not.
_SAFE_PLUGIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class PluginContributionError(ValueError):
    """A contribution that cannot be accepted, with the reason as the message."""


def _hooks_block(manifest: dict[str, Any]) -> dict[str, Any] | None:
    """``contributes.hooks`` as a full hooks config, or ``None`` if absent.

    A manifest may write the event map directly (``{"PreToolUse": [...]}``) or a
    whole config (``{"schema_version": "1.0", "hooks": {...}}``). Both are
    normalised to the second form here, so exactly one shape reaches the parser
    and the written file is always a hooks config the registry can load without
    knowing a plugin produced it.
    """
    contributes = manifest.get("contributes")
    if not isinstance(contributes, dict):
        return None
    hooks = contributes.get("hooks")
    if not isinstance(hooks, dict):
        return None
    if isinstance(hooks.get("hooks"), dict):
        return {"schema_version": str(hooks.get("schema_version", "1.0")), "hooks": hooks["hooks"]}
    return {"schema_version": "1.0", "hooks": hooks}


def _skill_entries(manifest: dict[str, Any]) -> list[Any]:
    """``contributes.skills`` as a list, or ``[]`` when the block is absent.

    A single mapping is accepted as a one-element list: a manifest contributing
    exactly one skill should not have to know that the field is plural.
    """
    contributes = manifest.get("contributes")
    if not isinstance(contributes, dict):
        return []
    skills = contributes.get("skills")
    if isinstance(skills, dict):
        return [skills]
    if isinstance(skills, list):
        return list(skills)
    return []


def _read_contributed_skill(entry: Any) -> SkillPackage:
    """Validate one manifest skill entry with the reader uploads go through.

    Two shapes, both ending at the same validator. ``document`` is a whole
    ``SKILL.md`` written by the plugin author and is passed through verbatim.
    ``body`` is the prose alone, with the frontmatter assembled here — the same
    assembly :meth:`SkillsService.build_skill` does, so a plugin cannot express a
    skill Raiker would otherwise refuse to build.
    """
    if not isinstance(entry, dict):
        raise SkillValidationError("skill_invalid_entry")
    name = entry.get("name")
    fallback = name.strip().lower() if isinstance(name, str) else None
    document = entry.get("document")
    if isinstance(document, str) and document.strip():
        return read_skill_md(document, fallback_name=fallback)
    body = entry.get("body")
    description = entry.get("description")
    if not isinstance(body, str) or not body.strip():
        raise SkillValidationError("skill_missing_body")
    if not isinstance(description, str) or not description.strip():
        raise SkillValidationError("skill_missing_description")
    if not fallback:
        raise SkillValidationError("skill_invalid_name")
    assembled = (
        "---\n"
        f"name: {fallback}\n"
        f"description: {' '.join(description.split())}\n"
        "---\n\n"
        f"{body.strip()}\n"
    )
    return read_skill_md(assembled, fallback_name=fallback)


def _contributed_skills(manifest: dict[str, Any]) -> tuple[list[SkillPackage], list[str]]:
    """Every valid skill in the manifest, plus a named refusal for each that is not.

    One bad entry refuses only itself. A manifest contributing five skills where
    the third is malformed installs four and says which one it dropped, because
    the alternative — refusing all five — hides four working contributions behind
    one typo.
    """
    entries = _skill_entries(manifest)
    if not entries:
        return [], []
    refused: list[str] = []
    if len(entries) > MAX_CONTRIBUTED_SKILLS:
        return [], [f"too_many_skills:{len(entries)}>{MAX_CONTRIBUTED_SKILLS}"]
    packages: list[SkillPackage] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        try:
            package = _read_contributed_skill(entry)
        except SkillValidationError as exc:
            refused.append(f"invalid_skill_contribution:{index}:{exc.reason}")
            continue
        if package.name in seen:
            # Two skills with one name would race for the same folder and the
            # same prompt handle; the second is refused rather than overwriting.
            refused.append(f"duplicate_skill_contribution:{package.name}")
            continue
        seen.add(package.name)
        packages.append(package)
    return packages, refused


_SAFE_SERVER_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _read_contributed_mcp_server(entry: Any) -> dict[str, Any]:
    """Validate one offered MCP server, or raise :class:`PluginContributionError`.

    This validates a *description* of a server, not a server. The fields are the
    same ones the owner would type on Extensions → MCP servers, held to the same
    shapes the create path holds them to, so an offer that would be refused there
    is refused here rather than becoming a button that fails when pressed.
    """
    if not isinstance(entry, dict):
        raise PluginContributionError("invalid_entry")
    name = entry.get("name")
    if not isinstance(name, str) or not _SAFE_SERVER_NAME.match(name.strip().lower()):
        raise PluginContributionError("invalid_name")
    transport = str(entry.get("transport") or "http").strip().lower()
    description = " ".join(str(entry.get("description") or "").split())[:400]
    if transport == "http":
        endpoint = entry.get("endpoint_url")
        if not isinstance(endpoint, str):
            raise PluginContributionError("invalid_endpoint")
        parsed = urlparse(endpoint.strip())
        # https only, and never a credential in the URL. A plugin author writing
        # `https://user:token@host` would be handing the owner a secret to store
        # in a field that is not built to hold one.
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise PluginContributionError("invalid_endpoint")
        auth_ref = entry.get("auth_ref")
        if auth_ref is not None and (
            not isinstance(auth_ref, str) or not re.match(r"^[A-Z][A-Z0-9_]{0,63}$", auth_ref)
        ):
            # `auth_ref` names an environment variable; it is never the token.
            raise PluginContributionError("invalid_auth_ref")
        return {
            "name": name.strip().lower(),
            "transport": "http",
            "endpoint_url": endpoint.strip(),
            "auth_ref": auth_ref or None,
            "description": description,
        }
    if transport == "stdio":
        template = entry.get("template")
        if not isinstance(template, str) or not template.strip():
            raise PluginContributionError("invalid_template")
        return {
            "name": name.strip().lower(),
            "transport": "stdio",
            "template": template.strip(),
            "description": description,
        }
    raise PluginContributionError(f"unsupported_transport:{transport}")


def _contributed_mcp_servers(
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Every valid server offer in the manifest, plus a named refusal for each
    that is not. One bad entry refuses only itself, as with skills."""
    contributes = manifest.get("contributes")
    if not isinstance(contributes, dict):
        return [], []
    raw = contributes.get("mcp_servers")
    entries = [raw] if isinstance(raw, dict) else (list(raw) if isinstance(raw, list) else [])
    if not entries:
        return [], []
    if len(entries) > MAX_CONTRIBUTED_MCP_SERVERS:
        return [], [
            f"too_many_mcp_servers:{len(entries)}>{MAX_CONTRIBUTED_MCP_SERVERS}"
        ]
    servers: list[dict[str, Any]] = []
    refused: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        try:
            server = _read_contributed_mcp_server(entry)
        except PluginContributionError as exc:
            refused.append(f"invalid_mcp_contribution:{index}:{exc}")
            continue
        if server["name"] in seen:
            refused.append(f"duplicate_mcp_contribution:{server['name']}")
            continue
        seen.add(server["name"])
        servers.append(server)
    return servers, refused


def contribution_summary(manifest: dict[str, Any], permissions: list[str]) -> dict[str, Any]:
    """What this manifest contributes, and why it would be refused if it would.

    Returns a plain dict rather than raising, because this is what the owner reads
    on the plan *before* deciding. A refusal is information at that point, not an
    error: ``{"hooks": 0, "refused": ["..."]}`` is the honest rendering of a
    plugin that asked for something it may not have.
    """
    refused: list[str] = []

    hooks = _hooks_block(manifest)
    hook_count = 0
    events: list[str] = []
    if hooks is not None:
        hook_refused: list[str] = []
        if HOOK_CONTRIBUTION_PERMISSION not in permissions:
            hook_refused.append(
                f"hooks_contribution_requires_permission:{HOOK_CONTRIBUTION_PERMISSION}"
            )
        try:
            rules = HooksRegistry.from_config(hooks, scope="plugin").rules
            hook_count = len(rules)
            events = sorted({rule.event for rule in rules})
        except HookConfigError as exc:
            hook_refused.append(f"invalid_hooks_contribution:{exc}")
        if hook_refused:
            hook_count, events = 0, []
            refused.extend(hook_refused)

    # A refusal on one kind never removes the other. The two are contributed
    # through different surfaces and asked for with different permissions, so a
    # manifest whose hooks are malformed still installs its valid skills — and
    # says which half it dropped.
    packages, skill_refused = _contributed_skills(manifest)
    if packages and SKILL_CONTRIBUTION_PERMISSION not in permissions:
        skill_refused.append(
            f"skills_contribution_requires_permission:{SKILL_CONTRIBUTION_PERMISSION}"
        )
        packages = []
    refused.extend(skill_refused)

    servers, mcp_refused = _contributed_mcp_servers(manifest)
    if servers and MCP_CONTRIBUTION_PERMISSION not in permissions:
        mcp_refused.append(
            f"mcp_contribution_requires_permission:{MCP_CONTRIBUTION_PERMISSION}"
        )
        servers = []
    refused.extend(mcp_refused)

    return {
        "hooks": hook_count,
        "events": events,
        "skills": len(packages),
        "skill_names": [package.name for package in packages],
        "mcp_servers": len(servers),
        "mcp_server_names": [server["name"] for server in servers],
        "refused": refused,
    }


def plugin_contribution_dir(workspace_root: str | Path, plugin_id: str) -> Path:
    """Everything this plugin contributed, in one directory, refusing an unsafe id.

    One directory per plugin is what makes revocation a single deletion rather
    than a list of places to remember — every future contribution kind lands
    inside it for that reason.
    """
    if not _SAFE_PLUGIN_ID.match(plugin_id or ""):
        raise PluginContributionError(f"unsafe_plugin_id:{plugin_id}")
    return Path(workspace_root) / PLUGIN_HOOKS_DIR / plugin_id


def plugin_hooks_path(workspace_root: str | Path, plugin_id: str) -> Path:
    """Where this plugin's contributed rules live, refusing an unsafe id."""
    return plugin_contribution_dir(workspace_root, plugin_id) / PLUGIN_HOOKS_FILE


def plugin_skills_dir(workspace_root: str | Path, plugin_id: str) -> Path:
    """Where this plugin's contributed skills live, refusing an unsafe id."""
    return plugin_contribution_dir(workspace_root, plugin_id) / PLUGIN_SKILLS_DIR


def plugin_mcp_path(workspace_root: str | Path, plugin_id: str) -> Path:
    """Where this plugin's *offered* MCP servers are recorded, unsafe id refused."""
    return plugin_contribution_dir(workspace_root, plugin_id) / PLUGIN_MCP_FILE


def install_contributions(
    workspace_root: str | Path,
    manifest: dict[str, Any],
    *,
    plugin_id: str,
    permissions: list[str],
) -> dict[str, Any]:
    """Write this plugin's contributed hook rules, or refuse and write nothing.

    Idempotent: re-installing the same plugin replaces its file rather than
    accumulating a second one, because a plugin has exactly one contribution and
    a stale copy of an older version's rules would still be loaded.
    """
    summary = contribution_summary(manifest, permissions)
    # Always start from nothing: a previous version's rules and skills must not
    # survive an upgrade that dropped them, and a partial write must not leave a
    # skill folder the new manifest no longer names.
    remove_contributions(workspace_root, plugin_id)
    if summary["hooks"] == 0 and summary["skills"] == 0 and summary["mcp_servers"] == 0:
        return summary

    written: dict[str, Any] = {**summary}
    if summary["hooks"] > 0:
        hooks = _hooks_block(manifest)
        assert hooks is not None  # summary["hooks"] > 0 implies a parsed block
        path = plugin_hooks_path(workspace_root, plugin_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(hooks, indent=2, sort_keys=True), encoding="utf-8")
        written["path"] = str(path)

    if summary["skills"] > 0:
        packages, _ = _contributed_skills(manifest)
        root = plugin_skills_dir(workspace_root, plugin_id)
        paths: list[str] = []
        for package in packages:
            # The folder is named from the *validated* name, which the skill
            # reader has already constrained to a lowercase slug — so the path
            # cannot be steered by the manifest.
            folder = root / package.name
            folder.mkdir(parents=True, exist_ok=True)
            document = folder / "SKILL.md"
            document.write_text(package.skill_md, encoding="utf-8")
            paths.append(str(document))
        written["skill_paths"] = paths

    if summary["mcp_servers"] > 0:
        servers, _ = _contributed_mcp_servers(manifest)
        path = plugin_mcp_path(workspace_root, plugin_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"servers": servers}, indent=2, sort_keys=True), "utf-8")
        written["mcp_path"] = str(path)
    return written


def remove_contributions(workspace_root: str | Path, plugin_id: str) -> bool:
    """Remove everything this plugin contributed. Revocation's teeth.

    An install record flipped to ``revoked`` stops the brokered execution path,
    but a hooks file on disk is read by :meth:`HooksRegistry.load`, which has no
    store and no business gaining one. So revocation deletes the contribution
    rather than annotating it: the rules are gone at the next load, and there is
    no state in which the page says revoked and the runtime still runs the rule.
    """
    try:
        directory = plugin_contribution_dir(workspace_root, plugin_id)
    except PluginContributionError:
        return False
    if not directory.is_dir():
        return False
    shutil.rmtree(directory, ignore_errors=True)
    return not directory.exists()


def installed_contributions(workspace_root: str | Path) -> dict[str, dict[str, Any]]:
    """What each plugin contributes *right now*, read from disk, keyed by id.

    Read from the files rather than from the install records on purpose: the
    files are what the runtime loads, so this cannot report a contribution the
    runtime does not have, or miss one it does.
    """
    root = Path(workspace_root) / PLUGIN_HOOKS_DIR
    found: dict[str, dict[str, Any]] = {}
    try:
        directories = sorted(entry for entry in root.iterdir() if entry.is_dir())
    except OSError:
        return found
    for directory in directories:
        entry: dict[str, Any] = {
            "hooks": 0,
            "events": [],
            "skills": 0,
            "skill_names": [],
            "mcp_servers": 0,
            "mcp_server_names": [],
            "error": None,
        }
        path = directory / PLUGIN_HOOKS_FILE
        if path.is_file():
            try:
                rules = HooksRegistry.from_config(
                    json.loads(path.read_text(encoding="utf-8")), scope="plugin"
                ).rules
            except (OSError, ValueError, HookConfigError):
                entry["error"] = "unreadable"
            else:
                entry["hooks"] = len(rules)
                entry["events"] = sorted({rule.event for rule in rules})
        for package in _read_skill_folder(directory / PLUGIN_SKILLS_DIR):
            entry["skills"] += 1
            entry["skill_names"].append(package.name)
        for server in _read_mcp_file(directory / PLUGIN_MCP_FILE):
            entry["mcp_servers"] += 1
            entry["mcp_server_names"].append(server["name"])
        # A directory with none of the three is not a contribution. Reporting it
        # as one would put a plugin on the tab claiming to provide something; an
        # unreadable file is still reported, because that *is* the answer to what
        # it provides.
        if (
            entry["hooks"] == 0
            and entry["skills"] == 0
            and entry["mcp_servers"] == 0
            and entry["error"] is None
        ):
            continue
        found[directory.name] = entry
    return found


def _read_skill_folder(root: Path) -> list[SkillPackage]:
    """Every valid contributed skill under one plugin's skills directory.

    A document that no longer validates is skipped rather than reported as a
    skill, because this answers "what does the runtime load" and the runtime
    would not load it either.
    """
    packages: list[SkillPackage] = []
    try:
        folders = sorted(entry for entry in root.iterdir() if entry.is_dir())
    except OSError:
        return packages
    for folder in folders:
        document = folder / "SKILL.md"
        if not document.is_file():
            continue
        try:
            package = read_skill_md(document.read_text(encoding="utf-8"), fallback_name=folder.name)
        except (OSError, SkillValidationError):
            continue
        packages.append(package)
    return packages


def _read_mcp_file(path: Path) -> list[dict[str, Any]]:
    """Every valid server offer in one plugin's ``mcp-servers.json``.

    Re-validated on read rather than trusted from the write: this answers what
    the owner is being offered, and a file edited by hand after the install is
    still only an offer — but it must not be able to smuggle in an endpoint the
    write path would have refused.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    raw = payload.get("servers") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return []
    servers: list[dict[str, Any]] = []
    for entry in raw:
        try:
            servers.append(_read_contributed_mcp_server(entry))
        except PluginContributionError:
            continue
    return servers


def contributed_mcp_servers(workspace_root: str | Path) -> list[tuple[str, dict[str, Any]]]:
    """``(plugin_id, offer)`` for every MCP server an installed plugin offers.

    These are **offers**, not servers. Nothing here is connected, stored as a
    server profile, or reachable: the owner adds one through the same governed
    create path they would use to type it in themselves, and that is where the
    capability gate, the decision mode and the audit event apply.
    """
    root = Path(workspace_root) / PLUGIN_HOOKS_DIR
    found: list[tuple[str, dict[str, Any]]] = []
    try:
        directories = sorted(entry for entry in root.iterdir() if entry.is_dir())
    except OSError:
        return found
    for directory in directories:
        for server in _read_mcp_file(directory / PLUGIN_MCP_FILE):
            found.append((directory.name, server))
    return found


def contributed_skills(workspace_root: str | Path) -> list[tuple[str, SkillPackage]]:
    """``(plugin_id, package)`` for every skill any installed plugin contributes.

    Read from disk for the same reason :func:`installed_contributions` is: these
    files are what revocation deletes, so a plugin that has been revoked cannot
    still be offering a skill through a stale row somewhere.
    """
    root = Path(workspace_root) / PLUGIN_HOOKS_DIR
    found: list[tuple[str, SkillPackage]] = []
    try:
        directories = sorted(entry for entry in root.iterdir() if entry.is_dir())
    except OSError:
        return found
    for directory in directories:
        for package in _read_skill_folder(directory / PLUGIN_SKILLS_DIR):
            found.append((directory.name, package))
    return found


__all__ = [
    "HOOK_CONTRIBUTION_PERMISSION",
    "MAX_CONTRIBUTED_MCP_SERVERS",
    "MAX_CONTRIBUTED_SKILLS",
    "MCP_CONTRIBUTION_PERMISSION",
    "PLUGIN_MCP_FILE",
    "PLUGIN_SKILLS_DIR",
    "SKILL_CONTRIBUTION_PERMISSION",
    "PluginContributionError",
    "contributed_mcp_servers",
    "contributed_skills",
    "contribution_summary",
    "install_contributions",
    "installed_contributions",
    "plugin_contribution_dir",
    "plugin_hooks_path",
    "plugin_mcp_path",
    "plugin_skills_dir",
    "remove_contributions",
]
