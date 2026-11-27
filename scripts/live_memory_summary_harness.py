# SPDX-License-Identifier: Apache-2.0
"""RU-11 live fixture: authorize an isolated account, or exercise real recall.

Use only with the disposable workspace supplied to the Playwright run. No
provider response is scripted; searches use the configured embedding service.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from raiker.control.service import RuntimeControlService
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.memory_tools import memory_search


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("operation", choices=("authorize", "search"))
    args = parser.parse_args()
    store = SQLiteStore(args.workspace)
    owner = store.original_account_principal_id()
    if owner is None:
        raise RuntimeError("The live account must exist first")
    if args.operation == "authorize":
        control = RuntimeControlService(args.workspace)
        result = control.activate_runtime_mode("local_single_user_runtime", owner, "RU-11 isolated live fixture")
        if not result.ok:
            raise RuntimeError(result.reason_code)
        capability = "model_provider_runtime"
        control.record_threat_model_ack(capability, owner, "RU-11 local model fixture")
        result = control.set_capability_state(capability, "enabled_runtime", owner, "RU-11 local model fixture", confirmation_token="confirm")
        if not result.ok:
            raise RuntimeError(result.reason_code)
        result = control.set_capability_decision_mode(capability, "always_allow", owner, "RU-11 local model fixture")
        if not result.ok:
            raise RuntimeError(result.reason_code)
        print(json.dumps({"authorized": True}))
    else:
        print(json.dumps(memory_search(args.workspace, "Which hot drink suits me?", owner_principal_id=owner)))


if __name__ == "__main__":
    main()
