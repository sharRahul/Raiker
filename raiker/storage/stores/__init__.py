"""The domain parts :class:`raiker.storage.sqlite.SQLiteStore` is assembled from (GCR-11).

Each part imports the connection helpers in ``raiker.storage.sqlite``, and that
module imports the parts to build the store. Importing the facade here, first,
makes either order work: a caller that reaches for a part directly gets the
whole store assembled before the part is handed back, and the facade importing
its parts finds this package already under way and carries on.
"""

import raiker.storage.sqlite  # noqa: F401 - assembles the store before any part
