"""The application lifecycle around the Raiker host.

``raiker-app`` (``apps/api/launcher.py``) made Raiker *start* like an
application. This package is the rest of what "an application" means on a
desktop: it stays running after the terminal that launched it is gone, it can be
paused and quit deliberately with its in-flight work stated first, and it can be
removed without leaving a service registration behind or silently destroying the
owner's data (BUG-40).

The modules match the things the distribution design asks for:

* :mod:`raiker.app.host` — is the host running, paused, or asking for something,
  and what background work would a quit interrupt.
* :mod:`raiker.app.service` — background start registered with the platform's own
  service manager (``launchd``, the Windows Startup folder, ``systemd --user``),
  never a custom daemon supervisor of Raiker's own.
* :mod:`raiker.app.uninstall` — what removal takes away, and the per-instance
  choice between retaining, exporting, and erasing.
* :mod:`raiker.app.release` — what a release artifact contains, that it rebuilds
  to the same bytes, and which signing identity each target requires (BUG-44).
* :mod:`raiker.app.installation` — what this installation is: released and
  signed, released and unsigned, or a source checkout that says so.
* :mod:`raiker.app.update` and :mod:`raiker.app.updater` — the signed channel and
  the verify-recover-migrate-or-roll-back boundary it feeds.
"""

from __future__ import annotations

from raiker.app.host import HostControl, HostStatus, PauseState, WaitingWork
from raiker.app.installation import (
    ChannelConfig,
    Installation,
    UpdateStatus,
    detect_installation,
    update_status,
)
from raiker.app.release import ReleaseTarget, SigningIdentity, current_target
from raiker.app.service import ServicePlan, ServiceRegistration, service_plan
from raiker.app.uninstall import InstanceRemoval, UninstallPlan, plan_uninstall
from raiker.app.update import ChannelUpdate, RecoveryPoint, apply_signed_update, select_update
from raiker.app.updater import check_for_update, download_and_apply

__all__ = [
    "ChannelConfig",
    "ChannelUpdate",
    "HostControl",
    "HostStatus",
    "Installation",
    "InstanceRemoval",
    "PauseState",
    "RecoveryPoint",
    "ReleaseTarget",
    "ServicePlan",
    "ServiceRegistration",
    "SigningIdentity",
    "UninstallPlan",
    "UpdateStatus",
    "WaitingWork",
    "apply_signed_update",
    "check_for_update",
    "current_target",
    "detect_installation",
    "download_and_apply",
    "plan_uninstall",
    "select_update",
    "service_plan",
    "update_status",
]
