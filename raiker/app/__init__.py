"""The application lifecycle around the Raiker host.

``raiker-app`` (``apps/api/launcher.py``) made Raiker *start* like an
application. This package is the rest of what "an application" means on a
desktop: it stays running after the terminal that launched it is gone, it can be
paused and quit deliberately with its in-flight work stated first, and it can be
removed without leaving a service registration behind or silently destroying the
owner's data (BUG-40).

Three modules, matching the three things the distribution design asks for:

* :mod:`raiker.app.host` — is the host running, paused, or asking for something,
  and what background work would a quit interrupt.
* :mod:`raiker.app.service` — background start registered with the platform's own
  service manager (``launchd``, the Windows Startup folder, ``systemd --user``),
  never a custom daemon supervisor of Raiker's own.
* :mod:`raiker.app.uninstall` — what removal takes away, and the per-instance
  choice between retaining, exporting, and erasing.
"""

from __future__ import annotations

from raiker.app.host import HostControl, HostStatus, PauseState, WaitingWork
from raiker.app.service import ServicePlan, ServiceRegistration, service_plan
from raiker.app.uninstall import InstanceRemoval, UninstallPlan, plan_uninstall

__all__ = [
    "HostControl",
    "HostStatus",
    "InstanceRemoval",
    "PauseState",
    "ServicePlan",
    "ServiceRegistration",
    "UninstallPlan",
    "WaitingWork",
    "plan_uninstall",
    "service_plan",
]
