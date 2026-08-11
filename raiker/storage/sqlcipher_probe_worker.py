from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        database = Path(str(payload["database"]))
        key = str(payload["key"])
        connection = sqlite3.connect(str(database))
        try:
            connection.execute("PRAGMA cipher_memory_security = ON")
            connection.execute(f"PRAGMA key = \"x'{key}'\"")
            connection.execute("CREATE TABLE probe(value TEXT NOT NULL)")
            connection.execute("INSERT INTO probe(value) VALUES ('ok')")
            connection.commit()
            if connection.execute("SELECT value FROM probe").fetchone()[0] != "ok":
                return 3
            enabled = str(connection.execute("PRAGMA cipher_memory_security").fetchone()[0])
            version = str(connection.execute("PRAGMA cipher_version").fetchone()[0])
            if enabled not in {"1", "on"}:
                return 4
        finally:
            connection.close()
    except BaseException:  # the parent needs only a fail-closed exit status
        return 2
    sys.stdout.write(json.dumps({"status": "supported", "sqlcipher_version": version}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

