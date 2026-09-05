"""Removing Raiker without removing what the owner actually cares about.

BUG-40. The distribution design's uninstall row reads: *"Remove application files
and service registration; offer to retain, export, or securely erase each local
instance and backup configuration."* Two obligations sit inside that sentence,
and only the first is obvious.

The obvious one is the choice. An owner uninstalling a governed agent host has
three genuinely different intentions — *I am reinstalling*, *I am moving to
another machine*, *I want this gone* — and a single "Are you sure?" serves none
of them. So the choice is per instance: ``keep``, ``export``, ``erase``.

The less obvious one is that the plan is stated **before** anything happens, in
the owner's terms, naming every path and its size. Uninstalling is the one
operation that cannot be undone by running it again, so the plan is a first-class
object here: it can be printed, shown in a dialog, and asserted in a test without
a single byte being touched.

``erase`` overwrites each file's bytes before unlinking. That is a best-effort
guarantee and it is described as one: on a copy-on-write or log-structured
filesystem, or on an SSD doing its own wear levelling, an overwrite reaches the
logical block and not necessarily every physical one. It is meaningfully better
than ``unlink`` and it is not a shredder — saying so is the honest thing, and it
is what the UI says too.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from raiker.storage.internal_paths import internal_io_path

DISPOSITIONS = ("keep", "export", "erase")
# Overwritten in chunks so a large encrypted database does not have to be
# materialised in memory to be erased.
_ERASE_CHUNK = 1 << 20


@dataclass(frozen=True)
class InstanceRemoval:
    """One Raiker instance and what uninstalling would do to it."""

    name: str
    path: Path
    bytes_on_disk: int
    disposition: str

    @property
    def kept(self) -> bool:
        return self.disposition == "keep"

    def describe(self) -> str:
        size = human_bytes(self.bytes_on_disk)
        if self.disposition == "keep":
            return f"{self.name} ({size}) — kept exactly where it is: {self.path}"
        if self.disposition == "export":
            return f"{self.name} ({size}) — copied out, still encrypted, then removed"
        return f"{self.name} ({size}) — overwritten and removed"


@dataclass(frozen=True)
class BuildArtefact:
    """A directory a source install created, and what it costs to keep."""

    label: str
    path: Path
    bytes_on_disk: int


@dataclass(frozen=True)
class UninstallPlan:
    """Everything an uninstall would remove and everything it would leave."""

    instances: list[InstanceRemoval]
    service_path: Path | None
    service_mechanism: str
    service_registered: bool
    export_to: Path | None = None
    not_removed: list[str] = field(default_factory=list)
    #: The applications-menu entry, when one is installed.
    launcher_path: Path | None = None
    launcher_mechanism: str = "none"
    launcher_installed: bool = False
    #: Regenerable directories a `pip install -e .` left in the checkout.
    build_artefacts: list[BuildArtefact] = field(default_factory=list)
    #: The checkout itself, when Raiker is running from one. Never removed.
    source_checkout: Path | None = None
    #: Whether the artefacts above are removed or only reported. Off by default:
    #: they live in the owner's own repository, and a tool that deletes out of a
    #: git checkout because it happens to be running from one has exceeded what
    #: "uninstall Raiker" can be read to mean. `--source-artifacts` opts in.
    remove_build_artefacts: bool = False

    @property
    def removes_data(self) -> bool:
        return any(not instance.kept for instance in self.instances)

    def describe(self) -> list[str]:
        """The plan as lines, removals first, then what is deliberately kept."""
        lines: list[str] = []
        if self.service_registered and self.service_path is not None:
            lines.append(f"Removed: the {self.service_mechanism} registration at {self.service_path}")
        else:
            lines.append(f"Nothing to remove: Raiker is not registered with {self.service_mechanism}")
        if self.launcher_installed and self.launcher_path is not None:
            lines.append(f"Removed: the {self.launcher_mechanism} at {self.launcher_path}")
        else:
            lines.append(f"Nothing to remove: there is no {self.launcher_mechanism} installed")
        for artefact in self.build_artefacts:
            verb = "Removed" if self.remove_build_artefacts else "Kept"
            lines.append(
                f"{verb}: {artefact.label} ({human_bytes(artefact.bytes_on_disk)}) "
                f"— {artefact.path}"
            )
        for instance in self.instances:
            lines.append(("Kept: " if instance.kept else "Removed: ") + instance.describe())
        if self.export_to is not None:
            lines.append(f"Exported to: {self.export_to}")
        for item in self.not_removed:
            lines.append(f"Kept: {item}")
        return lines


def plan_uninstall(
    workspace: str | Path,
    *,
    disposition: str = "keep",
    export_to: str | Path | None = None,
    port: int = 8765,
    os_name: str | None = None,
    home: Path | None = None,
    remove_build_artefacts: bool = False,
    checkout: Path | None = None,
    detect_source: bool = True,
) -> UninstallPlan:
    """Describe the uninstall without performing any part of it."""
    if disposition not in DISPOSITIONS:
        raise ValueError(f"unknown_disposition:{disposition}")
    if disposition == "export" and export_to is None:
        raise ValueError("export_requires_a_destination")

    from raiker.app.desktop_entry import status as launcher_status
    from raiker.app.service import registration

    root = Path(workspace).resolve()
    service = registration(root, port=port, os_name=os_name, home=home)
    launcher = launcher_status(os_name=os_name, home=home)
    # Both injectable, because the alternative is that every test of this
    # function silently takes the repository the test runner is executing from
    # as its subject — and `apply_uninstall` would then be pointed at it.
    found = checkout if checkout is not None else (source_checkout() if detect_source else None)
    instances = [
        InstanceRemoval(
            name=name,
            path=path,
            bytes_on_disk=directory_bytes(path),
            disposition=disposition,
        )
        for name, path in _instances(root)
    ]
    return UninstallPlan(
        instances=instances,
        service_path=Path(service.path) if service.path else None,
        service_mechanism=service.mechanism,
        service_registered=service.registered,
        export_to=Path(export_to).resolve() if export_to is not None else None,
        launcher_path=Path(launcher.path) if launcher.path else None,
        launcher_mechanism=launcher.mechanism,
        launcher_installed=launcher.installed,
        build_artefacts=build_artefacts(found),
        source_checkout=found,
        remove_build_artefacts=remove_build_artefacts,
        # Named explicitly because "uninstall" reads as "everything is gone", and
        # a backup the owner configured to a NAS is not Raiker's to delete.
        not_removed=[
            "any backup you configured to an external drive or provider — Raiker "
            "never deletes a copy it does not hold",
            *_source_notes(found),
        ],
    )


#: Directories a source install creates and can recreate. Removing one costs a
#: rebuild and nothing else; none of them holds anything the owner wrote.
BUILD_ARTEFACTS: tuple[tuple[str, str], ...] = (
    ("the built dashboard", "apps/web/dist"),
    ("the dashboard's downloaded packages", "apps/web/node_modules"),
    ("the Python build tree", "build"),
    ("the editable-install metadata", "raiker.egg-info"),
)


def source_checkout() -> Path | None:
    """The repository Raiker is running from, or ``None`` for a wheel install.

    An editable install leaves the code in the checkout, so `pip uninstall
    raiker` removes a link and leaves a directory that still contains a
    `.venv`, a `node_modules` and a `build/`. An owner who followed the source
    install and then uninstalled was told "the Python package itself" and left
    to find the rest.
    """
    root = Path(__file__).resolve().parents[2]
    return root if (root / "pyproject.toml").is_file() and (root / ".git").exists() else None


def build_artefacts(checkout: Path | None) -> list[BuildArtefact]:
    """Regenerable directories in *checkout*, largest first."""
    if checkout is None:
        return []
    found = [
        BuildArtefact(label=label, path=path, bytes_on_disk=directory_bytes(path))
        for label, relative in BUILD_ARTEFACTS
        if (path := checkout / relative).is_dir()
    ]
    return sorted(found, key=lambda item: item.bytes_on_disk, reverse=True)


def _source_notes(checkout: Path | None) -> list[str]:
    """What a source install keeps, said in the owner's terms.

    The checkout is never removed. It is the owner's directory — it may hold
    their branches, their notes, their unrelated work — and a tool that deletes
    a git repository because it happens to live inside it has exceeded what
    "uninstall Raiker" can possibly have meant.
    """
    notes = [
        "the Python package itself — remove it with your package manager "
        "(`pip uninstall raiker`)"
    ]
    if checkout is None:
        return notes
    notes.append(
        f"your source checkout at {checkout} — it is yours, and it may hold work "
        "that has nothing to do with Raiker"
    )
    venv = checkout / ".venv"
    if venv.is_dir():
        notes.append(
            f"the virtual environment at {venv} "
            f"({human_bytes(directory_bytes(venv))}) — delete the directory to "
            "reclaim it"
        )
    return notes


def apply_uninstall(
    plan: UninstallPlan,
    workspace: str | Path,
    *,
    port: int = 8765,
    os_name: str | None = None,
    home: Path | None = None,
) -> list[str]:
    """Carry out *plan* and report what was done, in the order it happened.

    Two orderings are deliberate. Service registration goes first: if erasing a
    large instance is interrupted, the owner is left with a partial workspace and
    *no* registration that would start a host over it. Instances go
    deepest-first, because a nested instance lives inside the main workspace and
    removing the parent first would make the child's own removal a no-op that
    still claimed to have happened.
    """
    from raiker.app.desktop_entry import entry_plan
    from raiker.app.desktop_entry import uninstall as remove_launcher
    from raiker.app.service import service_plan
    from raiker.app.service import uninstall as remove_service

    done: list[str] = []
    # Release SQLCipher handles before export/erase/rename operations. This is
    # required on Windows and ensures a removed workspace cannot retain a keyed
    # connection in the resident process.
    from raiker.storage.sqlite import invalidate_workspace_connections

    invalidate_workspace_connections(workspace)
    if plan.service_registered:
        result = remove_service(
            service_plan(workspace, port=port, os_name=os_name, home=home)
        )
        done.append(result.message)
    # Before the data, for the same reason the service registration goes first:
    # if a large erase is interrupted, the owner should not be left with a
    # partial workspace and a menu icon that still opens it.
    if plan.launcher_installed:
        done.append(remove_launcher(entry_plan(os_name=os_name, home=home)).message)
    if plan.remove_build_artefacts:
        for artefact in plan.build_artefacts:
            shutil.rmtree(artefact.path, ignore_errors=True)
            done.append(f"Removed {artefact.label} at {artefact.path}")

    for instance in sorted(plan.instances, key=lambda item: len(item.path.parts), reverse=True):
        if instance.kept:
            done.append(f"Kept {instance.name} at {instance.path}")
            continue
        if plan.export_to is not None:
            destination = plan.export_to / instance.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(instance.path, destination, dirs_exist_ok=True)
            done.append(f"Exported {instance.name} to {destination}")
        if instance.disposition == "erase":
            erased = secure_erase(instance.path)
            done.append(f"Overwrote and removed {erased} file(s) under {instance.path}")
        else:
            shutil.rmtree(instance.path, ignore_errors=True)
            done.append(f"Removed {instance.path}")
    return done


def secure_erase(root: Path) -> int:
    """Overwrite every file under *root* once, then remove the tree.

    Best effort, and deliberately so — see the module docstring. A file that
    cannot be opened for writing is still removed with the tree, because leaving
    it behind would be the worse failure of the two.
    """
    erased = 0
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            size = path.stat().st_size
            with path.open("r+b", buffering=0) as handle:
                remaining = size
                while remaining > 0:
                    chunk = min(remaining, _ERASE_CHUNK)
                    handle.write(os.urandom(chunk))
                    remaining -= chunk
                handle.flush()
                os.fsync(handle.fileno())
            erased += 1
        except OSError:
            continue
    shutil.rmtree(root, ignore_errors=True)
    return erased


def _instances(workspace: Path) -> list[tuple[str, Path]]:
    """The main workspace and every additional instance mounted under it."""
    found: list[tuple[str, Path]] = [("This device's Raiker data", workspace)]
    instance_root = internal_io_path(workspace / ".raiker" / "instances")
    if instance_root.is_dir():
        found.extend(
            (f"Instance “{child.name}”", child)
            for child in sorted(instance_root.iterdir())
            if child.is_dir()
        )
    return found


def directory_bytes(path: Path) -> int:
    """Total size of a tree, ignoring anything that cannot be measured."""
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def human_bytes(count: int) -> str:
    """A size an owner can act on, not one they have to convert."""
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
