"""The domain parts :class:`raiker.control.dashboard.DashboardService` is assembled from (GCR-43).

Each part imports the views and helpers in ``raiker.control.dashboard``, and
that module imports the parts to build the service. Importing the facade here,
first, makes either order work: a caller that reaches for a part directly gets
the whole service assembled before the part is handed back, and the facade
importing its parts finds this package already under way and carries on.
"""

import raiker.control.dashboard  # noqa: F401 - assembles the service before any part
