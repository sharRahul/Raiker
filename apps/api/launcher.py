"""Compatibility shim for installations that recorded this module path.

The launcher moved to :mod:`raiker.app.launcher`, where the rest of the
application lifecycle already lived — it has always imported
``raiker.app.host``. Nothing about what it does changed.

**Why this file still exists.** Three places fall back to the module form when
no ``raiker-app`` console script can be found, which is the case for a source
checkout that was never installed:

* ``raiker.app.service`` writes the command into a real service registration —
  a systemd unit, a launchd plist, a Windows Startup entry;
* ``raiker.app.desktop_entry`` writes it into a desktop shortcut;
* ``raiker.app.update_handoff`` uses it to relaunch after an update.

Those registrations are files on the owner's machine, written by an earlier
version and read by the platform long after this rename. Deleting the module
outright would mean an installed Raiker that had registered itself this way
stopped starting at login, with a Python traceback in a log nobody reads as the
only explanation. A rename inside the repository is not permission to break a
command somebody's operating system already stored.

New registrations name ``raiker.app.launcher``: the three call sites above were
updated with the move, so this path is only ever reached by a registration made
before it. It can be deleted once no supported upgrade path crosses that
boundary.
"""

from __future__ import annotations

from raiker.app.launcher import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
